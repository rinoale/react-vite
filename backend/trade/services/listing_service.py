from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from db.models import Listing, ListingOption, Enchant, GameItem
from db import models
from lib.utils.log import logger


_VALID_STATUS_TRANSITIONS = {0, 1, 2, 3}


def update_listing_status(db, listing_id, status, user_id):
    """Update listing status. Only the owner can change status."""
    if status not in _VALID_STATUS_TRANSITIONS:
        raise HTTPException(status_code=400, detail="Invalid status")
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not your listing")
    listing.status = status
    db.commit()
    return {"id": listing.id, "status": listing.status}


_ATTR_COLUMNS = {
    'damage', 'magic_damage', 'additional_damage', 'balance',
    'defense', 'protection', 'magic_defense', 'magic_protection',
    'durability', 'piercing_level',
}

_FILTERABLE_COLUMNS = frozenset({
    'special_upgrade_level', 'erg_level', 'piercing_level',
    'damage', 'magic_damage', 'additional_damage', 'balance',
    'defense', 'protection', 'magic_defense', 'magic_protection',
    'durability',
})


_OP_PREFIXES = {'min_': '>=', 'max_': '<=', 'eq_': '='}


def parse_attr_filters(query_params):
    """Extract min_/max_/eq_{col} query params as numeric attribute filters.

    Only columns in _FILTERABLE_COLUMNS are accepted.
    Returns list of (col, op_sql, value) tuples, or None if no valid filters found.
    """
    result = []
    for prefix, op_sql in _OP_PREFIXES.items():
        for col in _FILTERABLE_COLUMNS:
            val = query_params.get(f"{prefix}{col}")
            if val is not None:
                try:
                    result.append((col, op_sql, int(val)))
                except (ValueError, TypeError):
                    pass
    return result or None


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
        status=Listing.LISTED,
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
            l.status,
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
        WHERE l.status = 1
    """
    params = {"limit": limit, "offset": offset}
    if game_item_id is not None:
        params["game_item_id"] = game_item_id
        rows = db.execute(
            text(base_sql + """
                AND l.game_item_id = :game_item_id
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


def get_my_listings(db, user_id, limit=50, offset=0):
    """Fetch listings owned by a user (all statuses)."""
    rows = db.execute(
        text("""
            SELECT
                l.id, l.status, l.name, l.description, l.price, l.game_item_id,
                gi.name AS game_item_name,
                pe.name AS prefix_enchant_name,
                se.name AS suffix_enchant_name,
                l.item_type, l.item_grade,
                l.erg_grade, l.erg_level,
                l.special_upgrade_type, l.special_upgrade_level,
                l.damage, l.magic_damage, l.additional_damage, l.balance,
                l.defense, l.protection, l.magic_defense, l.magic_protection,
                l.durability, l.piercing_level,
                l.created_at
            FROM listings l
            LEFT JOIN game_items gi ON gi.id = l.game_item_id
            LEFT JOIN enchants pe ON pe.id = l.prefix_enchant_id
            LEFT JOIN enchants se ON se.id = l.suffix_enchant_id
            WHERE l.user_id = :user_id AND l.status != 3
            ORDER BY l.id DESC
            LIMIT :limit OFFSET :offset
        """),
        {"user_id": user_id, "limit": limit, "offset": offset},
    ).mappings()
    listings = [dict(r) for r in rows]

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


