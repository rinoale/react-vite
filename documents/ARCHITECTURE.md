# Architecture

Detailed stage-by-stage description of the V3 OCR pipeline. Each stage documents the exact algorithm, method calls, input format, parameters, and output.

For algorithm details of individual correction strategies, see [CORE_LOGIC.md](CORE_LOGIC.md).

---

## Pipeline Overview

```
Original color screenshot (BGR, any resolution)
    │
    ├── Stage 1: Border Detection + Crop
    │     segmenter.detect_bottom_border() + detect_vertical_borders()
    │     → crop to tooltip boundary
    │
    ├── Stage 2: Orange Header Detection
    │     segmenter.detect_headers()
    │     → list of header bands (y, h, x, w, content_y)
    │
    ├── Stage 3: Segmentation + Header Classification
    │     segmenter.segment_and_tag()
    │     → pre_header + N labeled (section, content) segments
    │
    ├── Stage 4: Per-Section Handler Processing
    │     Each section processed end-to-end by its handler:
    │     get_handler(section_key).process(seg, font_reader=..., ...)
    │     │
    │     ├── PreHeaderHandler (runs first — produces parsed_item_name):
    │     │     Dual-font preprocessing → OCR → font detection → parse_item_name()
    │     │     → P1 enchant entries, detected_font for content reader selection
    │     │
    │     ├── EnchantHandler:
    │     │     oreo_flip → detect_enchant_slot_headers() → classify lines
    │     │     Headers → enchant_header_reader; Effects → font_reader; Grey → skip
    │     │     FM: do_dullahan() on headers, match_enchant_effect() on effects
    │     │     merge_continuations() → build_enchant_structured()
    │     │
    │     ├── ReforgeHandler:
    │     │     BT.601 binary → OCR with prefix detection (bullet + subbullet)
    │     │     FM: correct_normalized(cutoff=0) on bullet lines
    │     │     build_reforge_structured()
    │     │
    │     ├── ColorHandler:
    │     │     Regex parse RGB from sub-segments (no OCR)
    │     │
    │     └── DefaultHandler (item_attrs, item_mod, erg, set_item, ego, item_grade):
    │           BT.601 binary → OCR with prefix detection (bullet + subbullet)
    │           FM: correct_normalized(cutoff=80) on bullet lines
    │
    ├── Stage 5: Line Index Assignment
    │     line_index = 0-based position within each section's lines[]
    │     Crop files: {section}/{line_index:03d}.png
    │
    └── Stage 6: Enchant Resolution (P1/P2/P3)
          _step_resolve_enchant()
          P1 (item name) > P2 (raw header OCR) > P3 (Dullahan)
          → winner's DB entry → build_templated_effects()
```

---

## Stage 1: Border Detection

**File:** `backend/lib/pipeline/segmenter.py`
**Entry:** `v3._step_segment()` → `segment_and_tag()`

### Methods called:

**`detect_bottom_border(img_bgr)`**
```
For each row (bottom → top):
  Count pixels where ALL of B, G, R ∈ [127, 137]  (132 ± 5)
  If count ≥ 30% of image width → return y
Return None if no border found
```

**`detect_vertical_borders(img_bgr)`**
```
Column-wise sum of border-colored pixels (RGB 132 ± 5)
Scan inward from each edge:
  Left:  first column where count ≥ 30% of image height
  Right: last column where count ≥ 30% of image height
Return (left_x, right_x), each may be None
```

**Crop:**
```
tooltip = img[0 : bottom_y+1,  left_x+1 : right_x]
```

All subsequent stages operate on this cropped tooltip. If any border is not detected, that edge falls back to the full image extent.

---

## Stage 2: Orange Header Detection

**File:** `backend/lib/pipeline/segmenter.py`
**Method:** `detect_headers(img_bgr, config)`

### Algorithm:

