# Architecture

Core technical design of the Mabinogi item OCR pipeline.

---

## Overview

Users upload an in-game item tooltip screenshot. The system automatically extracts structured item data (stats, enchants, reforging, color parts, etc.) using a custom-trained OCR model tuned specifically to Mabinogi's game font and tooltip layout.

```
Screenshot → Preprocessing → Line Splitting → OCR → Correction → Structured JSON
```

---

## 1. Image Preprocessing (Browser)

**File:** `frontend/src/pages/sell.jsx`

Before the image reaches the server, the browser converts the raw screenshot into a clean binary image:

1. Convert to grayscale: `avg = (R + G + B) / 3`
2. Apply contrast and brightness adjustments (user-configurable sliders)
3. Threshold at 80: pixels darker than 80 → black (0), others → white (255)

The result is a strictly binary PNG — black text on a white background. This eliminates color variation across different game graphic settings and simplifies every downstream step.

**Why browser-side?** Offloads compute from the server and ensures the image is in a consistent format before the network round-trip.

---

## 2. Line Splitting

**File:** `backend/lib/tooltip_line_splitter.py`
**Class:** `TooltipLineSplitter`

Mabinogi tooltips are structured, fixed-layout boxes. Rather than using CRAFT (a general-purpose scene text detector), the pipeline uses horizontal projection profiling — a simpler, faster, and more reliable approach for this domain.

### Why not CRAFT?

CRAFT is designed for natural scene text (signs, labels in photos). On structured tooltip layouts, it fragments lines, merges adjacent text blocks, and misses entire sections. The custom splitter achieves perfect line detection on all test images.

### How it works

```
Binary image
    ↓
_remove_borders()         — mask narrow high-density vertical columns (border pipes)
    ↓
Horizontal projection     — count ink pixels per row → row density profile
    ↓
Gap detection             — find rows below threshold (inter-line gaps)
    ↓
Gap tolerance (2 rows)    — close thin dips from character stroke gaps
    ↓
_rescue_gaps()            — second pass at lower threshold for sparse lines (e.g. "적용)")
    ↓
_has_internal_gap()       — detect merged lines → _split_tall_block()
    ↓
_add_line()               — for each detected row range:
                            find ink clusters → filter border artifacts
                            → compute tight x bounds
    ↓
extract_lines()           — crop each line with proportional padding
                            pad_x = max(2, h//3),  pad_y = max(1, h//5)
```

### Horizontal sub-splitting

Some lines contain multiple columns separated by wide gaps (e.g., `파트 A    R:0    G:0    B:0`). Lines with an internal gap wider than `line_height × split_factor` are split into sub-segments and OCR'd separately.

**Parameters:** `min_height=6`, `max_height=25`, `min_width=10`, `horizontal_split_factor=1.5` (color parts), `3.0` (default)

---

## 3. Section-Aware Parsing

**File:** `backend/lib/mabinogi_tooltip_parser.py`
**Class:** `MabinogiTooltipParser`
**Config:** `configs/mabinogi_tooltip.yaml`

Extends `TooltipLineSplitter` with Mabinogi-specific section categorization. After lines are split, each line's OCR text is matched against section header patterns defined in the YAML config.

Sections include: `item_name`, `item_type`, `enchant`, `item_mod`, `item_grade`, `item_color`, `flavor_text`, `shop_price`, etc.

Sections marked `skip: true` (e.g., `flavor_text`, `shop_price`) are omitted from the output.

**Color parts** (`parse_mode: color_parts`): RGB values are parsed via regex from horizontal sub-segments — OCR is bypassed entirely for these lines since the format is perfectly predictable (`R:187 G:153 B:85`).

---

## 4. OCR Recognition

**Model:** `TPS-ResNet-BiLSTM-CTC`
**Files:** `backend/ocr/models/custom_mabinogi.py`, `custom_mabinogi.yaml`, `custom_mabinogi.pth` (symlinks to active version)

Each line crop is passed directly to EasyOCR's `recognize()` function, bypassing the CRAFT detection stage entirely.

### Model architecture

| Stage | Component | Role |
|---|---|---|
| Transformation | TPS (Thin Plate Spline) | Normalize spatial distortion |
| Feature extraction | ResNet | Extract visual features |
| Sequence modeling | BiLSTM | Capture character sequence context |
| Prediction | CTC | Output character sequence |

### Key configuration

- `imgH: 32` — all crops resized to 32px height before inference
- `imgW: 200` — fixed width, applied via inference patch (`backend/lib/ocr_utils.py`)
- `sensitive: true` — preserves case (required for R, G, B, A-F characters)
- `PAD: true` — matches EasyOCR's hardcoded `keep_ratio_with_pad=True`
- Character set: 509 characters (e.g. `backend/ocr/general_model/a18/unique_chars.txt`)