def search_listings(db, q, tags=None, game_item_id=None, attr_filters=None, limit=50, offset=0):
    """Search listings by tags (AND) and/or text query (cascading) and/or game item and/or attr ranges.

    - tags: list of exact tag names — intersection (listings matching ALL)
    - q: text query — cascading tier search (tag ILIKE → game_item → listing name)
    - game_item_id: exact game item filter
    - attr_filters: list of (col, op_sql, value) tuples for numeric range filters
    All provided filters are intersected (AND).
    """
    id_sets = []

    # --- Multi-tag filter (AND / intersection) ---
    if tags:
        tag_ids = _search_by_exact_tags(db, tags)
        if not tag_ids:
            return []
        id_sets.append(tag_ids)

    # --- Text query (cascading) ---
    q = (q or '').strip()
    if q:
        text_ids = _search_by_text(db, q)
        if not text_ids:
            if not id_sets:
                return []
        else:
            id_sets.append(text_ids)

    # --- Game item filter ---
    if game_item_id is not None:
        gi_ids = set(
            db.execute(
                text("SELECT id FROM listings WHERE status = 1 AND game_item_id = :gi"),
                {"gi": game_item_id},
            ).scalars().all()
        )
        if not gi_ids:
            return []
        id_sets.append(gi_ids)

    # --- Attribute range filters (>=, <=, = conditions) ---
    if attr_filters:
        conds = []
        af_params = {}
        for i, (col, op_sql, val) in enumerate(attr_filters):
            if col in _FILTERABLE_COLUMNS:
                param_key = f"af_{i}_{col}"
                conds.append(f"l.{col} {op_sql} :{param_key}")
                af_params[param_key] = val
        if conds:
            where = " AND ".join(conds)
            af_ids = set(
                db.execute(
                    text(f"SELECT l.id FROM listings l WHERE l.status = 1 AND {where}"),
                    af_params,
                ).scalars().all()
            )
            if not af_ids:
                return []
            id_sets.append(af_ids)

    if not id_sets:
        return []

    result_ids = id_sets[0]
    for s in id_sets[1:]:
        result_ids = result_ids & s

    if not result_ids:
        return []

    return _fetch_listings_by_ids(db, list(result_ids), limit=limit, offset=offset)