```
Step 1: Orange mask — per-pixel:
  R > 150  AND  50 < G < 180  AND  B < 80
  → binary mask

Step 2: Horizontal projection — sum orange pixels per row → row_counts[y]

Step 3: Band clustering — contiguous rows where row_counts > 0
  Filter: band_height ≥ 8  AND  total_orange_pixels ≥ 40

Step 4: Black-square boundary expansion — for each orange band:
  a. Reference columns: right of orange text (ox_max to ox_max+10)
  b. Expand upward: while pure-black density ≥ 20% in ref columns
  c. Expand downward: same condition
  d. Scan left/right for pure-black extent
  → (y_top, y_bottom, x_left, x_right) = black square bounds
  → content_y = y_bottom + 1
```

**Parameters** (from `configs/mabinogi_tooltip.yaml` → `header_detection`):
- `orange.r_min=150, g_min=50, g_max=180, b_max=80`
- `orange.min_band_height=8, min_band_pixels=40`
- `boundary.pure_black_max=0, ref_columns=10, density_threshold=0.2, max_expansion=40`

**Output:** List of header dicts sorted by y: `{y, h, x, w, content_y}`

**Result:** 26/26 theme images detected, 0 false positives.

---

## Stage 3: Segmentation + Header Classification

**File:** `backend/lib/pipeline/segmenter.py`
**Methods:** `segment_and_tag()`, `classify_header()`, `_preprocess_header_crop()`

### `build_segments(headers, img_h)`

```
Segment 0 (pre_header):
  If first header y > 0 → content from row 0 to first header y

Segments 1..N (header + content):
  For each header[i]:
    content starts at header[i].content_y
    content ends at header[i+1].y (or img_h for last segment)
    content width: full tooltip image width
```

### `classify_header(header_crop, reader, section_patterns, config)`

```
Step 1: _preprocess_header_crop()
  cv2.cvtColor(BGR2GRAY)
  → cv2.threshold(50, BINARY_INV)  (50 not 80 — orange on dark needs lower threshold)

Step 2: OCR with dedicated header model
  reader.recognize(gray, horizontal_list=[[0,w,0,h]], free_list=[])
  Model: custom_header.pth (imgW=128, 22-char charset)

Step 3: Fuzzy match against section patterns
  Patterns from configs/mabinogi_tooltip.yaml → sections → header_patterns
  Scorer: fuzz.partial_ratio
  Cutoff: 50
  → section_name
```

**Section labels:** `item_grade`, `item_attrs`, `enchant`, `item_mod`, `reforge`, `erg`, `set_item`, `ego`, `item_color`

**Output:** List of segments: `{section, header_crop, header_ocr_text, header_ocr_conf, header_match_score, content_crop}`

---

## Stage 4: Per-Section Handler Processing

**Files:** `backend/lib/pipeline/section_handlers/` (one file per handler)
**Entry:** `v3.run_v3_pipeline()` → `handler.process(seg, font_reader=..., ...)`
**Dispatch:** `get_handler(section_key)` → `EnchantHandler`, `ReforgeHandler`, `ColorHandler`, or `DefaultHandler`

### 4.0 Common preprocessing (all sections except pre_header and enchant-with-bands)

**Methods:** `cv2.cvtColor()`, `cv2.threshold()`, `detect_text_lines()`, `_group_by_y()`

```
Step 1: cv2.cvtColor(content_bgr, COLOR_BGR2GRAY)
Step 2: cv2.threshold(gray, 80, 255, THRESH_BINARY_INV) → binary (black text on white)
Step 3: cv2.bitwise_not(binary) → binary_detect (white text on black, for line detection)
Step 4: TooltipLineSplitter.detect_text_lines(binary_detect)
  → horizontal projection profiling
  → gap detection (tolerance=2 rows)
  → _rescue_gaps() — second pass at lower threshold for sparse lines
  → _split_tall_block() / _has_internal_gap() — split merged blocks
  → _add_line() — filter border artifacts, compute tight x bounds
Step 5: _group_by_y(detected_lines) → list of line groups (sub-segments sorted by x)
```

### 4.1 Prefix Detection + Slicing

**File:** `backend/lib/image_processors/prefix_detector.py`
**Method:** `detect_prefix_per_color(bgr_crop, config)`
**Called from:** `_ocr_grouped_lines()` for each sub-line

Runs on all content sections (not pre_header, not skipped sections). Two configs are tried in order; first match wins:

