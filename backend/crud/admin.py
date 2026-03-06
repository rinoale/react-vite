from typing import List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError
from db import models, schemas

def get_summary(db: Session):
    return {
        "enchants": db.query(models.Enchant).count(),
        "effects": db.query(models.Effect).count(),
        "enchant_effects": db.query(models.EnchantEffect).count(),
        "reforge_options": db.query(models.ReforgeOption).count(),
        "listings": db.query(models.Listing).count(),
        "game_items": db.query(models.GameItem).count(),
        "tags": db.query(models.Tag).count(),
    }

def get_enchants(db: Session, limit: int = 100, offset: int = 0):
    # Use raw SQL for count aggregation to avoid complexity with ORM relationships in simple list
    # but we can also use ORM with label
    rows = db.execute(
        text(
            """
            SELECT
                e.id,
                e.slot,
                e.name,
                e.rank,
                e.header_text,
                COUNT(ee.id) AS effect_count
            FROM enchants e
            LEFT JOIN enchant_effects ee ON ee.enchant_id = e.id
            GROUP BY e.id
            ORDER BY e.id
            LIMIT :limit OFFSET :offset
            """
        ),
        {"limit": limit, "offset": offset},
    ).mappings()
    return [dict(r) for r in rows]

def get_effects(db: Session, limit: int = 100, offset: int = 0):
    return db.query(models.Effect).order_by(models.Effect.id).limit(limit).offset(offset).all()

def get_enchant_effects(db: Session, limit: int = 100, offset: int = 0):
    rows = db.execute(
        text(
            """
            SELECT
                ee.id,
                ee.enchant_id,
                ee.effect_id,
                ee.effect_order,
                ee.condition_text,
                ee.min_value,
                ee.max_value,
                ee.raw_text,
                e.name AS enchant_name,
                f.name AS effect_name
            FROM enchant_effects ee
            JOIN enchants e ON e.id = ee.enchant_id
            LEFT JOIN effects f ON f.id = ee.effect_id
            ORDER BY ee.id
            LIMIT :limit OFFSET :offset
            """
        ),
        {"limit": limit, "offset": offset},
    ).mappings()
    return [dict(r) for r in rows]

def get_enchant_effects_by_id(db: Session, enchant_id: int):
    rows = db.execute(
        text(
            """
            SELECT
                ee.id,
                ee.enchant_id,
                ee.effect_id,
                ee.effect_order,
                ee.condition_text,
                ee.min_value,
                ee.max_value,
                ee.raw_text,
                f.name AS effect_name
            FROM enchant_effects ee
            LEFT JOIN effects f ON f.id = ee.effect_id
            WHERE ee.enchant_id = :enchant_id
            ORDER BY ee.effect_order
            """
        ),
        {"enchant_id": enchant_id},
    ).mappings()
    return [dict(r) for r in rows]

def get_reforge_options(db: Session, limit: int = 100, offset: int = 0):
    return db.query(models.ReforgeOption).order_by(models.ReforgeOption.id).limit(limit).offset(offset).all()

