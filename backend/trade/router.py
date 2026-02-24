import json
import logging
import os
import shutil

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List

from db.connector import get_db
from db.models import OcrCorrection
from db.schemas import RegisterItemRequest
from trade.schemas import UploadItemV3Response
from lib.recommendation import recommender, ITEMS_DB
from lib.v3_pipeline import init_pipeline, run_v3_pipeline, prepare_sections_for_response

logger = logging.getLogger('mabinogi')

router = APIRouter()

# Initialize all OCR pipeline components
_pipeline = init_pipeline()

# --- Correction capture constants ---
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CROPS_DIR = os.path.join(_BASE_DIR, '..', 'tmp', 'ocr_crops')
_CORRECTIONS_DIR = os.path.join(_BASE_DIR, '..', 'data', 'corrections')
_MODELS_DIR = os.path.join(_BASE_DIR, 'ocr', 'models')


def _load_charset():
    """Load union of character sets from both font-specific models."""
    chars = set()
    for yaml_prefix in ('custom_mabinogi_classic', 'custom_nanum_gothic_bold'):
        yaml_path = os.path.join(_MODELS_DIR, f'{yaml_prefix}.yaml')
        if not os.path.exists(yaml_path):
            continue
        real_path = os.path.realpath(yaml_path)
        version_dir = os.path.dirname(real_path)
        chars_file = os.path.join(version_dir, 'unique_chars.txt')
        if os.path.exists(chars_file):
            with open(chars_file, 'r', encoding='utf-8') as f:
                chars.update(f.read().strip())
    return chars


_CHARSET = _load_charset()


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


@router.post("/upload-item-v3",
              response_model=UploadItemV3Response,
              response_model_exclude_none=True)
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

        result = run_v3_pipeline(img_bgr, **_pipeline, save_crops=True)

        result['sections'] = prepare_sections_for_response(result['sections'])
        # Strip is_header from all_lines (no longer in OcrLineResponse schema)
        for line in result.get('all_lines', []):
            line.pop('is_header', None)

        return {"filename": file.filename, **result}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("upload-item-v3 failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/register-item")
def register_item(payload: RegisterItemRequest, db: Session = Depends(get_db)):
    """Register an item and implicitly capture any OCR corrections.

    The frontend sends the final line texts along with session_id.
    The server loads the original OCR results from the session dir,
    diffs against the submitted lines, and saves any changes as
    correction training data.
    """
    corrections_saved = 0

    # Capture corrections if we have a session with stored originals
    if payload.session_id and payload.lines:
        session_dir = os.path.join(_CROPS_DIR, payload.session_id)
        results_path = os.path.join(session_dir, 'ocr_results.json')

        if os.path.isfile(results_path):
            with open(results_path, 'r', encoding='utf-8') as f:
                originals = json.load(f)

            # Build lookup: global_index → original line data
            orig_by_idx = {o['global_index']: o for o in originals}

            dest_dir = os.path.join(_CORRECTIONS_DIR, payload.session_id)

            for line in payload.lines:
                orig = orig_by_idx.get(line.global_index)
                if orig is None:
                    continue
                if line.text == orig['text']:
                    continue  # No change

                # Charset gate
                if _CHARSET:
                    bad = set(line.text) - _CHARSET - {' '}
                    if bad:
                        continue

                # Copy crop image
                crop_name = f"{line.global_index:03d}.png"
                src_path = os.path.join(session_dir, crop_name)
                if not os.path.isfile(src_path):
                    continue

                os.makedirs(dest_dir, exist_ok=True)
                shutil.copy2(src_path, os.path.join(dest_dir, crop_name))

                db.add(OcrCorrection(
                    session_id=payload.session_id,
                    line_index=line.global_index,
                    original_text=orig['text'],
                    corrected_text=line.text,
                    confidence=orig.get('confidence'),
                    section=orig.get('section', ''),
                    ocr_model=orig.get('ocr_model', ''),
                    fm_applied=orig.get('fm_applied', False),
                    status='pending',
                    image_filename=crop_name,
                ))
                corrections_saved += 1

            if corrections_saved:
                db.commit()

    # TODO: persist item to DB when item storage is implemented
    return {
        "registered": True,
        "name": payload.name,
        "corrections_saved": corrections_saved,
    }
