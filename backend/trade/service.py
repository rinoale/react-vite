import json
import os
import shutil

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.models import (
    OcrCorrection, Listing, ListingOption,
    Enchant, GameItem, Tag, TagTarget,
)
from lib.utils.log import logger

# --- Correction capture constants ---
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CROPS_DIR = os.path.join(_BASE_DIR, '..', 'tmp', 'ocr_crops')
_CORRECTIONS_DIR = os.path.join(_BASE_DIR, '..', 'data', 'corrections')
_MODELS_DIR = os.path.join(_BASE_DIR, 'ocr', 'models')


def _load_charsets():
    """Load per-model charsets for mismatch detection."""
    charsets = {}
    # Content models
    for yaml_prefix in ('custom_mabinogi_classic', 'custom_nanum_gothic_bold'):
        yaml_path = os.path.join(_MODELS_DIR, f'{yaml_prefix}.yaml')
        if not os.path.exists(yaml_path):
            continue
        real_path = os.path.realpath(yaml_path)
        version_dir = os.path.dirname(real_path)
        chars_file = os.path.join(version_dir, 'unique_chars.txt')
        if os.path.exists(chars_file):
            with open(chars_file, 'r', encoding='utf-8') as f:
                charsets[yaml_prefix] = set(f.read().strip())
    # Enchant header model
    enchant_hdr_dir = os.path.join(_MODELS_DIR, 'custom_enchant_header.yaml')
    if os.path.exists(enchant_hdr_dir):
        real_path = os.path.realpath(enchant_hdr_dir)
        version_dir = os.path.dirname(real_path)
        for fname in ('enchant_header_chars.txt', 'unique_chars.txt'):
            chars_file = os.path.join(version_dir, fname)
            if os.path.exists(chars_file):
                with open(chars_file, 'r', encoding='utf-8') as f:
                    charsets['enchant_header'] = set(f.read().strip())
                break
    return charsets


_CHARSETS = _load_charsets()


def capture_corrections(session_id, lines, db):
    """Diff submitted lines against stored OCR results and save corrections.

    Returns the number of corrections saved.
    """
    if not session_id or not lines:
        return 0

    session_dir = os.path.join(_CROPS_DIR, session_id)
    results_path = os.path.join(session_dir, 'ocr_results.json')

    if not os.path.isfile(results_path):
        return 0

    with open(results_path, 'r', encoding='utf-8') as f:
        originals = json.load(f)

    # Build lookup: (section, line_index) → original line data
    orig_by_key = {(o['section'], o['line_index']): o for o in originals}

    dest_dir = os.path.join(_CORRECTIONS_DIR, session_id)
    corrections_saved = 0

    for line in lines:
        orig = orig_by_key.get((line.section, line.line_index))
        if orig is None:
            continue

        submitted = line.text.strip()
        original = orig['text'].strip()

        if submitted == original:
            continue  # No change

        # Check charset mismatch against the model that produced this line
        charset_mismatch = None
        if _CHARSETS:
            ocr_model = orig.get('ocr_model', '')
            # Pick the right charset for this line's model
            if ocr_model == 'enchant_header':
                model_charset = _CHARSETS.get('enchant_header')
            else:
                # Content models — check union of both
                model_charset = _CHARSETS.get('custom_mabinogi_classic', set()) | _CHARSETS.get('custom_nanum_gothic_bold', set())
            if model_charset:
                bad = set(line.text) - model_charset - {' '}
                if bad:
                    charset_mismatch = ''.join(sorted(bad))

        # Copy crop image
        crop_name = f"{line.line_index:03d}.png"
        src_path = os.path.join(session_dir, line.section, crop_name)
        if not os.path.isfile(src_path):
            continue

        os.makedirs(dest_dir, exist_ok=True)
        shutil.copy2(src_path, os.path.join(dest_dir, f"{line.section}_{crop_name}"))

        db.add(OcrCorrection(
            session_id=session_id,
            line_index=line.line_index,
            original_text=orig.get('raw_text', orig['text']),
            corrected_text=submitted,
            confidence=orig.get('confidence'),
            section=line.section,
            ocr_model=orig.get('ocr_model', ''),
            fm_applied=orig.get('fm_applied', False),
            status='pending',
            charset_mismatch=charset_mismatch,
            image_filename=f"{line.section}_{crop_name}",
            is_stitched=orig.get('_is_stitched', False),
        ))
        corrections_saved += 1

    if corrections_saved:
        try:
            db.commit()
            logger.info("register-listing  saved %d correction(s)", corrections_saved)
        except Exception:
            db.rollback()
            logger.exception("register-listing  DB commit failed for %d correction(s)", corrections_saved)
            corrections_saved = 0

    return corrections_saved


