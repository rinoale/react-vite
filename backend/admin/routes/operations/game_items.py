from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from db.connector import get_db
from db import schemas
from admin.services.game_item_service import get_game_items

router = APIRouter()


@router.get("/game-items", response_model=schemas.PaginatedGameItemResponse)
def admin_game_items(
    q: str = Query(default=""),
    id: str = Query(default=""),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    rows = get_game_items(q=q or None, id=id or None, limit=limit, offset=offset, db=db)
    return {"limit": limit, "offset": offset, "rows": rows}
