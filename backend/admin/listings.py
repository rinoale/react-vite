from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db.connector import get_db
from db import schemas
from crud import admin as crud_admin
from trade.services import get_listing_detail as svc_get_listing_detail

router = APIRouter()


@router.get("/listings", response_model=schemas.PaginatedListingResponse)
def admin_listings(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    rows = crud_admin.get_listings(db, limit=limit, offset=offset)
    return {"limit": limit, "offset": offset, "rows": rows}


@router.get("/listings/{listing_id}/detail", response_model=schemas.ListingDetailOut)
def admin_listing_detail(
    listing_id: UUID,
    db: Session = Depends(get_db),
):
    result = svc_get_listing_detail(db, listing_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    return result


@router.get("/game-items", response_model=schemas.PaginatedGameItemResponse)
def admin_game_items(
    q: str = Query(default=""),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    rows = crud_admin.get_game_items(db, q=q or None, limit=limit, offset=offset)
    return {"limit": limit, "offset": offset, "rows": rows}
