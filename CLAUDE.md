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

### OCR Training Pipeline
All scripts must be run from the **project root**. Scripts are organized under `scripts/ocr/`:
```
scripts/ocr/
├── general_model/                    # Legacy combined content OCR model scripts
│   ├── generate_training_data.py
│   ├── create_model_config.py
│   ├── train.py
│   └── deploy.sh
├── general_mabinogi_classic_model/   # mabinogi_classic font-specific content OCR
│   ├── generate_training_data.py
│   ├── create_model_config.py
│   ├── train.py
│   └── deploy.sh
├── general_nanum_gothic_bold_model/  # NanumGothicBold font-specific content OCR
│   ├── generate_training_data.py
│   ├── create_model_config.py
│   ├── train.py
│   └── deploy.sh
├── category_header_model/            # Category header OCR model scripts
│   ├── create_lmdb.py
│   └── train.py
├── enchant_header_model/             # Enchant header OCR model scripts
│   ├── generate_training_data.py
│   ├── create_model_config.py
│   ├── create_lmdb.py
│   └── train.py
├── switch_model.sh          # Switch active model version (updates symlinks)
├── generate_enchant_dicts.py # Generate enchant dictionaries from YAML
└── lib/
    ├── model_version.py     # Shared version resolution utility
    ├── render_utils.py      # Game-like rendering pipeline (bright-on-dark → threshold → downscale)
    └── training_templates.py # Shared template generators for training data
```
```bash
python3 scripts/ocr/general_model/generate_training_data.py              # Uses active version (from symlink)
python3 scripts/ocr/general_model/generate_training_data.py --version a19 # Or specify version explicitly
python3 scripts/ocr/general_model/create_model_config.py --version a19   # Generate custom_mabinogi.yaml
python3 skills/ocr-trainer/scripts/create_lmdb_dataset.py \
  --input backend/ocr/general_model/a19/train_data \
  --output backend/ocr/general_model/a19/train_data_lmdb                 # Convert to LMDB for training
python3 scripts/v2/ocr/test_ocr.py                                       # Test OCR on sample image
python3 scripts/v2/line_split/test_line_splitter.py <image> <output_dir>  # Test line splitter visually
```
After training, deploy model with: `bash scripts/ocr/general_model/deploy.sh <version>` (e.g. `a19`).

## Architecture

### OCR Pipeline (core feature)

**New pipeline (segment-first — active):**
Determines section labels BEFORE running content OCR, eliminating cascade section-detection failures.
1. **Backend receives original color screenshot**
2. **Header detection** (`scripts/v3/segmentation/test_segmentation.py` logic): Orange-anchored header detection + black-square boundary expansion. Documented 26/26 theme images in Attempt 17.
3. **Segmentation**: Pre-header region + N header+content pairs. Each content region has a positional section slot.
4. **Header OCR**: Each header crop OCR'd independently (short text, ~10 fixed labels: 세공, 에르그, 인챈트, ...). Assigns canonical section name.
5. **Content OCR per segment**: `TooltipLineSplitter` + EasyOCR `recognize()` per line. FM uses pre-determined section dictionary — no post-hoc header pattern matching in the content stream.
6. **Item name parsing**: Pre-header first line parsed into structured components (holywater, enchant_prefix, enchant_suffix, item_name). Runs BEFORE FM so P1 enchant entries are available for effect dictionary selection.
7. **FM decision**: Server picks best text per line — if FM matches (`fm_score > 0`), `text` is replaced with FM result and `fm_applied=true`. Enchant effect FM prioritizes P1 entry (from item name) over Dullahan (P3) for dictionary selection. No separate `corrected_text` field.
8. **Structured rebuild**: After FM, `build_enchant_structured()` and `build_reforge_structured()` rebuild section data from corrected lines.
9. **Final enchant header competition**: P1 (item name) / P2 (raw header OCR) / P3 (Dullahan) candidates compared; winner determines final enchant identity and templated effects.

**Current production pipeline (old — still in `backend/main.py`):**
1. **Frontend** (`src/pages/sell.jsx`): Browser preprocesses uploaded image (BT.601 grayscale → threshold=80) → binary PNG (black text on white)
2. **Backend** (`backend/main.py` → `POST /upload-item-v2`): Receives binary image, runs:
   - `MabinogiTooltipParser` (`mabinogi_tooltip_parser.py`): Section-aware wrapper categorizing lines into game sections using `configs/mabinogi_tooltip.yaml`
   - `TooltipLineSplitter` (`tooltip_line_splitter.py`): Horizontal projection profiling splits tooltip into line crops.
   - `EasyOCR recognize()` on each line crop: Bypasses CRAFT entirely.
   - `TextCorrector` (`text_corrector.py`): RapidFuzz FM against per-section dictionaries. Section labels assigned post-hoc from OCR output — cascade failure if header word is garbled.