```
For each sub-line in a group:
  bgr_crop = content_bgr[y_pad:y_pad+h_pad, x_pad:x_pad+w_pad]

  For config in [BULLET_DETECTOR, SUBBULLET_DETECTOR]:
    For each color in config.colors:
      mask = _color_mask(bgr_crop, rgb, tolerance=15)
      result = _detect_prefix_on_mask(mask, config)
        → column projection state machine:
          [small ink cluster] → [gap] → [main text]
        → _classify_shape(mask, cluster_region)
          → shape_walker.find_shape() tests SHAPE_DOT / SHAPE_NIEUN
      If result.type is not None → break

  If type in ('bullet', 'subbullet') and main_x < crop_width:
    prefix_end = result.x + result.w
    cut_x = max(prefix_end, result.main_x - _PREFIX_ANTIALIAS_MARGIN)
    gray = gray[:, cut_x:]  ← slice prefix off before OCR

  Line tagged: _prefix_type = result.type  ('bullet', 'subbullet', or None)
```

**Configs:**
- `BULLET_DETECTOR`: colors=(blue, red, grey, light_grey), shapes=(SHAPE_DOT,) → detects `·`
- `SUBBULLET_DETECTOR`: colors=(white, red, grey), shapes=(SHAPE_NIEUN,) → detects `ㄴ`

### 4.2 Line OCR

**Method:** `_ocr_grouped_lines(img, grouped_lines, reader, ...)`

```
For each line group:
  For each sub-line:
    Crop with proportional padding: pad_x=max(2, h//3), pad_y=max(1, h//5)
    Convert to grayscale if needed
    [Prefix detection + slicing — see 4.1]
    reader.recognize(gray, horizontal_list=[[0,cw,0,ch]], free_list=[])
      DualReader: runs both font-specific models, picks highest confidence
    Record: text, confidence, ocr_model, prefix_type, prefix_abs_cut

  Merge sub-line results:
    merged_text = ' '.join(sub_texts)
    avg_conf = mean(sub_confs)
    merged_bounds = merge_group_bounds(group)
    _prefix_type = first sub-line's prefix_type
    _has_bullet = _prefix_type in ('bullet', 'subbullet')
```

### 4.3 Enchant section (`parse_mode: enchant_options`)

**File:** `backend/lib/pipeline/section_handlers/enchant.py`
**Handler:** `EnchantHandler.process()` → `_parse_enchant_with_bands()`

Only when `detect_enchant_slot_headers(content_bgr)` returns non-empty bands.

```
Step 1: _oreo_flip(content_bgr)
  Per-pixel: max_ch = max(R,G,B), min_ch = min(R,G,B)
  white_mask = (max_ch > 150) AND (max_ch / (min_ch + 1) < 1.4)
  Strip border columns: leftmost/rightmost 3 cols with >50% density → zero out
  Invert → ocr_source (black text on white)

Step 2: detect_enchant_slot_headers(content_bgr)
  Horizontal projection on white_mask
  ROW_THRESHOLD=10, GAP_TOLERANCE=2
  Filter: 8 ≤ height ≤ 15 AND total_white_px ≥ 150
  → slot_bands = [(y_start, y_end), ...]

Step 3: classify_enchant_line(group, bounds, bands, content_bgr)
  For each line group:
    'header' — line overlaps a white-mask band
    'effect' — text pixels have mean saturation ≥ 0.15
    'grey'   — text pixels have mean saturation < 0.15

Step 4: trim_outlier_tail(classifications)
  Remove leaked non-enchant lines at segment bottom via gap analysis

Step 5: promote_grey_by_prefix(classifications, content_bgr)
  For each grey line:
    detect_prefix_per_color(bgr_crop, BULLET_DETECTOR)
    If bullet detected → reclassify as 'effect'

Step 6: determine_enchant_slots(classifications)
  2 headers → ['접두', '접미']
  1 header + grey above → ['접미']
  1 header, no grey above → ['접두']

Step 7: OCR by type
  Headers → _ocr_enchant_headers():
    Crop from oreo_flip ocr_source
    Find x-extent of white pixels within matched band (≥3 per column)
    Proportional padding → enchant_header_reader.recognize()
  Effects → _ocr_grouped_lines(prefix_config=BULLET_DETECTOR):
    Standard binary → DualReader, with bullet slicing
  Grey → skipped (text='', is_grey=True)

Step 8: Assemble results
  Interleave header_batch and effect_batch in original order
  Assign enchant_slot from slot_queue
```

