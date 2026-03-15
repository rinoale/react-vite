from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from db.connector import get_db
from trade.services.listing_service import search_tags as svc_search_tags

router = APIRouter()


class SearchTagsParams:
    def __init__(self, q: str = Query(default=""), limit: int = Query(default=10, ge=1, le=50)):
        self.q = q
        self.limit = limit


@router.get("/tags/search")
def search_tags(params: SearchTagsParams = Depends(), db: Session = Depends(get_db)):
    if not params.q.strip():
        return []
    return svc_search_tags(q=params.q.strip(), limit=params.limit, db=db)
