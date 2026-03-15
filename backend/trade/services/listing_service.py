import json

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from db.models import Listing, ListingOption, Enchant, GameItem
from db import models
from lib.utils.log import logger


_VALID_STATUS_TRANSITIONS = {0, 1, 2, 3}


def update_listing_status(*, listing_id, status, user_id, db: Session):
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


_STRING_EQUALITY_COLUMNS = frozenset({'erg_grade', 'special_upgrade_type'})


def parse_attr_filters(query_params):
    """Extract min_/max_/eq_{col} query params as numeric attribute filters,
    plus string equality filters for erg_grade and special_upgrade_type.

    Only columns in _FILTERABLE_COLUMNS / _STRING_EQUALITY_COLUMNS are accepted.
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
    for col in _STRING_EQUALITY_COLUMNS:
        val = query_params.get(col)
        if val is not None:
            result.append((col, '=', val))
    return result or None


_OP_MAP = {'gte': '>=', 'lte': '<=', 'eq': '='}


def parse_reforge_filters(raw_json):
    """Parse reforge/echostone/murias filters from JSON string.

    Expected format: [{"id": "uuid", "op": "gte|lte|eq", "level": int|null}, ...]
    Returns list of (option_id, op_sql, level_or_None) tuples, or None.
    """
    return parse_option_filters(raw_json)


def parse_option_filters(raw_json):
    """Parse option filters from JSON string.

    Expected format: [{"id": "uuid", "op": "gte|lte|eq", "level": int|null}, ...]
    Returns list of (option_id, op_sql, level_or_None) tuples, or None.
    Level=None means existence-only (no rolled_value constraint).
    """
    if not raw_json:
        return None
    try:
        filters = json.loads(raw_json)
        if not isinstance(filters, list):
            return None
        result = []
        for f in filters:
            option_id = f.get('id')
            if not option_id:
                continue
            op = f.get('op', 'gte')
            level = f.get('level')
            op_sql = _OP_MAP.get(op, '>=')
            result.append((option_id, op_sql, int(level) if level is not None else None))
        return result or None
    except (json.JSONDecodeError, ValueError, TypeError):
        return None


def parse_enchant_filters(raw_json):
    """Parse enchant filters from JSON string.

    Expected format: [{"id": "uuid", "effects": [{"enchant_id": "uuid", "effect_order": int, "op": "gte|lte|eq", "value": int}]}]
    Returns list of dicts with 'id' and 'effects' keys, or None.
    """
    if not raw_json:
        return None
    try:
        filters = json.loads(raw_json)
        if not isinstance(filters, list):
            return None
        result = []
        for f in filters:
            enchant_id = f.get('id')
            if not enchant_id:
                continue
            effects = []
            for eff in f.get('effects', []):
                eff_enchant_id = eff.get('enchant_id')
                eff_order = eff.get('effect_order')
                op = eff.get('op', 'gte')
                value = eff.get('value')
                if eff_enchant_id is not None and eff_order is not None and value is not None:
                    effects.append({
                        'enchant_id': eff_enchant_id,
                        'effect_order': int(eff_order),
                        'op_sql': _OP_MAP.get(op, '>='),
                        'value': int(value),
                    })
            result.append({'id': enchant_id, 'effects': effects})
        return result or None
    except (json.JSONDecodeError, ValueError, TypeError):
        return None


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


def create_listing(*, payload, user_id=None, db: Session):
    """Resolve FKs and persist a Listing with listing options.

    Returns the created Listing.
    """
    game_item_id = payload.game_item_id

    # Enchant IDs come directly from frontend config
    prefix_enchant_id = None
    suffix_enchant_id = None
    for enc in payload.enchants:
        if enc.slot == 0:
            prefix_enchant_id = enc.id
        elif enc.slot == 1:
            suffix_enchant_id = enc.id

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
        logger.info("register-listing  persisted listing id=%s name=%r enchants=%d options=%d",
                     listing.id, listing.name, len(payload.enchants), len(payload.listing_options))
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("register-listing  listing persist failed")
        raise HTTPException(status_code=500, detail="Failed to persist listing")

    return listing


def _batch_resolve_tags(*, listing_ids, db: Session):
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
                SELECT l.id AS l_id, 'listings' AS ttype, l.id AS tid FROM listings l WHERE l.id IN ({placeholders})
                UNION ALL
                SELECT l.id, 'game_items', l.game_item_id FROM listings l WHERE l.id IN ({placeholders}) AND l.game_item_id IS NOT NULL
                UNION ALL
                SELECT lo.listing_id, lo.option_type, lo.option_id FROM listing_options lo WHERE lo.listing_id IN ({placeholders}) AND lo.option_id IS NOT NULL
                UNION ALL
                SELECT l.id, 'enchants', l.prefix_enchant_id FROM listings l WHERE l.id IN ({placeholders}) AND l.prefix_enchant_id IS NOT NULL
                UNION ALL
                SELECT l.id, 'enchants', l.suffix_enchant_id FROM listings l WHERE l.id IN ({placeholders}) AND l.suffix_enchant_id IS NOT NULL
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


def _batch_resolve_options(*, listing_ids, db: Session):
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


def get_listings(*, game_item_id=None, limit=50, offset=0, db: Session):
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
            u.game_id AS seller_game_id,
            u.verified AS seller_verified
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
    tags_map = _batch_resolve_tags(listing_ids=listing_ids, db=db)
    options_map = _batch_resolve_options(listing_ids=listing_ids, db=db)
    for l in listings:
        l['tags'] = tags_map.get(l['id'], [])
        l['listing_options'] = options_map.get(l['id'], [])

    return listings


def get_my_listings(*, user_id, limit=50, offset=0, db: Session):
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
    tags_map = _batch_resolve_tags(listing_ids=listing_ids, db=db)
    options_map = _batch_resolve_options(listing_ids=listing_ids, db=db)
    for l in listings:
        l['tags'] = tags_map.get(l['id'], [])
        l['listing_options'] = options_map.get(l['id'], [])

    return listings


def search_game_items(*, q, limit=20, db: Session):
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


def search_tags(*, q, limit=10, db: Session):
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


def _add_option_conditions(conditions, params, filters, option_type, prefix):
    """Append EXISTS conditions for listing_options filters (reforge/echostone/murias)."""
    for i, (option_id, op_sql, level) in enumerate(filters):
        id_key = f"{prefix}_id_{i}"
        params[id_key] = option_id
        if level is not None:
            level_key = f"{prefix}_level_{i}"
            params[level_key] = level
            conditions.append(f"""
                EXISTS (
                    SELECT 1 FROM listing_options lo
                    WHERE lo.listing_id = l.id
                    AND lo.option_type = '{option_type}'
                    AND lo.option_id = :{id_key}
                    AND lo.rolled_value {op_sql} :{level_key}
                )""")
        else:
            conditions.append(f"""
                EXISTS (
                    SELECT 1 FROM listing_options lo
                    WHERE lo.listing_id = l.id
                    AND lo.option_type = '{option_type}'
                    AND lo.option_id = :{id_key}
                )""")


def search_listings(*, q, tags=None, game_item_id=None, attr_filters=None,
                    reforge_filters=None, enchant_filters=None,
                    echostone_filters=None, murias_filters=None,
                    limit=50, offset=0, db: Session):
    """Search listings with all filters combined into a single query.

    Filters are intersected (AND). Text search uses cascading priority
    (tag ILIKE → game_item name → listing name) resolved via a CTE.
    """
    conditions = ["l.status = 1"]
    params = {"limit": limit, "offset": offset}

    # --- Text query (cascading: tag → game_item → listing name) ---
    q = (q or '').strip()
    if q:
        params["q_like"] = f"%{q}%"
        conditions.append(f"""
            l.id IN (
                SELECT _tq.id FROM (
                    SELECT DISTINCT sub.id, 1 AS tier
                    FROM tags t
                    JOIN tag_targets tt ON tt.tag_id = t.id
                    JOIN ({_LISTING_RESOLVE_CTE}) AS sub(id, ttype, tid)
                        ON tt.target_type = sub.ttype AND tt.target_id = sub.tid
                    WHERE t.name ILIKE :q_like
                    UNION ALL
                    SELECT l2.id, 2 FROM listings l2
                    JOIN game_items gi ON gi.id = l2.game_item_id
                    WHERE l2.status = 1 AND gi.name ILIKE :q_like
                    UNION ALL
                    SELECT l3.id, 3 FROM listings l3
                    WHERE l3.status = 1 AND l3.name ILIKE :q_like
                ) _tq
                WHERE _tq.tier = (
                    SELECT MIN(t) FROM (
                        SELECT 1 AS t WHERE EXISTS (SELECT 1 FROM tags t2 WHERE t2.name ILIKE :q_like)
                        UNION ALL
                        SELECT 2 WHERE EXISTS (SELECT 1 FROM game_items gi2 WHERE gi2.name ILIKE :q_like)
                        UNION ALL
                        SELECT 3
                    ) _mins
                )
            )""")

    # --- Multi-tag filter (AND / intersection) ---
    if tags:
        tag_placeholders = ', '.join(f':tag_{i}' for i in range(len(tags)))
        for i, name in enumerate(tags):
            params[f'tag_{i}'] = name
        params['tag_cnt'] = len(tags)
        conditions.append(f"""
            l.id IN (
                SELECT sub.id
                FROM tags t
                JOIN tag_targets tt ON tt.tag_id = t.id
                JOIN ({_LISTING_RESOLVE_CTE}) AS sub(id, ttype, tid)
                    ON tt.target_type = sub.ttype AND tt.target_id = sub.tid
                WHERE t.name IN ({tag_placeholders})
                GROUP BY sub.id
                HAVING COUNT(DISTINCT t.name) = :tag_cnt
            )""")

    # --- Game item filter ---
    if game_item_id is not None:
        params["game_item_id"] = game_item_id
        conditions.append("l.game_item_id = :game_item_id")

    # --- Attribute range filters ---
    if attr_filters:
        for i, (col, op_sql, val) in enumerate(attr_filters):
            if col in _FILTERABLE_COLUMNS or col in _STRING_EQUALITY_COLUMNS:
                key = f"af_{i}"
                params[key] = val
                conditions.append(f"l.{col} {op_sql} :{key}")

    # --- Option filters (reforge / echostone / murias) ---
    if reforge_filters:
        _add_option_conditions(conditions, params, reforge_filters, 'reforge_options', 'rf')
    if echostone_filters:
        _add_option_conditions(conditions, params, echostone_filters, 'echostone_options', 'es')
    if murias_filters:
        _add_option_conditions(conditions, params, murias_filters, 'murias_relic_options', 'mr')

    # --- Enchant filters (direct ID match) ---
    if enchant_filters:
        for i, ef in enumerate(enchant_filters):
            enc_id_key = f"enc_id_{i}"
            params[enc_id_key] = ef['id']
            conditions.append(f"""
                (l.prefix_enchant_id = :{enc_id_key}
                 OR l.suffix_enchant_id = :{enc_id_key})""")
            for j, eff in enumerate(ef.get('effects', [])):
                eff_enc_key = f"eff_enc_{i}_{j}"
                eff_ord_key = f"eff_ord_{i}_{j}"
                val_key = f"eff_val_{i}_{j}"
                params[eff_enc_key] = eff['enchant_id']
                params[eff_ord_key] = eff['effect_order']
                params[val_key] = eff['value']
                conditions.append(f"""
                    EXISTS (
                        SELECT 1 FROM listing_options lo
                        JOIN enchant_effects ee ON ee.id = lo.option_id
                        WHERE lo.listing_id = l.id
                        AND lo.option_type = 'enchant_effects'
                        AND ee.enchant_id = :{eff_enc_key}
                        AND ee.effect_order = :{eff_ord_key}
                        AND lo.rolled_value {eff['op_sql']} :{val_key}
                    )""")

    where = " AND ".join(conditions)
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
            WHERE {where}
            ORDER BY l.id DESC
            LIMIT :limit OFFSET :offset
        """),
        params,
    ).mappings()
    listings = [dict(r) for r in rows]

    if not listings:
        return []

    # Batch-resolve tags and options (2 queries)
    listing_ids = [l['id'] for l in listings]
    tags_map = _batch_resolve_tags(listing_ids=listing_ids, db=db)
    options_map = _batch_resolve_options(listing_ids=listing_ids, db=db)
    for l in listings:
        l['tags'] = tags_map.get(l['id'], [])
        l['listing_options'] = options_map.get(l['id'], [])

    return listings


