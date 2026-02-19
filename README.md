# Mabinogi Item Trade Website

A specialized marketplace for trading in-game items with automated OCR item registration and a content-based recommendation system.

## Features

- **OCR Item Registration** — Upload an item tooltip screenshot; stats and details are extracted automatically.
- **Smart Marketplace** — Search items by specific attributes (e.g., "Fire Damage > 50").
- **Recommendations** — Content-based filtering suggests items based on search and purchase history.
- **Custom OCR Model** — Trained on the actual Mabinogi game font; fine-tuned for tooltip layout.

## Tech Stack

- **Frontend:** React, Vite, Tailwind CSS
- **Backend:** Python, FastAPI, EasyOCR, scikit-learn
- **OCR model:** TPS-ResNet-BiLSTM-CTC (custom-trained via deep-text-recognition-benchmark)

---

## Project Structure

```
├── backend/
│   ├── main.py                    # FastAPI server, POST /upload-item-v2
│   ├── tooltip_line_splitter.py   # Line splitting via horizontal projection profiling
│   ├── mabinogi_tooltip_parser.py # Section-aware parser (extends line splitter)
│   ├── text_corrector.py          # RapidFuzz post-OCR correction
│   ├── ocr_utils.py               # EasyOCR inference patch (fixed imgW)
│   ├── models/                    # Custom model weights (.pth), config (.yaml, .py)
│   └── unique_chars.txt           # 509-char character set for the OCR model
├── configs/
│   ├── training_config.yaml       # All training parameters (single source of truth)
│   └── mabinogi_tooltip.yaml      # Section header patterns for the parser
├── data/
│   ├── fonts/                     # Mabinogi game font (mabinogi_classic.ttf)
│   ├── dictionary/                # per-section .txt files (reforge.txt, tooltip_general.txt, ...)
│   └── sample_images/             # GT images (.png) + labels (.txt, _expected.txt)
├── scripts/                       # Training pipeline, testing, config generation
├── skills/ocr-trainer/            # LMDB creation + deep-text-recognition-benchmark
├── frontend/                      # React/Vite app
├── documents/
│   ├── ARCHITECTURE.md            # OCR pipeline internals
│   └── STRATEGY_MABINOGI.md       # Design decisions with porting guides (D1–D10)
├── OCR_TRAINING_HISTORY.md        # Per-attempt training log and accuracy results
├── OCR_ISSUES.md                  # Issue tracker (resolved + current blockers)
└── CLAUDE.md                      # AI agent instructions and project conventions
```

---

## Quick Start

### Backend

```bash
pip install -r backend/requirements.txt
cd backend && uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:5173`.

---

## Docker Setup

```bash
# Build and start both services
docker compose build
docker compose up

# Rebuild backend without cache (if dependency compilation fails)
docker compose build backend --no-cache
```

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`

```bash
docker compose down
```

---

## OCR Pipeline

```
Screenshot → Frontend (threshold=80) → Line Splitter → Recognition → Correction → JSON
```

1. **Preprocessing** (`frontend/src/pages/sell.jsx`) — Browser converts screenshot to binary PNG (black text on white, threshold=80).
2. **Line splitting** (`backend/tooltip_line_splitter.py`) — Horizontal projection profiling splits the tooltip into individual line crops. Replaces EasyOCR's CRAFT detector, which performs poorly on structured layouts.
3. **Section parsing** (`backend/mabinogi_tooltip_parser.py`) — Categorizes each line into game sections (enchant, reforge, color parts, etc.) using `configs/mabinogi_tooltip.yaml`. Color part RGB values are parsed via regex and bypass OCR entirely.
4. **Recognition** — Each crop goes to the custom `TPS-ResNet-BiLSTM-CTC` model via EasyOCR's `recognize()`, skipping CRAFT detection.
5. **Correction** (`backend/text_corrector.py`) — RapidFuzz fuzzy matching against game dictionaries fixes common substitution errors.

See `documents/ARCHITECTURE.md` for full internals and `documents/STRATEGY_MABINOGI.md` for design decisions.

---

## Training Custom OCR Model

All parameters are in `configs/training_config.yaml` (single source of truth). Run all commands from the **project root**.

### Steps

**1. Generate synthetic training images**
```bash
rm -rf backend/train_data backend/train_data_lmdb
python3 scripts/generate_training_data.py
# Output: backend/train_data/  (~11k images)
```

**2. Generate model config**

Required when `imgW`, `imgH`, network params, or `unique_chars.txt` change.
```bash
python3 scripts/create_model_config.py
# Output: backend/models/custom_mabinogi.yaml
```

**3. Create LMDB dataset**
```bash
python3 skills/ocr-trainer/scripts/create_lmdb_dataset.py \
  --input backend/train_data --output backend/train_data_lmdb
```

**4. Train**

Use `nohup` — training must not be a subprocess (OOM risk).
```bash
nohup python3 -u scripts/train.py > logs/training_attemptN.log 2>&1 &

# Resume from checkpoint
nohup python3 -u scripts/train.py --resume > logs/training_attemptN.log 2>&1 &

# Monitor
tail -f logs/training_attemptN.log
```

**5. Deploy**

Back up the current model before replacing it:
```bash
cp backend/models/custom_mabinogi.pth backend/models/custom_mabinogi_aN.pth   # version backup
cp saved_models/TPS-ResNet-BiLSTM-CTC-Seed1111/best_accuracy.pth \
   backend/models/custom_mabinogi.pth                                          # deploy
```

**6. Validate**
```bash
# Full output
python3 scripts/test_v2_pipeline.py --normalize --gt-suffix _expected.txt

# Summary only
python3 scripts/test_v2_pipeline.py -q --normalize --gt-suffix _expected.txt
```

`--normalize` strips punctuation differences; `--gt-suffix _expected.txt` uses the expected-OCR GT files (not full item GT). Omitting these flags produces artificially low scores.

For training history and known pitfalls, see `OCR_TRAINING_HISTORY.md` and `OCR_ISSUES.md`.

---

## Scripts Reference

All scripts run from the **project root**.

| Script | Purpose |
|---|---|
| `scripts/generate_training_data.py` | Generate synthetic training images |
| `scripts/create_model_config.py` | Generate `custom_mabinogi.yaml` from `unique_chars.txt` |
| `scripts/train.py` | Training launcher (reads `configs/training_config.yaml`) |
| `scripts/test_v2_pipeline.py` | Evaluate pipeline on GT images (`--include-fuzzy` for FM results) |
| `scripts/test_line_splitter.py <img> <out>` | Visual line detection verification |
| `scripts/regenerate_gt.py` | Regenerate GT candidates from pipeline output |
| `skills/ocr-trainer/scripts/create_lmdb_dataset.py` | Convert image/label pairs to LMDB |

---

## Documentation

| Document | Contents |
|---|---|
| `documents/ARCHITECTURE.md` | OCR pipeline internals: how each stage works |
| `documents/STRATEGY_MABINOGI.md` | Design decisions D1–D10 with porting guides |
| `OCR_TRAINING_HISTORY.md` | Per-attempt accuracy results and analysis |
| `OCR_ISSUES.md` | Resolved issues and current blockers |
| `CLAUDE.md` | AI agent instructions and project conventions |
