from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from db.connector import get_db
from db.models import User
from pydantic import BaseModel
from trade.schemas.listing import RegisterListingRequest
from trade.services.listing_service import (
    create_listing, get_listings as svc_get_listings, get_my_listings as svc_get_my_listings,
    search_listings as svc_search_listings, get_listing_detail, update_listing_status as svc_update_status,
    parse_attr_filters, parse_reforge_filters, parse_enchant_filters, parse_option_filters,
)
from trade.services.tag_service import create_listing_tags
from trade.services.correction_service import capture_corrections
from trade.services.short_code import encode, decode
from trade.services.activity_service import log_activity
from lib.utils.log import logger
from auth.dependencies import get_current_user, optional_user

class _StatusUpdate(BaseModel):
    status: int

_STATUS_ACTIONS = {0: "listing_drafted", 1: "listing_listed", 2: "listing_sold", 3: "listing_deleted"}

router = APIRouter()


class GetListingsParams:
    def __init__(
        self,
        game_item_id: UUID | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
    ):
        self.game_item_id = game_item_id
        self.limit = limit
        self.offset = offset


@router.get("/listings")
def get_listings(params: GetListingsParams = Depends(), db: Session = Depends(get_db)):
    return svc_get_listings(game_item_id=params.game_item_id, limit=params.limit, offset=params.offset, db=db)


class SearchListingsParams:
    def __init__(
        self,
        q: str = Query(default=""),
        tags: list[str] = Query(default=[]),
        game_item_id: UUID | None = Query(default=None),
        reforge_filters: str | None = Query(default=None),
        enchant_filters: str | None = Query(default=None),
        echostone_filters: str | None = Query(default=None),
        murias_filters: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
    ):
        self.q = q
        self.tags = tags
        self.game_item_id = game_item_id
        self.reforge_filters = reforge_filters
        self.enchant_filters = enchant_filters
        self.echostone_filters = echostone_filters
        self.murias_filters = murias_filters
        self.limit = limit
        self.offset = offset


@router.get("/listings/search")
def search_listings(
    request: Request,
    params: SearchListingsParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(optional_user),
    bg: BackgroundTasks = None,
):
    attr_filters = parse_attr_filters(request.query_params)
    parsed_reforge = parse_reforge_filters(params.reforge_filters)
    parsed_enchant = parse_enchant_filters(params.enchant_filters)
    parsed_echostone = parse_option_filters(params.echostone_filters)
    parsed_murias = parse_option_filters(params.murias_filters)
    if not params.q.strip() and not params.tags and params.game_item_id is None and not attr_filters and not parsed_reforge and not parsed_enchant and not parsed_echostone and not parsed_murias:
        return svc_get_listings(limit=params.limit, offset=params.offset, db=db)
    result = svc_search_listings(
        q=params.q.strip() or None, tags=params.tags or None, game_item_id=params.game_item_id,
        attr_filters=attr_filters, reforge_filters=parsed_reforge, enchant_filters=parsed_enchant,
        echostone_filters=parsed_echostone, murias_filters=parsed_murias,
        limit=params.limit, offset=params.offset, db=db,
    )
    bg.add_task(log_activity, action="search", user_id=current_user.id if current_user else None,
                target_type="search_query", metadata={"query": params.q.strip(), "tags": params.tags, "game_item_id": params.game_item_id, "results": len(result) if isinstance(result, list) else 0})
    return result


class MyListingsParams:
    def __init__(
        self,
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
    ):
        self.limit = limit
        self.offset = offset


@router.get("/listings/mine")
def get_my_listings(
    params: MyListingsParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return svc_get_my_listings(user_id=current_user.id, limit=params.limit, offset=params.offset, db=db)


@router.patch("/listings/{listing_id}/status")
def update_status(
    listing_id: UUID,
    body: _StatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    bg: BackgroundTasks = None,
):
    result = svc_update_status(listing_id=listing_id, status=body.status, user_id=current_user.id, db=db)
    bg.add_task(log_activity, action=_STATUS_ACTIONS.get(body.status, "listing_status_changed"),
                user_id=current_user.id, target_type="listing", target_id=listing_id,
                metadata={"new_status": body.status})
    return result


@router.get("/listings/s/{code}")
def get_listing_by_code(code: str, db: Session = Depends(get_db), current_user: User | None = Depends(optional_user),
                        bg: BackgroundTasks = None):
    listing_id = decode(code)
    if listing_id is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    result = get_listing_detail(listing_id=listing_id, db=db)
    if result is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    result["short_code"] = code
    bg.add_task(log_activity, action="listing_viewed", user_id=current_user.id if current_user else None,
                target_type="listing", target_id=listing_id)
    return result


@router.get("/listings/{listing_id}")
def get_listing(listing_id: UUID, db: Session = Depends(get_db), current_user: User | None = Depends(optional_user),
                bg: BackgroundTasks = None):
    result = get_listing_detail(listing_id=listing_id, db=db)
    if result is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    result["short_code"] = encode(listing_id)
    bg.add_task(log_activity, action="listing_viewed", user_id=current_user.id if current_user else None,
                target_type="listing", target_id=listing_id)
    return result


@router.post("/register-listing")
def register_listing(payload: RegisterListingRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
                     bg: BackgroundTasks = None):
    """Register a listing and implicitly capture any OCR corrections."""
    logger.info(
        "register-listing  session=%s  name=%r  lines=%d",
        payload.session_id, payload.name, len(payload.lines),
    )

    corrections_saved = capture_corrections(session_id=payload.session_id, lines=payload.lines, db=db)
    listing = create_listing(payload=payload, user_id=current_user.id, db=db)

    bg.add_task(create_listing_tags, listing_id=listing.id, tags=payload.tags, payload=payload)
    bg.add_task(log_activity, action="listing_created", user_id=current_user.id,
                target_type="listing", target_id=listing.id,
                metadata={"game_item_id": payload.game_item_id})

    return {
        "registered": True,
        "name": payload.name,
        "listing_id": listing.id,
        "short_code": encode(listing.id),
        "corrections_saved": corrections_saved,
    }
