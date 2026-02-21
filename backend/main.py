from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging
import shutil
import os
import tempfile
import easyocr
from recommendation import recommender, ITEMS_DB
from text_corrector import TextCorrector
from ocr_utils import patch_reader_imgw
from mabinogi_tooltip_parser import MabinogiTooltipParser
from tooltip_segmenter import init_header_reader, load_section_patterns, load_config, segment_and_tag
from pydantic import BaseModel
from typing import List

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_PATH = os.path.join(LOG_DIR, 'backend.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-8s  %(name)s  %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH, encoding='utf-8'),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger('mabinogi')

# Route uvicorn's access & error logs to the same file
for name in ('uvicorn', 'uvicorn.access', 'uvicorn.error'):
    uv_logger = logging.getLogger(name)
    uv_logger.handlers = logging.getLogger().handlers
    uv_logger.propagate = False

app = FastAPI()

# Allow CORS for local development
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Text Corrector with both dictionaries
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DICT_DIR = os.path.join(BASE_DIR, '..', 'data', 'dictionary')
corrector = TextCorrector(dict_dir=DICT_DIR)

# Initialize EasyOCR Reader with custom trained model
MODELS_DIR = os.path.join(BASE_DIR, 'ocr', 'models')

reader = easyocr.Reader(
    ['ko'],
    model_storage_directory=MODELS_DIR,
    user_network_directory=MODELS_DIR,
    recog_network='custom_mabinogi'
)
patch_reader_imgw(reader, MODELS_DIR)

# Initialize Mabinogi tooltip parser
CONFIG_PATH = os.path.join(BASE_DIR, '..', 'configs', 'mabinogi_tooltip.yaml')
tooltip_parser = MabinogiTooltipParser(CONFIG_PATH)

# Initialize header reader + section patterns for the v3 segment-first pipeline
header_reader    = init_header_reader(models_dir=MODELS_DIR)
section_patterns = load_section_patterns(CONFIG_PATH)
tooltip_config   = load_config(CONFIG_PATH)

class UserHistory(BaseModel):
    history_ids: List[int]

@app.get("/")
def read_root():
    return {"message": "Mabinogi Item Trade API is running"}

@app.get("/items")
def get_items():
    return ITEMS_DB

@app.get("/recommend/item/{item_id}")
def recommend_by_item(item_id: int):
    results = recommender.get_recommendations(item_id)
    return results

@app.post("/recommend/user")
def recommend_for_user(user_history: UserHistory):
    results = recommender.recommend_for_user(user_history.history_ids)
    return results

@app.post("/upload-item")
async def upload_item(file: UploadFile = File(...)):
    """Upload tooltip image and return flat list of detected lines.

    Uses the v2 pipeline (MabinogiTooltipParser) internally.
    Returns detected_lines in the same format as before for frontend compatibility.
    """
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            shutil.copyfileobj(file.file, tmp)
            temp_filename = tmp.name

        try:
            # Use v2 pipeline: section-aware splitter + EasyOCR recognize()
            result = tooltip_parser.parse_tooltip(temp_filename, reader)
        finally:
            os.remove(temp_filename)

        results = []
        for line in result.get('all_lines', []):
            raw_text = line.get('text', '')
            if not raw_text.strip():
                continue

            corrected_text, score = corrector.correct(raw_text)
            final_text = corrected_text if score > 60 else raw_text

            results.append({
                "text": final_text,
                "raw_text": raw_text,
                "confidence": float(line.get('confidence', 0.0)),
                "correction_score": float(score) / 100.0,
                "bounds": line.get('bounds', {}),
            })

        return {
            "filename": file.filename,
            "detected_lines": results,
            "raw_text_summary": "\n".join([r['text'] for r in results]),
        }

    except Exception as e:
        logger.exception("upload-item failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload-item-v2")
async def upload_item_v2(file: UploadFile = File(...)):
    """V2 endpoint: section-aware tooltip parsing.

    Uses MabinogiTooltipParser to split, OCR, and categorize tooltip
    lines into game-specific sections (item_attrs, reforge, enchant, etc.).
    """
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            shutil.copyfileobj(file.file, tmp)
            temp_filename = tmp.name

        try:
            # Run section-aware parsing pipeline
            result = tooltip_parser.parse_tooltip(temp_filename, reader)
        finally:
            os.remove(temp_filename)

        # Apply text correction to each OCR line
        for line in result.get('all_lines', []):
            raw_text = line.get('text', '')
            if raw_text.strip():
                corrected_text, score = corrector.correct(raw_text)
                line['corrected_text'] = corrected_text if score > 60 else raw_text
                line['correction_score'] = float(score) / 100.0
            else:
                line['corrected_text'] = raw_text
                line['correction_score'] = 0.0

        # Also correct text within sections
        for section_key, section_data in result.get('sections', {}).items():
            if 'lines' in section_data:
                for line in section_data['lines']:
                    raw_text = line.get('text', '')
                    if raw_text.strip():
                        corrected_text, score = corrector.correct(raw_text)
                        line['corrected_text'] = corrected_text if score > 60 else raw_text
                        line['correction_score'] = float(score) / 100.0

        return {
            "filename": file.filename,
            "sections": result['sections'],
            "all_lines": result['all_lines'],
        }

    except Exception as e:
        logger.exception("upload-item-v2 failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload-item-v3")
async def upload_item_v3(file: UploadFile = File(...)):
    """V3 endpoint: segment-first pipeline.

    Accepts the original color screenshot (not preprocessed).
    1. detect_headers() on color image → segment_and_tag() → section labels
    2. For each segment: BT.601 + threshold → line split → content OCR
    3. Text correction applied per line

    Returns same JSON shape as /upload-item-v2.
    """
    try:
        import cv2
        import numpy as np

        raw = await file.read()
        arr = np.frombuffer(raw, np.uint8)
        img_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img_bgr is None:
            raise HTTPException(status_code=400, detail="Could not decode image")

        # Step 1: segment with header OCR labels
        tagged = segment_and_tag(img_bgr, header_reader, section_patterns, tooltip_config)

        # Step 2: content OCR per segment → assemble structured result
        result = tooltip_parser.parse_from_segments(tagged, reader)

        # Step 3: section-aware text correction — FM decision
        # all_lines and sections share the same line objects — correct once.
        # Server picks best text: if FM matches (score > 0), use FM result;
        # otherwise keep raw OCR.  No separate corrected_text field.
        current_enchant_entry = None
        enchant_db_ready = bool(corrector._enchant_db)
        fm_sections = set(corrector._section_norm_cache.keys())

        for line in result.get('all_lines', []):
            raw_text = line.get('text', '')
            section  = line.get('section', '')

            if not raw_text.strip():
                line['fm_applied'] = False
                continue

            # Section headers (orange text) don't need FM
            if line.get('is_header'):
                line['fm_applied'] = False
                continue

            # Enchant: try header FM on every line — let the score decide,
            # don't rely on regex tag (OCR garbles headers beyond regex recognition)
            if section == 'enchant' and enchant_db_ready:
                hdr_text, hdr_score, hdr_entry = corrector.match_enchant_header(raw_text)
                if hdr_score > 0:
                    fm_text, fm_score = hdr_text, hdr_score
                    current_enchant_entry = hdr_entry
                else:
                    fm_text, fm_score = corrector.match_enchant_effect(raw_text, current_enchant_entry)
            elif section in fm_sections:
                fm_text, fm_score = corrector.correct_normalized(raw_text, section=section)
            else:
                fm_text, fm_score = raw_text, 0

            # FM decision: if match found, replace text
            if fm_score > 0:
                line['text'] = fm_text
                line['fm_applied'] = True
            else:
                line['fm_applied'] = False

        # Step 4: rebuild structured data from FM-corrected lines
        sections = result.get('sections', {})

        if 'enchant' in sections and sections['enchant'].get('lines'):
            enchant_updated = tooltip_parser.build_enchant_structured(sections['enchant']['lines'])
            sections['enchant'].update(enchant_updated)

        if 'reforge' in sections and sections['reforge'].get('lines'):
            reforge_updated = tooltip_parser.build_reforge_structured(sections['reforge']['lines'])
            sections['reforge'].update(reforge_updated)

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