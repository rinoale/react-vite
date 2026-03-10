# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Mabinogi (MMORPG) item trading marketplace with OCR-powered item registration. Users upload a screenshot of an in-game item tooltip, and the system automatically extracts item details using a custom-trained EasyOCR model.

**Current performance:** 398/557 exact, 94.5% char accuracy, FM=242 (18 images).

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
pip install -r backend/requirements.txt              # Web server only (no OCR/ML)
pip install -r backend/requirements-worker.txt       # Worker (includes OCR/ML packages)
cd backend && uvicorn main:app --reload --port 8000  # API at http://localhost:8000
python -m pytest tests/ -v     # Run pytest (262 tests, from project root)
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
    |     +-- ItemMod: color mask (pink) -> content_ng_reader -> regex R/S + level 1-8
    |     +-- Erg: @plain_lines_only -> regex 등급 S/A/B + level/max_level
    |     +-- SetItem: @filter_prefix('bullet') -> regex {name}(강화|증가) +N -> FM(cutoff=90)
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

**Backend module layout:**
```
backend/lib/
+-- pipeline/
|   +-- v3.py                    # V3 pipeline orchestrator (init, segment, run)
|   +-- segmenter.py             # Orange header detection, segmentation, header OCR
|   +-- tooltip_parsers/
|   |   +-- mabinogi.py          # Section-aware parser, structured builders
|   +-- line_split/
|   |   +-- line_splitter.py     # Horizontal projection line detection
|   |   +-- mabinogi_tooltip_splitter.py  # Mabinogi-specific splitter subclass
|   |   +-- line_processing.py   # Group/merge/classify utilities
|   |   +-- line_merge.py        # Continuation merge, excess line absorption
|   +-- section_handlers/        # Per-section handler classes
|       +-- pre_header.py        # PreHeaderHandler: dual-font OCR, item name parsing
|       +-- enchant.py           # EnchantHandler: white-mask bands, Dullahan FM
|       +-- reforge.py           # ReforgeHandler: prefix detection, level parsing
|       +-- color.py             # ColorHandler: regex RGB parse (no OCR)
|       +-- item_attrs.py        # ItemAttrsHandler: structured key-value extraction
|       +-- item_mod.py          # ItemModHandler: pink mask → content_ng_reader → R/S + level
|       +-- erg.py               # ErgHandler: @plain_lines_only → regex grade/level
|       +-- set_item.py          # SetItemHandler: @filter_prefix('bullet') → FM set names
|       +-- default.py           # DefaultHandler: generic sections
|       +-- _base.py             # BaseHandler: template pattern base class
|       +-- _helpers.py          # Shared: BT.601 binary, header prepend, decorators
|       +-- _ocr.py              # Shared: OCR grouped lines, enchant headers
+-- text_processors/
|   +-- common.py                # TextCorrector base: dictionary loading, correct()
|   +-- mabinogi.py              # MabinogiTextCorrector: Dullahan, FM, item name parsing
+-- image_processors/
|   +-- prefix_detector.py       # Bullet/subbullet detection via color masks
|   +-- mabinogi_processor.py    # Enchant line classification, oreo_flip
|   +-- shape_walker.py          # Shape recognition (DOT, NIEUN)
+-- patches/
|   +-- easyocr_imgw.py          # EasyOCR inference patch (double-resize fix, fixed imgW)
+-- legacy/
|   +-- dual_reader.py           # DualReader (legacy, superseded by font-matched routing)
+-- storage/
|   +-- __init__.py              # re-export FileStorage, get_storage
|   +-- base.py                  # FileStorage ABC
|   +-- local.py                 # LocalFileStorage (disk, dev)
|   +-- r2.py                    # R2FileStorage (Cloudflare R2 via boto3)
|   +-- connection.py            # get_storage() factory (keyed instance cache)
+-- utils/
    +-- log.py                   # Logging + @timed decorator
```

**Section Handlers** (`backend/lib/pipeline/section_handlers/`):
- Each section processed end-to-end by its handler (image process -> OCR -> FM -> structured rebuild)
- `get_handler(section_key)` dispatches to: `EnchantHandler`, `ReforgeHandler`, `ColorHandler`, `ItemAttrsHandler`, `ItemModHandler`, `ErgHandler`, `SetItemHandler`, `DefaultHandler`
- `PreHeaderHandler` runs first (produces `parsed_item_name` for enchant P1)
- No `all_lines` flat list -- lines identified by `(section, line_index)` instead of `global_index`

