# Architecture

Detailed stage-by-stage description of the V3 OCR pipeline. Each stage documents the exact algorithm, input format, parameters, and output.

For algorithm details of individual correction strategies, see [CORE_LOGIC.md](CORE_LOGIC.md).

---

## Pipeline Overview

```
Original color screenshot (BGR, any resolution)
    │
    ├── Stage 1: Border Detection + Crop — RGB(132,132,132) pixel scan → crop to tooltip
    │     → tooltip image (game background and UI excluded)
    │
    ├── Stage 2: Orange Header Detection — orange mask + black-square expansion
    │     → list of header bands (y, h, x, w) — on cropped tooltip only
    │
    ├── Stage 3: Segmentation — pair headers with content regions
    │     → pre_header + N header+content segments
    │
    ├── Stage 4: Header OCR — BT.601 + threshold=50 → custom_header model → fuzzy match
    │     → section label per segment (enchant, reforge, erg, ...)
    │
    ├── Stage 5: Content OCR — per-section preprocessing + line splitting + recognition
    │     │
    │     ├── Enchant section:
    │     │     ├── oreo_flip (white mask) → slot header band detection
    │     │     ├── classify lines: header / effect / grey (by band overlap + saturation)
    │     │     ├── Header OCR: oreo_flip crop → custom_enchant_header model
    │     │     ├── Effect OCR: BT.601 + threshold=80 → DualReader (2 font models)
    │     │     └── Grey lines: skipped (no OCR)
    │     │
    │     ├── Reforge section:
    │     │     ├── BT.601 + threshold=80 → DualReader
    │     │     └── Sub-line detection by x-offset indent
    │     │
    │     ├── Color section:
    │     │     └── Regex parse RGB from sub-segments (no OCR)
    │     │
    │     └── All other sections:
    │           └── BT.601 + threshold=80 → DualReader
    │
    ├── Stage 6: Fuzzy Matching (FM) — section-aware text correction
    │     │
    │     ├── Enchant headers: Dullahan algorithm (effect-guided header correction)
    │     ├── Enchant effects: match_enchant_effect (partial_ratio against entry's effects)
    │     ├── Reforge: correct_normalized (number-normalized, level suffix stripped)
    │     └── Other sections: correct_normalized (section dictionary or combined)
    │
    └── Stage 7: Structured Rebuild — build_enchant_structured / build_reforge_structured
          → JSON response with prefix/suffix slots, reforge options, color parts
```

---

## Stage 1: Border Detection

**File:** `backend/lib/tooltip_segmenter.py`
**Functions:** `detect_bottom_border()`, `detect_vertical_borders()`

**Input:** Original color screenshot as BGR numpy array (cv2.imread default). No preprocessing, no resize, no grayscale conversion. The image is exactly what the user uploaded or screenshotted.

**Algorithm:**

Mabinogi tooltips have a gray border at RGB(132, 132, 132). The border is a game engine constant — same color across all 26 theme backgrounds.

```
Bottom border — detect_bottom_border():
  For each row (bottom → top):
    Count pixels where ALL of B, G, R ∈ [127, 137]  (132 ± 5)
    If count ≥ 30% of image width → return y
  Return None if no border found

Vertical borders — detect_vertical_borders():
  Column-wise sum of border-colored pixels
  Scan inward from each edge:
    Left:  first column where count ≥ 30% of image height
    Right: last column where count ≥ 30% of image height
  Return (left_x, right_x), each may be None
```

**Output:** `bottom_y`, `left_x`, `right_x` — pixel coordinates. `None` if not detected (fallback to full image extent).

After detection, the image is **cropped to the tooltip boundary** before any further processing:

```
tooltip = img[0 : bottom_y+1,  left_x+1 : right_x]
```

All subsequent stages operate on this cropped `tooltip` image. This eliminates stray orange pixels, game world background, and UI elements outside the tooltip from ever reaching header detection or content OCR.

If any border is not detected, that edge falls back to the full image extent (no crop on that side).

---

## Stage 2: Orange Header Detection

**File:** `backend/lib/tooltip_segmenter.py`
**Function:** `detect_headers()`

**Input:** Border-cropped tooltip image (BGR). Only tooltip pixels are scanned — stray orange outside the tooltip area is excluded by the Stage 1 crop.

**Algorithm:**

Section headers (인챈트, 세공, 에르그, ...) are rendered as orange text on a pure-black background square. The orange color is a game engine constant.

