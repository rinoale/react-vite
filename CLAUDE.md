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
2. **Backend** (`backend/main.py` → `POST /upload-item`): Receives image, runs the v2 pipeline:
   - `TooltipLineSplitter` (`tooltip_line_splitter.py`): Horizontal projection profiling splits the tooltip into individual line crops. Handles vertical border removal, gap tolerance, and proportional padding.
   - `EasyOCR recognize()` on each line crop: Bypasses CRAFT detection entirely, runs custom TPS-ResNet-BiLSTM-CTC model directly on pre-cropped line images.
   - `TextCorrector` (`text_corrector.py`): RapidFuzz fuzzy matching against game dictionaries (`data/dictionary/reforging_options.txt` + `tooltip_general.txt`) to fix OCR errors
3. Results returned as JSON with corrected text, raw text, confidence, correction score, and line positions

**Why not CRAFT?** CRAFT is designed for natural scene text detection (signs, labels in photos). On structured tooltip layouts, it fragments lines, merges adjacent text, and misses entire sections. The `TooltipLineSplitter` achieves perfect detection on all test images (75/75, 22/22, 23/23 lines).

### Custom OCR Model
- Architecture: `TPS-ResNet-BiLSTM-CTC` (from `deep-text-recognition-benchmark/`)
- Font: `data/fonts/mabinogi_classic.ttf` (actual game font)
- Character set (509 chars) defined in `backend/unique_chars.txt` and mirrored in `backend/models/custom_mabinogi.yaml`
- Model weights: `backend/models/custom_mabinogi.pth`
- Model architecture for EasyOCR integration: `backend/models/custom_mabinogi.py`
- Training history and known issues: `OCR_TRAINING_HISTORY.md`

### Line Splitter (`backend/tooltip_line_splitter.py`)
Splits tooltip images into individual text line crops using horizontal projection profiling:
- Auto-detects background polarity (light vs dark)
- `_remove_borders()`: Masks vertical UI border columns (>15% row density) that bridge gaps between lines
- Gap tolerance of 2 rows closes thin character stroke dips without merging separate lines
- `_split_tall_block()`: Handles oversized merged blocks by local projection analysis
- Proportional padding: `pad_x = max(2, h//3)`, `pad_y = max(1, h//5)`
- Parameters: `min_height=6, max_height=25, min_width=10`
- Horizontal separators are intentionally kept (they don't bridge sections, and removing them destroys adjacent headers like "개조", "세공")
- Ground truth test images in `data/sample_images/` with matching `.txt` files

### Training Flags (Critical)
When training with `deep-text-recognition-benchmark/train.py`:
- `--workers 0` — Required. LMDB can't be pickled for multiprocessing.
- `--sensitive` — Required. Prevents lowercasing labels (needed for R,G,B,L,A-F characters).
- `--PAD` — Required. Matches EasyOCR's `keep_ratio_with_pad=True` inference preprocessing.
- `--batch_max_length 55` — Longest labels are ~55 chars.
- `--character "$(cat ../backend/unique_chars.txt | tr -d '\n')"` — Full 509-char Korean set.
- Note: `train.py` line 287-289 was patched so `--sensitive` no longer overrides the character set.

### Training Data Requirements
Synthetic training images must match real line crops from the splitter:
- **Dimensions**: Render at font sizes 8-11 (`[8,8,9,9,10,10,11]`, ~30% size-8) on proportional canvas width. Do NOT pre-resize to 32px; let model inference handle that.
  - Font size 8 → 8-9px height (matches real 7px cluster, produces 5x+ squash factor)
  - Font sizes 9-11 → 10-14px height (matches real 10px cluster)
- **Canvas width**: Proportional to text length. Short text gets tight-cropped (60% of the time, width = text + padding); long text uses full ~260px canvas. Matches splitter's ink-bound cropping (real widths: 22-269px).
- **Binary only**: Pixel values strictly 0 and 255. Re-threshold after any resize.
- **Frontend threshold**: Base value 80 with small random variation, matching `sell.jsx`.
- **Content**: Template-based full tooltip lines (not just dictionary words):
  - Stat lines: `방어력 {N}`, `내구력 {N}/{N}`, `공격 {N}~{N}`
  - Color parts: `- 파트 {A-F} R:{N} G:{N} B:{N}`
  - Enchant headers/effects, hashtag lines, price lines, piercing text
  - Item names, flavor text, sub-bullets with `ㄴ` marker
  - All GT lines included verbatim
- **Character set**: `backend/unique_chars.txt` (509 chars) must cover all characters in GT
- **Font**: `data/fonts/mabinogi_classic.ttf` (actual game font)

### Testing
- `scripts/test_v2_pipeline.py` — Splits GT images → `recognize()` → compares against GT `.txt` files
- `scripts/test_line_splitter.py <image> <output_dir>` — Visual line detection verification
- Ground truth pairs in `data/sample_images/`: 5 images, 235 total lines

### Recommendation System
- `backend/recommendation.py`: TF-IDF vectorization of item descriptions + cosine similarity
- Endpoints: `GET /recommend/item/{id}` and `POST /recommend/user` (history-based)

### Frontend Routes
- `/` → `Marketplace` — item grid with recommendations
- `/sell` → `Sell` — image upload + OCR item registration
- `/navigate` → `Navigate` — Leaflet map (experimental)
- `/image_process` → `ImageProcess` — OCR training data preparation tool

## Documentation Policy

**Always update documentation when a notable change occurs.** This includes:
- New training attempts or results → update `OCR_TRAINING_HISTORY.md`
- Issue status changes (resolved/new) → update `OCR_ISSUES.md`
- Architecture or pipeline changes → update `CLAUDE.md` and `AGENTS.md`
- New findings, insights, or root cause analyses → update the relevant doc

Documents to keep in sync: `CLAUDE.md`, `AGENTS.md`, `OCR_TRAINING_HISTORY.md`, `OCR_ISSUES.md`.

## Key Constraints

- Frontend sends preprocessed (thresholded) images: black text on white background, pixel values strictly 0 or 255
- The v2 pipeline uses `TooltipLineSplitter` for detection + EasyOCR `recognize()` for recognition. CRAFT is not used.
- The EasyOCR custom model can only recognize characters present in `backend/unique_chars.txt`; any characters not in this set will never be output
- EasyOCR always uses `keep_ratio_with_pad=True` during inference (hardcoded in `recognition.py` lines 199, 213), regardless of yaml PAD setting. Training must use `--PAD` to match.
- Item database is currently mocked in `backend/recommendation.py` (`ITEMS_DB`); no persistent storage yet
- The `data/` directory (fonts, dictionary, sample images) is not fully committed to git
- Ground truth files (`data/sample_images/*.txt`) exist for: `lightarmor_processed_3`, `captain_suit_processed`, `lobe_processed`, `titan_blade_processed`, `dropbell_processed`
- Character set expanded to 509 chars (was 442) — all GT characters now covered
- Training must run independently (not as subprocess of Claude Code) to avoid OOM kills — use `nohup` in a separate terminal
- Training requires `--batch_size 64` (default 192 causes extreme slowdown on 8GB VRAM) and `python3 -u` for unbuffered log output
- Continued training from checkpoint is supported via `--saved_model <path_to_pth>`
- Two-stage training strategy: Stage 1 synthetic-only until 60% real char accuracy, Stage 2 fine-tune with real GT line crops (see `OCR_TRAINING_HISTORY.md`)