**Fallback:** If `detect_enchant_slot_headers` returns empty, falls through to `_parse_enchant_section()` (regex-based `[접두|접미]` detection on OCR text).

### 4.4 Reforge section (`parse_mode: reforge_options`)

**File:** `backend/lib/pipeline/section_handlers/reforge.py`
**Handler:** `ReforgeHandler.process()`

```
Step 1: OCR via common path (4.0 + 4.1 + 4.2)
  prefix_configs=[BULLET_DETECTOR, SUBBULLET_DETECTOR]
  → each line gets _prefix_type flag, bullet/subbullet sliced before OCR

Step 2: Regex detection of level-suffixed options
  _REFORGE_HEADER_RE: '- name(current/max 레벨)'
  → reforge_name, reforge_level, reforge_max_level, is_reforge_sub=False

Step 3: _detect_sub_lines(lines)
  For each untagged line:
    line['is_reforge_sub'] = (line._prefix_type == 'subbullet')

Step 4: Remaining non-sub, non-header lines → level-less options
  reforge_name = text, level = None

Step 5: build_reforge_structured(lines)
  Main lines → option records {name, level, max_level}
  Sub-bullet lines → option.effect = text
```

### 4.5 Color section (`parse_mode: color_parts`)

```
No OCR. Horizontal sub-segments parsed via regex:
  Pattern: R:N G:N B:N
  Each sub-segment → {part, r, g, b}
```

### 4.6 Pre-header

**File:** `backend/lib/pipeline/section_handlers/pre_header.py`
**Handler:** `PreHeaderHandler.process()`

```
Step 1: Preprocessing — two variants, both run:
  _preprocess_mabinogi_classic(content_bgr):
    mabinogi_classic_mask() — white RGB(255,255,255) + yellow RGB(255,252,157), tolerance=5
    → mask, cv2.bitwise_not(mask)
  _preprocess_nanum_gothic(content_bgr):
    cv2.cvtColor(BGR2HSV) → reject saturated non-yellow pixels
    cv2.threshold(gray, 120, BINARY_INV)

Step 2: OCR both variants
  _ocr_pre_header_image(detect_binary, ocr_binary, parser, reader)
    parser.detect_text_lines(detect_binary)
    parser._group_by_y(detected)
    parser._ocr_grouped_lines(ocr_binary, grouped, reader)
  No prefix detection (pre_header has no bullets)

Step 3: Font detection — pick variant with higher total confidence
  detected_font = 'mabinogi_classic' or 'nanum_gothic'
  (also used to select content reader for Stage 4)

Step 4: _parse_pre_header(ocr_results)
  Tag all lines section='pre_header'
```

### 4.7 Generic sections (item_attrs, item_mod, erg, set_item, ego, item_grade)

```
Common path (4.0 + 4.1 + 4.2):
  BT.601 grayscale → threshold=80 → line detection → prefix detection → DualReader OCR
  prefix_configs=[BULLET_DETECTOR, SUBBULLET_DETECTOR]

Return: {'lines': [{text, confidence, bounds, section, ocr_model, _prefix_type}]}
```

---

## Stage 5: Item Name Parsing

**File:** `backend/lib/text_processors/mabinogi.py`
**Entry:** `PreHeaderHandler.process()` → `corrector.parse_item_name()`

**Input:** First pre_header line (OCR text, before FM).

**Why before FM:** Parsed enchant names (P1 candidates) are used as the prioritized effect dictionary source in enchant handler FM.

### Algorithm: `parse_item_name(text)`

```
Right-to-left item_name anchor:
  1. Strip holywater from start (fuzzy match against holywater dict, score ≥ 70)
  2. Strip '정령' ego keyword
  3. Anchor item_name from right:
     For progressively longer suffixes of remaining text:
       fuzzy match against item_name.txt (20k entries)
     Pick longest match with score ≥ 85
  4. Remaining left part → match against _enchant_prefixes / _enchant_suffixes
  → {item_name, enchant_prefix, enchant_suffix, _holywater, _ego}
```