```
Step 1: Orange mask — per-pixel condition:
  R > 150  AND  50 < G < 180  AND  B < 80
  → binary mask (1 = orange pixel)

Step 2: Horizontal projection — sum orange pixels per row
  → row_counts[y]

Step 3: Band clustering — contiguous rows where row_counts > 0
  Filter: band_height ≥ 8  AND  total_orange_pixels ≥ 40

Step 4: Black-square boundary expansion — for each orange band:
  a. Reference columns: right of orange text (ox_max to ox_max+10)
  b. Expand upward from band top: while pure-black density ≥ 20% in ref columns
  c. Expand downward from band bottom: same condition
  d. Scan left/right from orange center for pure-black extent
  → (y_top, y_bottom, x_left, x_right) = black square bounds
  → content_y = y_bottom + 1 (first row below the header)
```

**Parameters** (from `configs/mabinogi_tooltip.yaml` → `header_detection`):
- `orange.r_min=150, g_min=50, g_max=180, b_max=80`
- `orange.min_band_height=8, min_band_pixels=40`
- `boundary.pure_black_max=0, ref_columns=10, density_threshold=0.2, max_expansion=40`

**Output:** List of header dicts sorted by y: `{y, h, x, w, content_y}`

**Result:** 26/26 theme images detected, 0 false positives (on properly cropped tooltips).

---

## Stage 3: Segmentation

**File:** `backend/lib/tooltip_segmenter.py`
**Function:** `build_segments()`

**Input:** Header list from Stage 2 + cropped tooltip image from Stage 1.

**Algorithm:**

Since the image was already cropped to tooltip borders in Stage 1, segmentation operates on tooltip-local coordinates with full image width.

```
Segment 0 (pre_header):
  If first header y > 0 → content from row 0 to first header y
  Contains: item name, item type, craftsman text

Segments 1..N (header + content):
  For each header[i]:
    content starts at header[i].content_y
    content ends at header[i+1].y (or tooltip image height for last segment)
    content width: full tooltip image width
```

**Output:** List of segments: `{index, header: dict|None, content: {y, h, x, w}}`

---

## Stage 4: Header OCR + Classification

**File:** `backend/lib/tooltip_segmenter.py`
**Functions:** `classify_header()`, `_preprocess_header_crop()`

**Input:** Header crop (tight black-square region from original color image).

**Algorithm:**

```
Step 1: Preprocess header crop
  BT.601 grayscale (cv2.cvtColor BGR2GRAY)
  → threshold at 50, BINARY_INV
  → black text on white background
  (threshold=50, not 80 — orange text on dark bg needs lower threshold)

Step 2: OCR with dedicated header model
  Model: custom_header.pth (imgW=128, 22-char charset, trained on 9 section labels)
  EasyOCR recognize() with imgW patch applied

Step 3: Fuzzy match against section patterns
  Patterns from configs/mabinogi_tooltip.yaml → sections → header_patterns
  Scorer: fuzz.partial_ratio (handles OCR adding/dropping characters)
  Cutoff: 50 (from config)
  Best-scoring pattern → section name
```

**Section labels:** `item_grade`, `item_attrs`, `enchant`, `item_mod`, `reforge`, `erg`, `set_item`, `ego`, `item_color`

**Output:** `(section_name, ocr_text, confidence, match_score)`

---

## Stage 5: Content OCR

**File:** `backend/lib/mabinogi_tooltip_parser.py`
**Method:** `_parse_segment_from_array()`

**Input:** Content crop (BGR, region below each header), pre-known section label.

Processing varies by section type:

### 5a. Default content preprocessing (most sections)

```
Step 1: BT.601 grayscale → threshold=80, BINARY_INV → black text on white
Step 2: Invert for line detection (detect_text_lines needs white-on-black)
Step 3: TooltipLineSplitter.detect_text_lines()
  → horizontal projection profiling
  → gap detection with 2-row tolerance
  → _rescue_gaps (second pass at lower threshold)
  → _split_tall_block (oversized merged blocks)
  → _has_internal_gap (split blocks with 2+ zero rows)
  → _add_line (filter border artifacts, compute tight x bounds)
Step 4: _group_by_y() — merge horizontal sub-segments into line groups
Step 5: _ocr_grouped_lines() — for each line group:
  Crop with proportional padding: pad_x=max(2, h//3), pad_y=max(1, h//5)
  DualReader.recognize():
    Run both font-specific models (mabinogi_classic + nanum_gothic_bold)
    Pick highest confidence result per line
  Merge sub-line texts with space separator
```