_ATTR_COLUMNS = {
    'damage', 'magic_damage', 'additional_damage', 'balance',
    'defense', 'protection', 'magic_defense', 'magic_protection',
    'durability', 'piercing_level',
}


def _parse_attrs(attrs_dict):
    """Convert attrs dict (string values) to int kwargs for known Listing columns.

    Ignores unknown keys and non-numeric values.
    """
    if not attrs_dict:
        return {}
    result = {}
    for key, val in attrs_dict.items():
        if key not in _ATTR_COLUMNS:
            continue
        try:
            result[key] = int(val)
        except (ValueError, TypeError):
            continue
    return result


def create_listing(payload, db, *, user_id=None):
    """Resolve FKs and persist a Listing with listing options.

    Returns the created Listing.
    """
    # Resolve game_item FK: use explicit ID if provided, else match by name
    game_item_id = payload.game_item_id
    if not game_item_id and payload.name:
        gi = db.query(GameItem).filter(GameItem.name == payload.name).first()
        if gi:
            game_item_id = gi.id

    # Resolve enchant FKs
    prefix_enchant_id = None
    suffix_enchant_id = None
    enchant_rows_by_slot = {}
    for enc in payload.enchants:
        enchant_row = db.query(Enchant).filter(
            Enchant.name == enc.name,
            Enchant.slot == enc.slot,
        ).first()
        if not enchant_row:
            logger.warning("register-listing  enchant not found: name=%r slot=%d", enc.name, enc.slot)
            continue
        enchant_rows_by_slot[enc.slot] = (enchant_row, enc)
        if enc.slot == 0:
            prefix_enchant_id = enchant_row.id
        elif enc.slot == 1:
            suffix_enchant_id = enchant_row.id

    # Parse price string to integer (frontend sends comma-stripped digits)
    price_int = None
    if payload.price:
        try:
            price_int = int(payload.price)
        except ValueError:
            pass

    listing = Listing(
        user_id=user_id,
        name=payload.name,
        description=payload.description,
        price=price_int,
        game_item_id=game_item_id,
        prefix_enchant_id=prefix_enchant_id,
        suffix_enchant_id=suffix_enchant_id,
        item_type=payload.item_type,
        item_grade=payload.item_grade,
        erg_grade=payload.erg_grade,
        erg_level=payload.erg_level,
        special_upgrade_type=payload.special_upgrade_type,
        special_upgrade_level=payload.special_upgrade_level,
        **_parse_attrs(payload.attrs),
    )
    db.add(listing)
    try:
        db.flush()  # get listing.id for FK references

        # --- All listing options (enchant_effect, reforge, echostone, murias_relic) ---
        for opt in payload.listing_options:
            db.add(ListingOption(
                listing_id=listing.id,
                option_type=opt.option_type,
                option_id=opt.option_id,
                option_name=opt.option_name,
                rolled_value=opt.rolled_value,
                max_level=opt.max_level,
            ))

        db.commit()
        db.refresh(listing)
        logger.info("register-listing  persisted listing id=%d name=%r enchants=%d options=%d",
                     listing.id, listing.name, len(payload.enchants), len(payload.listing_options))
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("register-listing  listing persist failed")
        raise HTTPException(status_code=500, detail="Failed to persist listing")

    return listing