3. Results returned as JSON with structured sections, text, confidence, and line positions. V2 still uses `corrected_text`; V3 uses server-side FM decision (single `text` field).

**Why not CRAFT?** CRAFT is designed for natural scene text detection (signs, labels in photos). On structured tooltip layouts, it fragments lines, merges adjacent text, and misses entire sections. The `TooltipLineSplitter` achieves perfect detection on all test images (244 total lines across 5 images).

### Custom OCR Model
- Architecture: `TPS-ResNet-BiLSTM-CTC` (from `deep-text-recognition-benchmark/`)
- Fonts: `data/fonts/mabinogi_classic.ttf` and `data/fonts/NanumGothicBold.ttf` (game uses both)
- **Dual-model inference** (`backend/lib/dual_reader.py`): Two font-specific models run on every line; highest-confidence result wins. Falls back to single legacy model if font-specific models aren't deployed yet.
- Current deployed content model: a18 (509-char output space, legacy combined). Font-specific models: `custom_mabinogi_classic` and `custom_nanum_gothic_bold` (a19).
- **Model versioning**: Each model type has versioned folders under `backend/ocr/`:
  - `general_model/a18/` — legacy combined content OCR
  - `general_mabinogi_classic_model/a19/` — mabinogi_classic font content OCR
  - `general_nanum_gothic_bold_model/a19/` — NanumGothicBold font content OCR
  - `category_header_model/v1/` — category header OCR
  - `enchant_header_model/v1/` — enchant header OCR
- **Symlinks**: `backend/ocr/models/` contains symlinks to active version folders — all backend code loads from `models/` unchanged. Font-specific models add `custom_mabinogi_classic.*` and `custom_nanum_gothic_bold.*` symlinks alongside the existing `custom_mabinogi.*` (kept for rollback).
- **Version switching**: `bash scripts/ocr/switch_model.sh <type> <version>` — types: `general`, `general_mabinogi_classic`, `general_nanum_gothic_bold`, `category_header`, `enchant_header`
- **Deployment**: `bash scripts/ocr/general_mabinogi_classic_model/deploy.sh <version>` or `bash scripts/ocr/general_nanum_gothic_bold_model/deploy.sh <version>` (copies trained model to version folder + updates symlinks)
- Inference patch: `backend/lib/ocr_utils.py` — fixes EasyOCR's dynamic imgW to use yaml's fixed value
- Training history and known issues: `OCR_TRAINING_HISTORY.md`

### Line Processing (`backend/lib/line_processing.py`)
Reusable line processing functions extracted from `_parse_enchant_with_bands`, composable across segment types:
- `merge_group_bounds(group)`: Merge sub-line dicts into a single bounding box
- `trim_outlier_tail(items, header_test)`: Remove spatially leaked lines at segment bottom via gap outlier detection
- `promote_grey_by_prefix(classifications, prefix_mask)`: Reclassify grey lines with bullet prefix as 'effect'
- `determine_enchant_slots(classifications)`: Derive slot queue ('접두'/'접미') from header count and grey positions
- `merge_continuations(lines, header_field)`: Merge continuation lines (no prefix) into preceding bullet-prefixed anchors. Replaced the legacy count-based `merge_excess_lines` algorithm.
- `count_effects_per_header(lines, header_field)`: Count effect lines per header for metadata

### Excess Line Merging — Legacy (`backend/lib/line_merge.py`)
- Previously contained count-based excess line merging (`merge_excess_lines`, `find_fragment_indices`, `mark_trimmed`, `merge_fragments`, `_stitch_crops`) — compared OCR line count against DB `expected_count` to detect and merge wrapped fragments. Replaced by prefix-based `merge_continuations()` in `line_processing.py`.
- Now only contains `detect_gap_outlier()`, used by `trim_outlier_tail()`.

