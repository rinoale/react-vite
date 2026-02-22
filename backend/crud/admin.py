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