_TAG_POSITION_WEIGHTS = [80, 60, 30]
_SPECIAL_UPGRADE_NAMES = {'R': '붉개', 'S': '푸개'}


def _get_or_create_tag(db, name, weight=0):
    """Get existing tag or create a new one. Handles concurrent insert race."""
    tag = db.query(Tag).filter(Tag.name == name).first()
    if tag:
        return tag
    sp = db.begin_nested()
    tag = Tag(name=name, weight=weight)
    db.add(tag)
    try:
        sp.commit()
    except IntegrityError:
        sp.rollback()
        tag = db.query(Tag).filter(Tag.name == name).first()
    return tag


def _attach_tag(db, tag, target_type, target_id, weight):
    """Attach a tag to a target. Silently skips duplicates."""
    sp = db.begin_nested()
    db.add(TagTarget(
        tag_id=tag.id,
        target_type=target_type,
        target_id=target_id,
        weight=weight,
    ))
    try:
        sp.commit()
    except IntegrityError:
        sp.rollback()


def create_listing_tags(listing, payload, db):
    """Create user-submitted and auto-generated tags for a listing.

    User tags use positional weights [80, 60, 30].
    Auto tags (enchant, erg, special upgrade) use weight 0.
    Deduplicates: auto tags already attached by user tags are skipped.
    """
    try:
        attached = set()

        # --- User-submitted tags (positional weights) ---
        for i, tag_name in enumerate(payload.tags[:3]):
            tag_name = tag_name.strip()
            if not tag_name:
                continue
            pos_weight = _TAG_POSITION_WEIGHTS[i] if i < len(_TAG_POSITION_WEIGHTS) else 0
            tag = _get_or_create_tag(db, tag_name)
            weight = max(0, pos_weight - tag.weight)
            _attach_tag(db, tag, 'listing', listing.id, weight)
            attached.add(tag_name)

        # --- Auto tags (skip if already attached by user) ---
        auto_tags = _build_auto_tags(payload, db)
        for name in auto_tags:
            if name in attached:
                continue
            tag = _get_or_create_tag(db, name)
            _attach_tag(db, tag, 'listing', listing.id, 0)

        db.commit()
        logger.info("register-listing  tags created for listing id=%d user=%d auto=%d",
                     listing.id, min(len(payload.tags), 3), len(auto_tags))
    except Exception:
        db.rollback()
        logger.exception("register-listing  tag creation failed for listing id=%d", listing.id)


def _build_auto_tags(payload, db):
    """Build list of auto-generated tag names from structured listing data."""
    tags = []
    _tag_enchant_names(tags, payload)
    _tag_erg(tags, payload)
    _tag_special_upgrade(tags, payload)
    _tag_piercing_maxroll(tags, payload, db)
    return tags


def _tag_enchant_names(tags, payload):
    for enc in payload.enchants:
        if enc.name:
            tags.append(enc.name)


def _tag_erg(tags, payload):
    if payload.erg_grade and payload.erg_level == 50:
        tags.append(f'{payload.erg_grade}르그50')


def _tag_special_upgrade(tags, payload):
    if not payload.special_upgrade_type:
        return
    upgrade_name = _SPECIAL_UPGRADE_NAMES.get(payload.special_upgrade_type)
    if upgrade_name:
        tags.append(upgrade_name)
    if payload.special_upgrade_level in (7, 8):
        tags.append(f'{payload.special_upgrade_level}강')


def _tag_piercing_maxroll(tags, payload, db):
    for opt in payload.listing_options:
        if opt.option_type != 'enchant_effects' or opt.option_name != '피어싱 레벨':
            continue
        if opt.rolled_value is None or not opt.option_id:
            continue
        row = db.execute(
            text("SELECT max_value FROM enchant_effects WHERE id = :id"),
            {"id": opt.option_id},
        ).mappings().first()
        if row and row['max_value'] is not None and float(opt.rolled_value) >= float(row['max_value']):
            tags.append('풀피어싱')
            return