### 5b. Enchant section (`parse_mode: enchant_options`)

When white-mask slot header bands are detected (`detect_enchant_slot_headers` returns non-empty):

```
Step 1: oreo_flip (white-text color mask)
  Per-pixel: max_ch = max(R,G,B), min_ch = min(R,G,B)
  white_mask = (max_ch > 150) AND (max_ch / (min_ch + 1) < 1.4)
  Strip border columns: leftmost/rightmost 3 cols with >50% density → zero out
  Invert: white_mask → ocr_input (black text on white)

Step 2: Horizontal projection on white_mask → detect slot header bands
  Run detection with ROW_THRESHOLD=10, GAP_TOLERANCE=2
  Filter: 8 ≤ height ≤ 15 AND total_white_px ≥ 150

Step 3: Classify each line group — classify_enchant_line()
  'header': line overlaps a white-mask band
  'effect': text pixels have mean saturation ≥ 0.15 (colored text)
  'grey':   text pixels have mean saturation < 0.15 (desaturated descriptions)

Step 4: OCR by line type
  Headers → _ocr_enchant_headers():
    Crop from oreo_flip ocr_source (not binary)
    Find x-extent of white pixels within the matched band (≥3 per column)
    Proportional padding, then enchant_header_reader (custom_enchant_header model)
  Effects → _ocr_grouped_lines():
    Standard BT.601+threshold=80 binary → DualReader
  Grey → skipped (no OCR, empty text, is_grey=True)

Step 5: Position-based slot assignment (not OCR-dependent)
  2 headers → slot_queue = ['접두', '접미']
  1 header  → check if grey lines appear above first header
              grey above → prefix is empty → header is '접미'
              no grey above → header is '접두'
  0 headers → slot_queue = []
```

Fallback: if `detect_enchant_slot_headers` returns empty, falls through to `_parse_enchant_section()` which uses regex on OCR text to detect `[접두|접미]` headers.

### 5c. Reforge section (`parse_mode: reforge_options`)

```
Step 1: Standard preprocessing (BT.601 + threshold=80) → DualReader OCR
Step 2: Regex detection of level-suffixed options
  Pattern: '- name(current/max 레벨)' → reforge_name, reforge_level, reforge_max_level
Step 3: Sub-line detection by x-offset indent
  min_x = minimum x among all content lines
  Indented if (line.x - min_x) > min_x  (relative threshold, resolution-independent)
  Fallback: ㄴ prefix regex detection
  Sub-lines tagged is_reforge_sub=True → skip FM
Step 4: Non-indented lines without reforge_name → level-less options
```

### 5d. Color section (`parse_mode: color_parts`)

```
No OCR. Horizontal sub-segments parsed via regex:
  Pattern: R:N G:N B:N
  Each sub-segment → {part, r, g, b}
```

### 5e. Pre-header (no section label)

```
Standard OCR, then:
  First line matching _PRE_NAME_PATTERNS ('전용 해제') → item_flags
  Next line → item_name
  Remaining → item_type
```

---

## Stage 6: Fuzzy Matching (FM)

**File:** `backend/lib/text_corrector.py`
**Method:** `apply_fm()`

**Input:** `all_lines` (flat list) + `sections` dict from Stage 5.

**Preprocessing:** Strip structural prefixes (`-`, `ㄴ`, `,`, `L`) from content lines before matching. Dictionary entries don't have these prefixes.

### 6a. Non-enchant sections

For each line with a known section:

```
correct_normalized(text, section=section):
  1. Choose dictionary: section-specific if available, skip if known but no dict (score=-2)
  2. Section-specific transform:
     reforge: strip '(N/N 레벨)' suffix, re-attach after match
     enchant header: extract just the name via regex
  3. Extract numbers, replace with N
  4. Match against normalized dictionary entries (fuzz.ratio, cutoff=80)
  5. Re-inject OCR numbers into matched template
  → (corrected_text, score)
```

Reforge sub-lines (`is_reforge_sub=True`) skip FM entirely (score=-3).

### 6b. Enchant section — has_slot_hdrs=True (white-mask detected)

