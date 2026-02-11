# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Mabinogi (MMORPG) item trading marketplace with OCR-powered item registration. Users upload a screenshot of an in-game item tooltip, and the system automatically extracts item details using a custom-trained EasyOCR model.

## Development Commands

### Frontend (React + Vite)
```bash
npm install          # Install dependencies
npm run dev          # Dev server at http://localhost:5173
npm run build        # Production build to dist/
npm run lint         # ESLint (flat config, React hooks + refresh plugins)
npm run preview      # Preview production build
```

### Backend (Python FastAPI)
```bash
pip install -r backend/requirements.txt
cd backend && uvicorn main:app --reload --port 8000   # API at http://localhost:8000
```

### OCR Training Pipeline
All scripts must be run from the **project root**:
```bash
python3 scripts/generate_training_data.py                    # Synthetic training images → backend/train_data/
python3 scripts/create_model_config.py                       # Generate custom_mabinogi.yaml from unique_chars.txt
python3 skills/ocr-trainer/scripts/create_lmdb_dataset.py \
  --input backend/train_data --output backend/train_data_lmdb # Convert to LMDB for training
python3 scripts/test_ocr.py                                  # Test OCR on sample image (full-image readtext)
python3 scripts/test_line_splitter.py <image> <output_dir>   # Test line splitter visually
```
After training, deploy model by copying `.pth` to `backend/models/custom_mabinogi.pth`.

## Architecture

### OCR Pipeline (core feature)
The data flow for item registration:
1. **Frontend** (`src/pages/sell.jsx`): Browser preprocesses uploaded image (grayscale → thresholding) to produce black-text-on-white-background PNG (contrast=1.0, brightness=1.0, threshold=80)
2. **Backend** (`backend/main.py` → `POST /upload-item`): Receives image, runs the pipeline:
   - `EasyOCR` with custom model (`models/custom_mabinogi.pth` + `.yaml` + `.py`): CRAFT detects text regions, then custom TPS-ResNet-BiLSTM-CTC model recognizes Korean text
   - `TextCorrector` (`text_corrector.py`): RapidFuzz fuzzy matching against game dictionaries (`data/dictionary/reforging_options.txt` + `tooltip_general.txt`) to fix OCR errors
3. Results returned as JSON with corrected text, raw text, confidence, correction score, and bounding boxes

### Custom OCR Model
- Architecture: `TPS-ResNet-BiLSTM-CTC` (from `deep-text-recognition-benchmark/`)
- Font: `data/fonts/mabinogi_classic.ttf` (actual game font)
- Character set (442 chars) defined in `backend/unique_chars.txt` and mirrored in `backend/models/custom_mabinogi.yaml`
- Model weights: `backend/models/custom_mabinogi.pth`
- Model architecture for EasyOCR integration: `backend/models/custom_mabinogi.py`
- Training history and known issues: `OCR_TRAINING_HISTORY.md`

### Training Flags (Critical)
When training with `deep-text-recognition-benchmark/train.py`:
- `--workers 0` — Required. LMDB can't be pickled for multiprocessing.
- `--sensitive` — Required. Prevents lowercasing labels (needed for R,G,B,L,A-F characters).
- `--PAD` — Required. Matches EasyOCR's `keep_ratio_with_pad=True` inference preprocessing.
- `--batch_max_length 30` — Labels can be up to 29 characters long.
- `--character "$(cat ../backend/unique_chars.txt | tr -d '\n')"` — Full 442-char Korean set.
- Note: `train.py` line 287-289 was patched so `--sensitive` no longer overrides the character set.

### Recommendation System
- `backend/recommendation.py`: TF-IDF vectorization of item descriptions + cosine similarity
- Endpoints: `GET /recommend/item/{id}` and `POST /recommend/user` (history-based)

### Frontend Routes
- `/` → `Marketplace` — item grid with recommendations
- `/sell` → `Sell` — image upload + OCR item registration
- `/navigate` → `Navigate` — Leaflet map (experimental)
- `/image_process` → `ImageProcess` — OCR training data preparation tool

## Key Constraints

- Frontend sends preprocessed (thresholded) images: black text on white background
- The `TooltipLineSplitter` (`tooltip_line_splitter.py`) auto-detects background polarity and uses horizontal projection profiling for line detection; however, the backend OCR pipeline uses EasyOCR's CRAFT detector directly instead
- The EasyOCR custom model can only recognize characters present in `backend/unique_chars.txt`; any characters not in this set will never be output
- Item database is currently mocked in `backend/recommendation.py` (`ITEMS_DB`); no persistent storage yet
- The `data/` directory (fonts, dictionary, sample images) is not fully committed to git