def _batch_resolve_tags(db, listing_ids):
    """Batch-resolve tags for multiple listings via a single query.

    Returns dict: listing_id -> [tag_name, ...]
    """
    if not listing_ids:
        return {}
    placeholders = ', '.join(f':id{i}' for i in range(len(listing_ids)))
    params = {f'id{i}': lid for i, lid in enumerate(listing_ids)}
    rows = db.execute(
        text(f"""
            SELECT DISTINCT sub.l_id, t.name, (t.weight + tt.weight) AS weight
            FROM (
                SELECT l.id AS l_id, 'listing' AS ttype, l.id AS tid FROM listings l WHERE l.id IN ({placeholders})
                UNION ALL
                SELECT l.id, 'game_item', l.game_item_id FROM listings l WHERE l.id IN ({placeholders}) AND l.game_item_id IS NOT NULL
                UNION ALL
                SELECT lo.listing_id, lo.option_type, lo.option_id FROM listing_options lo WHERE lo.listing_id IN ({placeholders}) AND lo.option_id IS NOT NULL
                UNION ALL
                SELECT l.id, 'enchant', l.prefix_enchant_id FROM listings l WHERE l.id IN ({placeholders}) AND l.prefix_enchant_id IS NOT NULL
                UNION ALL
                SELECT l.id, 'enchant', l.suffix_enchant_id FROM listings l WHERE l.id IN ({placeholders}) AND l.suffix_enchant_id IS NOT NULL
            ) AS sub(l_id, ttype, tid)
            JOIN tag_targets tt ON tt.target_type = sub.ttype AND tt.target_id = sub.tid
            JOIN tags t ON t.id = tt.tag_id
            ORDER BY (t.weight + tt.weight) DESC, t.name
        """),
        params,
    ).mappings()

    tags_by_listing = {}
    for r in rows:
        tags_by_listing.setdefault(r['l_id'], []).append({'name': r['name'], 'weight': r['weight']})
    # Deduplicate by name (DISTINCT in SQL covers (l_id, name, weight) triples)
    for lid in tags_by_listing:
        seen = set()
        deduped = []
        for tag in tags_by_listing[lid]:
            if tag['name'] not in seen:
                seen.add(tag['name'])
                deduped.append(tag)
        tags_by_listing[lid] = deduped
    return tags_by_listing


def _batch_resolve_options(db, listing_ids):
    """Batch-fetch listing_options for a set of listing IDs."""
    if not listing_ids:
        return {}
    placeholders = ', '.join(f':id{i}' for i in range(len(listing_ids)))
    params = {f'id{i}': lid for i, lid in enumerate(listing_ids)}
    rows = db.execute(
        text(f"""
            SELECT listing_id, option_type, option_name, rolled_value, max_level
            FROM listing_options
            WHERE listing_id IN ({placeholders})
            ORDER BY id
        """),
        params,
    ).mappings()
    options_by_listing = {}
    for r in rows:
        options_by_listing.setdefault(r['listing_id'], []).append({
            'option_type': r['option_type'],
            'option_name': r['option_name'],
            'rolled_value': r['rolled_value'],
            'max_level': r['max_level'],
        })
    return options_by_listing


