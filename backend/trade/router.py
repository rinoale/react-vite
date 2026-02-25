import json
import os
import shutil

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List

from db.connector import get_db
from db.models import OcrCorrection, Item, ItemEnchant, ItemEnchantEffect, ItemReforgeOption, Enchant, EnchantEffect, ReforgeOption
from db.schemas import RegisterItemRequest
from trade.schemas import UploadItemV3Response
from lib.log import logger
from lib.recommendation import recommender, ITEMS_DB
from lib.v3_pipeline import init_pipeline, run_v3_pipeline, prepare_sections_for_response

router = APIRouter()

# Initialize all OCR pipeline components
_pipeline = init_pipeline()

# --- Correction capture constants ---
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CROPS_DIR = os.path.join(_BASE_DIR, '..', 'tmp', 'ocr_crops')
_CORRECTIONS_DIR = os.path.join(_BASE_DIR, '..', 'data', 'corrections')
_MODELS_DIR = os.path.join(_BASE_DIR, 'ocr', 'models')


def _load_charsets():
    """Load per-model charsets for mismatch detection."""
    charsets = {}
    # Content models
    for yaml_prefix in ('custom_mabinogi_classic', 'custom_nanum_gothic_bold'):
        yaml_path = os.path.join(_MODELS_DIR, f'{yaml_prefix}.yaml')
        if not os.path.exists(yaml_path):
            continue
        real_path = os.path.realpath(yaml_path)
        version_dir = os.path.dirname(real_path)
        chars_file = os.path.join(version_dir, 'unique_chars.txt')
        if os.path.exists(chars_file):
            with open(chars_file, 'r', encoding='utf-8') as f:
                charsets[yaml_prefix] = set(f.read().strip())
    # Enchant header model
    enchant_hdr_dir = os.path.join(_MODELS_DIR, 'custom_enchant_header.yaml')
    if os.path.exists(enchant_hdr_dir):
        real_path = os.path.realpath(enchant_hdr_dir)
        version_dir = os.path.dirname(real_path)
        for fname in ('enchant_header_chars.txt', 'unique_chars.txt'):
            chars_file = os.path.join(version_dir, fname)
            if os.path.exists(chars_file):
                with open(chars_file, 'r', encoding='utf-8') as f:
                    charsets['enchant_header'] = set(f.read().strip())
                break
    return charsets


_CHARSETS = _load_charsets()
# Union of all model charsets — used only for logging, not gating
_ALL_CHARS = set().union(*_CHARSETS.values()) if _CHARSETS else set()


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

        h, w = img_bgr.shape[:2]
        logger.info("upload-item-v3  file=%s  size=%dx%d", file.filename, w, h)

        result = run_v3_pipeline(img_bgr, **_pipeline, save_crops=True)

        all_lines = result.get('all_lines', [])
        sections = result.get('sections', {})
        session_id = result.get('session_id', '')
        n_crops = sum(1 for l in all_lines if '_crop' not in l)  # crops already popped by pipeline

        logger.info(
            "upload-item-v3  session=%s  sections=%s  lines=%d  crops=%d",
            session_id,
            list(sections.keys()),
            len(all_lines),
            n_crops,
        )

        result['sections'] = prepare_sections_for_response(sections)
        # Strip is_header from all_lines (no longer in OcrLineResponse schema)
        for line in all_lines:
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
    logger.info(
        "register-item  session=%s  name=%r  lines=%d",
        payload.session_id, payload.name, len(payload.lines),
    )
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

                # Check charset mismatch against the model that produced this line
                charset_mismatch = None
                if _CHARSETS:
                    ocr_model = orig.get('ocr_model', '')
                    # Pick the right charset for this line's model
                    if ocr_model == 'enchant_header':
                        model_charset = _CHARSETS.get('enchant_header')
                    else:
                        # Content models — check union of both
                        model_charset = _CHARSETS.get('custom_mabinogi_classic', set()) | _CHARSETS.get('custom_nanum_gothic_bold', set())
                    if model_charset:
                        bad = set(line.text) - model_charset - {' '}
                        if bad:
                            charset_mismatch = ''.join(sorted(bad))

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
                    charset_mismatch=charset_mismatch,
                    image_filename=crop_name,
                ))
                corrections_saved += 1

            if corrections_saved:
                try:
                    db.commit()
                    logger.info("register-item  saved %d correction(s)", corrections_saved)
                except Exception:
                    db.rollback()
                    logger.exception("register-item  DB commit failed for %d correction(s)", corrections_saved)
                    corrections_saved = 0

    # Persist item + join rows in a single transaction
    item = Item(name=payload.name)
    db.add(item)
    try:
        db.flush()  # get item.id for FK references

        # --- Enchants ---
        for enc in payload.enchants:
            enchant_row = db.query(Enchant).filter(
                Enchant.name == enc.name,
                Enchant.slot == enc.slot,
            ).first()
            if not enchant_row:
                logger.warning("register-item  enchant not found: name=%r slot=%d", enc.name, enc.slot)
                continue

            db.add(ItemEnchant(item_id=item.id, enchant_id=enchant_row.id, slot=enc.slot))

            for idx, eff in enumerate(enc.effects):
                if eff.option_level is None:
                    continue
                ee_row = db.query(EnchantEffect).filter(
                    EnchantEffect.enchant_id == enchant_row.id,
                    EnchantEffect.effect_order == idx,
                ).first()
                if ee_row:
                    db.add(ItemEnchantEffect(
                        item_id=item.id,
                        enchant_effect_id=ee_row.id,
                        value=eff.option_level,
                    ))

        # --- Reforge options ---
        for opt in payload.reforge_options:
            reforge_row = db.query(ReforgeOption).filter(
                ReforgeOption.option_name == opt.name,
            ).first()
            db.add(ItemReforgeOption(
                item_id=item.id,
                reforge_option_id=reforge_row.id if reforge_row else None,
                option_name=opt.name,
                level=opt.level,
                max_level=opt.max_level,
            ))

        db.commit()
        db.refresh(item)
        logger.info("register-item  persisted item id=%d name=%r enchants=%d reforges=%d",
                     item.id, item.name, len(payload.enchants), len(payload.reforge_options))
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("register-item  item persist failed")
        raise HTTPException(status_code=500, detail="Failed to persist item")

    return {
        "registered": True,
        "name": payload.name,
        "item_id": item.id,
        "corrections_saved": corrections_saved,
    }