### Inference patch

EasyOCR computes a dynamic `imgW = ceil(w/h) * 32` per image at runtime, which mismatches the fixed `imgW=200` the model was trained with. `backend/lib/ocr_utils.py` monkey-patches `recognize()` to use the yaml-specified value instead.

### Model versioning

Each model type has versioned folders under `backend/ocr/`. The `models/` directory contains only symlinks to the active version — all backend code loads from `models/` unchanged.

```
backend/ocr/
├── general_model/
│   └── a18/                          ← version folder (self-contained)
│       ├── custom_mabinogi.pth
│       ├── custom_mabinogi.py
│       ├── custom_mabinogi.yaml
│       ├── unique_chars.txt
│       ├── training_config.yaml
│       ├── train_data/
│       └── train_data_lmdb/
├── category_header_model/v1/         ← header OCR model
├── enchant_header_model/v1/          ← enchant header OCR model
└── models/                           ← symlinks only + shared modules/
    ├── custom_mabinogi.pth → ../general_model/a18/custom_mabinogi.pth
    ├── custom_mabinogi.py  → ../general_model/a18/custom_mabinogi.py
    ├── custom_mabinogi.yaml → ../general_model/a18/custom_mabinogi.yaml
    └── modules/                      ← shared architecture modules
```

To switch versions: `bash scripts/ocr/switch_model.sh general a18`
To deploy after training: `bash scripts/ocr/general_model/deploy.sh <version>`

---

## 5. Text Correction

**File:** `backend/lib/text_corrector.py`
**Dictionaries:** `data/dictionary/` — one `.txt` file per section (e.g. `reforge.txt`, `tooltip_general.txt`). File stem maps to section name for targeted lookup.

After OCR, each recognized string is fuzzy-matched against game dictionaries using RapidFuzz (`fuzz.ratio`, cutoff 80). This corrects common OCR errors like character substitutions (`속` → `색`) that are visually plausible but semantically wrong in the game context.

---

## 6. Custom Model Training

The OCR model is trained on synthetically generated images that match real tooltip line crops.

### Training pipeline

All OCR scripts are under `scripts/ocr/`, organized by model type. Each accepts `--version <ver>` (defaults to active version from symlink). Training parameters live in each version's `training_config.yaml`.

```
scripts/ocr/general_model/
  generate_training_data.py — render template lines with Mabinogi font
                              tight-crop to ink bounds + proportional padding
                              binary only (0 and 255), no augmentation
    ↓
skills/ocr-trainer/scripts/
  create_lmdb_dataset.py    — convert image/label pairs to LMDB format
    ↓
scripts/ocr/general_model/
  train.py                  — fine-tune TPS-ResNet-BiLSTM-CTC
                              reads params from version's training_config.yaml
    ↓
scripts/v3/
  test_v3_pipeline.py       — evaluate on GT images (segment-first pipeline)
                              always run with --normalize --gt-suffix _expected.txt
```

### Synthetic image requirements

- **Font:** `data/fonts/mabinogi_classic.ttf` (actual game font)
- **Font sizes:** `[10, 10, 10, 11, 11, 11]` → produces h=14-15px crops (dominant)
- **Tight crop:** width matches text extent + padding, not a fixed canvas
- **Binary:** strictly 0 and 255 after thresholding
- **No augmentation:** no blur, noise, or morphological ops
- **Quality gates:** `min_ink_ratio=2%`, `min_width=10px`, `min_height=8px`

### Accuracy benchmark (as of Attempt 14)

Evaluated on 5 real tooltip images, 230 expected lines:

| Image | Exact match | Char accuracy |
|---|---|---|
| lightarmor | 11/71 | 79.0% |
| titan_blade | 18/84 | 77.9% |
| dropbell | 9/35 | 74.0% |
| lobe | 4/19 | 69.6% |
| captain_suit | 3/21 | 62.1% |
| **Total** | **45/230 (19.6%)** | **75.5%** |

---

## 7. User-Correction Training Pipeline

Users edit OCR-recognized text in the frontend. Those edits are captured as training data for model improvement.

### Data flow

```
Upload screenshot
    │
    ▼
/upload-item-v3 → session_id=uuid4()
    │  saves per-line crop PNGs to tmp/ocr_crops/{session_id}/
    │  saves ocr_results.json (original text per line, for server-side diffing)
    │  tags each line with global_index
    │  returns { session_id, sections, all_lines }
    │
    ▼
Frontend: user edits text, clicks "Register Item"
    │  POST /register-item { session_id, name, price, category, lines[] }
    │  (lines = flat array of { global_index, text } from all sections)
    │
    ▼
Backend (trade/router.py):
    │  1. Loads ocr_results.json from session dir
    │  2. Diffs submitted lines against originals (server-side)
    │  3. For each changed line: charset-validate, copy crop, insert DB row
    │  4. Register item (TODO: persistent item storage)
    │  Returns { registered, name, corrections_saved }
    │
    ▼
(Admin) GET /admin/corrections/list?status=pending → review
(Admin) POST /admin/corrections/approve/{id} → status=approved
    │
    ▼
(Manual) merge_corrections.py → new version with synthetic + corrections
    │
    ▼
(Manual) retrain_with_corrections.sh → LMDB + resume training
    │
    ▼
(Manual) eval_compare.py → A/B gate → deploy if no regression
```