def get_listings(db, game_item_id=None, limit=50, offset=0):
    """Fetch listing summaries, optionally filtered by game_item_id."""
    base_sql = """
        SELECT
            l.id,
            l.name,
            l.description,
            l.price,
            l.game_item_id,
            gi.name AS game_item_name,
            pe.name AS prefix_enchant_name,
            se.name AS suffix_enchant_name,
            l.item_type,
            l.item_grade,
            l.erg_grade,
            l.erg_level,
            l.special_upgrade_type,
            l.special_upgrade_level,
            l.damage,
            l.magic_damage,
            l.additional_damage,
            l.balance,
            l.defense,
            l.protection,
            l.magic_defense,
            l.magic_protection,
            l.durability,
            l.piercing_level,
            l.created_at,
            u.server AS seller_server,
            u.game_id AS seller_game_id
        FROM listings l
        LEFT JOIN game_items gi ON gi.id = l.game_item_id
        LEFT JOIN enchants pe ON pe.id = l.prefix_enchant_id
        LEFT JOIN enchants se ON se.id = l.suffix_enchant_id
        LEFT JOIN users u ON u.id = l.user_id
    """
    params = {"limit": limit, "offset": offset}
    if game_item_id is not None:
        params["game_item_id"] = game_item_id
        rows = db.execute(
            text(base_sql + """
                WHERE l.game_item_id = :game_item_id
                ORDER BY l.id DESC
                LIMIT :limit OFFSET :offset
            """),
            params,
        ).mappings()
    else:
        rows = db.execute(
            text(base_sql + """
                ORDER BY l.id DESC
                LIMIT :limit OFFSET :offset
            """),
            params,
        ).mappings()
    listings = [dict(r) for r in rows]

    # Batch-resolve tags and options
    listing_ids = [l['id'] for l in listings]
    tags_map = _batch_resolve_tags(db, listing_ids)
    options_map = _batch_resolve_options(db, listing_ids)
    for l in listings:
        l['tags'] = tags_map.get(l['id'], [])
        l['listing_options'] = options_map.get(l['id'], [])

    return listings


def search_game_items(db, q, limit=20):
    """Search game items by name (ILIKE)."""
    rows = db.execute(
        text("""
            SELECT id, name
            FROM game_items
            WHERE name ILIKE :q
            ORDER BY name
            LIMIT :limit
        """),
        {"q": f"%{q}%", "limit": limit},
    ).mappings()
    return [dict(r) for r in rows]


def search_tags(db, q, limit=10):
    """Search tag names by ILIKE. Returns [{name, weight}, ...]."""
    if not q.strip():
        return []
    rows = db.execute(
        text("""
            SELECT name, weight
            FROM tags
            WHERE name ILIKE :q AND weight > 0
            ORDER BY weight DESC, name
            LIMIT :limit
        """),
        {"q": f"%{q.strip()}%", "limit": limit},
    ).mappings()
    return [dict(r) for r in rows]


def search_listings(db, q, tags=None, limit=50, offset=0):
    """Search listings by tags (AND) and/or text query (cascading).

    - tags: list of exact tag names — intersection (listings matching ALL)
    - q: text query — cascading tier search (tag ILIKE → game_item → listing name)
    When both are provided, intersect the results.
    """
    tag_ids = set()
    text_ids = set()

    # --- Multi-tag filter (AND / intersection) ---
    if tags:
        tag_ids = _search_by_exact_tags(db, tags)
        if not tag_ids:
            return []

    # --- Text query (cascading) ---
    q = (q or '').strip()
    if q:
        text_ids = _search_by_text(db, q)
        if not text_ids:
            if not tags:
                return []

    # Combine
    if tags and q:
        result_ids = tag_ids & text_ids
    elif tags:
        result_ids = tag_ids
    else:
        result_ids = text_ids

    if not result_ids:
        return []

    return _fetch_listings_by_ids(db, list(result_ids), limit=limit, offset=offset)


_LISTING_RESOLVE_CTE = """
    SELECT l.id, 'listing' AS ttype, l.id AS tid FROM listings l
    UNION ALL
    SELECT l.id, 'game_item', l.game_item_id FROM listings l WHERE l.game_item_id IS NOT NULL
    UNION ALL
    SELECT lo.listing_id, lo.option_type, lo.option_id FROM listing_options lo WHERE lo.option_id IS NOT NULL
    UNION ALL
    SELECT l.id, 'enchant', l.prefix_enchant_id FROM listings l WHERE l.prefix_enchant_id IS NOT NULL
    UNION ALL
    SELECT l.id, 'enchant', l.suffix_enchant_id FROM listings l WHERE l.suffix_enchant_id IS NOT NULL
"""