**Tooltip Segmenter** (`backend/lib/pipeline/segmenter.py`):
- `detect_headers()`: Orange-anchored header detection, 26/26 themes
- `classify_header()`: Header OCR + fuzzy match to section label (9 labels, cutoff 50)
- `segment_and_tag()`: Segment + classify in one pass

**Section-Aware Parser** (`backend/lib/pipeline/tooltip_parsers/mabinogi.py`):
- Config: `configs/mabinogi_tooltip.yaml` -- sections, header patterns, parse modes, skip flags
- `build_enchant_structured(lines)` / `build_reforge_structured(lines)`: Rebuild structured data from FM-corrected lines

**Line Splitter** (`backend/lib/pipeline/line_split/line_splitter.py`):
- Horizontal projection profiling, auto-detects background polarity
- `_remove_borders()`: Masks narrow (<=3px) high-density vertical column runs
- **Greedy Group Merging** (`detect_centered_lines`): no gap tolerance, no `_has_internal_gap`, no `_split_tall_block`. Finds raw ink groups, greedily absorbs groups until span reaches `min_height=13`, centers window on content
- `horizontal_split_factor`: 3 default, 1.5 for Mabinogi color parts
- Horizontal padding only: `pad_x = max(2, h//3)` — no vertical padding (centered windows provide margin)
- Parameters: `min_height=13, min_width=10`
- `_add_line()` filters thin vertical borders and wide horizontal bars

**Line Processing** (`backend/lib/pipeline/line_split/line_processing.py`):
- `merge_group_bounds()`, `trim_outlier_tail()`, `promote_grey_by_prefix()`
- `determine_enchant_slots()`, `merge_continuations()`, `count_effects_per_header()`

**Inference Patch** (`backend/lib/patches/easyocr_imgw.py`):
- `patch_reader_imgw()`: Fixes two EasyOCR issues:
  1. **Double-dip resize**: EasyOCR resized twice (cv2.LANCZOS then PIL.BICUBIC); training only once. Patch replaces `get_image_list()` with `_crop_boxes()`. **+37 exact matches, no retraining.**
  2. **Fixed imgW**: Uses yaml's fixed imgW (200) instead of dynamic per-image width
- **NEVER bypass this patch** -- unpatched `recognize()` suffers double-dip degradation
- **Verification rule**: OCR-ing training images must give ~100% accuracy. If not, preprocessing mismatch -- investigate before retraining.

**Prefix Detector** (`backend/lib/image_processors/prefix_detector.py`):
- Detects bullet (`·`) and subbullet (`ㄴ`) prefixes via color masks (blue RGB(74,149,238), red RGB(255,103,103), grey RGB(128,128,128), light grey RGB(167,167,167), white RGB(255,255,255))
- Column projection state machine: [small ink cluster] -> [gap] -> [main text]
- Both bullet and subbullet prefixes are sliced from line crops before OCR in all content sections
- Zero false positives on 26 theme images

### Key Algorithms (details in `documents/CORE_LOGIC.md`)

**Dullahan** (`text_processors/mabinogi.py` -> `do_dullahan()`): Effect-guided enchant header correction. When header OCR is garbled (e.g., `폭단` instead of `성단`), scores all DB entries by name similarity, then uses effect lines to break ties. 802/1172 enchants have unique effect signatures.

**Number-Normalized FM** (`text_processors/mabinogi.py` -> `correct_normalized()`): Extracts numbers from OCR text, replaces with N, matches against N-normalized dictionary, re-injects OCR numbers. Section-specific transforms (reforge strips level suffix, enchant extracts name).

**Dual-Form Matching**: Enchant effects matched against both `effects_norm` (effect-only) and `effects_full_norm` (condition+effect). Pick higher `fuzz.ratio` score. Full form wins when `merge_fragments` rejoins wrapped lines. Uses `fuzz.ratio` (not `partial_ratio`) to prevent short-entry inflation.

**Item Name Parsing** (`text_processors/mabinogi.py` -> `parse_item_name()`): Right-to-left anchor: strip holywater (fuzzy >=70) -> strip ego keyword -> anchor item_name from right against item_name.txt -> split remaining into enchant prefix/suffix.

