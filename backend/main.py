from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
import cv2
import easyocr
import numpy as np
from pathlib import Path
from tooltip_line_splitter import TooltipLineSplitter
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

# Initialize Text Corrector
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DICT_PATH = os.path.join(BASE_DIR, '..', 'data', 'dictionary', 'reforging_options.txt')
corrector = TextCorrector(DICT_PATH)

# Initialize EasyOCR Reader (loads model into memory)
# 'ko' for Korean, 'en' for English
# Using custom model trained on Mabinogi font
MODELS_DIR = os.path.join(BASE_DIR, 'models')

reader = easyocr.Reader(
    ['ko'],
    model_storage_directory=MODELS_DIR,
    user_network_directory=MODELS_DIR,
    recog_network='custom_mabinogi' 
)

# Initialize Splitter
# We will use a temp directory for intermediate split images
TEMP_DIR = "temp_split"
splitter = TooltipLineSplitter(output_dir=TEMP_DIR)

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
        
        # 2. Process image to get text lines
        # This uses the CV2 logic from your existing script
        extracted_lines = splitter.process_image(temp_filename, save_visualization=False)
        
        results = []
        
        # 3. Run EasyOCR on each extracted line
        for line_data in extracted_lines:
            line_img_path = line_data['path']
            
            # Read the split line image
            # detail=0 returns just the text list
            ocr_result = reader.readtext(line_img_path, detail=0)
            
            # Combine text parts if multiple
            raw_text = " ".join(ocr_result)
            
            if raw_text.strip():
                # 4. Apply Dictionary Correction
                corrected_text, score = corrector.correct(raw_text)
                
                # If matched well (e.g. > 60), use corrected, else keep raw
                # Using 60 because OCR might be quite messy
                final_text = corrected_text if score > 60 else raw_text
                
                results.append({
                    "text": final_text,
                    "raw_text": raw_text,
                    "confidence": float(score)/100.0, # Using fuzzy score as confidence proxy
                    "bounds": line_data['bounds']
                })

        # Cleanup temp files
        os.remove(temp_filename)
        # Optional: cleanup split images in TEMP_DIR if you don't want to keep them
        # shutil.rmtree(TEMP_DIR) 

        return {
            "filename": file.filename,
            "detected_lines": results,
            "raw_text_summary": "\n".join([r['text'] for r in results])
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))