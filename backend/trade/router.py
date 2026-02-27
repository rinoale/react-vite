import json
import os
import shutil

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from sqlalchemy.orm import Session

from sqlalchemy import text

from db.connector import get_db
from db.models import OcrCorrection, Listing, ListingEnchantEffect, ListingReforgeOption, Enchant, EnchantEffect, ReforgeOption, GameItem
from db.schemas import RegisterListingRequest
from trade.schemas import ExamineItemResponse
from lib.log import logger
from lib.v3_pipeline import init_pipeline, run_v3_pipeline, prepare_sections_for_response
from crud.admin import get_listing_detail

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


@router.get("/listings")
def get_listings(game_item_id: int | None = Query(default=None), db: Session = Depends(get_db)):
    base_sql = """
        SELECT
            l.id,
            l.name,
            l.price,
            l.game_item_id,
            gi.name AS game_item_name,
            pe.name AS prefix_enchant_name,
            se.name AS suffix_enchant_name,
            l.item_type,
            l.item_grade,
            l.erg_grade,
            l.erg_level,
            l.created_at,
            COUNT(DISTINCT lro.id) AS reforge_count
        FROM listings l
        LEFT JOIN game_items gi ON gi.id = l.game_item_id
        LEFT JOIN enchants pe ON pe.id = l.prefix_enchant_id
        LEFT JOIN enchants se ON se.id = l.suffix_enchant_id
        LEFT JOIN listing_reforge_options lro ON lro.listing_id = l.id
    """
    if game_item_id is not None:
        rows = db.execute(
            text(base_sql + """
                WHERE l.game_item_id = :game_item_id
                GROUP BY l.id, gi.name, pe.name, se.name
                ORDER BY l.id DESC
            """),
            {"game_item_id": game_item_id},
        ).mappings()
    else:
        rows = db.execute(
            text(base_sql + """
                GROUP BY l.id, gi.name, pe.name, se.name
                ORDER BY l.id DESC
            """)
        ).mappings()
    return [dict(r) for r in rows]


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
    rows = db.execute(
        text(
            """
            SELECT id, name
            FROM game_items
            WHERE name ILIKE :q
            ORDER BY name
            LIMIT :limit
            """
        ),
        {"q": f"%{q.strip()}%", "limit": limit},
    ).mappings()
    return [dict(r) for r in rows]


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

        result = run_v3_pipeline(img_bgr, **_pipeline, save_crops=True)

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
    """Register a listing and implicitly capture any OCR corrections.

    The frontend sends the final line texts along with session_id.
    The server loads the original OCR results from the session dir,
    diffs against the submitted lines, and saves any changes as
    correction training data.
    """
    logger.info(
        "register-listing  session=%s  name=%r  lines=%d",
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
                    original_text=orig.get('raw_text', orig['text']),
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
                    logger.info("register-listing  saved %d correction(s)", corrections_saved)
                except Exception:
                    db.rollback()
                    logger.exception("register-listing  DB commit failed for %d correction(s)", corrections_saved)
                    corrections_saved = 0

    # Resolve game_item FK: use explicit ID if provided, else match by name
    game_item_id = payload.game_item_id
    if not game_item_id and payload.name:
        gi = db.query(GameItem).filter(GameItem.name == payload.name).first()
        if gi:
            game_item_id = gi.id

    # Resolve enchant FKs
    prefix_enchant_id = None
    suffix_enchant_id = None
    enchant_rows_by_slot = {}
    for enc in payload.enchants:
        enchant_row = db.query(Enchant).filter(
            Enchant.name == enc.name,
            Enchant.slot == enc.slot,
        ).first()
        if not enchant_row:
            logger.warning("register-listing  enchant not found: name=%r slot=%d", enc.name, enc.slot)
            continue
        enchant_rows_by_slot[enc.slot] = (enchant_row, enc)
        if enc.slot == 0:
            prefix_enchant_id = enchant_row.id
        elif enc.slot == 1:
            suffix_enchant_id = enchant_row.id

    # Persist listing + join rows in a single transaction
    # Parse price string to integer (frontend sends comma-stripped digits)
    price_int = None
    if payload.price:
        try:
            price_int = int(payload.price)
        except ValueError:
            pass

    listing = Listing(
        name=payload.name,
        price=price_int,
        game_item_id=game_item_id,
        prefix_enchant_id=prefix_enchant_id,
        suffix_enchant_id=suffix_enchant_id,
        item_type=payload.item_type,
        item_grade=payload.item_grade,
        erg_grade=payload.erg_grade,
        erg_level=payload.erg_level,
    )
    db.add(listing)
    try:
        db.flush()  # get listing.id for FK references

        # --- Enchant effects (rolled values) ---
        for slot, (enchant_row, enc) in enchant_rows_by_slot.items():
            # Pre-load enchant_effects with effect names for name-based fallback
            ee_rows = db.execute(text("""
                SELECT ee.id, ee.effect_order, f.name AS effect_name
                FROM enchant_effects ee
                LEFT JOIN effects f ON f.id = ee.effect_id
                WHERE ee.enchant_id = :eid
                ORDER BY ee.effect_order
            """), {"eid": enchant_row.id}).mappings()
            ee_by_name = {}
            for row in ee_rows:
                if row['effect_name']:
                    ee_by_name.setdefault(row['effect_name'], []).append(row['id'])

            for eff in enc.effects:
                if eff.option_level is None:
                    continue
                # Use direct ID from config when provided
                ee_id = eff.enchant_effect_id
                if not ee_id and eff.option_name:
                    # Fallback: exact name match first, then fuzzy (longest substring)
                    candidates = ee_by_name.get(eff.option_name, [])
                    if not candidates:
                        fuzzy = [(n, ids) for n, ids in ee_by_name.items() if n in eff.option_name and ids]
                        if fuzzy:
                            best_name = max(fuzzy, key=lambda x: len(x[0]))[0]
                            candidates = ee_by_name[best_name]
                    if candidates:
                        ee_id = candidates.pop(0)  # consume to avoid reuse
                if ee_id:
                    db.add(ListingEnchantEffect(
                        listing_id=listing.id,
                        enchant_effect_id=ee_id,
                        value=eff.option_level,
                    ))

        # --- Reforge options ---
        for opt in payload.reforge_options:
            reforge_option_id = opt.reforge_option_id
            if not reforge_option_id:
                reforge_row = db.query(ReforgeOption).filter(
                    ReforgeOption.option_name == opt.name,
                ).first()
                reforge_option_id = reforge_row.id if reforge_row else None
            db.add(ListingReforgeOption(
                listing_id=listing.id,
                reforge_option_id=reforge_option_id,
                option_name=opt.name,
                level=opt.level,
                max_level=opt.max_level,
            ))

        db.commit()
        db.refresh(listing)
        logger.info("register-listing  persisted listing id=%d name=%r enchants=%d reforges=%d",
                     listing.id, listing.name, len(payload.enchants), len(payload.reforge_options))
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("register-listing  listing persist failed")
        raise HTTPException(status_code=500, detail="Failed to persist listing")

    return {
        "registered": True,
        "name": payload.name,
        "listing_id": listing.id,
        "corrections_saved": corrections_saved,
    }
