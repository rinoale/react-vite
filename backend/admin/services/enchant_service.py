from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from db import models


def get_enchants(*, q: Optional[str] = None, id: Optional[str] = None, limit: int = 100, offset: int = 0, db: Session):
    where = ""
    params = {"limit": limit, "offset": offset}
    if id:
        where = "WHERE e.id = :id"
        params["id"] = id
    elif q:
        where = "WHERE e.name ILIKE :q"
        params["q"] = f"%{q}%"
    rows = db.execute(
        text(f"""
            SELECT e.id, e.slot, e.name, e.rank, e.header_text,
                   COUNT(ee.id) AS effect_count
            FROM enchants e
            LEFT JOIN enchant_effects ee ON ee.enchant_id = e.id
            {where}
            GROUP BY e.id
            ORDER BY e.id
            LIMIT :limit OFFSET :offset
        """),
        params,
    ).mappings()
    return [dict(r) for r in rows]


def get_effects(*, limit: int = 100, offset: int = 0, db: Session):
    return db.query(models.Effect).order_by(models.Effect.id).limit(limit).offset(offset).all()


def get_enchant_effects(*, limit: int = 100, offset: int = 0, db: Session):
    rows = db.execute(
        text(
            """
            SELECT
                ee.id, ee.enchant_id, ee.effect_id, ee.effect_order,
                ee.condition_text, ee.min_value, ee.max_value, ee.raw_text,
                e.name AS enchant_name, f.name AS effect_name
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


def get_enchant_effects_by_id(*, enchant_id, db: Session):
    rows = db.execute(
        text(
            """
            SELECT
                ee.id, ee.enchant_id, ee.effect_id, ee.effect_order,
                ee.condition_text, ee.min_value, ee.max_value, ee.raw_text,
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
