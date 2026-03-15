from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from db.connector import get_db
from trade.services.listing_service import search_game_items as svc_search_game_items

router = APIRouter()


class SearchGameItemsParams:
    def __init__(self, q: str = Query(default=""), limit: int = Query(default=20, ge=1, le=100)):
        self.q = q
        self.limit = limit


@router.get("/game-items")
def search_game_items(params: SearchGameItemsParams = Depends(), db: Session = Depends(get_db)):
    if not params.q.strip():
        return []
    return svc_search_game_items(q=params.q.strip(), limit=params.limit, db=db)
