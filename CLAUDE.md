# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Mabinogi (MMORPG) item trading marketplace with OCR-powered item registration. Users upload a screenshot of an in-game item tooltip, and the system automatically extracts item details using a custom-trained EasyOCR model.

**Current performance:** 151/309 exact, 84.7% char accuracy, FM=60 (19 images, 7 with GT).

**Eval command:** `python3 scripts/v3/test_v3_pipeline.py -q 'data/sample_images/*_original.png'`

## Development Commands

### Frontend (React + Vite)
```bash
npm install          # Install dependencies
npm run dev          # Dev server at http://localhost:5173
npm run build        # Production build to dist/
npm run lint         # ESLint (flat config, React hooks + refresh plugins)
npm run preview      # Preview production build
cd frontend && npm test        # Run vitest (29 tests)
cd frontend && npm run test:watch  # Watch mode
```

### Backend (Python FastAPI)
```bash
pip install -r backend/requirements.txt
cd backend && uvicorn main:app --reload --port 8000   # API at http://localhost:8000
python -m pytest tests/ -v     # Run pytest (58 tests, from project root)
```

### Database (PostgreSQL via Docker)
```bash
docker compose up -d db
docker compose logs -f db
```

Connection defaults (local dev): host `localhost`, port `5432`, db `mabinogi`, user `mabinogi`, password `mabinogi`.

Dictionary import command:
```bash
python3 scripts/db/import_dictionaries.py
```

## Architecture

### V3 OCR Pipeline (active)

Determines section labels BEFORE running content OCR, eliminating cascade section-detection failures.

```
Original color screenshot (BGR, any resolution)
    |
    +-- Stage 1: Border Detection + Crop -- RGB(132,132,132) pixel scan -> crop to tooltip
    +-- Stage 2: Orange Header Detection -- orange mask (R>150, 50<G<180, B<80) + black-square expansion
    |     -> list of header bands; 26/26 theme images, 0 false positives
    +-- Stage 3: Segmentation -- pre_header + N header+content pairs
    +-- Stage 4: Header OCR -- BT.601 + threshold=50 -> custom_header model -> fuzzy match
    |     -> section label per segment (enchant, reforge, erg, ...)
    +-- Stage 5: Content OCR per segment:
    |     +-- Enchant: oreo_flip (white mask) -> slot header bands -> classify (header/effect/grey)
    |     |     Headers -> custom_enchant_header model; Effects -> DualReader; Grey -> skipped
    |     +-- Reforge: BT.601 + threshold=80 -> DualReader; sub-line detection by x-offset indent
    |     +-- Color: regex parse RGB from sub-segments (no OCR)
    |     +-- All others: BT.601 + threshold=80 -> DualReader
    +-- Stage 6a: Item Name Parsing -- parse pre_header into enchant prefix/suffix/item_name
    |     -> P1 enchant entries available for effect dictionary selection
    +-- Stage 6b: Fuzzy Matching (FM) -- section-aware text correction
    |     +-- Enchant headers: Dullahan algorithm (effect-guided header correction)
    |     +-- Enchant effects: P1 entry prioritized, Dullahan fallback
    |     +-- Reforge: correct_normalized (number-normalized, level suffix stripped)
    |     +-- Other: correct_normalized (section dictionary or combined)
    +-- Stage 7: Structured Rebuild -- build_enchant_structured / build_reforge_structured
    +-- Stage 8: Final Enchant Header Competition -- P1/P2/P3 resolution -> winner + templated effects
```

**Legacy v2** (`/upload-item-v2`): Frontend preprocesses (BT.601 + threshold=80 -> binary PNG), backend does line split -> OCR -> post-hoc section detection -> FM. Section labels assigned from OCR output -- cascade failure if header word is garbled.

**Why not CRAFT?** CRAFT fragments lines, merges adjacent text, and misses entire sections on structured tooltip layouts. `TooltipLineSplitter` achieves perfect detection (244 total lines across 5 images).

### Key Backend Components

**Tooltip Segmenter** (`backend/lib/tooltip_segmenter.py`):
- `detect_headers()`: Orange-anchored header detection, 26/26 themes
- `classify_header()`: Header OCR + fuzzy match to section label (9 labels, cutoff 50)
- `build_segments()`: Pair headers with content regions

