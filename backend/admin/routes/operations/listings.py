from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db.connector import get_db
from trade.schemas.listing import PaginatedListingResponse, ListingDetailOut
from admin.services.listing_service import get_listings
from trade.services.listing_service import get_listing_detail as svc_get_listing_detail

router = APIRouter()


@router.get("/listings", response_model=PaginatedListingResponse)
def admin_listings(
    q: str = Query(default=""),
    id: str = Query(default=""),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    rows = get_listings(q=q or None, id=id or None, limit=limit, offset=offset, db=db)
    return {"limit": limit, "offset": offset, "rows": rows}


@router.get("/listings/{listing_id}/detail", response_model=ListingDetailOut)
def admin_listing_detail(
    listing_id: UUID,
    db: Session = Depends(get_db),
):
    result = svc_get_listing_detail(listing_id=listing_id, db=db)
    if result is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    return result
