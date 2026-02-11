from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
import easyocr
from recommendation import recommender, ITEMS_DB
from text_corrector import TextCorrector
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
corrector = TextCorrector(os.path.join(DICT_DIR, 'reforging_options.txt'))
corrector.load_dictionary(os.path.join(DICT_DIR, 'tooltip_general.txt'))

# Initialize EasyOCR Reader with custom trained model
MODELS_DIR = os.path.join(BASE_DIR, 'models')

reader = easyocr.Reader(
    ['ko'],
    model_storage_directory=MODELS_DIR,
    user_network_directory=MODELS_DIR,
    recog_network='custom_mabinogi'
)

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
    try:
        # 1. Save uploaded file temporarily
        temp_filename = f"temp_{file.filename}"
        with open(temp_filename, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 2. Run OCR directly on the full image (CRAFT handles text detection)
        ocr_results = reader.readtext(temp_filename)

        results = []
        for bbox, raw_text, confidence in ocr_results:
            if not raw_text.strip():
                continue

            # 3. Apply Dictionary Correction
            corrected_text, score = corrector.correct(raw_text)
            final_text = corrected_text if score > 60 else raw_text

            # Convert bbox to simple bounds
            xs = [pt[0] for pt in bbox]
            ys = [pt[1] for pt in bbox]
            bounds = {
                "x": int(min(xs)),
                "y": int(min(ys)),
                "width": int(max(xs) - min(xs)),
                "height": int(max(ys) - min(ys)),
            }

            results.append({
                "text": final_text,
                "raw_text": raw_text,
                "confidence": float(confidence),
                "correction_score": float(score) / 100.0,
                "bounds": bounds,
            })

        # Cleanup temp file
        os.remove(temp_filename)

        return {
            "filename": file.filename,
            "detected_lines": results,
            "raw_text_summary": "\n".join([r['text'] for r in results])
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))