**P1/P2/P3 Enchant Resolution** (`pipeline/v3.py` -> `_step_resolve_enchant()`): P1 (item name parsing) > P2 (raw header OCR) > P3 (Dullahan). Winner's DB entry -> `build_templated_effects()` injects OCR numbers into DB templates.

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

**DualReader** (`backend/lib/legacy/dual_reader.py`): Legacy wrapper for two font-specific readers. Superseded by font-matched routing in V3 (pre_header detects font, pipeline selects matching reader).

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
+-- generate_enchant_dicts.py         # Generate enchant_slot_header.txt from YAML
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
- `imgW: 200` -- Fixed via `patches/easyocr_imgw.py` patch. Dynamic imgW causes garbage output.
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
- **Dynamic imgW pitfall**: `recognize()` computes `max_width = ceil(w/h) * 32` per image (576-1056px). Fixed by `patches/easyocr_imgw.py`.

## Testing

### Unit Tests
```bash
python -m pytest tests/ -v                # Backend (262 tests) — from project root
cd frontend && npm test                   # Frontend (29 tests) — vitest
```

**Backend (pytest):** Config in `pyproject.toml`, fixtures in `tests/conftest.py`. Tests cover `line_processing`, `line_merge`, `prefix_detector`, `line_splitter`, `text_corrector`, `tooltip_parser`, `shape_walker`, `parse_effect_number`. No GPU/DB/images needed — pure functions + synthetic numpy arrays.

**Frontend (vitest):** Config in `frontend/vitest.config.js`, setup in `frontend/test-setup.js` (mocks i18n + window globals). Tests cover `gameItems`, `examineResult`, `SectionCard`, `ConfigSearchInput`, `EnchantSection`, `ReforgeSection`.

### Pipeline Eval (end-to-end, requires GPU + sample images)
- `scripts/v3/test_v3_pipeline.py` -- V3 pipeline test on original color screenshots. **Primary eval.**
- `scripts/legacy/test_v2_pipeline.py` -- Legacy v2 test. **Always run with `--normalize --gt-suffix _expected.txt`** -- without these flags scores are artificially low.
- Ground truth in `data/sample_images/`: `*.txt` (full GT), `*_expected.txt` (expected OCR output), `*_gt_candidate.txt` (pipeline candidates)

## Frontend

### Routes (Trade)
- `/` -> `Marketplace` -- item grid with recommendations
- `/sell` -> `Sell` -- image upload + OCR item registration
- `/listing/:id` -> `ListingDetail` -- single listing view
- `/my-listings` -> `MyListings` -- user's own listings with status management
- `/login` -> `Login` -- Discord OAuth login
- `/navigate` -> `Navigate` -- Leaflet map (experimental)
- `/image_process` -> `ImageProcess` -- OCR training data preparation tool

### Routes (Admin)
- `/source_of_truth/*` -- Enchants, Effects, Reforge/Echostone/Murias options, Game Items
- `/trade/*` -- Listings, Corrections, Tags
- `/system/*` -- Jobs, Users, Roles, Feature Flags, Usage (R2 + OCI)

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
| FM dictionaries | `data/dictionary/*.txt` | Runtime FM: `reforge.txt`, `tooltip_general.txt`, `item_name.txt`, `enchant_prefix.txt`, `enchant_suffix.txt` |
| Training words | `data/train_words/*.txt` | Training-only: `enchant_slot_header.txt`, `item_type_armor.txt`, `item_type_melee.txt`, `special_weight_item_name.txt` |
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
- `data/source_of_truth/enchant.yaml` is the canonical enchant data source; `data/train_words/enchant_slot_header.txt` is generated from it via `scripts/ocr/generate_enchant_dicts.py`. Enchant effects for training come directly from enchant.yaml via `training_templates.py`.

## Design Principles

**Generalize, don't patch.** When fixing an issue, the solution must work across all cases -- not just the failing one. Adjusting a threshold or adding special-case logic for one image may break others. Always verify against the full test set.

**Encapsulate and modularize business logic.** Logic should be structured so it can be inspected via API spec and replaced with another language implementation immediately. Keep business logic language-agnostic and decoupled from framework specifics.

**Favor decorators for cross-cutting concerns.** Always consider whether repeated code patterns (timing, logging, validation, retry, caching, etc.) can be extracted into a decorator to reduce duplication.