def _search_by_exact_tags(db, tag_names):
    """Find listing IDs matching ALL given tag names (intersection)."""
    placeholders = ', '.join(f':t{i}' for i in range(len(tag_names)))
    params = {f't{i}': name for i, name in enumerate(tag_names)}
    params['cnt'] = len(tag_names)
    rows = db.execute(
        text(f"""
            SELECT sub.id
            FROM tags t
            JOIN tag_targets tt ON tt.tag_id = t.id
            JOIN ({_LISTING_RESOLVE_CTE}) AS sub(id, ttype, tid)
                ON tt.target_type = sub.ttype AND tt.target_id = sub.tid
            WHERE t.name IN ({placeholders})
            GROUP BY sub.id
            HAVING COUNT(DISTINCT t.name) = :cnt
        """),
        params,
    ).scalars().all()
    return set(rows)


def _search_by_text(db, q):
    """Cascading text search: tag ILIKE → game_item name → listing name."""
    like_q = f"%{q}%"

    # Tier 1: tag name ILIKE
    tag_listing_ids = db.execute(
        text(f"""
            SELECT DISTINCT sub.id
            FROM tags t
            JOIN tag_targets tt ON tt.tag_id = t.id
            JOIN ({_LISTING_RESOLVE_CTE}) AS sub(id, ttype, tid)
                ON tt.target_type = sub.ttype AND tt.target_id = sub.tid
            WHERE t.name ILIKE :q
        """),
        {"q": like_q},
    ).scalars().all()
    if tag_listing_ids:
        return set(tag_listing_ids)

    # Tier 2: game_item name
    gi_listing_ids = db.execute(
        text("""
            SELECT l.id
            FROM listings l
            JOIN game_items gi ON gi.id = l.game_item_id
            WHERE gi.name ILIKE :q
        """),
        {"q": like_q},
    ).scalars().all()
    if gi_listing_ids:
        return set(gi_listing_ids)

    # Tier 3: listing name
    name_listing_ids = db.execute(
        text("""
            SELECT l.id FROM listings l WHERE l.name ILIKE :q
        """),
        {"q": like_q},
    ).scalars().all()
    return set(name_listing_ids)


def _fetch_listings_by_ids(db, listing_ids, limit=50, offset=0):
    """Fetch full listing summaries for a set of IDs."""
    if not listing_ids:
        return []
    placeholders = ', '.join(f':id{i}' for i in range(len(listing_ids)))
    params = {f'id{i}': lid for i, lid in enumerate(listing_ids)}
    params['limit'] = limit
    params['offset'] = offset
    rows = db.execute(
        text(f"""
            SELECT
                l.id, l.name, l.description, l.price, l.game_item_id,
                gi.name AS game_item_name,
                pe.name AS prefix_enchant_name,
                se.name AS suffix_enchant_name,
                l.item_type, l.item_grade,
                l.erg_grade, l.erg_level,
                l.special_upgrade_type, l.special_upgrade_level,
                l.damage, l.magic_damage, l.additional_damage, l.balance,
                l.defense, l.protection, l.magic_defense, l.magic_protection,
                l.durability, l.piercing_level,
                l.created_at,
                u.server AS seller_server,
                u.game_id AS seller_game_id
            FROM listings l
            LEFT JOIN game_items gi ON gi.id = l.game_item_id
            LEFT JOIN enchants pe ON pe.id = l.prefix_enchant_id
            LEFT JOIN enchants se ON se.id = l.suffix_enchant_id
            LEFT JOIN users u ON u.id = l.user_id
            WHERE l.id IN ({placeholders})
            ORDER BY l.id DESC
            LIMIT :limit OFFSET :offset
        """),
        params,
    ).mappings()
    listings = [dict(r) for r in rows]

    ids = [l['id'] for l in listings]
    tags_map = _batch_resolve_tags(db, ids)
    options_map = _batch_resolve_options(db, ids)
    for l in listings:
        l['tags'] = tags_map.get(l['id'], [])
        l['listing_options'] = options_map.get(l['id'], [])

    return listings
