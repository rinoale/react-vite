from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from db import models


def get_game_items(*, q: Optional[str] = None, id: Optional[str] = None, limit: int = 20, offset: int = 0, db: Session):
    if id:
        rows = db.execute(
            text("SELECT id, name, type, searchable, tradable FROM game_items WHERE id = :id"),
            {"id": id},
        ).mappings()
    elif q:
        rows = db.execute(
            text("""
                SELECT id, name, type, searchable, tradable
                FROM game_items
                WHERE name ILIKE :q
                ORDER BY name
                LIMIT :limit OFFSET :offset
            """),
            {"q": f"%{q}%", "limit": limit, "offset": offset},
        ).mappings()
    else:
        rows = db.execute(
            text("""
                SELECT id, name, type, searchable, tradable
                FROM game_items
                ORDER BY name
                LIMIT :limit OFFSET :offset
            """),
            {"limit": limit, "offset": offset},
        ).mappings()
    return [dict(r) for r in rows]


def get_game_item_count(*, db: Session):
    return db.query(models.GameItem).count()
