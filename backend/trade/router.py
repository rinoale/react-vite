import logging

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import List

from lib.recommendation import recommender, ITEMS_DB
from lib.v3_pipeline import init_pipeline, run_v3_pipeline

logger = logging.getLogger('mabinogi')

router = APIRouter()

# Initialize all OCR pipeline components
_pipeline = init_pipeline()


class UserHistory(BaseModel):
    history_ids: List[int]


@router.get("/items")
def get_items():
    return ITEMS_DB


@router.get("/recommend/item/{item_id}")
def recommend_by_item(item_id: int):
    results = recommender.get_recommendations(item_id)
    return results


@router.post("/recommend/user")
def recommend_for_user(user_history: UserHistory):
    results = recommender.recommend_for_user(user_history.history_ids)
    return results


@router.post("/upload-item-v3")
async def upload_item_v3(file: UploadFile = File(...)):
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

        result = run_v3_pipeline(img_bgr, **_pipeline)

        return {
            "filename": file.filename,
            "sections": result['sections'],
            "all_lines": result['all_lines'],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("upload-item-v3 failed")
        raise HTTPException(status_code=500, detail=str(e))
