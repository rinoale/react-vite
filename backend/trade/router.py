from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from sqlalchemy.orm import Session

from db.connector import get_db
from db.schemas import RegisterListingRequest
from trade.schemas import ExamineItemResponse
from trade.service import capture_corrections, create_listing, create_listing_tags, get_listings as svc_get_listings, search_game_items as svc_search_game_items, search_listings as svc_search_listings, search_tags as svc_search_tags
from lib.utils.log import logger
from lib.pipeline.v3 import init_pipeline, run_v3_pipeline, prepare_sections_for_response
from crud.admin import get_listing_detail

router = APIRouter()

# Initialize pipeline singleton (loaded once at import time)
init_pipeline()


@router.get("/listings")
def get_listings(game_item_id: int | None = Query(default=None), db: Session = Depends(get_db)):
    return svc_get_listings(db, game_item_id=game_item_id)


@router.get("/listings/search")
def search_listings(
    q: str = Query(default=""),
    tags: list[str] = Query(default=[]),
    db: Session = Depends(get_db),
):
    if not q.strip() and not tags:
        return svc_get_listings(db)
    return svc_search_listings(db, q.strip() or None, tags=tags or None)


@router.get("/tags/search")
def search_tags(q: str = Query(default=""), limit: int = Query(default=10, ge=1, le=50), db: Session = Depends(get_db)):
    if not q.strip():
        return []
    return svc_search_tags(db, q.strip(), limit=limit)


@router.get("/listings/{listing_id}")
def get_listing(listing_id: int, db: Session = Depends(get_db)):
    result = get_listing_detail(db, listing_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    return result


@router.get("/game-items")
def search_game_items(q: str = Query(default=""), limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db)):
    if not q.strip():
        return []
    return svc_search_game_items(db, q.strip(), limit=limit)


@router.post("/examine-item",
              response_model=ExamineItemResponse,
              response_model_exclude_none=True)
async def examine_item(file: UploadFile = File(...)):
    """Segment-first OCR pipeline.

    Accepts the original color screenshot (not preprocessed).
    """
    try:
        import cv2
        import numpy as np

        raw = await file.read()
        arr = np.frombuffer(raw, np.uint8)
        img_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img_bgr is None:
            raise HTTPException(status_code=400, detail="Could not decode image")

        h, w = img_bgr.shape[:2]
        logger.info("examine-item  file=%s  size=%dx%d", file.filename, w, h)

        result = run_v3_pipeline(img_bgr, save_crops=True)

        sections = result.get('sections', {})
        session_id = result.get('session_id', '')

        logger.info(
            "examine-item  session=%s  sections=%s",
            session_id,
            list(sections.keys()),
        )

        response = {
            "filename": file.filename,
            "sections": prepare_sections_for_response(sections),
            "abbreviated": result.get('abbreviated', True),
        }
        if session_id:
            response["session_id"] = session_id
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("examine-item failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/register-listing")
def register_listing(payload: RegisterListingRequest, db: Session = Depends(get_db)):
    """Register a listing and implicitly capture any OCR corrections."""
    logger.info(
        "register-listing  session=%s  name=%r  lines=%d",
        payload.session_id, payload.name, len(payload.lines),
    )

    corrections_saved = capture_corrections(payload.session_id, payload.lines, db)
    listing = create_listing(payload, db)
    create_listing_tags(listing, payload, db)

    return {
        "registered": True,
        "name": payload.name,
        "listing_id": listing.id,
        "corrections_saved": corrections_saved,
    }
