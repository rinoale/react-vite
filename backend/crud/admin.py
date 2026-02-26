from typing import List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from db import models, schemas

def get_summary(db: Session):
    return {
        "enchants": db.query(models.Enchant).count(),
        "effects": db.query(models.Effect).count(),
        "enchant_effects": db.query(models.EnchantEffect).count(),
        "reforge_options": db.query(models.ReforgeOption).count(),
        "listings": db.query(models.Listing).count(),
        "game_items": db.query(models.GameItem).count(),
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
        "price": listing.price,
        "game_item_id": listing.game_item_id,
        "game_item_name": game_item_name,
        "item_type": listing.item_type,
        "item_grade": listing.item_grade,
        "erg_grade": listing.erg_grade,
        "erg_level": listing.erg_level,
        "prefix_enchant": prefix_enchant,
        "suffix_enchant": suffix_enchant,
        "reforge_options": [dict(r) for r in reforge_rows],
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