Corrections are captured implicitly — no separate submit step for the user.

### Crop persistence

**Files:** `backend/lib/v3_pipeline.py`, `backend/lib/mabinogi_tooltip_parser.py`

During `/upload-item-v3`, when `save_crops=True`:
- `run_v3_pipeline()` generates a `session_id` (UUID4) and creates `tmp/ocr_crops/{session_id}/`
- `_ocr_grouped_lines()` attaches the grayscale line crop as `line['_crop']` (numpy array)
- After all lines are assembled and tagged with `global_index`, crops are saved as `{global_index:03d}.png`
- The `_crop` key is removed from lines before returning to the caller
- `ocr_results.json` is written with original text, confidence, section, ocr_model, fm_applied per line

Temp crops are cleaned by `scripts/ocr/cleanup_crops.py` (removes dirs older than 24h with no DB corrections).

### Database schema

**Table:** `ocr_corrections` (migration: `infra/database/init/002_corrections.sql`)

| Column | Type | Description |
|--------|------|-------------|
| session_id | TEXT | Links to crop directory |
| line_index | SMALLINT | global_index from the OCR pipeline |
| original_text | TEXT | OCR output (after FM) |
| corrected_text | TEXT | User-edited text |
| confidence | NUMERIC | OCR confidence at recognition time |
| section | TEXT | Section label (enchant, reforge, etc.) |
| ocr_model | TEXT | Which model won (mabinogi_classic, nanum_gothic_bold) |
| fm_applied | BOOLEAN | Whether FM was applied to this line |
| status | TEXT | `pending` → `approved` → `trained` |
| image_filename | TEXT | Crop filename (e.g. `003.png`) |
| trained_version | TEXT | Set when merged into a training version |

### API endpoints

| Endpoint | Method | File | Description |
|----------|--------|------|-------------|
| `/register-item` | POST | `backend/trade/router.py` | Register item + implicitly capture corrections |
| `/admin/corrections/list` | GET | `backend/admin/router.py` | Query by status, paginated |
| `/admin/corrections/approve/{id}` | POST | `backend/admin/router.py` | `pending` → `approved` |

Charset gate (in `/register-item`): lines with characters not in the union of both font models' `unique_chars.txt` are silently skipped (not saved as corrections).

### Training scripts

| Script | Purpose |
|--------|---------|
| `scripts/ocr/merge_corrections.py` | Query approved corrections, charset-validate, copy base version's synthetic data + correction crops (×N duplication), write `gt.txt`, update DB to `trained` |
| `scripts/ocr/retrain_with_corrections.sh` | Wrapper: merge → create_model_config → create_lmdb → print `nohup train.py --resume` command |
| `scripts/ocr/eval_compare.py` | Switch model versions, run `test_v3_pipeline.py --json` on each, print comparison table, gate on exact matches + char accuracy |
| `scripts/ocr/cleanup_crops.py` | Remove `tmp/ocr_crops/` dirs older than N hours with no DB corrections |

### Frontend

**File:** `frontend/src/pages/sell.jsx`

After OCR scan, `sessionId` is stored from response. On "Register Item" submit, the frontend collects all lines with `global_index` + current `text` from `formData.sections` and POSTs to `/register-item`. No client-side diffing — the server handles it.

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser (sell.jsx)                                             │
│  PNG screenshot → grayscale → threshold=80 → binary PNG        │
└───────────────────────────┬─────────────────────────────────────┘
                            │ POST /upload-item-v2
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  MabinogiTooltipParser                                          │
│                                                                 │
│  binary image                                                   │
│     → TooltipLineSplitter.detect_text_lines()                  │
│        → list of (x, y, w, h) bounding boxes                   │
│     → extract_lines()  → list of cropped line images           │
│     → horizontal sub-split where gaps > threshold              │
│                                                                 │
│  for each crop:                                                 │
│     if color part sub-segment → regex parse RGB                │
│     else → EasyOCR.recognize() → raw text + confidence         │
│          → TextCorrector.correct() → corrected text            │
│                                                                 │
│  → categorize lines into sections (mabinogi_tooltip.yaml)      │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
              Structured JSON response
              {
                item_name, item_type, enchant,
                item_mod, item_grade, item_color,
                all_lines, confidence, ...
              }
```
