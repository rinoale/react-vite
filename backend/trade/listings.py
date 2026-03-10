from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db.connector import get_db
from db.models import User
from db.schemas import RegisterListingRequest
from trade.services import capture_corrections, create_listing, create_listing_tags, get_listings as svc_get_listings, search_listings as svc_search_listings, get_listing_detail
from lib.utils.log import logger
from auth.dependencies import get_current_user

router = APIRouter()


@router.get("/listings")
def get_listings(
    game_item_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    return svc_get_listings(db, game_item_id=game_item_id, limit=limit, offset=offset)


@router.get("/listings/search")
def search_listings(
    q: str = Query(default=""),
    tags: list[str] = Query(default=[]),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    if not q.strip() and not tags:
        return svc_get_listings(db, limit=limit, offset=offset)
    return svc_search_listings(db, q.strip() or None, tags=tags or None, limit=limit, offset=offset)


@router.get("/listings/{listing_id}")
def get_listing(listing_id: int, db: Session = Depends(get_db)):
    result = get_listing_detail(db, listing_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    return result


@router.post("/register-listing")
def register_listing(payload: RegisterListingRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Register a listing and implicitly capture any OCR corrections."""
    logger.info(
        "register-listing  session=%s  name=%r  lines=%d",
        payload.session_id, payload.name, len(payload.lines),
    )

    corrections_saved = capture_corrections(payload.session_id, payload.lines, db)
    listing = create_listing(payload, db, user_id=current_user.id)
    create_listing_tags(listing, payload, db)

    return {
        "registered": True,
        "name": payload.name,
        "listing_id": listing.id,
        "corrections_saved": corrections_saved,
    }