_LISTING_RESOLVE_CTE = """
    SELECT l.id, 'listing' AS ttype, l.id AS tid FROM listings l WHERE l.status = 1
    UNION ALL
    SELECT l.id, 'game_item', l.game_item_id FROM listings l WHERE l.status = 1 AND l.game_item_id IS NOT NULL
    UNION ALL
    SELECT lo.listing_id, lo.option_type, lo.option_id FROM listing_options lo
        JOIN listings l ON l.id = lo.listing_id WHERE l.status = 1 AND lo.option_id IS NOT NULL
    UNION ALL
    SELECT l.id, 'enchant', l.prefix_enchant_id FROM listings l WHERE l.status = 1 AND l.prefix_enchant_id IS NOT NULL
    UNION ALL
    SELECT l.id, 'enchant', l.suffix_enchant_id FROM listings l WHERE l.status = 1 AND l.suffix_enchant_id IS NOT NULL
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
            WHERE l.status = 1 AND gi.name ILIKE :q
        """),
        {"q": like_q},
    ).scalars().all()
    if gi_listing_ids:
        return set(gi_listing_ids)

    # Tier 3: listing name
    name_listing_ids = db.execute(
        text("""
            SELECT l.id FROM listings l WHERE l.status = 1 AND l.name ILIKE :q
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
                l.id, l.status, l.name, l.description, l.price, l.game_item_id,
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


def _resolve_listing_tags(db: Session, listing_id: int):
    """Resolve all tags for a single listing (used by detail view)."""
    rows = db.execute(
        text("""
            SELECT DISTINCT t.name, (t.weight + tt.weight) AS weight
            FROM (
                SELECT 'listing' AS ttype, :lid AS tid
                UNION ALL
                SELECT 'game_item', l.game_item_id FROM listings l WHERE l.id = :lid AND l.game_item_id IS NOT NULL
                UNION ALL
                SELECT lo.option_type, lo.option_id FROM listing_options lo WHERE lo.listing_id = :lid AND lo.option_id IS NOT NULL
                UNION ALL
                SELECT 'enchant', l.prefix_enchant_id FROM listings l WHERE l.id = :lid AND l.prefix_enchant_id IS NOT NULL
                UNION ALL
                SELECT 'enchant', l.suffix_enchant_id FROM listings l WHERE l.id = :lid AND l.suffix_enchant_id IS NOT NULL
            ) AS sub(ttype, tid)
            JOIN tag_targets tt ON tt.target_type = sub.ttype AND tt.target_id = sub.tid
            JOIN tags t ON t.id = tt.tag_id
            ORDER BY (t.weight + tt.weight) DESC, t.name
        """),
        {"lid": listing_id},
    ).mappings()
    return [{"name": r["name"], "weight": r["weight"]} for r in rows]


def _build_enchant_detail(db: Session, listing_id: int, enchant_id: int, slot: int):
    """Build enchant detail dict with all effects for a single enchant slot."""
    enc = db.query(models.Enchant).filter(models.Enchant.id == enchant_id).first()
    if not enc:
        return None
    effect_rows = db.execute(
        text(
            """
            SELECT ee.raw_text, ee.min_value, ee.max_value, lo.rolled_value AS value
            FROM enchant_effects ee
            LEFT JOIN listing_options lo
              ON lo.option_type = 'enchant_effects'
              AND lo.option_id = ee.id
              AND lo.listing_id = :listing_id
            WHERE ee.enchant_id = :enchant_id
            ORDER BY ee.effect_order
            """
        ),
        {"listing_id": listing_id, "enchant_id": enchant_id},
    ).mappings()
    return {
        "slot": slot,
        "enchant_name": enc.name,
        "rank": enc.rank,
        "effects": [dict(e) for e in effect_rows],
    }


def get_listing_detail(db: Session, listing_id: int):
    """Fetch full listing detail including enchants, options, tags, and seller info."""
    listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
    if not listing:
        return None

    # Resolve seller info
    seller = None
    if listing.user_id:
        seller = db.query(models.User).filter(models.User.id == listing.user_id).first()

    game_item_name = None
    if listing.game_item_id:
        gi = db.query(models.GameItem).filter(models.GameItem.id == listing.game_item_id).first()
        if gi:
            game_item_name = gi.name

    prefix_enchant = None
    if listing.prefix_enchant_id:
        prefix_enchant = _build_enchant_detail(db, listing_id, listing.prefix_enchant_id, 0)

    suffix_enchant = None
    if listing.suffix_enchant_id:
        suffix_enchant = _build_enchant_detail(db, listing_id, listing.suffix_enchant_id, 1)

    # All listing options (reforge, echostone, murias_relic, enchant_effect)
    option_rows = db.execute(
        text(
            """
            SELECT option_type, option_name, rolled_value, max_level
            FROM listing_options
            WHERE listing_id = :listing_id
            ORDER BY id
            """
        ),
        {"listing_id": listing_id},
    ).mappings()

    return {
        "id": listing.id,
        "status": listing.status,
        "name": listing.name,
        "description": listing.description,
        "price": listing.price,
        "game_item_id": listing.game_item_id,
        "game_item_name": game_item_name,
        "item_type": listing.item_type,
        "item_grade": listing.item_grade,
        "erg_grade": listing.erg_grade,
        "erg_level": listing.erg_level,
        "special_upgrade_type": listing.special_upgrade_type,
        "special_upgrade_level": listing.special_upgrade_level,
        "damage": listing.damage,
        "magic_damage": listing.magic_damage,
        "additional_damage": listing.additional_damage,
        "balance": listing.balance,
        "defense": listing.defense,
        "protection": listing.protection,
        "magic_defense": listing.magic_defense,
        "magic_protection": listing.magic_protection,
        "durability": listing.durability,
        "piercing_level": listing.piercing_level,
        "prefix_enchant": prefix_enchant,
        "suffix_enchant": suffix_enchant,
        "listing_options": [dict(r) for r in option_rows],
        "tags": _resolve_listing_tags(db, listing_id),
        "seller_server": seller.server if seller else None,
        "seller_game_id": seller.game_id if seller else None,
        "seller_discord_id": seller.discord_id if seller else None,
    }