**Output:** `sections['pre_header']['parsed_item_name']`

---

## Stage 6: Fuzzy Matching (FM)

**File:** `backend/lib/text_processors/mabinogi.py`
**Entry:** Each handler calls corrector methods directly (no centralized `apply_fm()`)

FM is now per-handler. Each handler calls `corrector.strip_text_prefix()` then its section-specific FM:

### Non-enchant FM (DefaultHandler, ReforgeHandler)

**Gate: only lines with `_prefix_type == 'bullet'` proceed.** All others (sub-bullets, unprefixed lines, headers) → `fm_applied=False`, skip.

For each bullet line:

```
correct_normalized(text, section):
  1. Section dictionary lookup:
     Known section with dict → use section-specific entries
     Known section, no dict → score=-2, skip
  2. Section-specific transform:
     reforge: strip '(N/N 레벨)' suffix, re-attach after match
  3. _normalize_nums(text): replace all numbers with 'N'
  4. fuzz.ratio(normalized_text, each_dict_entry)
     cutoff: 0 for reforge (closed set), 80 for others
  5. Re-inject OCR numbers into matched template
  → (corrected_text, score, paren_range)
```

### Enchant FM (EnchantHandler)

**File:** `backend/lib/pipeline/section_handlers/enchant.py` → `_apply_enchant_fm()`

```
Step 1: Resolve P1 entries from parsed_item_name (Stage 5)
  For '접두'/'접미': lookup_enchant_by_name(name) → DB entry

Step 2: Group lines by slot header
  Each slot = (header_line, [effect_lines])

Step 3: Header FM — do_dullahan(header_text, effect_texts, slot_type)
  Score all DB entries by fuzz.ratio on header name
  Use effect lines to break ties (body scoring)
  → (corrected_header, score, matched_entry)

Step 4: Effect FM — for each effect line:
  effect_entry = P1 entry (prioritized) or Dullahan entry (fallback)
  match_enchant_effect(text, effect_entry, cutoff_score=75):
    Normalize both OCR and DB effects (numbers → N)
    Match OCR against entry's effects_norm + effects_full_norm
    Pick higher fuzz.ratio score (effect-only vs full-form)

    If NOT ranged (no '~' in DB effect):
      → Return raw DB text directly (all numbers are fixed constants)

    If ranged ('N ~ N' in DB effect):
      Extract rolled value from OCR text
      Primary: find opt_name in OCR, take numbers after it
      Fallback: cond_has_number → skip first number, take second
      _inject(template, numbers): replace N placeholders, clean up '~ N'
      → Return template with OCR number injected
```

### Enchant FM — has_slot_hdrs=False (linear fallback)

```
Linear scan of enchant lines:
  Try match_enchant_header(line): fuzz.ratio, cutoff=80
    If match → remember as current_entry
  Else try match_enchant_effect(line, current_entry): cutoff=75
```

---

## Stage 7: Structured Rebuild

**File:** `backend/lib/pipeline/tooltip_parsers/mabinogi.py`
**Entry:** Each handler calls `parser.build_enchant_structured()` / `parser.build_reforge_structured()` after FM

Called AFTER FM so corrected text propagates into structured data.

### 7a. `build_enchant_structured(lines)`

```
For each line with is_enchant_hdr=True:
  Create slot record: {text, name, rank, effects: []}
  Enrich text with rank from DB if available:
    "[slot] name (랭크 rank)" when rank known but absent from OCR
  Following non-header, non-grey lines → effects[]
    Each effect: {text, option_name, option_level} via _parse_effect_number()

Output: {prefix: slot_record | None, suffix: slot_record | None}
```

### 7b. `build_reforge_structured(lines)`

```
For each main line (is_reforge_sub=False, has reforge_name):
  Re-parse name/level/max_level from FM-corrected text via _REFORGE_HEADER_RE
  Following sub-bullet lines → option.effect = text.strip()

Output: {options: [{name, level, max_level, option_name, option_level, effect}]}
```

---

## Stage 8: Enchant Resolution (P1/P2/P3)