_LISTING_RESOLVE_CTE = """
    SELECT l.id, 'listings' AS ttype, l.id AS tid FROM listings l WHERE l.status = 1
    UNION ALL
    SELECT l.id, 'game_items', l.game_item_id FROM listings l WHERE l.status = 1 AND l.game_item_id IS NOT NULL
    UNION ALL
    SELECT lo.listing_id, lo.option_type, lo.option_id FROM listing_options lo
        JOIN listings l ON l.id = lo.listing_id WHERE l.status = 1 AND lo.option_id IS NOT NULL
    UNION ALL
    SELECT l.id, 'enchants', l.prefix_enchant_id FROM listings l WHERE l.status = 1 AND l.prefix_enchant_id IS NOT NULL
    UNION ALL
    SELECT l.id, 'enchants', l.suffix_enchant_id FROM listings l WHERE l.status = 1 AND l.suffix_enchant_id IS NOT NULL
"""




def _resolve_listing_tags(*, listing_id, db: Session):
    """Resolve all tags for a single listing (used by detail view)."""
    rows = db.execute(
        text("""
            SELECT DISTINCT t.name, (t.weight + tt.weight) AS weight
            FROM (
                SELECT 'listings' AS ttype, :lid AS tid
                UNION ALL
                SELECT 'game_items', l.game_item_id FROM listings l WHERE l.id = :lid AND l.game_item_id IS NOT NULL
                UNION ALL
                SELECT lo.option_type, lo.option_id FROM listing_options lo WHERE lo.listing_id = :lid AND lo.option_id IS NOT NULL
                UNION ALL
                SELECT 'enchants', l.prefix_enchant_id FROM listings l WHERE l.id = :lid AND l.prefix_enchant_id IS NOT NULL
                UNION ALL
                SELECT 'enchants', l.suffix_enchant_id FROM listings l WHERE l.id = :lid AND l.suffix_enchant_id IS NOT NULL
            ) AS sub(ttype, tid)
            JOIN tag_targets tt ON tt.target_type = sub.ttype AND tt.target_id = sub.tid
            JOIN tags t ON t.id = tt.tag_id
            ORDER BY (t.weight + tt.weight) DESC, t.name
        """),
        {"lid": listing_id},
    ).mappings()
    return [{"name": r["name"], "weight": r["weight"]} for r in rows]


def _build_enchant_detail(*, listing_id, enchant_id, slot: int, db: Session):
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


def get_listing_detail(*, listing_id, db: Session):
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
        prefix_enchant = _build_enchant_detail(listing_id=listing_id, enchant_id=listing.prefix_enchant_id, slot=0, db=db)

    suffix_enchant = None
    if listing.suffix_enchant_id:
        suffix_enchant = _build_enchant_detail(listing_id=listing_id, enchant_id=listing.suffix_enchant_id, slot=1, db=db)

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
        "tags": _resolve_listing_tags(listing_id=listing_id, db=db),
        "seller_server": seller.server if seller else None,
        "seller_game_id": seller.game_id if seller else None,
        "seller_discord_id": seller.discord_id if seller else None,
        "seller_verified": seller.verified if seller else False,
    }