**Section-Aware Parser** (`backend/lib/mabinogi_tooltip_parser.py`):
- Extends `TooltipLineSplitter` with Mabinogi-specific section categorization
- Config: `configs/mabinogi_tooltip.yaml` -- sections, header patterns, parse modes, skip flags
- Color parts (`parse_mode: color_parts`): RGB parsed via regex, bypassing OCR
- Enchant (`parse_mode: enchant_options`): Structured as `prefix`/`suffix` slot dicts with `name`, `rank`, `effects[]`
- Reforge (`parse_mode: reforge_options`): Options include `option_name`/`option_level` unified fields
- `build_enchant_structured(lines)` / `build_reforge_structured(lines)`: Rebuild structured data from FM-corrected lines

**Line Splitter** (`backend/lib/tooltip_line_splitter.py`):
- Horizontal projection profiling, auto-detects background polarity
- `_remove_borders()`: Masks narrow (<=3px) high-density vertical column runs
- Gap tolerance=2 rows, `_rescue_gaps()` two-pass detection for sparse lines
- `_split_tall_block()`, `_has_internal_gap()` for merged blocks (1+ consecutive zero rows triggers split)
- `horizontal_split_factor`: 3 default, 1.5 for Mabinogi color parts
- Proportional padding: `pad_x = max(2, h//3)`, `pad_y = max(1, h//5)`
- Parameters: `min_height=6, max_height=25, min_width=10`
- `_add_line()` filters thin vertical borders and wide horizontal bars

**Line Processing** (`backend/lib/line_processing.py`):
- `merge_group_bounds()`, `trim_outlier_tail()`, `promote_grey_by_prefix()`
- `determine_enchant_slots()`, `merge_continuations()`, `count_effects_per_header()`

**Inference Patch** (`backend/lib/ocr_utils.py`):
- `patch_reader_imgw()`: Fixes two EasyOCR issues:
  1. **Double-dip resize**: EasyOCR resized twice (cv2.LANCZOS then PIL.BICUBIC); training only once. Patch replaces `get_image_list()` with `_crop_boxes()`. **+37 exact matches, no retraining.**
  2. **Fixed imgW**: Uses yaml's fixed imgW (200) instead of dynamic per-image width
- **NEVER bypass this patch** -- unpatched `recognize()` suffers double-dip degradation
- **Verification rule**: OCR-ing training images must give ~100% accuracy. If not, preprocessing mismatch -- investigate before retraining.

**Prefix Detector** (`backend/lib/prefix_detector.py`):
- Detects bullet (`·`) and subbullet (`ㄴ`) prefixes via color masks (blue RGB(74,149,238), red RGB(255,103,103), grey RGB(128,128,128), light grey RGB(167,167,167), white RGB(255,255,255))
- Column projection state machine: [small ink cluster] -> [gap] -> [main text]
- Zero false positives on 26 theme images

### Key Algorithms (details in `documents/CORE_LOGIC.md`)

**Dullahan** (`text_corrector.py` -> `do_dullahan()`): Effect-guided enchant header correction. When header OCR is garbled (e.g., `폭단` instead of `성단`), scores all DB entries by name similarity, then uses effect lines to break ties. 802/1172 enchants have unique effect signatures.

**Number-Normalized FM** (`text_corrector.py` -> `correct_normalized()`): Extracts numbers from OCR text, replaces with N, matches against N-normalized dictionary, re-injects OCR numbers. Section-specific transforms (reforge strips level suffix, enchant extracts name).

**Dual-Form Matching**: Enchant effects matched against both `effects_norm` (effect-only) and `effects_full_norm` (condition+effect). Pick higher `fuzz.ratio` score. Full form wins when `merge_fragments` rejoins wrapped lines. Uses `fuzz.ratio` (not `partial_ratio`) to prevent short-entry inflation.

**Item Name Parsing** (`text_corrector.py` -> `parse_item_name()`): Right-to-left anchor: strip holywater (fuzzy >=70) -> strip ego keyword -> anchor item_name from right against item_name.txt -> split remaining into enchant prefix/suffix.

