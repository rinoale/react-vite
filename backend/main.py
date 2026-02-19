from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
import tempfile
import easyocr
from recommendation import recommender, ITEMS_DB
from text_corrector import TextCorrector
from ocr_utils import patch_reader_imgw
from mabinogi_tooltip_parser import MabinogiTooltipParser
from pydantic import BaseModel
from typing import List

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
MODELS_DIR = os.path.join(BASE_DIR, 'models')

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
        import traceback
        traceback.print_exc()
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
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))