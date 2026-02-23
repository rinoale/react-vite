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
│   ├── main.py                    # FastAPI server (v2 + v3 OCR endpoints)
│   ├── tooltip_line_splitter.py   # Line splitting via horizontal projection profiling
│   ├── mabinogi_tooltip_parser.py # Section-aware parser (extends line splitter)
│   ├── text_corrector.py          # RapidFuzz post-OCR correction
│   ├── ocr_utils.py               # EasyOCR inference patch (fixed imgW)
│   ├── models/                    # Custom model weights (.pth), config (.yaml, .py)
│   └── unique_chars.txt           # Current deployed content model charset (a15: 509 chars)
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
├── infra/
│   ├── README.md                  # Infra/service layout guide
│   └── database/                  # PostgreSQL Docker assets
│       ├── Dockerfile
│       └── init/                  # Optional SQL bootstrap scripts
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
# Build and start all services (frontend, backend, db)
docker compose build
docker compose up

# Rebuild backend without cache (if dependency compilation fails)
docker compose build backend --no-cache

# Open a bash shell in the backend container
docker compose exec backend bash
```

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- PostgreSQL: `localhost:5432` (`db=mabinogi`, `user=mabinogi`, `password=mabinogi`)

```bash
docker compose down
```

If you add `.sql` files under `infra/database/init/`, they will run automatically
on first DB initialization.

## Database Dictionary Import

Import `enchant.txt` and `reforge.txt` into PostgreSQL:

```bash
# 1) Ensure db is running
docker compose up -d db

# 2) Install backend deps (includes SQLAlchemy + psycopg2)
pip install -r backend/requirements.txt

# 3) Run importer from project root
python3 scripts/db/import_dictionaries.py
```

Optional explicit connection arguments:

```bash
python3 scripts/db/import_dictionaries.py \
  --db-host localhost --db-port 5432 \
  --db-name mabinogi --db-user mabinogi --db-password mabinogi
```

---

## OCR Pipeline

```
Color Screenshot → Header Detection → Segmentation → Header OCR → Content OCR → FM → JSON
```

1. **V3 input** (`POST /upload-item-v3`) — Backend receives the original color screenshot.
2. **Segmentation-first flow** (`backend/lib/tooltip_segmenter.py`) — Detects section headers, segments header/content regions, OCRs short headers, and assigns canonical section labels before content OCR.
3. **Content OCR** (`backend/lib/mabinogi_tooltip_parser.py`) — Per-segment BT.601 + threshold preprocessing, line splitting with `TooltipLineSplitter`, and EasyOCR `recognize()` per line (no CRAFT).
4. **FM + structured output** (`backend/lib/text_corrector.py`) — Section-specific fuzzy matching, server-side FM decision (`text` + `fm_applied`), plus structured enchant/reforge reconstruction.

Legacy v2 (`/upload-item-v2`) remains available but is not the primary pipeline.

See `documents/ARCHITECTURE.md` for full internals and `documents/STRATEGY_MABINOGI.md` for design decisions.

---

## Training Custom OCR Model

Training parameters live in each version's `training_config.yaml` (e.g. `backend/ocr/general_model/a18/training_config.yaml`). All scripts accept `--version <ver>` (defaults to active version from symlink). Run all commands from the **project root**.

### Steps

**1. Generate synthetic training images**
```bash
python3 scripts/ocr/general_model/generate_training_data.py --version a18
# Output: backend/ocr/general_model/a18/train_data/  (~11k images)
```

**2. Generate model config**

Required when `imgW`, `imgH`, network params, or `unique_chars.txt` change.
```bash
python3 scripts/ocr/general_model/create_model_config.py --version a18
# Output: saved_models/custom_mabinogi.yaml
```

**3. Create LMDB dataset**
```bash
python3 skills/ocr-trainer/scripts/create_lmdb_dataset.py \
  --input backend/ocr/general_model/a18/train_data \
  --output backend/ocr/general_model/a18/train_data_lmdb
```

**4. Train**

Use `nohup` — training must not be a subprocess (OOM risk).
```bash
nohup python3 -u scripts/ocr/general_model/train.py --version a18 > logs/training_attemptN.log 2>&1 &

# Resume from checkpoint
nohup python3 -u scripts/ocr/general_model/train.py --version a18 --resume > logs/training_attemptN.log 2>&1 &

# Monitor
tail -f logs/training_attemptN.log
```

**5. Deploy**

Copies trained model into version folder and updates symlinks:
```bash
bash scripts/ocr/general_model/deploy.sh a18
```

**6. Validate**
```bash
# Full output
python3 scripts/v2/test_v2_pipeline.py --normalize --gt-suffix _expected.txt

# Summary only
python3 scripts/v2/test_v2_pipeline.py -q --normalize --gt-suffix _expected.txt
```

`--normalize` strips punctuation differences; `--gt-suffix _expected.txt` uses the expected-OCR GT files (not full item GT). Omitting these flags produces artificially low scores.

Current benchmark status (docs): v2 best (Attempt 15) = 77.0% char acc, v3 (Attempt 17, no retraining) = 87.5% char acc. See `OCR_TRAINING_HISTORY.md` and `OCR_ISSUES.md`.

---

## Scripts Reference

All scripts run from the **project root**. OCR scripts are organized under `scripts/ocr/`.

| Script | Purpose |
|---|---|
| `scripts/ocr/general_model/generate_training_data.py` | Generate synthetic training images |
| `scripts/ocr/general_model/create_model_config.py` | Generate `custom_mabinogi.yaml` from `unique_chars.txt` |
| `scripts/ocr/general_model/train.py` | Training launcher (reads version's `training_config.yaml`) |
| `scripts/ocr/general_model/deploy.sh` | Deploy trained model to version folder + update symlinks |
| `scripts/ocr/category_header_model/train.py` | Train category header OCR model |
| `scripts/ocr/category_header_model/create_lmdb.py` | Create category header training LMDB |
| `scripts/ocr/enchant_header_model/train.py` | Train enchant header OCR model |
| `scripts/ocr/enchant_header_model/create_lmdb.py` | Create enchant header training LMDB |
| `scripts/ocr/enchant_header_model/generate_training_data.py` | Generate enchant header training data |
| `scripts/ocr/enchant_header_model/create_model_config.py` | Generate enchant header model config |
| `scripts/ocr/switch_model.sh` | Switch active model version (updates symlinks) |
| `scripts/ocr/generate_enchant_dicts.py` | Generate enchant dictionaries from YAML |
| `scripts/v3/test_v3_pipeline.py` | Evaluate v3 segment-first pipeline on original color GT images |
| `scripts/v2/test_v2_pipeline.py` | Evaluate legacy v2 pipeline on processed GT images |
| `scripts/v3/segmentation/test_line_split.py` | Visual line detection verification per segment |
| `scripts/v2/ocr/regenerate_gt.py` | Regenerate GT candidates from v2 parser output |
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