**P1/P2/P3 Enchant Resolution** (`v3_pipeline.py` -> `_step_resolve_enchant()`): P1 (item name parsing) > P2 (raw header OCR) > P3 (Dullahan). Winner's DB entry -> `build_templated_effects()` injects OCR numbers into DB templates.

## Models

All models: `TPS-ResNet-BiLSTM-CTC`, `imgH=32`, `hidden_size=256`.

| Model | Version | Chars | imgW | Font | Purpose |
|-------|---------|-------|------|------|---------|
| Content (mabinogi_classic) | a19 | 554 | 200 | mabinogi_classic.ttf | Font-specific content OCR |
| Content (NanumGothicBold) | a19 | 554 | 200 | NanumGothicBold.ttf | Font-specific content OCR |
| Category Header | v1 | 21 | 128 | (real crops) | 9-label section recognition |
| Enchant Header | v3 | 626 | 256 | synthetic + real | Slot header + rank OCR |
| Preheader (mabinogi_classic) | v1 | 1,181 | 200 | mabinogi_classic.ttf | Item name region OCR |
| Preheader (NanumGothicBold) | v1 | 1,181 | 200 | NanumGothicBold.ttf | Item name region OCR |
| Legacy Content (rollback) | a18 | 554 | 200 | both fonts mixed | Combined content OCR |

**DualReader** (`backend/lib/dual_reader.py`): Wraps two font-specific readers. Both run `recognize()` per line; highest-confidence result wins. Transparent to parser. Falls back to legacy single model if font-specific models aren't deployed.

**Model versioning**: `backend/ocr/{model_type}/{version}/` -- self-contained with `.pth`, `.py`, `.yaml`, `training_config.yaml`, charset, training data. Symlinks at `backend/ocr/models/` point to active versions.

**Active versions**: general=a18 (legacy), general_mabinogi_classic=v1, general_nanum_gothic_bold=a19, category_header=v1, enchant_header=v3, preheader_mabinogi_classic=v1, preheader_nanum_gothic=v1.

**Switch**: `bash scripts/ocr/switch_model.sh <type> <version>`
**Deploy**: `bash scripts/ocr/<model_type>/deploy.sh <version>`

Full model details: [documents/OCR_MODELS.md](documents/OCR_MODELS.md)

## Training Pipeline

All scripts run from **project root**. All accept `--version <ver>` (defaults to active symlink). Training config lives in each version folder (e.g. `backend/ocr/general_mabinogi_classic_model/a19/training_config.yaml`).

### OCR Script Layout
```
scripts/ocr/
+-- general_model/                    # Legacy combined content OCR
+-- general_mabinogi_classic_model/   # mabinogi_classic font-specific content OCR
+-- general_nanum_gothic_bold_model/  # NanumGothicBold font-specific content OCR
+-- category_header_model/            # Category header OCR
+-- enchant_header_model/             # Enchant header OCR
+-- switch_model.sh                   # Switch active model version
+-- generate_enchant_dicts.py         # Generate enchant dictionaries from YAML
+-- lib/
    +-- model_version.py              # Shared version resolution
    +-- render_utils.py               # Game-like rendering pipeline
    +-- training_templates.py         # Shared template generators
```

### Full Pipeline (font-specific models)
```bash
MODEL=general_mabinogi_classic_model  # or general_nanum_gothic_bold_model
VER=a19

# Step 1: Generate synthetic training images
python3 scripts/ocr/${MODEL}/generate_training_data.py --version $VER

# Step 2: Generate model config (required when imgW/imgH/charset change)
python3 scripts/ocr/${MODEL}/create_model_config.py --version $VER

# Step 3: Create LMDB dataset
python3 skills/ocr-trainer/scripts/create_lmdb_dataset.py \
  --input backend/ocr/${MODEL}/$VER/train_data \
  --output backend/ocr/${MODEL}/$VER/train_data_lmdb

# Step 4: Train (nohup required -- avoid OOM kills)
nohup python3 -u scripts/ocr/${MODEL}/train.py --version $VER > logs/training_${MODEL}.log 2>&1 &

# Step 5: Deploy (copy model + update symlinks)
bash scripts/ocr/${MODEL}/deploy.sh $VER

# Step 6: Validate
python3 scripts/v3/test_v3_pipeline.py 'data/sample_images/*_original.png'
```

