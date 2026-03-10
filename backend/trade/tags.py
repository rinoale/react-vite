from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from db.connector import get_db
from trade.services import search_tags as svc_search_tags

router = APIRouter()


@router.get("/tags/search")
def search_tags(q: str = Query(default=""), limit: int = Query(default=10, ge=1, le=50), db: Session = Depends(get_db)):
    if not q.strip():
        return []
    return svc_search_tags(db, q.strip(), limit=limit)