def get_listings(db: Session, limit: int = 100, offset: int = 0):
    rows = db.execute(
        text(
            """
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
                l.created_at,
                COUNT(DISTINCT lro.id) AS reforge_count
            FROM listings l
            LEFT JOIN game_items gi ON gi.id = l.game_item_id
            LEFT JOIN enchants pe ON pe.id = l.prefix_enchant_id
            LEFT JOIN enchants se ON se.id = l.suffix_enchant_id
            LEFT JOIN listing_reforge_options lro ON lro.listing_id = l.id
            GROUP BY l.id, gi.name, pe.name, se.name
            ORDER BY l.id DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"limit": limit, "offset": offset},
    ).mappings()
    return [dict(r) for r in rows]

def get_listing_count(db: Session):
    return db.query(models.Listing).count()

def _build_enchant_detail(db: Session, listing_id: int, enchant_id: int, slot: int):
    """Build enchant detail dict with all effects for a single enchant slot.

    LEFT JOINs listing_enchant_effects so fixed effects (no rolled value)
    also appear. Returns min_value/max_value from enchant_effects for display.
    """
    enc = db.query(models.Enchant).filter(models.Enchant.id == enchant_id).first()
    if not enc:
        return None
    effect_rows = db.execute(
        text(
            """
            SELECT ee.raw_text, ee.min_value, ee.max_value, lee.value
            FROM enchant_effects ee
            LEFT JOIN listing_enchant_effects lee
              ON lee.enchant_effect_id = ee.id
              AND lee.listing_id = :listing_id
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
    listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
    if not listing:
        return None

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

    # Reforge options
    reforge_rows = db.execute(
        text(
            """
            SELECT option_name, level, max_level
            FROM listing_reforge_options
            WHERE listing_id = :listing_id
            ORDER BY id
            """
        ),
        {"listing_id": listing_id},
    ).mappings()

    return {
        "id": listing.id,
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
        "reforge_options": [dict(r) for r in reforge_rows],
        "tags": resolve_listing_tags(db, listing_id),
    }

def get_game_items(db: Session, q: Optional[str] = None, limit: int = 20, offset: int = 0):
    if q:
        rows = db.execute(
            text(
                """
                SELECT id, name
                FROM game_items
                WHERE name ILIKE :q
                ORDER BY name
                LIMIT :limit OFFSET :offset
                """
            ),
            {"q": f"%{q}%", "limit": limit, "offset": offset},
        ).mappings()
    else:
        rows = db.execute(
            text(
                """
                SELECT id, name
                FROM game_items
                ORDER BY name
                LIMIT :limit OFFSET :offset
                """
            ),
            {"limit": limit, "offset": offset},
        ).mappings()
    return [dict(r) for r in rows]

def get_game_item_count(db: Session):
    return db.query(models.GameItem).count()


# --- Tags (normalized: tags + tag_targets) ---

def _get_or_create_tag(db: Session, name: str, weight: int = 0):
    """Get existing tag by name or create a new one. Returns Tag model instance."""
    tag = db.query(models.Tag).filter(models.Tag.name == name).first()
    if tag:
        return tag
    tag = models.Tag(name=name, weight=weight)
    db.add(tag)
    db.flush()
    return tag


def get_tags(db: Session, target_type: Optional[str] = None, limit: int = 100, offset: int = 0):
    where = "WHERE tt.target_type = :target_type" if target_type else ""
    params = {"limit": limit, "offset": offset}
    if target_type:
        params["target_type"] = target_type
    rows = db.execute(
        text(f"""
            SELECT
                tt.id,
                t.id AS tag_id,
                tt.target_type,
                tt.target_id,
                t.name,
                t.weight,
                CASE tt.target_type
                    WHEN 'reforge_option' THEN (SELECT ro.option_name FROM reforge_options ro WHERE ro.id = tt.target_id)
                    WHEN 'game_item'      THEN (SELECT gi.name FROM game_items gi WHERE gi.id = tt.target_id)
                    WHEN 'listing'        THEN (SELECT l.name FROM listings l WHERE l.id = tt.target_id)
                    WHEN 'enchant'        THEN (SELECT e.name FROM enchants e WHERE e.id = tt.target_id)
                END AS target_display_name
            FROM tag_targets tt
            JOIN tags t ON t.id = tt.tag_id
            {where}
            ORDER BY tt.id DESC
            LIMIT :limit OFFSET :offset
        """),
        params,
    ).mappings()
    return [dict(r) for r in rows]


def create_tag(db: Session, data: schemas.TagCreate):
    """Get-or-create tag definition (weight on tags table), then attach to the target."""
    tag = _get_or_create_tag(db, data.name, data.weight)
    tt = models.TagTarget(
        tag_id=tag.id,
        target_type=data.target_type,
        target_id=data.target_id,
    )
    db.add(tt)
    try:
        db.commit()
        db.refresh(tt)
    except IntegrityError:
        db.rollback()
        return None
    return tt


def delete_tag(db: Session, tag_target_id: int):
    """Delete a tag-target association. If tag has no remaining targets, delete the tag too."""
    tt = db.query(models.TagTarget).filter(models.TagTarget.id == tag_target_id).first()
    if not tt:
        return False
    tag_id = tt.tag_id
    db.delete(tt)
    db.flush()
    # Clean up orphaned tag definition
    remaining = db.query(models.TagTarget).filter(models.TagTarget.tag_id == tag_id).count()
    if remaining == 0:
        tag = db.query(models.Tag).filter(models.Tag.id == tag_id).first()
        if tag:
            db.delete(tag)
    db.commit()
    return True


def search_entities(db: Session, target_type: str, q: str, limit: int = 20, like: bool = True):
    if target_type == 'reforge_option':
        tbl, col = 'reforge_options', 'option_name'
    elif target_type == 'game_item':
        tbl, col = 'game_items', 'name'
    elif target_type == 'listing':
        tbl, col = 'listings', 'name'
    elif target_type == 'enchant':
        tbl, col = 'enchants', 'name'
    else:
        return []
    q_param = f"%{q}%" if like else q
    rows = db.execute(
        text(f"""
            SELECT id, {col} AS name
            FROM {tbl}
            WHERE {col} ILIKE :q
            ORDER BY {col}
            LIMIT :limit
        """),
        {"q": q_param, "limit": limit},
    ).mappings()
    return [dict(r) for r in rows]


_TAG_POSITION_WEIGHTS = [80, 60, 30]


def bulk_create_tags(db: Session, data: schemas.BulkTagCreate):
    created = 0
    duplicates = 0
    seen = set()
    explicit_weight = data.weight
    for i, name in enumerate(data.names):
        if name in seen:
            continue
        seen.add(name)
        existing = db.query(models.Tag).filter(models.Tag.name == name).first()
        if explicit_weight is not None:
            tag = existing or models.Tag(name=name, weight=explicit_weight)
            if not existing:
                db.add(tag)
                db.flush()
            weight = explicit_weight
        else:
            pos_weight = _TAG_POSITION_WEIGHTS[i] if i < len(_TAG_POSITION_WEIGHTS) else 0
            if existing:
                tag = existing
                weight = max(0, pos_weight - tag.weight)
            else:
                tag = models.Tag(name=name, weight=0)
                db.add(tag)
                db.flush()
                weight = pos_weight
        if not data.targets:
            if not existing:
                created += 1
            else:
                duplicates += 1
            continue
        for target in data.targets:
            sp = db.begin_nested()
            tt = models.TagTarget(
                tag_id=tag.id,
                target_type=target.target_type,
                target_id=target.target_id,
                weight=weight,
            )
            db.add(tt)
            try:
                sp.commit()
                created += 1
            except IntegrityError:
                sp.rollback()
                duplicates += 1
    db.commit()
    return {"created": created, "duplicates": duplicates}


def get_unique_tags(db: Session, limit: int = 100, offset: int = 0):
    rows = db.execute(
        text("""
            SELECT t.id, t.name, t.weight, COUNT(tt.id) AS target_count
            FROM tags t
            LEFT JOIN tag_targets tt ON tt.tag_id = t.id
            GROUP BY t.id
            ORDER BY t.id DESC
            LIMIT :limit OFFSET :offset
        """),
        {"limit": limit, "offset": offset},
    ).mappings()
    return [dict(r) for r in rows]


def delete_tag_by_id(db: Session, tag_id: int):
    """Delete a tag and all its tag_targets (via CASCADE)."""
    tag = db.query(models.Tag).filter(models.Tag.id == tag_id).first()
    if not tag:
        return False
    db.delete(tag)
    db.commit()
    return True


def resolve_listing_tags(db: Session, listing_id: int):
    rows = db.execute(
        text("""
            SELECT DISTINCT t.name, (t.weight + tt.weight) AS weight
            FROM (
                SELECT 'listing' AS ttype, :lid AS tid
                UNION ALL
                SELECT 'game_item', l.game_item_id FROM listings l WHERE l.id = :lid AND l.game_item_id IS NOT NULL
                UNION ALL
                SELECT 'reforge_option', lro.reforge_option_id FROM listing_reforge_options lro WHERE lro.listing_id = :lid AND lro.reforge_option_id IS NOT NULL
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


def get_tag_detail(db: Session, tag_id: int):
    tag = db.query(models.Tag).filter(models.Tag.id == tag_id).first()
    if not tag:
        return None
    rows = db.execute(
        text("""
            SELECT
                tt.id,
                tt.target_type,
                tt.target_id,
                tt.weight,
                CASE tt.target_type
                    WHEN 'reforge_option' THEN (SELECT ro.option_name FROM reforge_options ro WHERE ro.id = tt.target_id)
                    WHEN 'game_item'      THEN (SELECT gi.name FROM game_items gi WHERE gi.id = tt.target_id)
                    WHEN 'listing'        THEN (SELECT l.name FROM listings l WHERE l.id = tt.target_id)
                    WHEN 'enchant'        THEN (SELECT e.name FROM enchants e WHERE e.id = tt.target_id)
                END AS target_display_name
            FROM tag_targets tt
            WHERE tt.tag_id = :tag_id
            ORDER BY tt.id
        """),
        {"tag_id": tag_id},
    ).mappings()
    return {
        "id": tag.id,
        "name": tag.name,
        "weight": tag.weight,
        "targets": [dict(r) for r in rows],
    }


def update_tag_weight(db: Session, tag_id: int, weight: int):
    tag = db.query(models.Tag).filter(models.Tag.id == tag_id).first()
    if not tag:
        return False
    tag.weight = weight
    db.commit()
    return True


def update_tag_target_weight(db: Session, tag_target_id: int, weight: int):
    tt = db.query(models.TagTarget).filter(models.TagTarget.id == tag_target_id).first()
    if not tt:
        return False
    tt.weight = weight
    db.commit()
    return True
