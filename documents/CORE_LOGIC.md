# Core Logic Reference

Detailed descriptions of individual algorithms and correction strategies in the OCR pipeline. For the high-level pipeline overview, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 1. Dullahan — Effect-Guided Enchant Header Correction

**File:** `backend/lib/text_corrector.py`
**Methods:** `do_dullahan()`, `_dullahan_score_body()`
**Called from:** `apply_fm()` → `has_slot_hdrs` branch

*Named after the headless horseman (and Mabinogi boss monster) who searches for its head. The algorithm's "body" (effect lines) finds the correct "head" (header name) when OCR can't tell them apart.*

### Problem

The enchant header OCR model reads tiny crops (55-120px wide, ~15px tall). At this resolution, visually similar Korean characters are indistinguishable:

- `마` vs `바` — differ by 1-2 pixels
- `성` vs `폭` — similar stroke density
- `충` vs `씁` — small structural difference

Standard fuzzy matching can't fix this because **both the OCR'd name and the correct name are valid enchant names** in the dictionary.

### Key Insight

802 of 1,172 enchants have unique effect signatures. The effect lines (already OCR'd in the same tooltip) provide a disambiguation signal that the header alone cannot.

### Algorithm

```
Input: header_text = "[접미] 폭단"
       effect_texts = ["수리비 100% 증가", "연금술 마스터리 랭크 1 이상일 때 ...", ...]
       slot_type = "접미"

Step 1: Parse header → extract name "폭단"

Step 2: Score ALL DB entries by name similarity
        폭주=50%  성단=50%  흑단=50%  단장=50%  ...

Step 3: Take candidates within 15 points of best (50-15=35 cutoff)
        → 폭주, 성단, 흑단, 단장, ...

Step 4: Score each candidate's effects against OCR effects (1:1 matching, total)
        성단: 261.7  (수리비✓ 연금술✓ 엘리멘탈✓)
        폭주: 168.9  (수리비✓ partial matches)
        흑단: 119.5
        단장:  59.4

Step 5: Pick candidate with highest effect total → 성단
        effect_total > 0 → accept

Step 6: Name changed? (성단 ≠ 폭단) → return with rank
        → "[접미] 성단 (랭크 8)"
```

### Decision Flow

```
Parse OCR header → extract name
     │
     ├─ Score all DB entries by name (fuzz.ratio)
     │
     ├─ No effects available?
     │    YES → return best name match if score ≥ 80 (header-only, same as old FM)
     │
     ├─ Take candidates within 15 points of best, min 30
     │
     ├─ Score each candidate's effects (1:1 matching, total)
     │    │
     │    ├─ Best candidate has effect_total > 0?
     │    │    YES → effects agree or broke tie → accept
     │    │         (requires name_score ≥ 80 OR effect_total ≥ 120)
     │    │
     │    └─ ALL candidates have effect_total = 0?
     │         YES → header is confidently wrong
     │              → search ALL entries by effects alone
     │              → accept if best_total ≥ 100
     │
     └─ Format output:
          name changed? → "[slot] name (랭크 rank)"   (correction adds info)
          name same?    → "[slot] name"               (preserve OCR format)
```

### Three Cases

#### Case A: Correct header, effects confirm

```
OCR:  [접두] 사라진
      수리비 200% 증가, 보호 3 증가, 대미지밸런스 10 증가, ...

Name match:  사라진 = 100% (only candidate above 85)
Effects:     사라진's effects all match OCR → total ~570
Decision:    effect_total > 0, name_score ≥ 80 → accept
Output:      [접두] 사라진  (name unchanged → no rank)
```

#### Case B: Garbled header, effects break tie

```
OCR:  [접미] 폭단                      ← 성단 with 성→폭 misread
      수리비 100% 증가, 연금술 마스터리 ..., 엘리멘탈 웨이브 ...

Name match:  폭주=50%, 성단=50%, 흑단=50%, 단장=50%  (all tied)
Effects:     성단=261.7 >> 폭주=168.9 >> 흑단=119.5
Decision:    성단 wins by effect total, effect_total ≥ 120 → accept
Output:      [접미] 성단 (랭크 8)  (name changed → rank added)
```

#### Case C: Confident but wrong, effect-only fallback

```
OCR:  [접미] 바드                      ← 마녀, but 마/바 identical at 55px
      파이어 마스터리 ..., 라이트닝 마스터리 ...  (magic effects)

Name match:  바드 = 100%  (perfect match to WRONG enchant)
             마녀 = 0%    (correct enchant has zero name similarity)
Effects:     바드's effects = HP/생명력/대미지 → 0 matches vs magic OCR lines
             effect_total = 0 for ALL header candidates
Decision:    all candidates have 0 → header likely wrong → search by effects
             Effect search: 마녀=148.1, 보물=148.9 (garbled OCR too close to call)
Output:      [접미] 보물 (랭크 9)  (best available — 마녀 needs cleaner OCR)
```

### Body Scoring: `_dullahan_score_body()`

Uses **total** of matched scores, NOT divided by entry effect count. This avoids penalizing entries with availability effects (`발에 인챈트 가능`) that don't appear in OCR output.

```
For each OCR effect line (normalized):
    Find best-matching entry effect (fuzz.ratio, 1:1, no reuse)
    If score > 50: add to total

Return: sum of matched scores (0 if no matches above 50)
```

### Limitations

- **Garbled effects:** When OCR effect quality is poor (e.g., `마리트 격력` for `마법 공격력`), effect matching can't distinguish between enchants with similar effect patterns (마녀 vs 보물: both have `마스터리 ... 마법 공격력`).
- **Low-effect enchants:** Enchants with 1-2 generic effects (like `수리비 n% 증가`) are hard to uniquely identify by effects alone.
- **370 non-unique enchants:** Out of 1,172 entries, 370 share effect signatures with at least one other enchant (including synonym pairs like 음유시인/바드).

---

## 2. Number-Normalized Fuzzy Matching

**File:** `backend/lib/text_corrector.py`
**Method:** `correct_normalized()`

### Problem

OCR output contains numbers that vary per item (`내구력 11/12`, `내구력 8/15`), but dictionary entries use templates (`내구력 n/n`). Direct fuzzy matching fails because digit differences inflate the edit distance.

### Algorithm

```
Input:  "내구력 11/12"   section="item_attrs"

Step 1: Strip structural prefix (- or ㄴ)
        "내구력 11/12"  (no prefix here)

Step 2: Section-specific transform
        reforge: strip "(15/20 레벨)" suffix
        enchant header: extract just the name via regex

Step 3: Extract numbers [11, 12], replace with N
        "내구력 N/N"

Step 4: Match against section dictionary (also N-normalized)
        "내구력 N/N" vs "내구력 N/N" → score 100

Step 5: Re-inject OCR numbers into matched template
        "내구력 N/N" → "내구력 11/12"

Output: ("내구력 11/12", 100)
```

### Section-Specific Behavior

| Section | Special handling |
|---------|-----------------|
| `reforge` | Strip `(N/N 레벨)` suffix before match, re-attach after. Skip `ㄴ` sub-bullets (score=-3). |
| `enchant` | Header lines: extract name only via `_ENCHANT_HDR_PAT`. Effect lines: match full text. |
| `None` | Unknown section → search combined dictionary (all files merged). |
| known but no dict | Return score=-2 (no dictionary prepared for this section). |

---

## 3. Two-Phase Enchant Matching

**File:** `backend/lib/text_corrector.py`
**Methods:** `match_enchant_header()`, `match_enchant_effect()`
**Used in:** Both `has_slot_hdrs` branch (effect FM after Dullahan header match) and linear fallback (`has_slot_hdrs = False`)

### Problem

When enchant headers aren't detected by the white-mask segmentation, lines arrive in a linear stream. The system must identify where headers are and which effects belong to which enchant.

### Algorithm

```
For each enchant line (linear scan):

  Try match_enchant_header(line):
    Match against all _enchant_headers_norm (full "[접미] name (랭크 N)" form)
    If score ≥ 80 → this is a header line
                   → remember entry as current_entry

  Else try match_enchant_effect(line, current_entry):
    Match against only the current_entry's effects (4-8 lines, not full dict)
    Strip prefix, normalize numbers, match, re-inject numbers
    If score ≥ 75 → corrected effect line
```

This is the old path, still used as fallback when white-mask segmentation doesn't detect slot headers.

### Condition-Stripped Effects + `fuzz.ratio`

**Method:** `match_enchant_effect()` uses `fuzz.ratio` against **condition-stripped** effects.

**Why:** Mabinogi enchant effects have two parts: an optional **condition** (e.g., `파 어웨이 랭크 24 이상일 때`) and the actual **effect** (e.g., `최대대미지 20 ~ 45 증가`). Abbreviated tooltips show only the effect. `enchant.yaml` stores these as separate fields:

```yaml
# enchant.yaml structure
- condition: 파 어웨이 랭크 24 이상일 때    # optional, kept for reference
  effect: 최대대미지 20 ~ 45 증가           # used for FM matching
- 수리비 200% 증가                          # plain string = no condition
```

The loading code (`_load_enchant_structured`) extracts only the `effect` field for `effects_norm`. This means FM matching always compares OCR text against the effect-only portion.

**Why `ratio`, not `partial_ratio`:** With condition-stripped effects, all entries are short and similar length. `partial_ratio` inflates scores for very short entries (e.g., `지력 N 증가` trivially matches as a substring of any `...N 증가` text). `ratio` correctly penalizes length differences:

```
OCR:                    "피어싱 레벨 N 증가"
DB effect (correct):    "피어싱 레벨 N ~ N 증가"   → ratio=85 ✓  (wins)
DB effect (wrong):      "지력 N 증가"              → ratio=56 ✗  (loses)
                                                      partial_ratio=92 ✗ (would win!)
```

**Decision:** `fuzz.ratio` with condition-stripped effects, threshold 75. No fallback.

---

## 4. Effect-Only Enchant Identification

**File:** `backend/lib/text_corrector.py`
**Method:** `identify_enchant_from_effects()`

### Problem

In some cases, the slot header exists visually (white-mask detected) but has no OCR text — only the effect lines are readable.

### Algorithm

```
Input:  effect_texts = ["수리비 200% 증가", "보호 3 증가", ...]
        slot_type = "접두"  (optional filter)

For each DB entry (filtered by slot_type):
    1:1 match each OCR effect against entry's effects
    Score = total_matched / n_entry_effects  (avg per entry effect)

Threshold: avg ≥ 50
Return: (best_entry, avg_score) or (None, 0)
```

Note: This method uses `total / n_eff` (average), unlike `_dullahan_score_body` which uses raw total. The average works well for identification from scratch; the total works better for verification where availability effects shouldn't penalize.

---

## 5. Dual-Model Inference

**File:** `backend/lib/dual_reader.py`
**Class:** `DualReader`

### Problem

Mabinogi uses two fonts: `mabinogi_classic.ttf` and `NanumGothicBold.ttf`. A single model trained on both fonts compromises on neither.

### Algorithm

```
Input: line crop image

Run both readers in sequence:
  reader_mc = mabinogi_classic model → (text_mc, conf_mc)
  reader_ng = nanum_gothic_bold model → (text_ng, conf_ng)

Pick winner by confidence:
  if conf_mc ≥ conf_ng → return (text_mc, conf_mc, "mabinogi_classic")
  else                 → return (text_ng, conf_ng, "nanum_gothic_bold")
```

Falls back to single legacy model (`custom_mabinogi.pth`) if font-specific models aren't deployed.

---

## 6. Double-Dip Resize Fix

**File:** `backend/lib/ocr_utils.py`
**Function:** `patch_reader_imgw()`

### Problem

EasyOCR's inference pipeline resizes images **twice**:
1. `get_image_list()`: cv2.LANCZOS resize to fit bounding box
2. `AlignCollate`: PIL.BICUBIC resize to model input size (32 x imgW)

Training only resizes once (step 2). This mismatch degraded accuracy across all models.

### Fix

Replace `get_image_list()` with `_crop_boxes()` that crops without resizing, letting `AlignCollate` handle the single resize — matching training exactly.

**Impact:** +37 exact matches across all models, no retraining needed.

### Verification Rule

OCR on training images must give ~100% accuracy. If not, there's a preprocessing mismatch — investigate before retraining.

---

## 7. Orange-Anchored Header Detection

**File:** `backend/tooltip_segmenter.py`
**Method:** `detect_headers()`

### Problem

Mabinogi tooltips have section headers (인챈트, 세공, 에르그, ...) rendered as orange text on a dark background. Detecting these headers determines segment boundaries for section-aware processing.

### Algorithm

```
Input: original color screenshot (BGR)

Step 1: Orange mask — single pixel condition:
        R > 150, 50 < G < 180, B < 80

Step 2: Horizontal projection — sum orange pixels per row

Step 3: Band filter — contiguous rows with:
        height ≥ 8 AND total orange pixels ≥ 40

Step 4: Local boundary refinement — expand each orange band
        to nearest near-black boundary (dark background edges)

Output: list of (y_start, y_end) header regions
```

**Result:** 26/26 theme images detected, 0 false positives.

---

## 8. Game-Like Rendering Pipeline

**File:** `scripts/ocr/lib/render_utils.py`

### Problem

Synthetic training images must match real inference crops. Previous attempts with simple white-on-black rendering produced training/inference mismatch.

### Pipeline

```
Step 1: Render text
        Dark background (20,20,20) + bright text (220,220,220)
        Font size: random from [16, 16, 17, 17, 18, 18]

Step 2: BT.601 grayscale conversion

Step 3: Threshold at 80 ± random(-10, +40)
        BINARY_INV → bright text becomes black ink

Step 4: Tight-crop to ink bounds
        + splitter padding: pad_y = max(1, h//5), pad_x = max(2, h//3)

Step 5: Downscale to target ~14-15px via cv2.INTER_AREA

Step 6: Re-threshold to strict binary (0/255)

Quality gates: MIN_INK_RATIO=0.02, MIN_WIDTH=10, MIN_HEIGHT=8
```

This closes both the ink ratio gap and the height distribution gap between synthetic and real crops.

---

## 9. Oreo-Flip Enchant Header Preprocessing

**File:** `backend/lib/mabinogi_tooltip_parser.py`
**Functions:** `_oreo_flip()`, `_strip_border_cols()`, `detect_enchant_slot_headers()`
**Training counterpart:** `scripts/ocr/lib/render_utils.py` → `render_enchant_header()`

### Problem

Enchant headers (e.g., `[접미] 성단 (랭크 8)`) are rendered as **white text on a dark background** inside the tooltip. The general content OCR pipeline processes black-on-white binary images (threshold=80). Feeding enchant headers through the same pipeline destroys the text — white text on dark background becomes an all-white or garbled image after standard thresholding.

### Key Insight

The name "oreo" comes from the cross-section pattern: dark background → white text → dark ink after inversion. Like an Oreo cookie: dark-light-dark. The preprocessing isolates white pixels (text) via a color-balanced brightness mask, then inverts to produce black-on-white for OCR.

### Algorithm

```
Input: content_bgr — BGR color crop of enchant region

Step 1: White mask — per-pixel condition on color channels:
        max_ch = max(R, G, B)
        min_ch = min(R, G, B)
        white = (max_ch > 150) AND (max_ch / (min_ch + 1) < 1.4)

        The brightness check (>150) catches white text.
        The ratio check (<1.4) rejects colored pixels (orange headers,
        tinted backgrounds) where one channel dominates.

Step 2: Strip border columns — _strip_border_cols():
        For the leftmost and rightmost 3 columns:
          If column white-pixel density > 50% → zero out column
        Removes UI border pipes that would confuse horizontal projection.

Step 3: Invert — bitwise NOT:
        white_mask (white text = True) → ocr_input (black text on white)

Output: (white_mask, ocr_input)
        white_mask: used for band detection (horizontal projection)
        ocr_input: fed to enchant header OCR model
```

### Slot Header Detection: `detect_enchant_slot_headers()`

Uses the white_mask from oreo_flip to find enchant slot header bands:

```
Input: content_bgr — enchant section color crop

Step 1: _oreo_flip() → white_mask, ocr_source

Step 2: Horizontal projection — sum white_mask pixels per row

Step 3: Run detection — contiguous rows above threshold
        Gap tolerance: 2 rows (same as line splitter)

Step 4: Band filter:
        8 ≤ height ≤ 15  AND  total white pixels ≥ 150

        Height 8-15 matches enchant header text height.
        150px minimum rejects noise bands.

Output: list of (y_start, y_end) slot header bands
```

### OCR Flow: `_ocr_enchant_headers()`

```
For each detected slot header band (y0, y1):
    Crop from ocr_source (black-on-white) with proportional padding:
      pad_y = max(1, h // 5)
      pad_x = max(2, h // 3)

    Run enchant header OCR model → text, confidence

    Parse slot type from text (접두/접미 prefix)
```

### Training-Side Simulation: `render_enchant_header()`

The training data renderer simulates what oreo_flip produces:

```
Step 1: Render bright text (220-255) on dark background (20-45)
        at target font size — grayscale, no color

Step 2: Threshold at 132:
        pixels > 132 → 255 (white), else → 0 (black)
        → white-on-black (simulating white_mask stage)

Step 3: Invert → black-on-white
        Matches oreo_flip's final ocr_input

Output: binary image matching real inference preprocessing
```

This ensures the enchant header OCR model sees the same pixel distribution during training and inference.

### Why Not Standard Thresholding?

Standard grayscale + threshold=80 (used for general content) fails on enchant headers:
- White text (R≈G≈B≈220) on dark bg (R≈G≈B≈30) → grayscale avg ≈ 220 → above threshold → becomes white background, text disappears
- The oreo_flip approach uses a **color-balanced brightness mask** instead of a simple luminance threshold, which correctly isolates white text while rejecting colored elements (orange section headers, tinted UI elements)
