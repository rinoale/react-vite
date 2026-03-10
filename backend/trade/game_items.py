from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from db.connector import get_db
from trade.services import search_game_items as svc_search_game_items

router = APIRouter()


@router.get("/game-items")
def search_game_items(q: str = Query(default=""), limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db)):
    if not q.strip():
        return []
    return svc_search_game_items(db, q.strip(), limit=limit)