### Section-Aware Parser (`backend/lib/mabinogi_tooltip_parser.py`)
- Extends `TooltipLineSplitter` with Mabinogi-specific section categorization
- Config: `configs/mabinogi_tooltip.yaml` — defines sections (item_name, item_attrs, enchant, reforge, erg, set_item, item_color, etc.), header patterns, parse modes, skip flags
- Color parts (`parse_mode: color_parts`): RGB values parsed via regex from horizontal sub-segments, bypassing general OCR
- Sections with `skip: true` (flavor_text, shop_price) omitted from output
- `horizontal_split_factor: 1.5` configured for Mabinogi's color part gap sizes
- Enchant section (`parse_mode: enchant_options`): Structured as `prefix`/`suffix` slot dicts (not a flat list). Each slot has `name`, `rank`, and `effects[]` where each effect has `text` and optional `option_name`/`option_level` extracted by `_parse_effect_number()`.
- Reforge section (`parse_mode: reforge_options`): Options include `option_name`/`option_level` as unified fields (aliases for `name`/`level`) for DB storage.
- `build_enchant_structured(lines)` / `build_reforge_structured(lines)`: Rebuild structured data from tagged lines. Called after FM correction in `main.py` to propagate corrected text into section data. See `documents/API_SPEC.md` for full response schema.