### Training Configuration Gotchas
- `imgW: 200` -- Fixed via `ocr_utils.py` patch. Dynamic imgW causes garbage output.
- `workers: 0` -- Required. LMDB can't be pickled for multiprocessing.
- `sensitive: true` -- Required. Prevents lowercasing (needed for R,G,B,L,A-F).
- `PAD: true` -- Required. Matches EasyOCR's hardcoded `keep_ratio_with_pad=True`.
- `batch_size: 64` -- Default 192 causes extreme slowdown on 8GB VRAM.
- `batch_max_length: 55` -- Longest labels are ~55 chars.
- **Critical rule:** When changing `imgH`, `imgW`, or any `model:` param in `training_config.yaml`, you **MUST** re-run `create_model_config.py`. Mismatched `imgW` causes TPS layer shape errors.
- Training must run independently (not as subprocess of Claude Code) to avoid OOM kills.

### Training Data Requirements
Synthetic training images must match real line crops from the splitter:
- **Rendering pipeline** (`scripts/ocr/lib/render_utils.py`): Dark bg (20,20,20) + bright text (220,220,220) at font 16-18 -> BT.601 grayscale -> threshold 80 +/- random(-10,+40) BINARY_INV -> tight-crop to ink bounds + splitter padding -> downscale to ~14-15px -> re-threshold to strict binary (0/255)
- **Tight-crop to ink bounds**: NOT full 260px canvas. Full-canvas causes hallucination.
- **Padding**: `pad_y = max(1, text_h // 5)`, `pad_x = max(2, text_h // 3)`
- **Binary only**: Pixel values strictly 0 and 255. Re-threshold after any resize.
- **No augmentation**: No blur, erode/dilate, or noise. Clean binary only.
- **Quality gates**: `MIN_INK_RATIO=0.02`, `MIN_WIDTH=10`, `MIN_HEIGHT=8`
- **Content**: Template-based lines from `scripts/ocr/lib/training_templates.py` + GT lines verbatim
- **Fonts**: Each font-specific model uses only its font

### EasyOCR Internals
- `recognize(img_grey, horizontal_list=[[0, w, 0, h]], free_list=[], reformat=False)` = recognition only on pre-cropped images
- `recognition.py` lines 199, 213: `keep_ratio_with_pad=True` is hardcoded; `PAD` in yaml is ignored
- Must pass `free_list=[]` (not None) when `horizontal_list` is set, otherwise TypeError
- **Dynamic imgW pitfall**: `recognize()` computes `max_width = ceil(w/h) * 32` per image (576-1056px). Fixed by `ocr_utils.py`.

## Testing

### Unit Tests
```bash
python -m pytest tests/ -v                # Backend (58 tests) — from project root
cd frontend && npm test                   # Frontend (29 tests) — vitest
```

**Backend (pytest):** Config in `pyproject.toml`, fixtures in `tests/conftest.py`. Tests cover `line_processing`, `line_merge`, `prefix_detector`, `line_splitter`, `text_corrector`, `mabinogi_tooltip_parser`. No GPU/DB/images needed — pure functions + synthetic numpy arrays.

**Frontend (vitest):** Config in `frontend/vitest.config.js`, setup in `frontend/test-setup.js` (mocks i18n + window globals). Tests cover `gameItems`, `examineResult`, `SectionCard`, `ConfigSearchInput`, `EnchantSection`, `ReforgeSection`.

### Pipeline Eval (end-to-end, requires GPU + sample images)
- `scripts/v3/test_v3_pipeline.py` -- V3 pipeline test on original color screenshots. **Primary eval.**
- `scripts/v2/test_v2_pipeline.py` -- Legacy v2 test. **Always run with `--normalize --gt-suffix _expected.txt`** -- without these flags scores are artificially low.
- `scripts/v2/line_split/test_line_splitter.py <image> <output_dir>` -- Visual line detection verification
- `scripts/v2/ocr/regenerate_gt.py` -- Regenerate GT candidates from parser output
- Ground truth in `data/sample_images/`: `*.txt` (full GT), `*_expected.txt` (expected OCR output), `*_gt_candidate.txt` (pipeline candidates)

