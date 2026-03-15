from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from db import models


def get_listings(*, q: Optional[str] = None, id: Optional[str] = None, limit: int = 100, offset: int = 0, db: Session):
    where = ""
    params = {"limit": limit, "offset": offset}
    if id:
        where = "WHERE l.id = :id"
        params["id"] = id
    elif q:
        where = "WHERE l.name ILIKE :q"
        params["q"] = f"%{q}%"
    rows = db.execute(
        text(f"""
            SELECT
                l.id, l.status, l.name, l.description, l.price, l.game_item_id,
                gi.name AS game_item_name,
                pe.name AS prefix_enchant_name,
                se.name AS suffix_enchant_name,
                l.item_type, l.item_grade, l.erg_grade, l.erg_level, l.created_at,
                COUNT(DISTINCT lo.id) AS option_count
            FROM listings l
            LEFT JOIN game_items gi ON gi.id = l.game_item_id
            LEFT JOIN enchants pe ON pe.id = l.prefix_enchant_id
            LEFT JOIN enchants se ON se.id = l.suffix_enchant_id
            LEFT JOIN listing_options lo ON lo.listing_id = l.id
            {where}
            GROUP BY l.id, gi.name, pe.name, se.name
            ORDER BY l.id DESC
            LIMIT :limit OFFSET :offset
        """),
        params,
    ).mappings()
    return [dict(r) for r in rows]


def get_listing_count(*, db: Session):
    return db.query(models.Listing).count()