### Line Splitter (`backend/lib/tooltip_line_splitter.py`)
Splits tooltip images into individual text line crops using horizontal projection profiling:
- Auto-detects background polarity (light vs dark)
- `_remove_borders()`: Masks narrow (≤3px wide) high-density vertical column runs. Only masks actual border pipes, not text alignment positions.
- Gap tolerance of 2 rows closes thin character stroke dips without merging separate lines
- `_split_tall_block()`: Handles oversized merged blocks by local projection analysis
- `_rescue_gaps()`: Two-pass detection — re-scans large gaps with lower threshold to catch sparse continuation lines (e.g., `적용)`, `제외)`)
- `_has_internal_gap()`: Blocks with 2+ consecutive zero-projection rows get split even if within max_height
- Configurable `horizontal_split_factor` (default 3) — gaps wider than `line_height * factor` trigger horizontal sub-splitting
- Proportional padding: `pad_x = max(2, h//3)`, `pad_y = max(1, h//5)`
- Parameters: `min_height=6, max_height=25, min_width=10`
- Horizontal separators are intentionally kept (they don't bridge sections, and removing them destroys adjacent headers like "개조", "세공")
- `_add_line()` filters UI border elements from line crops:
  - Thin vertical borders (≤2px clusters far from text) — `|` pipe characters at box edges
  - Wide horizontal bars (w > `line_h*3`, avg column density < 2.0) — `ㅡㅡㅡ` bar borders
- Ground truth test images in `data/sample_images/` with matching `.txt` files

### Inference Patch (`backend/lib/ocr_utils.py`)
- `patch_reader_imgw()`: Monkey-patches EasyOCR's `recognize()` to match training preprocessing exactly
- **Double-dip resize fix (Attempt 18)**: EasyOCR inference resized images twice (cv2.LANCZOS in `get_image_list()` then PIL.BICUBIC in `AlignCollate`). Training only resizes once (PIL.BICUBIC in `AlignCollate`). The patch replaces `get_image_list()` with `_crop_boxes()` that crops without resizing, letting `AlignCollate` handle the single resize. This fix alone gave +37 exact matches across all models.
- **Fixed imgW**: Uses yaml's fixed imgW (200) instead of EasyOCR's dynamic per-image width
- Applied in `backend/main.py` and `scripts/v2/test_v2_pipeline.py` after reader init
- **NEVER bypass this patch** — any code path that calls EasyOCR's unpatched `recognize()` will suffer double-dip resize degradation. Always use `patch_reader_imgw()` after creating a reader.
- **Verification rule**: OCR-ing training images should give ~100% accuracy. If it doesn't, there's a preprocessing mismatch — investigate before retraining.

### Training Configuration
Each version folder has its own **`training_config.yaml`** (e.g. `backend/ocr/general_model/a18/training_config.yaml`). This is the single source of truth for that version's model architecture, hyperparameters, and paths.

**Critical rule:** When changing `imgH`, `imgW`, or any `model:` param in the version's `training_config.yaml`, you **MUST** re-run `python3 scripts/ocr/general_model/create_model_config.py --version <ver>` to regenerate `saved_models/custom_mabinogi.yaml` (training prep). This does NOT touch the production yaml — deploy with `bash scripts/ocr/general_model/deploy.sh <version>`. Mismatched `imgW` between training and inference will cause TPS layer shape errors or garbage output.

Key parameters and why (see the version's `training_config.yaml` for full list):
- `imgW: 200` — Fixed via `ocr_utils.py` patch. Attempts 10-11 tried imgW=600 but failed; Attempt 12 reverted to 200 and patched inference to use the yaml value instead of dynamic per-image width.
- `workers: 0` — Required. LMDB can't be pickled for multiprocessing.
- `sensitive: true` — Required. Prevents lowercasing (needed for R,G,B,L,A-F characters).
- `PAD: true` — Required. Matches EasyOCR's hardcoded `keep_ratio_with_pad=True`.
- `batch_size: 64` — Default 192 causes extreme slowdown on 8GB VRAM.
- `batch_max_length: 55` — Longest labels are ~55 chars.
- Note: `train.py` line 287-289 was patched so `--sensitive` no longer overrides the character set.

**Training launcher:** `scripts/ocr/general_model/train.py --version <ver>` reads the version's config and runs `deep-text-recognition-benchmark/train.py` with all args. Supports `--resume`, `--num_iter`, `--batch_size` overrides. Defaults to the active version (detected from symlink).

### Training Data Requirements
Synthetic training images must match real line crops from the splitter:
- **Font sizes**: `[16, 16, 17, 17, 18, 18]` for rendering. Rendered at large size, then downscaled to ~14-15px to match real inference crops.
- **Rendering pipeline** (`scripts/ocr/lib/render_utils.py`): Game-like rendering that closes both ink ratio and height gaps:
  1. Dark bg (20,20,20) + bright text (220,220,220) at font 16-18
  2. BT.601 grayscale → threshold 80 ± random(-10, +40) with BINARY_INV (bright→black ink)
  3. Tight-crop to ink bounds + splitter padding
  4. Downscale to target ~14-15px via cv2.INTER_AREA
  5. Re-threshold to strict binary (0/255)
- **Tight-crop to ink bounds**: Crop to text width + padding, NOT full 260px canvas. Real splitter crops are tight (22-80px for short text). Full-canvas training causes hallucination.
- **Padding**: Match splitter formula: `pad_y = max(1, text_h // 5)`, `pad_x = max(2, text_h // 3)`
- **Binary only**: Pixel values strictly 0 and 255. Re-threshold after any resize.
- **No augmentation**: No blur, erode/dilate, or noise. Clean binary only.
- **Quality gates on every image**: `MIN_INK_RATIO=0.02`, `MIN_WIDTH=10`, `MIN_HEIGHT=8`. Reject and retry any image that fails.
- **Content**: Template-based full tooltip lines (shared in `scripts/ocr/lib/training_templates.py`):
  - Stat lines: `방어력 {N}`, `내구력 {N}/{N}`, `공격 {N}~{N}`
  - Color parts: `- 파트 {A-F} R:{N} G:{N} B:{N}`
  - Enchant headers/effects, hashtag lines, price lines, piercing text
  - Item names, flavor text, sub-bullets with `ㄴ` marker
  - All GT lines included verbatim
- **Character set**: Current deployed model is 509 chars (a18). Expand only with proportional data/iteration scaling to avoid Attempt 16-style regression.
- **Fonts**: Each font-specific model uses only its font: `mabinogi_classic.ttf` or `NanumGothicBold.ttf`

### Full Training Pipeline (run from project root)
All scripts accept `--version <ver>` (defaults to active version from symlink).

**Font-specific models** (a19+): Each font has its own model. Replace `MODEL` with `general_mabinogi_classic_model` or `general_nanum_gothic_bold_model`:
```bash
VER=a19  # or omit --version to use the active symlink
MODEL=general_mabinogi_classic_model  # or general_nanum_gothic_bold_model

# Step 1: Generate synthetic training images (uses game-like rendering pipeline)
python3 scripts/ocr/${MODEL}/generate_training_data.py --version $VER

# Step 2: Verify dimension distribution (acceptance check)
python3 - <<PY
import os, random, numpy as np
from PIL import Image
img_dir='backend/ocr/${MODEL}/$VER/train_data/images'
files=[f for f in os.listdir(img_dir) if f.endswith('.png')]
random.seed(0); files=random.sample(files, min(3000, len(files)))
wh=[Image.open(os.path.join(img_dir,f)).size for f in files]
w=np.array([x for x,_ in wh]); h=np.array([y for _,y in wh])
print(f"n={len(files)}, width>220={100*(w>220).mean():.0f}%")
for lo,hi in [(8,9),(10,11),(12,13),(14,15),(16,20)]:
    c=int(((h>=lo)&(h<=hi)).sum()); print(f"  h={lo}-{hi}: {c} ({100*c/len(h):.1f}%)")
PY
# Expected: h=13-16 should be 80-90%, ink ratio ~0.18-0.22

# Step 3: Generate model config
python3 scripts/ocr/${MODEL}/create_model_config.py --version $VER

# Step 4: Create LMDB dataset
python3 skills/ocr-trainer/scripts/create_lmdb_dataset.py \
  --input backend/ocr/${MODEL}/$VER/train_data \
  --output backend/ocr/${MODEL}/$VER/train_data_lmdb

# Step 5: Train (run with nohup to avoid OOM kills)
nohup python3 -u scripts/ocr/${MODEL}/train.py --version $VER > logs/training_${MODEL}_attemptN.log 2>&1 &
# Monitor: tail -f logs/training_${MODEL}_attemptN.log

# Step 6: Deploy trained model to versioned folder + update symlinks
bash scripts/ocr/${MODEL}/deploy.sh $VER

# Step 7: Validate on real GT images (DualReader picks best per line)
python3 scripts/v3/test_v3_pipeline.py 'data/sample_images/*_original.png'
```

**Legacy combined model** (a18, kept for rollback): use `scripts/ocr/general_model/` scripts as before.

**When to re-run `create_model_config.py`:** Anytime you change `model:` section in the version's `training_config.yaml` (especially `imgW`, `imgH`), or update the version's `unique_chars.txt`. This writes to `saved_models/custom_mabinogi_classic.yaml` or `saved_models/custom_nanum_gothic_bold.yaml` (training prep only). Production yaml at `backend/ocr/models/` is updated only via `deploy.sh`. The yaml must match training args exactly — the TPS Spatial Transformer is built with `I_size=(imgH, imgW)` and mismatched weights will crash or produce garbage.

### Testing
- `scripts/v2/test_v2_pipeline.py` — Uses `MabinogiTooltipParser` to split GT images → `recognize()` → compares against GT `.txt` files. **Always run with `--normalize --gt-suffix _expected.txt`** — without these flags scores are artificially low (`.` bullet prefix mismatches + skipped sections inflate error count). Supports `--sections`/`-s` flag for section breakdown.
- `scripts/v2/line_split/test_line_splitter.py <image> <output_dir>` — Visual line detection verification using `MabinogiTooltipParser`
- `scripts/v2/ocr/regenerate_gt.py` — Runs parser on GT images, outputs `_gt_candidate.txt` files for manual review. `--apply` strips comments and overwrites `.txt` GT files.
- `scripts/v3/test_v3_pipeline.py` — V3 pipeline test: segment-first on original color screenshots, compares against GT. Supports same flags as v2.
- Ground truth in `data/sample_images/`: 5 images, 244 total lines. File types: `*.txt` (full GT), `*_expected.txt` (expected OCR output), `*_gt_candidate.txt` (pipeline candidates)

### Recommendation System
- `backend/lib/recommendation.py`: TF-IDF vectorization of item descriptions + cosine similarity
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

- Active API path is v3 (`/upload-item-v3`) with original color input and segment-first processing. Legacy v2 still exists for comparison.
- In both v2 and v3 content OCR, CRAFT is not used; `TooltipLineSplitter` + `recognize()` is used for line-level recognition.
- The EasyOCR custom model can only recognize characters present in the active version's `unique_chars.txt` (e.g. `backend/ocr/general_model/a18/unique_chars.txt`); any characters not in this set will never be output
- EasyOCR always uses `keep_ratio_with_pad=True` during inference (hardcoded in `recognition.py` lines 199, 213), regardless of yaml PAD setting. Training must use `--PAD` to match.
- Item database is currently mocked in `backend/lib/recommendation.py` (`ITEMS_DB`); no persistent storage yet
- The `data/` directory (fonts, dictionary, sample images, source_of_truth) is not fully committed to git
- `data/source_of_truth/enchant.yaml` is the canonical enchant data source; `data/dictionary/enchant_*.txt` files are generated from it via `scripts/ocr/generate_enchant_dicts.py`
- Ground truth files (`data/sample_images/*.txt`) exist for: `lightarmor_processed_3`, `captain_suit_processed`, `lobe_processed`, `titan_blade_processed`, `dropbell_processed`. Additional `*_expected.txt` files track expected OCR output (may differ from full GT due to skipped sections).
- Current deployed model charset is 509; known missing enchant characters remain and are tracked in `OCR_ISSUES.md`.
- Training must run independently (not as subprocess of Claude Code) to avoid OOM kills — use `nohup` in a separate terminal