**File:** `backend/lib/pipeline/v3.py`
**Method:** `_step_resolve_enchant(sections, corrector)`

Three candidates per slot (접두/접미):

```
P1: Item name parsing (Stage 5)
  enchant_prefix/suffix from pre_header OCR
  → lookup_enchant_by_name() → exact or fuzzy (≥85) match
  Score: 100 (exact name match)

P2: Raw header OCR
  Snapshot of enchant header text before Dullahan
  → extract name via regex from '[접두] name (랭크 X)'

P3: Dullahan result (Stage 6)
  enchant_name and _dullahan_score from matched entry

Priority: P1 > P2 > P3
Winner with DB entry → build_templated_effects():
  Match OCR effect lines to DB effects by dual-form matching
  Non-ranged effects: use DB text directly
  Ranged effects: extract rolled values from OCR, inject into DB templates
  → final enchant slot: {text, name, rank, effects[], source}
```

**Output:** `sections['enchant']['resolution']` with per-slot winner info, `sections['enchant']['prefix'|'suffix']` enriched with templated effects.

---

## Models

| Model | File | imgW | Charset | Purpose |
|-------|------|------|---------|---------|
| custom_header | `backend/ocr/models/custom_header.*` | 128 | 22 chars | Section header OCR (9 labels) |
| custom_enchant_header | `backend/ocr/models/custom_enchant_header.*` | 256 | 626 chars | Enchant slot header OCR |
| custom_mabinogi_classic | `backend/ocr/models/custom_mabinogi_classic.*` | 200 | 554 chars | Content OCR (mabinogi_classic font) |
| custom_nanum_gothic_bold | `backend/ocr/models/custom_nanum_gothic_bold.*` | 200 | 554 chars | Content OCR (NanumGothicBold font) |
| preheader_mabinogi_classic | `backend/ocr/models/preheader_mabinogi_classic.*` | 200 | 1,181 chars | Pre-header OCR (mabinogi_classic font) |
| preheader_nanum_gothic | `backend/ocr/models/preheader_nanum_gothic.*` | 200 | 1,181 chars | Pre-header OCR (NanumGothicBold font) |

All models: TPS-ResNet-BiLSTM-CTC architecture, imgH=32, `sensitive=true`, `PAD=true`.

**DualReader** (`backend/lib/legacy/dual_reader.py`): Legacy wrapper for two font-specific readers. Superseded by font-matched routing in V3 (pre_header detects font, pipeline selects matching reader).

**Inference patch** (`backend/lib/patches/easyocr_imgw.py`): `patch_reader_imgw()` replaces EasyOCR's double-resize path (cv2.LANCZOS in `get_image_list()` → PIL.BICUBIC in `AlignCollate`) with single-resize (`_crop_boxes()` → `AlignCollate`), matching training exactly.

---

## Data Sources

| Source | Path | Purpose |
|--------|------|---------|
| `enchant.yaml` | `data/source_of_truth/enchant.yaml` | Canonical enchant DB: 1,172 entries with slot/name/rank/effects |
| FM dictionaries | `data/dictionary/*.txt` | Runtime FM: `reforge.txt`, `tooltip_general.txt`, `item_name.txt`, `enchant_prefix.txt`, `enchant_suffix.txt` |
| Training words | `data/train_words/*.txt` | Training-only: `enchant_slot_header.txt`, `item_type_armor.txt`, `item_type_melee.txt`, `special_weight_item_name.txt` |
| Tooltip config | `configs/mabinogi_tooltip.yaml` | Section definitions, header patterns, parse modes, detection params |
| GT images | `data/sample_images/*_original.png` | Test images with ground truth `.txt` files |

---

## API Endpoints

| Endpoint | Input | Pipeline |
|----------|-------|----------|
| `POST /upload-item-v3` | Original color screenshot (multipart) | Full V3 pipeline (Stages 1-8) |
| `POST /upload-item-v2` | Browser-preprocessed binary PNG | Legacy pipeline (line split → OCR → FM, no segmentation) |

V3 response: `{sections: {section_name: OcrSectionResponse}, tagged_segments, abbreviated, session_id?}`

See `documents/API_SPEC.md` for full response schema.
