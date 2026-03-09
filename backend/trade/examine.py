from fastapi import APIRouter, File, HTTPException, UploadFile

from trade.schemas import ExamineItemResponse
from lib.utils.log import logger
from lib.pipeline.v3 import init_pipeline, run_v3_pipeline, prepare_sections_for_response

router = APIRouter()

# Initialize pipeline singleton (loaded once at import time)
init_pipeline()


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
