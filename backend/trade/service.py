import json
import os
import shutil

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session, joinedload

from db.models import (
    OcrCorrection, Listing, ListingEnchantEffect, ListingReforgeOption,
    Enchant, EnchantEffect, ReforgeOption, GameItem, Tag,
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


def create_listing(payload, db):
    """Resolve FKs and persist a Listing with enchant effects and reforge options.

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

        # --- Enchant effects (rolled values) ---
        for slot, (enchant_row, enc) in enchant_rows_by_slot.items():
            # Pre-load enchant_effects with effect names for name-based fallback
            ee_rows = (db.query(EnchantEffect)
                       .options(joinedload(EnchantEffect.effect_def))
                       .filter(EnchantEffect.enchant_id == enchant_row.id)
                       .order_by(EnchantEffect.effect_order)
                       .all())
            ee_by_name = {}
            for row in ee_rows:
                if row.effect_def and row.effect_def.name:
                    ee_by_name.setdefault(row.effect_def.name, []).append(row.id)

            for eff in enc.effects:
                if eff.option_level is None:
                    continue
                # Use direct ID from config when provided
                ee_id = eff.enchant_effect_id
                if not ee_id and eff.option_name:
                    # Fallback: exact name match first, then fuzzy (longest substring)
                    candidates = ee_by_name.get(eff.option_name, [])
                    if not candidates:
                        fuzzy = [(n, ids) for n, ids in ee_by_name.items() if n in eff.option_name and ids]
                        if fuzzy:
                            best_name = max(fuzzy, key=lambda x: len(x[0]))[0]
                            candidates = ee_by_name[best_name]
                    if candidates:
                        ee_id = candidates.pop(0)  # consume to avoid reuse
                if ee_id:
                    db.add(ListingEnchantEffect(
                        listing_id=listing.id,
                        enchant_effect_id=ee_id,
                        value=eff.option_level,
                    ))

        # --- Reforge options ---
        for opt in payload.reforge_options:
            reforge_option_id = opt.reforge_option_id
            if not reforge_option_id:
                reforge_row = db.query(ReforgeOption).filter(
                    ReforgeOption.option_name == opt.name,
                ).first()
                reforge_option_id = reforge_row.id if reforge_row else None
            db.add(ListingReforgeOption(
                listing_id=listing.id,
                reforge_option_id=reforge_option_id,
                option_name=opt.name,
                level=opt.level,
                max_level=opt.max_level,
            ))

        # --- Tags (weights 9, 6, 3 for positions 0, 1, 2) ---
        _TAG_WEIGHTS = [80, 60, 30]
        for idx, tag_name in enumerate(payload.tags[:3]):
            tag_name = tag_name.strip()
            if not tag_name:
                continue
            db.add(Tag(
                target_type='listing',
                target_id=listing.id,
                name=tag_name,
                weight=_TAG_WEIGHTS[idx],
            ))

        db.commit()
        db.refresh(listing)
        logger.info("register-listing  persisted listing id=%d name=%r enchants=%d reforges=%d tags=%d",
                     listing.id, listing.name, len(payload.enchants), len(payload.reforge_options), min(len(payload.tags), 3))
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("register-listing  listing persist failed")
        raise HTTPException(status_code=500, detail="Failed to persist listing")

    return listing


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
            SELECT DISTINCT sub.l_id, t.name, t.weight
            FROM (
                SELECT l.id AS l_id, 'listing' AS ttype, l.id AS tid FROM listings l WHERE l.id IN ({placeholders})
                UNION ALL
                SELECT l.id, 'game_item', l.game_item_id FROM listings l WHERE l.id IN ({placeholders}) AND l.game_item_id IS NOT NULL
                UNION ALL
                SELECT lro.listing_id, 'reforge_option', lro.reforge_option_id FROM listing_reforge_options lro WHERE lro.listing_id IN ({placeholders}) AND lro.reforge_option_id IS NOT NULL
                UNION ALL
                SELECT l.id, 'enchant', l.prefix_enchant_id FROM listings l WHERE l.id IN ({placeholders}) AND l.prefix_enchant_id IS NOT NULL
                UNION ALL
                SELECT l.id, 'enchant', l.suffix_enchant_id FROM listings l WHERE l.id IN ({placeholders}) AND l.suffix_enchant_id IS NOT NULL
            ) AS sub(l_id, ttype, tid)
            JOIN tags t ON t.target_type = sub.ttype AND t.target_id = sub.tid
            ORDER BY t.weight DESC, t.name
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


def get_listings(db, game_item_id=None):
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
            COUNT(DISTINCT lro.id) AS reforge_count
        FROM listings l
        LEFT JOIN game_items gi ON gi.id = l.game_item_id
        LEFT JOIN enchants pe ON pe.id = l.prefix_enchant_id
        LEFT JOIN enchants se ON se.id = l.suffix_enchant_id
        LEFT JOIN listing_reforge_options lro ON lro.listing_id = l.id
    """
    if game_item_id is not None:
        rows = db.execute(
            text(base_sql + """
                WHERE l.game_item_id = :game_item_id
                GROUP BY l.id, gi.name, pe.name, se.name
                ORDER BY l.id DESC
            """),
            {"game_item_id": game_item_id},
        ).mappings()
    else:
        rows = db.execute(
            text(base_sql + """
                GROUP BY l.id, gi.name, pe.name, se.name
                ORDER BY l.id DESC
            """)
        ).mappings()
    listings = [dict(r) for r in rows]

    # Batch-resolve tags
    listing_ids = [l['id'] for l in listings]
    tags_map = _batch_resolve_tags(db, listing_ids)
    for l in listings:
        l['tags'] = tags_map.get(l['id'], [])

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


def search_listings(db, q):
    """Cascading search: tag name → game_item name → listing name.

    Returns listings matching the first tier that produces results.
    """
    q = q.strip()
    if not q:
        return get_listings(db)

    like_q = f"%{q}%"

    # Tier 1: tag name → resolve to listing IDs via polymorphic tags
    tag_listing_ids = db.execute(
        text("""
            SELECT DISTINCT l.id
            FROM tags t
            JOIN (
                SELECT l.id, 'listing' AS ttype, l.id AS tid FROM listings l
                UNION ALL
                SELECT l.id, 'game_item', l.game_item_id FROM listings l WHERE l.game_item_id IS NOT NULL
                UNION ALL
                SELECT lro.listing_id, 'reforge_option', lro.reforge_option_id FROM listing_reforge_options lro WHERE lro.reforge_option_id IS NOT NULL
                UNION ALL
                SELECT l.id, 'enchant', l.prefix_enchant_id FROM listings l WHERE l.prefix_enchant_id IS NOT NULL
                UNION ALL
                SELECT l.id, 'enchant', l.suffix_enchant_id FROM listings l WHERE l.suffix_enchant_id IS NOT NULL
            ) AS sub(id, ttype, tid) ON t.target_type = sub.ttype AND t.target_id = sub.tid
            JOIN listings l ON l.id = sub.id
            WHERE t.name ILIKE :q
        """),
        {"q": like_q},
    ).scalars().all()

    if tag_listing_ids:
        return _fetch_listings_by_ids(db, tag_listing_ids)

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
        return _fetch_listings_by_ids(db, gi_listing_ids)

    # Tier 3: listing name
    name_listing_ids = db.execute(
        text("""
            SELECT l.id FROM listings l WHERE l.name ILIKE :q
        """),
        {"q": like_q},
    ).scalars().all()

    if name_listing_ids:
        return _fetch_listings_by_ids(db, name_listing_ids)

    return []


def _fetch_listings_by_ids(db, listing_ids):
    """Fetch full listing summaries for a set of IDs."""
    if not listing_ids:
        return []
    placeholders = ', '.join(f':id{i}' for i in range(len(listing_ids)))
    params = {f'id{i}': lid for i, lid in enumerate(listing_ids)}
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
                COUNT(DISTINCT lro.id) AS reforge_count
            FROM listings l
            LEFT JOIN game_items gi ON gi.id = l.game_item_id
            LEFT JOIN enchants pe ON pe.id = l.prefix_enchant_id
            LEFT JOIN enchants se ON se.id = l.suffix_enchant_id
            LEFT JOIN listing_reforge_options lro ON lro.listing_id = l.id
            WHERE l.id IN ({placeholders})
            GROUP BY l.id, gi.name, pe.name, se.name
            ORDER BY l.id DESC
        """),
        params,
    ).mappings()
    listings = [dict(r) for r in rows]

    tags_map = _batch_resolve_tags(db, [l['id'] for l in listings])
    for l in listings:
        l['tags'] = tags_map.get(l['id'], [])

    return listings
