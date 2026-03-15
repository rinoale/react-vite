from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from db.connector import get_db
from admin.schemas.data import PaginatedGameItemResponse
from admin.services.game_item_service import get_game_items

router = APIRouter()


class AdminGameItemsParams:
    def __init__(
        self,
        q: str = Query(default=""),
        id: str = Query(default=""),
        limit: int = Query(default=100, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
    ):
        self.q = q
        self.id = id
        self.limit = limit
        self.offset = offset


@router.get("/game-items", response_model=PaginatedGameItemResponse)
def admin_game_items(params: AdminGameItemsParams = Depends(), db: Session = Depends(get_db)):
    rows = get_game_items(q=params.q or None, id=params.id or None, limit=params.limit, offset=params.offset, db=db)
    return {"limit": params.limit, "offset": params.offset, "rows": rows}
