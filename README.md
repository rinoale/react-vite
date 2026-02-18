# Mabinogi Item Trade Website

A specialized marketplace for trading in-game items with automated OCR (Optical Character Recognition) item registration and smart recommendation system.

## 🚀 Features

*   **OCR Item Registration:** Upload item screenshots to automatically fill in stats and details.
*   **Smart Marketplace:** Search items by specific attributes (e.g., "Fire Damage > 50").
*   **Recommendations:** Content-based filtering suggests items based on search and purchase history.
*   **Custom OCR Training:** Tooling to train EasyOCR on Mabinogi's specific game font.

## 🛠️ Tech Stack

*   **Frontend:** React, Vite, Tailwind CSS
*   **Backend:** Python, FastAPI, EasyOCR, scikit-learn
*   **Database:** (Mocked/SQLite)
*   **OCR:** EasyOCR (with custom trained model capabilities)

## 📂 Project Structure

```
├── backend/
│   ├── main.py                    # FastAPI server, OCR pipeline endpoint
│   ├── tooltip_line_splitter.py   # Line detection via horizontal projection
│   ├── text_corrector.py          # Fuzzy matching post-correction
│   ├── models/                    # Custom EasyOCR model (.pth, .yaml, .py)
│   └── unique_chars.txt           # 442-char Korean character set
├── data/
│   ├── fonts/                     # Mabinogi game font
│   ├── dictionary/                # Reforging + tooltip dictionaries
│   └── sample_images/             # Ground truth pairs (.png + .txt)
├── scripts/                       # Training data gen, testing, config
├── skills/                        # Gemini CLI Skills (OCR Trainer)
├── frontend/                      # React/Vite frontend app
├── OCR_TRAINING_HISTORY.md        # Full training history (6 attempts)
├── OCR_ISSUES.md                  # Known issues and resolutions
├── AGENTS.md                      # Detailed project context for AI agents
└── CLAUDE.md                      # Claude Code instructions
```

## ⚡ Quick Start

### 1. Backend Setup

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:5173` to browse the marketplace.

---

## 🐳 Docker Setup

This project includes:
- `backend/Dockerfile` (Python `3.14.2`, FastAPI/uvicorn)
- `frontend/Dockerfile` (Node `25.2.1`, Vite frontend)
- `docker-compose.yml` (runs both services together)

### Build Images

```bash
docker compose build
```

If backend dependency compilation fails or cache gets stale, rebuild backend without cache:

```bash
docker compose build backend --no-cache
```

### Start Services

```bash
docker compose up
```

Run detached:

```bash
docker compose up -d
```

### Service URLs

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`

### Stop Services

```bash
docker compose down
```

---

## 📜 Scripts & Utilities

This project includes several helper scripts in the `scripts/` directory to help with development and OCR model training.

**Note:** Always run these scripts from the **project root directory**.

### 1. Generate Training Data (`scripts/generate_training_data.py`)
Generates synthetic training images using the Mabinogi font and a dictionary of item options.

```bash
# Generates images in backend/train_data/
python3 scripts/generate_training_data.py
```

### 2. Test OCR Pipeline (`scripts/test_ocr.py`)
Runs EasyOCR with the custom trained model directly on a sample image. Useful for evaluating OCR accuracy.

```bash
python3 scripts/test_ocr.py
```

### 3. Check Image Stats (`scripts/check_image_stats.py`)
Simple utility to print the dimensions and mean brightness of an image. Used to debug why OCR might be failing on dark screenshots.

```bash
python3 scripts/check_image_stats.py
```

### 4. Test Line Splitter (`scripts/test_line_splitter.py`)
Splits a tooltip image into individual text line images using horizontal projection profiling. Useful for visually verifying that line detection is working correctly.

```bash
python3 scripts/test_line_splitter.py <image_path> <output_dir>

# Example
python3 scripts/test_line_splitter.py data/sample_images/lightarmor_processed_2.png test_split_output
```

The output directory will contain:
- `*_line_001.png`, `*_line_002.png`, ... — cropped line images
- `*_visualization.png` — original image with detected line bounding boxes

### 5. Create Model Config (`scripts/create_model_config.py`)
Generates the YAML configuration file required by EasyOCR to load a custom trained model. Reads characters from `backend/unique_chars.txt`.

```bash
python3 scripts/create_model_config.py
```

---

## 🔍 OCR Pipeline (v2)

The OCR pipeline uses a two-stage approach:

1. **Detection** — `TooltipLineSplitter` splits the tooltip image into individual text lines using horizontal projection profiling. This replaces EasyOCR's CRAFT detector, which is designed for natural scene text and performs poorly on structured tooltip layouts.

2. **Recognition** — Each line crop is fed directly to the custom EasyOCR recognition model (`TPS-ResNet-BiLSTM-CTC`) via the `recognize()` API, bypassing CRAFT entirely.

3. **Correction** — RapidFuzz fuzzy matching against game dictionaries fixes common OCR errors.

```
Screenshot → Frontend (binary threshold) → Line Splitter → Recognition → Correction → Structured JSON
```

## 🧠 Training Custom OCR Model

All training parameters are centralized in **`configs/training_config.yaml`**.

1.  **Generate Data:** `python3 scripts/generate_training_data.py`
2.  **Generate Model Config:** `python3 scripts/create_model_config.py` — Reads `training_config.yaml` → generates `backend/models/custom_mabinogi.yaml`. **Required** when `imgW`, `imgH`, network params, or `unique_chars.txt` change.
3.  **Create LMDB:** `python3 skills/ocr-trainer/scripts/create_lmdb_dataset.py --input backend/train_data --output backend/train_data_lmdb`
4.  **Train** (use `nohup` — reads `configs/training_config.yaml`):
    ```bash
    nohup python3 -u scripts/train.py > logs/training.log 2>&1 &
    # Resume from checkpoint: nohup python3 -u scripts/train.py --resume > logs/training.log 2>&1 &
    # Override iterations: nohup python3 -u scripts/train.py --num_iter 20000 > logs/training.log 2>&1 &
    ```
5.  **Deploy:** `cp saved_models/TPS-ResNet-BiLSTM-CTC-Seed1111/best_accuracy.pth backend/models/custom_mabinogi.pth`
6.  **Validate:** `python3 scripts/test_v2_pipeline.py -q`

For training history and known pitfalls, see `OCR_TRAINING_HISTORY.md`.