## Frontend

### Routes
- `/` -> `Marketplace` -- item grid with recommendations
- `/sell` -> `Sell` -- image upload + OCR item registration
- `/navigate` -> `Navigate` -- Leaflet map (experimental)
- `/image_process` -> `ImageProcess` -- OCR training data preparation tool

### Monorepo Structure
```
frontend/packages/
+-- shared/   # @mabi/shared -- raw JSX source, no build step
+-- trade/    # @mabi/trade -- Marketplace + Sell (port 5173)
+-- admin/    # @mabi/admin -- Admin Dashboard (port 5174)
+-- misc/     # @mabi/misc -- Navigate + Image Process (port 5175)
```

### Recommendation System
- `backend/lib/recommendation.py`: TF-IDF vectorization + cosine similarity
- Endpoints: `GET /recommend/item/{id}`, `POST /recommend/user` (history-based)

## Data Sources

| Source | Path | Purpose |
|--------|------|---------|
| `enchant.yaml` | `data/source_of_truth/enchant.yaml` | Canonical enchant DB: 1,172 entries with slot/name/rank/effects |
| Section dictionaries | `data/dictionary/*.txt` | Per-section FM dictionaries |
| Tooltip config | `configs/mabinogi_tooltip.yaml` | Section definitions, header patterns, parse modes, detection params |
| GT images | `data/sample_images/*_original.png` | Test images with ground truth `.txt` files |

## Documentation

| Document | Contents |
|---|---|
| `documents/ARCHITECTURE.md` | Full V3 pipeline stages (1-8) with algorithms |
| `documents/OCR_MODELS.md` | Model inventory, symlink layout, DualReader, inference patch |
| `documents/CORE_LOGIC.md` | Algorithm details: Dullahan, FM, item name parsing, etc. |
| `documents/STRATEGY_MABINOGI.md` | Design decisions D1-D11 with porting guides |
| `documents/API_SPEC.md` | API contract and response schema |
| `documents/IMAGE_PROCESS.md` | Image processing technique catalog |
| `OCR_TRAINING_HISTORY.md` | Per-attempt accuracy results and analysis |
| `OCR_ISSUES.md` | Resolved issues and current blockers |
| `TASKS.md` | Consolidated task tracker (backend + frontend) |

## Documentation Policy

**Always update documentation when a notable change occurs.** This includes:
- New training attempts or results -> update `OCR_TRAINING_HISTORY.md`
- Issue status changes (resolved/new) -> update `OCR_ISSUES.md`
- Architecture or pipeline changes -> update `documents/ARCHITECTURE.md` and this file
- New findings, insights, or root cause analyses -> update the relevant doc

## Key Constraints

- Active API path is v3 (`/upload-item-v3`) with original color input and segment-first processing. Legacy v2 exists for comparison.
- CRAFT is not used; `TooltipLineSplitter` + `recognize()` is used for line-level recognition in both v2 and v3.
- EasyOCR custom model can only recognize characters in the active version's `unique_chars.txt`; missing chars will never be output.
- EasyOCR always uses `keep_ratio_with_pad=True` during inference (hardcoded). Training must use `--PAD` to match.
- Item database is currently mocked in `backend/lib/recommendation.py` (`ITEMS_DB`); no persistent storage yet.
- The `data/` directory (fonts, dictionary, sample images, source_of_truth) is not fully committed to git.
- `data/source_of_truth/enchant.yaml` is the canonical enchant data source; `data/dictionary/enchant_*.txt` files are generated from it via `scripts/ocr/generate_enchant_dicts.py`.

## Design Principles

**Generalize, don't patch.** When fixing an issue, the solution must work across all cases -- not just the failing one. Adjusting a threshold or adding special-case logic for one image may break others. Always verify against the full test set.

**Encapsulate and modularize business logic.** Logic should be structured so it can be inspected via API spec and replaced with another language implementation immediately. Keep business logic language-agnostic and decoupled from framework specifics.

**Favor decorators for cross-cutting concerns.** Always consider whether repeated code patterns (timing, logging, validation, retry, caching, etc.) can be extracted into a decorator to reduce duplication.
