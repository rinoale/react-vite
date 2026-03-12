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
    │     ├── ItemModHandler:
    │     │     Color mask (pink) → detect special upgrade line → content_ng_reader OCR
    │     │     Regex: ([RS])\s*[\(\[]?\s*(\d+)\s*단계 → type + level (1-8)
    │     │     Always emits has_special_upgrade flag for frontend correction UI
    │     │
    │     ├── ErgHandler:
    │     │     @plain_lines_only (only unprefixed lines OCR'd)
    │     │     Regex: 등급\s+([SAB])\s*[\(\[]?\s*(\d{1,2})\s*/\s*(\d{1,2})\s*레벨
    │     │     → erg_grade, erg_level, erg_max_level; first match wins
    │     │
    │     ├── SetItemHandler:
    │     │     @detect_prefix('bullet') + @filter_prefix('bullet')
    │     │     Regex: (.+(?:강화|증가))\s*\+\s*(\d+) → FM vs set_name.txt (cutoff=90)
    │     │     → set_effects: [{set_name, set_level}, ...]
    │     │
    │     └── DefaultHandler (item_attrs, ego, item_grade):
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

**Methods:** `cv2.cvtColor()`, `cv2.threshold()`, `detect_centered_lines()`, `_group_by_y()`

```
Step 1: cv2.cvtColor(content_bgr, COLOR_BGR2GRAY)
Step 2: cv2.threshold(gray, 80, 255, THRESH_BINARY_INV) → binary (black text on white)
Step 3: cv2.bitwise_not(binary) → binary_detect (white text on black, for line detection)
Step 4: TooltipLineSplitter.detect_centered_lines(binary_detect)
  → horizontal projection profiling
  → greedy group merging (no gap tolerance, min_height=13)
  → centered window placement with conflict resolution
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
    parser.detect_centered_lines(detect_binary)
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

FM is now per-handler. Each handler calls `snapshot_and_strip()` (which saves `raw_text` before FM), then its section-specific FM. `merge_continuations()` runs BEFORE FM in the enchant handler so FM sees complete merged text with all numbers.

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
Step 0: merge_continuations(lines)  — BEFORE FM
  Merge continuation lines (no bullet prefix) into preceding anchor.
  Merges both 'text' and 'raw_text'. Sets anchor['_is_stitched'] = True.
  This ensures FM sees the complete effect text with all rolled numbers.

Step 1: Resolve P1 entries from parsed_item_name (Stage 5)
  For '접두'/'접미': lookup_enchant_by_name(name) → DB entry

Step 2: Group lines by slot header
  Each slot = (header_line, [effect_lines])

Step 3: Header FM — do_dullahan(header_text, effect_texts, slot_type)
  Score all DB entries by fuzz.ratio on header name
  Use effect lines to break ties (body scoring)
  → (corrected_header, score, matched_entry)

Step 4: Effect FM — _assign_effects_batch() when entry is known:
  a. Build score matrix: score_enchant_effects(texts, entry)
     → scores[i][j] = fuzz.ratio(ocr_line_i, db_effect_j)
  b. find_best_pairs(queries, candidates, scorer=matrix_lookup)
     → greedy 1:1 assignment: highest score first, no duplicates
  c. For each assigned pair: match_enchant_effect(text, entry, force_idx=j)
     → text correction with known DB effect index

  Fallback (no entry): match_enchant_effect per line (cutoff_score=75):
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

### Continuation Stitch Tracking

```
merge_continuations() sets _is_stitched=True on anchor lines
  → _save_crops_by_section() propagates to ocr_results.json
    → router.py reads from ocr_results.json and writes to OcrCorrection.is_stitched
      → Admin dashboard shows badge for stitched corrections
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
| `POST /examine-item` | Original color screenshot (multipart) | Start async V3 pipeline job, return `{job_id}` |
| `GET /examine-item/{job_id}/stream` | — | SSE stream: progress events + final result |
| `POST /upload-item-v2` | Browser-preprocessed binary PNG | Legacy pipeline (line split → OCR → FM, no segmentation) |

V3 response (via SSE `result` event): `{filename, sections: {section_name: OcrSectionResponse}, abbreviated, session_id?}`

See `documents/API_SPEC.md` for full response schema.

### Async Examine-Item (SSE)

The examine-item endpoint runs the V3 pipeline asynchronously and streams progress via Server-Sent Events.

```
Browser                             Backend
  │                                   │
  ├── POST /examine-item ────────────►│  decode image, create job_id
  │◄── { job_id } ───────────────────┤  start pipeline in background thread
  │                                   │
  ├── GET /examine-item/{id}/stream ─►│  SSE connection
  │◄── event: progress {SEGMENTING} ─┤  Stage 1: segment tooltip
  │◄── event: progress {RECOGNIZING} ┤  Stages 2-4: OCR all sections
  │◄── event: progress {RESOLVING} ──┤  Stage 6: enchant P1/P2/P3
  │◄── event: result {data} ─────────┤  final ExamineItemResponse
  │    (stream closes)                │
```

**Pipeline progress callback:** `run_v3_pipeline()` accepts an optional `on_progress(step: str)` callback, invoked at each major stage boundary. The examine endpoint feeds these into a `queue.Queue` consumed by the SSE `StreamingResponse`.

**Thread safety:** The pipeline singleton (`_pipeline`) contains shared EasyOCR readers with GPU state. Concurrent inference is not safe. Current mitigation: low traffic (single user). For production scale, use `ThreadPoolExecutor(max_workers=1)` or move to the distributed worker architecture (see below).

**Frontend:** `examineItemStream(file, {onProgress, onResult, onError})` in `shared/src/api/items.js` posts the file, opens an `EventSource`, and routes SSE events to callbacks. The `useImageUpload` hook maps server-pushed `step` values directly to `loadingStep` state — progress display reflects real pipeline stages, not client-side timers.

---

## Background Jobs

### Overview

Background jobs run in a **standalone worker process** separate from the web server. The worker can run anywhere — on the same server, a different server, or a local PC with a GPU. Communication happens via Redis (message queue) and PostgreSQL (job history).

```
                 PRODUCERS                        BROKER                      CONSUMER
           ┌───────────────────┐              ┌──────────┐              ┌───────────────────┐
           │  Admin API        │──enqueue()──►│          │──dequeue()──►│  Worker process   │
           │  (FastAPI)        │              │  Redis   │              │  (standalone)     │
           ├───────────────────┤              │  Lists   │              │                   │
           │  Scheduler        │──enqueue()──►│          │◄──ack()/────►│  Executes job fn  │
           │  (inside worker)  │              └──────────┘   fail()     │  Records to DB    │
           └───────────────────┘                                        └───────────────────┘
```

### Broker Abstraction

**File:** `backend/jobs/broker.py`

```python
class JobBroker(Protocol):
    def enqueue(self, queue: str, message: JobMessage) -> None: ...
    def dequeue(self, queue: str, timeout: int) -> JobMessage | None: ...
    def ack(self, queue: str, message: JobMessage) -> None: ...
    def fail(self, queue: str, message: JobMessage, error: str) -> None: ...
```

`RedisBroker` is the current implementation. Uses two Redis lists per queue:
- `jobs:{queue}` — pending messages (`LPUSH` to enqueue)
- `jobs:{queue}:processing` — in-flight messages (`BRPOPLPUSH` to dequeue atomically)

Swapping to SQS, Kafka, or Pub/Sub requires only implementing a new class — no changes to worker, jobs, or admin code.

### Message Format

```json
{
  "job_id": "uuid4",
  "job_name": "cleanup_zero_weight_tags",
  "run_id": 42,
  "enqueued_at": "2026-03-09T12:00:00Z",
  "payload": {}
}
```

`run_id` links the message to a `job_runs` DB row for status tracking.

### Job Registry

**File:** `backend/jobs/__init__.py`

```python
REGISTRY = {
    "cleanup_zero_weight_tags": {
        "fn": cleanup_zero_weight_tags,
        "description": "Delete user-created tags with weight 0",
        "schedule_seconds": 12 * 3600,
        "queue": "default",
    },
    "run_v3_pipeline": {
        "fn": _lazy_run_v3_pipeline_job,    # deferred import (cv2/numpy not on backend)
        "description": "Run V3 OCR pipeline on uploaded image (GPU-heavy)",
        "queue": "gpu",
    },
}
```

Each entry: a Python function `fn(db: Session, *, payload: dict) -> str`, a description, an optional schedule interval, and a `queue` name. Adding a new job = write a function + add it here.

`get_queue(job_name)` returns the queue for a given job. Enqueue call sites use this to route jobs to the correct queue.

### Worker

**File:** `backend/worker.py`

Standalone process with two responsibilities:

1. **Dequeue loop** — round-robin poll across subscribed queues (1s timeout per queue), execute job, update `job_runs` row, ack/fail
2. **Scheduler thread** — daemon thread that enqueues scheduled jobs at their configured intervals (only for queues this worker handles)

```bash
# All queues (default for Docker worker)
python worker.py --queues default gpu

# GPU pipeline only (local PC with GPU)
python worker.py --queues gpu

# Lightweight jobs only (deployed server without GPU)
python worker.py --queues default

# No args = all queues from registry
python worker.py

# Remote worker via SSH tunnel (e.g., local PC with GPU)
bash scripts/worker/run-remote.sh gpu
```

**Queue routing:** Jobs are routed to queues by the `queue` field in `REGISTRY`. The `gpu` queue isolates GPU-heavy OCR pipeline jobs so they can be processed by a dedicated worker (e.g. a local PC with a GPU) while the deployed server handles only lightweight `default` queue jobs.

The worker records `worker_id` (hostname) and `payload` (JSON) on each `job_runs` row — visible in the admin dashboard to track which machine processed a job and with what arguments.

Handles `SIGINT`/`SIGTERM` for graceful shutdown.

### Admin API

**File:** `backend/admin/jobs.py`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/admin/jobs` | GET | List registered jobs with last run status and schedule |
| `/admin/jobs/{name}/run` | POST | Enqueue a job (creates `job_runs` row + Redis message) |
| `/admin/jobs/history` | GET | Paginated execution history |

Triggering a job via admin inserts a `pending` row into `job_runs` and calls `broker.enqueue()`. The web server does not execute jobs — it only enqueues them.

### Database

**Table:** `job_runs`

| Column | Type | Description |
|--------|------|-------------|
| `id` | int (PK) | Auto-increment |
| `job_name` | text | Registry key |
| `status` | text | `pending` → `running` → `completed` / `failed` |
| `payload` | text | Job arguments as JSON (set when worker picks up job) |
| `result_summary` | text | Return value of job function |
| `error` | text | Exception message (truncated to 500 chars) |
| `worker_id` | text | Hostname of the worker that executed the job |
| `started_at` | timestamptz | Row creation time |
| `finished_at` | timestamptz | Completion/failure time |

### Infrastructure

Redis runs as a Docker container in both dev and staging:

```yaml
# docker-compose.yml / docker-compose.stg.yml
redis:
  image: redis:7-alpine
  command: redis-server --requirepass ${REDIS_PASSWORD}
  ports:
    - "6379:6379"

worker:
  build:
    context: .
    dockerfile: backend/Dockerfile
    args:
      REQUIREMENTS: requirements-worker.txt   # includes OCR/ML packages
  command: python worker.py --queues default gpu
  depends_on: [db, redis]
```

Staging exposes Redis on port 6379 (password-protected) so remote workers (local PC) can connect.

All Docker services have logging configured with `json-file` driver, `max-size: 10m`, `max-file: 3`.

### File Layout

```
backend/
├── worker.py                  # Standalone worker entry point (--queues arg)
├── jobs/
│   ├── __init__.py            # REGISTRY — job definitions, queue routing, get_queue()
│   ├── broker.py              # JobBroker protocol + RedisBroker implementation
│   ├── connection.py          # get_broker() factory (Redis connection from settings)
│   ├── cleanup_tags.py        # Job: delete zero-weight tags (queue: default)
│   └── run_pipeline.py        # Job: V3 OCR pipeline (queue: gpu)
├── admin/
│   └── jobs.py                # Admin API: list, trigger, history
└── db/
    └── models.py              # JobRun model
```

---

## File Storage

### Overview

File storage abstracts where binary artifacts (uploaded images, OCR crop PNGs, `ocr_results.json`) are persisted. A strategy pattern allows swapping storage backends without changing calling code.

```
FileStorage (ABC)
  ├── R2FileStorage      ← Cloudflare R2 (staging/production)
  ├── S3FileStorage      ← AWS S3 (future, same boto3 SDK)
  └── LocalFileStorage   ← Local disk (dev — shared via ./tmp:/app/tmp volume)
```

### Interface

```python
class FileStorage(ABC):
    def upload(self, key: str, data: bytes, content_type: str) -> str: ...
    def download(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
```

- `key` — storage path (e.g. `ocr_crops/{session_id}/original.png`)
- `upload` returns the storage key/path for the uploaded object
- Implementations handle auth, bucket selection, and SDK specifics internally
- `get_storage(backend=None)` accepts an optional backend override; defaults to `STORAGE_BACKEND` env var
- Instance cache keyed by backend name — multiple backends can coexist

**Storage backend coordination:** The backend passes `storage_backend` in the job payload so the worker uses the same storage the image was uploaded to. This prevents mismatches when backend and worker have different default storage settings.

### File Layout

```
backend/lib/storage/
├── __init__.py       # re-export FileStorage, LocalFileStorage, get_storage
├── base.py           # FileStorage ABC
├── local.py          # LocalFileStorage (disk-based, dev)
├── r2.py             # R2FileStorage (Cloudflare R2 via boto3)
└── connection.py     # get_storage() factory singleton from settings
```

### Why Cloudflare R2

| | Cloudflare R2 | GCS | OCI | AWS S3 |
|---|---|---|---|---|
| **Free storage** | 10 GB | 5 GB | 20 GB | 5 GB (12mo only) |
| **Free ops/mo** | 1M class A, 10M class B | 5K / 50K | 50K / 50K | 2K / 20K |
| **Egress** | Free, unlimited | 100 GB/mo | 10 TB/mo | 100 GB/mo |
| **Always free** | Yes | Yes | Yes | No |

R2 chosen for: zero egress fees (critical for distributed worker), generous free ops, S3-compatible API (boto3), and future use as frontend CDN origin.

### Configuration

```env
STORAGE_BACKEND=r2
R2_ACCOUNT_ID=<cloudflare account id>
R2_ACCESS_KEY_ID=<r2 api token>
R2_SECRET_ACCESS_KEY=<r2 api secret>
R2_BUCKET=mabinogi-ocr
R2_PREFIX=                    # optional key prefix
```

R2 API tokens are created in Cloudflare dashboard → R2 → Manage R2 API Tokens.

### Motivation: Distributed OCR Worker

The V3 pipeline is GPU-heavy (~3s per image). To offload this from the web server, the pipeline can run on a separate worker (e.g. a local PC with a GPU). Shared file storage bridges the gap:

```
POST /examine-item
  → upload image to R2 (key: ocr_jobs/{job_id}/input.png)
  → push job to Redis queue
  → return {job_id}

Worker (local PC)
  ← pull job from Redis
  ← download image from R2
  → run V3 pipeline
  → upload crops to R2 (key: ocr_crops/{session_id}/*.png)
  → publish result via Redis pub/sub

GET /examine-item/{job_id}/stream
  ← subscribe Redis channel
  → forward SSE events to browser
```

The web server never touches the GPU. The worker can be anywhere with network access to Redis and R2.

---

## Authentication & Authorization

### Overview

Stateless JWT-based auth. No server-side sessions — the backend validates the JWT signature and expiry on each request.

### Token Architecture

| Token | Algorithm | Lifetime | Storage | Purpose |
|-------|-----------|----------|---------|---------|
| Access token | HS256 JWT | 30 minutes | `HttpOnly` cookie (`access_token`) | Sent automatically with every request via cookie |
| Refresh token | HS256 JWT | 7 days | `HttpOnly` cookie (`refresh_token`) | Used only to obtain a new token pair when access token expires |

JWT payload: `{"sub": "<user_id>", "type": "access"|"refresh", "exp": <unix_ts>}`

Secret: `JWT_SECRET_KEY` env var (falls back to dev default).

Cookie attributes: `HttpOnly; SameSite=Lax; Domain=.mabitra.com; Path=/`

- `HttpOnly` — not accessible via JavaScript (XSS protection)
- `SameSite=Lax` — sent on same-site requests and top-level navigations
- `Domain=.mabitra.com` — shared across all subdomains (trade, admin, api)

Note: `Secure` and `SameSite=None` are NOT used. Chrome blocks `SameSite=None; Secure` cookies on self-signed certs. Instead, each frontend proxies API calls through `/api/` on its own origin (same-origin), so `SameSite=Lax` suffices.

**Dual-mode token extraction:** Backend reads token from cookie first, falls back to `Authorization: Bearer` header. This supports both web (cookie) and future mobile (header) clients.

### Authentication Flow

```
1. Discord OAuth (sole login method)
   User clicks "Discord" button on /login
     → GET /auth/discord → redirect to Discord authorize URL
     → Discord callback → backend exchanges code for Discord user info
     → Link to existing user (by discord_id or email) or create new user
     → Backend sets HttpOnly cookies (access_token + refresh_token) on response
     → Backend redirects to frontend /login?auth=success
     → Frontend detects ?auth=success → GET /auth/me (cookie sent automatically)
     → AuthProvider sets user state → navigate to home

2. Authenticated Requests
   Any API call (axios baseURL = '/api', withCredentials: true)
     → Same-origin request to /api/* → nginx proxies to backend
     → Browser sends cookies automatically (same-origin, SameSite=Lax)
     → Backend get_current_user reads access_token cookie (or Bearer header fallback)
     → Decodes JWT, loads user from DB
     → If valid + user.status == 0 → request proceeds
     → If invalid/expired → 401

3. Automatic Token Refresh
   API call returns 401
     → Axios response interceptor catches it
     → POST /auth/refresh (refresh_token cookie sent automatically)
     → Backend validates refresh token, sets NEW cookie pair on response
     → Interceptor retries original request (new cookies sent automatically)
     → User never sees the 401
   Concurrent 401s: queued — only one refresh call, then all retry

4. Logout
   POST /auth/logout
     → Backend clears both cookies (set Max-Age=0)
     → Frontend clears user state
```

### Session Persistence

| Scenario | Behavior |
|----------|----------|
| Access token expires (30min) | Auto-refreshed silently via interceptor |
| Refresh token expires (7 days idle) | Refresh fails → cookies cleared → user logged out |
| Active usage | Each refresh issues new 7-day refresh token → session extends indefinitely |
| Tab closed, reopened | Cookies persist → AuthProvider calls GET /auth/me → restores session (or auto-refreshes) |
| Logout clicked | Backend clears cookies, frontend clears user state |

Effective session lifetime: **7 days from last activity**. Indefinite with continuous use.

### Authorization Model

```
Files:
  backend/auth/service.py        — password hashing (bcrypt), JWT encode/decode, Discord OAuth
  backend/auth/dependencies.py   — FastAPI dependencies for auth guards (cookie + Bearer dual-mode)
  backend/auth/router.py         — /auth/* endpoints (Discord OAuth, refresh, logout, me)
  backend/auth/cookies.py        — set_auth_cookies() / clear_auth_cookies() helpers
  backend/crud/user.py           — User/Role/Feature CRUD
```

**Database tables:** `users`, `roles`, `user_roles`, `feature_flags`, `role_feature_flags`

**Seeded data:** roles=`{master, admin}`, feature_flags=`{manage_tags, manage_corrections}`

**Dependency chain:**

```
get_current_user         → any valid JWT, active user (status=0)
optional_user            → same but returns None if no token
require_role("admin")    → user has "admin" role (master bypasses all)
require_feature("X")     → user's roles have feature flag X (master bypasses all)
```

### Marketplace Search

The marketplace search combines three filter types, all AND-intersected.

#### Frontend Flow

When the user types in the search bar (debounced 200ms), three lookups run in parallel:

| # | Source | Endpoint | Dropdown section |
|---|--------|----------|-----------------|
| 1 | PostgreSQL | `GET /tags/search?q=text` | Tag suggestions (up to 10) |
| 2 | In-memory | `searchGameItemsLocal(text)` | Game item suggestions (up to 3) |
| 3 | PostgreSQL | `GET /listings/search?q=text` | Listing suggestions |

Selecting a **tag** adds it as a chip (AND filter) and immediately re-searches. Selecting a **game item** adds an orange chip (AND filter). Selecting a **listing** navigates to its detail view.

The final search call: `GET /listings/search?q=text&tags=tag1&tags=tag2&game_item_id=123`

#### Backend Search Logic (`listing_service.py:search_listings`)

Three independent filters compute sets of listing IDs, then intersect:

```
result_ids = tag_ids ∩ text_ids ∩ game_item_ids
```

**Filter 1 — Tags** (exact name, AND across all chips):
```sql
SELECT listing_id FROM tags t
JOIN tag_targets tt ... JOIN (listing_resolve_cte) sub ...
WHERE t.name IN (:tags)
GROUP BY listing_id
HAVING COUNT(DISTINCT t.name) = :tag_count
```

Tags resolve through a CTE that maps each listing to all its related entities (`listing`, `game_item`, `enchant`, `listing_options`). A tag on an enchant matches any listing with that enchant.

**Filter 2 — Text query** (cascading ILIKE, stops at first tier with results):

| Tier | SQL | CTE? | Matches |
|------|-----|------|---------|
| 1 | `tags.name ILIKE '%q%'` | Yes | Tag names → resolve to listing IDs via CTE |
| 2 | `game_items.name ILIKE '%q%'` | No | Direct JOIN to listings |
| 3 | `listings.name ILIKE '%q%'` | No | Direct WHERE on listings |

Only one tier executes — once results are found, lower tiers are skipped.

**Filter 3 — Game item** (exact ID):
```sql
SELECT id FROM listings WHERE status = 1 AND game_item_id = :gi
```

#### Activity Logging

Search activity is logged via `BackgroundTasks` (after response is sent) to `user_activity_logs` with action `search`. Metadata includes query text, tags, game_item_id, and result count.

### Endpoint Authorization Map

| Router | Endpoint Pattern | Guard |
|--------|-----------------|-------|
| `/auth/*` | refresh, logout, discord, discord/callback | None (public) |
| `/auth/me` | GET, PATCH | `get_current_user` |
| `/admin/*` | All GET endpoints | `require_role("admin")` |
| `/admin/tags` | POST, DELETE, PATCH (mutations) | `require_feature("manage_tags")` |
| `/admin/users/*/roles/*` | POST, DELETE | `require_role("master")` |
| `/admin/roles/*/features/*` | POST, DELETE | `require_role("master")` |
| `/admin/corrections/*` | All except crop | `require_feature("manage_corrections")` |
| `/admin/corrections/crop/*` | GET | None (public, serves static images) |
| `/register-listing` | POST | `get_current_user` |
| `/examine-item` | POST | None (public) |
| `/listings`, `/tags/search`, `/game-items` | GET | None (public) |

### Frontend Auth Infrastructure

```
Files:
  shared/src/api/auth.js              — API functions (getMe, logout, updateProfile, getDiscordAuthUrl)
  shared/src/api/client.js            — Axios with withCredentials: true, response interceptor (auto-refresh on 401)
  shared/src/hooks/useAuth.js         — AuthContext + useAuth() hook
  shared/src/components/AuthProvider   — Context provider (cookie-based, calls getMe on mount)
  shared/src/components/RequireAuth    — Route guard (redirects to /login if not authenticated)
  trade/src/pages/login.jsx           — Discord OAuth login page
```

**AuthProvider** wraps the app at root level (`main.jsx`). On mount, calls `GET /auth/me` (cookies sent automatically). Exposes `{user, loading, loadUser, logout, isAuthenticated}` via context. No localStorage — cookies are managed entirely by the browser.

**RequireAuth** wraps protected routes (e.g. `/sell`). Redirects to `/login` with `state.from` if not authenticated.

**Sidebar** shows discord username + logout button when authenticated, login link when not.

**Admin dashboard** conditionally shows "Users" tab only when `user.roles` includes `'master'`.

### Cross-Domain Cookie Sharing

All apps are served behind nginx under subdomains of `.mabitra.com`. The backend sets `HttpOnly` cookies with `Domain=.mabitra.com`, making them accessible to all subdomains automatically. No `localStorage` — the browser manages cookie lifecycle.

**Why not `localStorage`?** `localStorage` is scoped per origin (protocol + domain + port). The monorepo apps run on different subdomains, so `localStorage` is not shared between them. Cookies with a shared domain solve this.

**Why same-origin proxy instead of cross-origin AJAX?** Chrome blocks `SameSite=None; Secure` cookies on self-signed certs (treats them as "not truly secure"). Rather than requiring real SSL certs for development, each frontend's nginx server block includes `location /api/` that proxies to the backend. This makes all API calls same-origin, so `SameSite=Lax` works naturally. The `dev.api.mabitra.com` subdomain still exists for direct API access (Swagger docs, mobile clients with Bearer header).

---

## Infrastructure & Domains

### Domain Structure

| Environment | Trade | Admin | API |
|-------------|-------|-------|-----|
| Development | `dev.trade.mabitra.com` | `dev.admin.mabitra.com` | `dev.api.mabitra.com` |
| Staging | (TBD) | (TBD) | (TBD) |
| Production | `trade.mabitra.com` | `admin.mabitra.com` | `api.mabitra.com` |

All subdomains share cookies via `Domain=.mabitra.com`.

### Reverse Proxy (nginx)

nginx terminates HTTPS and routes traffic by subdomain. Each frontend server block includes an `/api/` location that proxies to the backend (same-origin API access):

```
Client (HTTPS)
  │
  └── nginx (port 443, SSL termination)
        ├── dev.trade.mabitra.com
        │     ├── /api/*  → backend FastAPI (:8000)   ← same-origin proxy
        │     └── /*      → frontend trade app (:5173)
        ├── dev.admin.mabitra.com
        │     ├── /api/*  → backend FastAPI (:8000)   ← same-origin proxy
        │     └── /*      → frontend admin app (:5174)
        ├── dev.misc.mabitra.com
        │     ├── /api/*  → backend FastAPI (:8000)   ← same-origin proxy
        │     └── /*      → frontend misc app (:5175)
        └── dev.api.mabitra.com    → backend FastAPI (:8000)  (direct, for Swagger/mobile)
```

Port 80 redirects all HTTP requests to HTTPS (`301`).

### HTTPS (Development)

Self-signed wildcard certificate for `*.mabitra.com`:
- Certificate: `infra/nginx/certs/dev.crt`
- Key: `infra/nginx/certs/dev.key`
- Validity: 365 days, regenerate as needed

Users must accept the self-signed cert in their browser for each subdomain on first visit.

### Local DNS

For development, `/etc/hosts` (both WSL and Windows) maps subdomains to `127.0.0.1`:

```
127.0.0.1  dev.trade.mabitra.com dev.admin.mabitra.com dev.misc.mabitra.com dev.api.mabitra.com
```

### Package Split

Backend and worker have separate requirements files to avoid installing GPU/ML packages on the web server:

| File | Purpose | Installs |
|------|---------|----------|
| `requirements.txt` | Web server (FastAPI) | fastapi, SQLAlchemy, httpx, boto3, oci, etc. |
| `requirements-worker.txt` | Worker (OCR pipeline) | `-r requirements.txt` + easyocr, opencv, numpy, Pillow, scikit-learn, rapidfuzz |

The Dockerfile accepts `ARG REQUIREMENTS=requirements.txt` (defaults to slim). Worker overrides via docker-compose build arg:
```yaml
worker:
  build:
    args:
      REQUIREMENTS: requirements-worker.txt
```

Jobs that need OCR packages use lazy imports (e.g. `_lazy_run_v3_pipeline_job`) so the backend can register them in `REGISTRY` without importing `cv2`/`numpy` at startup.

### Usage Monitoring

**Files:**
- `backend/admin/usage.py` — Cloudflare R2 usage (GraphQL Analytics API)
- `backend/admin/usage_oci.py` — OCI cost breakdown (Cost Analysis API)
- `frontend/packages/admin/src/components/UsagePanel.jsx` — Admin dashboard panel

**R2 Usage** (`GET /admin/usage/r2`):

Queries Cloudflare GraphQL Analytics API (`r2StorageAdaptiveGroups` + `r2OperationsAdaptiveGroups`) for current month. Returns storage bytes, object count, Class A/B operation counts, and percentages vs free tier limits (10GB storage, 1M Class A, 10M Class B).

Note: Storage dataset uses `Date!` type with `date_geq`/`date_leq` filters. Operations dataset uses `DateTime!` type with `datetime_geq`/`datetime_leq` filters. Storage does not support `orderBy`.

**OCI Cost** (`GET /admin/usage/oci`):

Uses OCI Python SDK `UsageapiClient.request_summarized_usages()` for current month cost breakdown by service. Returns total estimated cost and per-service breakdown in account currency.

Note: OCI Cost API requires date parameters at midnight UTC precision (zero hours/minutes/seconds). End date is set to tomorrow midnight.

**Config:**
```env
CLOUDFLARE_API_TOKEN=<token>   # Cloudflare API token with Account Analytics Read
OCI_TENANCY_OCID=ocid1.tenancy.oc1..xxx
OCI_USER_OCID=ocid1.user.oc1..xxx
OCI_FINGERPRINT=xx:xx:xx:...
OCI_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----
OCI_REGION=ap-chuncheon-1
```

### Docker Environment

Backend reads `.env.development` via symlink created at container startup:
```
/app/env/.env.development  (mounted from host, read-only)
  ↑
/app/backend/.env.development  (symlink, created by init script)
```

This avoids Docker mount conflicts when `./backend` volume already contains a symlink at that path.