```
Group lines by slot header:
  Each slot = (header_line, [effect_lines])

For each slot:
  Header FM: do_dullahan(header_text, effect_texts, slot_type)
    → Dullahan algorithm: score DB entries by name similarity,
      use effect lines to break ties or find correct entry when header is garbled
    → Returns (corrected_header, score, entry)
    → Sets enchant_slot, enchant_name, enchant_rank from matched entry

  Effect FM: match_enchant_effect(text, entry) for each effect line
    → Uses fuzz.partial_ratio (not ratio) to handle abbreviated tooltips
    → Searches only the matched entry's effects (4-8 lines, not full dict)
    → Number normalization + re-injection
    → Cutoff: 75
```

**Why partial_ratio for effects:** The simple/abbreviated tooltip (ALT key) shows only effect text without conditions. `enchant.yaml` stores full condition+effect sentences. `fuzz.ratio` penalizes the length difference; `fuzz.partial_ratio` finds the best matching substring.

### 6c. Enchant section — has_slot_hdrs=False (linear fallback)

```
Linear scan of enchant lines:
  Try match_enchant_header(line):
    fuzz.ratio against all _enchant_headers_norm, cutoff=80
    If match → remember entry as current_entry

  Else try match_enchant_effect(line, current_entry):
    fuzz.partial_ratio against current entry's effects, cutoff=75
```

---

## Stage 7: Structured Rebuild

**File:** `backend/lib/mabinogi_tooltip_parser.py`
**Methods:** `build_enchant_structured()`, `build_reforge_structured()`

Called AFTER FM correction to propagate corrected text into structured section data.

### 7a. Enchant structured

```
For each line tagged is_enchant_hdr=True:
  Create slot record: {text, name, rank, effects: []}
  Enrich text with rank from DB if available but not in OCR output:
    display_text = "[slot] name (랭크 rank)" when rank known but absent from text
  Following non-header, non-grey lines → effects[]
    Each effect: {text, option_name, option_level} via _parse_effect_number()

Output: {prefix: slot_record | None, suffix: slot_record | None}
```

### 7b. Reforge structured

```
For each main line (is_reforge_sub=False, has reforge_name):
  Re-parse name/level/max_level from corrected text (regex)
  Following sub-lines → effect text

Output: {options: [{name, level, max_level, option_name, option_level, effect}]}
```

---

## Models

| Model | File | imgW | Charset | Purpose |
|-------|------|------|---------|---------|
| custom_header | `backend/ocr/models/custom_header.*` | 128 | 22 chars | Section header OCR (9 labels) |
| custom_enchant_header | `backend/ocr/models/custom_enchant_header.*` | 200 | 627 chars | Enchant slot header OCR |
| custom_mabinogi_classic | `backend/ocr/models/custom_mabinogi_classic.*` | 200 | 509 chars | Content OCR (mabinogi_classic font) |
| custom_nanum_gothic_bold | `backend/ocr/models/custom_nanum_gothic_bold.*` | 200 | 509 chars | Content OCR (NanumGothicBold font) |

All models: TPS-ResNet-BiLSTM-CTC architecture, imgH=32, `sensitive=true`, `PAD=true`.

DualReader wraps the two content models. For each line, both models run and the highest-confidence result wins. Transparent to the parser — it sees one `reader.recognize()` call.

All readers have `patch_reader_imgw()` applied after creation. This replaces EasyOCR's double-resize inference path (cv2.LANCZOS in `get_image_list()` → PIL.BICUBIC in `AlignCollate`) with a single-resize path (`_crop_boxes()` → `AlignCollate`), matching training exactly.

---

## Data Sources

| Source | Path | Purpose |
|--------|------|---------|
| `enchant.yaml` | `data/source_of_truth/enchant.yaml` | Canonical enchant DB: 1,172 entries with slot/name/rank/effects |
| Section dictionaries | `data/dictionary/*.txt` | Per-section FM dictionaries (reforge.txt, enchant_effect.txt, etc.) |
| Tooltip config | `configs/mabinogi_tooltip.yaml` | Section definitions, header patterns, parse modes, detection params |
| GT images | `data/sample_images/*_original.png` | Test images with ground truth `.txt` files |

---

## API Endpoints

| Endpoint | Input | Pipeline |
|----------|-------|----------|
| `POST /upload-item-v3` | Original color screenshot (multipart) | Full V3 pipeline (Stages 1-7) |
| `POST /upload-item-v2` | Browser-preprocessed binary PNG | Legacy pipeline (line split → OCR → FM, no segmentation) |

V3 response: `{sections: {section_name: OcrSectionResponse}, all_lines: [OcrLineResponse], session_id?}`

See `documents/API_SPEC.md` for full response schema.
