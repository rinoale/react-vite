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

### Dual-Form Matching: Effect-Only + Full Condition+Effect

**Methods:** `match_enchant_effect()`, `_dullahan_score_body()`, `identify_enchant_from_effects()`, `build_templated_effects()`

Mabinogi enchant effects have two parts: an optional **condition** (e.g., `내츄럴 매직 실드 랭크 3 이상일 때`) and the actual **effect** (e.g., `마법 공격력 12 증가`). `enchant.yaml` stores these as separate fields:

```yaml
# enchant.yaml structure
- condition: 내츄럴 매직 실드 랭크 3 이상일 때
  effect: 마법 공격력 5 ~ 15 증가
- 수리비 200% 증가                          # plain string = no condition
```

**Two parallel normalized lists** per DB entry:
- `effects_norm` — effect-only: `마법 공격력 N ~ N 증가`
- `effects_full_norm` — condition+effect: `내츄럴 매직 실드 랭크 N 이상일 때 마법 공격력 N ~ N 증가`

For plain strings (no condition), both forms are identical.

**Why both forms:** Abbreviated tooltips show only the effect — `effects_norm` wins. But after `merge_fragments` rejoins wrapped lines, the OCR text includes the condition prefix. Matching against `effects_norm` tanks because the unmatched condition prefix inflates edit distance. `effects_full_norm` provides the correct template.

**Matching:** Every scoring site tries both forms and picks the higher `fuzz.ratio` score:

```
OCR (merged):  "내츄럴 매직 실드 랭크 3 이상일 때 마법 공격력 12 증가"
effect-only:   "마법 공격력 N ~ N 증가"                    → ratio=48 ✗
full form:     "내츄럴 매직 실드 랭크 N 이상일 때 마법 공격력 N ~ N 증가"  → ratio=89 ✓
```

**Number re-injection with full form:**

```
Full norm template: "내츄럴 매직 실드 랭크 N 이상일 때 마법 공격력 N ~ N 증가"  (3 N's)
OCR numbers:        ['3', '12']                                                  (2 values)

len(numbers)=2 < n_placeholders=3 → "last N" trim does NOT fire
Inject: N→3, N→12 → "...랭크 3 이상일 때 마법 공격력 12 ~ N 증가"
Cleanup ~ N       → "...랭크 3 이상일 때 마법 공격력 12 증가"  ✓
```

**Min/max extraction:** Always uses `effects[idx]` (effect-only raw text), never the full form. Condition numbers (e.g., `랭크 3`) must not pollute range parsing.

**Why `ratio`, not `partial_ratio`:** `partial_ratio` inflates scores for very short entries (e.g., `지력 N 증가` trivially matches as a substring of any `...N 증가` text). `ratio` correctly penalizes length differences:

```
OCR:                    "피어싱 레벨 N 증가"
DB effect (correct):    "피어싱 레벨 N ~ N 증가"   → ratio=85 ✓  (wins)
DB effect (wrong):      "지력 N 증가"              → ratio=56 ✗  (loses)
                                                      partial_ratio=92 ✗ (would win!)
```

**Decision:** `fuzz.ratio` with dual-form matching, threshold 75 for effect FM.

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

---

## 10. Item Name Parsing (`parse_item_name`)

**File:** `backend/lib/text_corrector.py`
**Method:** `TextCorrector.parse_item_name()`
**Constants:** `_HOLYWATER`, `_EGO_KEYWORD`

### Problem

The pre_header region contains a single line with multiple components concatenated:

```
[holywater] [enchant_prefix] [enchant_suffix] [정령] item_name
```

All components except `item_name` are optional. The OCR outputs this as a flat string — the algorithm must decompose it into structured fields. This is challenging because:
- Enchant prefix/suffix names can be 1-4 words (e.g., `창백한` or `피닉스의 불꽃`)
- Some item names coincidentally start with words that are also enchant prefix names (e.g., `파멸의 로브` where `파멸의` is both an enchant prefix AND part of the item name)
- OCR errors mean exact string matching won't work

### Algorithm (right-to-left anchor)

The key insight: **item_name is the longest, most unique component** and always appears at the rightmost position. Anchor it first, then parse what remains.

```
Input: "각인된 창백한 명사수 정령 나이트브링어 프레데터"

Step 1 — Holywater strip:
    words = [각인된, 창백한, 명사수, 정령, 나이트브링어, 프레데터]
    fuzz.ratio('각인된', '각인된') = 100 ≥ 70 → holywater = '각인된'
    words = [창백한, 명사수, 정령, 나이트브링어, 프레데터]

Step 2 — Ego strip:
    Scan all words for '정령' match (fuzz.ratio ≥ 70)
    fuzz.ratio('정령', '정령') = 100 → ego = True, remove
    words = [창백한, 명사수, 나이트브링어, 프레데터]

Step 3 — Item name anchor (right-to-left):
    Try progressively longer suffixes against item_name.txt (~20K entries):
    i=0: '창백한 명사수 나이트브링어 프레데터'  → score=73
    i=1: '명사수 나이트브링어 프레데터'          → score=85
    i=2: '나이트브링어 프레데터'                 → score=100 ← BEST
    i=3: '프레데터'                              → None
    best_split = 2, item_name = '나이트브링어 프레데터'

Step 4 — Prefix/suffix split (multi-word):
    left_words = [창백한, 명사수]
    Try every split point k of left_words:
    k=0: prefix=None,           suffix='창백한 명사수' → total=0
    k=1: prefix='창백한'(100),  suffix='명사수'(100)   → total=200 ← BEST
    k=2: prefix='창백한 명사수', suffix=None            → total=0

Output: holywater=각인된, ego=True, prefix=창백한, suffix=명사수,
        item_name=나이트브링어 프레데터
```

### Multi-Word Example

```
Input: "축복받은 꿈결 같은 별 조각 크로스보우"

After holywater strip: [꿈결, 같은, 별, 조각, 크로스보우]
Step 3: item_name = '크로스보우' (from right)
Step 4: left_words = [꿈결, 같은, 별, 조각]

    k=0: suffix='꿈결 같은 별 조각'         → no match         → total=0
    k=1: prefix='꿈결', suffix='같은 별 조각' → no good match   → total≈0
    k=2: prefix='꿈결 같은'(100), suffix='별 조각'(100)         → total=200 ← BEST
    k=3: prefix='꿈결 같은 별', suffix='조각' → no match        → total≈0
    k=4: prefix='꿈결 같은 별 조각'          → no match         → total=0

Output: prefix=꿈결 같은, suffix=별 조각
```

The split-point enumeration naturally discovers the optimal boundary between multi-word prefix and multi-word suffix without needing n-gram combinations.

### Threshold Safety Analysis

Holywater and ego detection use `fuzz.ratio ≥ 70` on individual words.

**Holywater — verified safe at 70:**

| Holywater word | Closest enchant name | Score | Margin |
|----------------|---------------------|-------|--------|
| `각인된` | (none above 60) | — | safe |
| `축복받은` | (none above 60) | — | safe |
| `신성한` | `각성한`, `성실한`, `신속한`, `신중한` | 67 | **3 points** |

`신성한` has the tightest margin — 4 enchant prefixes score 67, just 3 points below the 70 cutoff.

**Ego keyword `정령` — verified safe at 70:** No enchant prefix or suffix scores above 60.

**Item name / prefix / suffix use `fuzz.ratio` with cutoff 60.** These operate on longer strings where the scoring has more granularity, so 60 is sufficient.

### Dictionaries

| Dict | Source | Entries | Word counts |
|------|--------|---------|-------------|
| Holywater | hardcoded `_HOLYWATER` | 3 | `각인된`, `축복받은`, `신성한` |
| Ego | hardcoded `_EGO_KEYWORD` | 1 | `정령` |
| Item names | `item_name.txt` | ~20K | Pure base names (no enchant decorations) |
| Enchant prefix | `enchant_prefix.txt` | 587 | 527×1w + 52×2w + 7×3w + 1×4w |
| Enchant suffix | `enchant_suffix.txt` | 577 | 544×1w + 29×2w + 4×3w |

### Known Edge Cases

- **Coincidental prefix overlap:** ~1847/20166 item names start with an enchant prefix word (e.g., `파멸의 로브`). Step 3 correctly anchors the full item name, leaving no words for Step 4. No false prefix extraction.
- **OCR corruption in holywater/ego:** Single-character errors (e.g., `각인딘` → `각인된`) tolerated by fuzzy threshold. Multi-character corruption fails to match — the word falls through to prefix/suffix matching instead (graceful degradation).

### Maintenance Rules

1. **New holywater types added to game** → add to `_HOLYWATER`, re-run threshold safety check against all enchant prefixes/suffixes.
2. **New enchant prefixes/suffixes added** with names similar to holywater (especially 3-char names similar to `신성한`) → re-verify the margin is still ≥ 3.
3. **`item_name.txt` regenerated** → no algorithm changes needed, FM handles dynamically.
4. **Threshold values (70 for holywater/ego, 60 for item_name/prefix/suffix) must not be changed** without re-running the full safety analysis across all dictionaries.

---

## 11. Distanced Line Finder — Gap-Based Outlier Detection

**File:** `backend/lib/line_merge.py`
**Function:** `detect_gap_outlier()`

### Problem

The tooltip segmenter assigns content regions to sections by header boundaries, but the boundaries aren't pixel-perfect. Non-enchant content (e.g., `불 속성` elemental damage text) can leak into the bottom of an enchant segment. These leaked lines are spatially distant from the real enchant effects — there's a visible gap in the tooltip where a different section begins.

### Key Insight

Within a single section, consecutive lines have consistent vertical spacing (typically 3-5px gaps between line bounding boxes). A leaked line from another section breaks this rhythm with a much larger gap. The algorithm doesn't need to know *what* the leaked content is — it only needs to detect the spatial discontinuity.

### Algorithm

```
Input: active_items = [(orig_index, bounds_dict), ...]
       Each bounds_dict has 'y' (top) and 'height'

Step 1: Compute inter-line vertical gaps for consecutive pairs
        gap[k] = item[k].y - (item[k-1].y + item[k-1].height)

        Example gaps for dropbell enchant segment:
        [3, 4, 3, 4, 3, 4, 3, 11]
                                 ↑ leaked 불 속성

Step 2: Median gap
        sorted = [3, 3, 3, 3, 4, 4, 4, 11]
        median = 3  (middle value)

Step 3: Outlier threshold = max(median * 2, median + 4)
        = max(6, 7) = 7

        Why this formula:
        - median * 2: scales with line spacing (tolerates denser/sparser layouts)
        - median + 4: absolute floor (prevents false positives when median=0 or 1
          due to tightly packed lines where 2× would trigger on normal variation)
        - max(): whichever is more conservative wins

Step 4: Scan from bottom — first gap ≥ threshold is the boundary
        gap=11 ≥ 7 → outlier found at position k

Output: k (position in active_items where outlier starts), or None
```

### Why Bottom-Up Scan

Leaked content always comes from *below* (the segmenter's lower boundary overshoots into the next section). Scanning from bottom finds the outermost boundary first. If multiple gaps exceed the threshold, the bottom-most one is the correct cut point — everything below it is non-enchant.

### Threshold Robustness

| Scenario | Median | Threshold | Typical outlier | Margin |
|----------|--------|-----------|----------------|--------|
| Standard tooltip (1080p) | 3-4 | 7-8 | 10-15 | 3-7px |
| Compact tooltip (768p) | 1-2 | 4-5 | 6-10 | 2-5px |
| Sparse tooltip (1440p) | 5-6 | 10-12 | 15-20 | 5-8px |

The `max(2×, +4)` formula adapts to different resolutions without resolution-specific parameters.

---

## 12. Excess Effect Line Merging

**File:** `backend/lib/line_merge.py`
**Orchestrator:** `merge_excess_lines()`
**Called from:** `text_corrector.py` → `apply_fm()` → after Dullahan header match, before effect FM

### Problem

The line splitter produces one OCR crop per visual text line. Long enchant effects wrap in the tooltip, creating more OCR lines than real effects. Additionally, non-enchant content can leak into the segment from below (addressed by Section 11).

### Prerequisite

The `enchant.yaml` migration gives the exact expected effect count per enchant entry. With both the OCR line count and the DB expected count, the algorithm knows exactly how many excess lines to eliminate.

### Two-Pass Algorithm

**Pass 1 — Gap-Based Trim** (Section 11): `detect_gap_outlier` → `mark_trimmed`. Eliminates leaked non-enchant lines at the segment boundary.

**Pass 2 — Tail-Window Merge:** Absorbs wrapped line fragments into their parent effect lines.

```
Input: remaining active lines after Pass 1

Step 1: excess = len(active) - expected_count
        If excess ≤ 0: done

Step 2: Search window = last (excess * 2) active lines
        Fragments cluster at the bottom because long effects are sorted last
        and are the ones that wrap

Step 3: Rank lines in window by width (ascending)
        Narrowest = most likely fragment

Step 4: Pick narrowest `excess` lines as fragments

Step 5: For each fragment (sorted by index):
        Find nearest preceding active neighbor → append text
        If no preceding neighbor → merge forward into next active line
        Clear fragment (text='', _merged=True)
```

Example: `wingshoes` tooltip — a long enchant effect wraps into a narrow continuation line (~30px wide vs ~150px for full lines). The width ranking correctly identifies it as a fragment.

### Decision Flow

```
Build active list (filter grey/empty)
     │
     ├── len(active) ≤ expected_count?
     │    YES → return (nothing to merge)
     │
     ├── Pass 1: detect_gap_outlier(active)  [Section 11]
     │    │
     │    ├── Outlier found?
     │    │    YES → mark_trimmed() from outlier position onward
     │    │         Rebuild active list
     │    │
     │    └── No outlier → skip
     │
     ├── Recompute excess after trim
     │    excess ≤ 0? → return
     │
     └── Pass 2: find_fragment_indices(active, excess)
          │
          └── merge_fragments() into neighbors
               Clear absorbed fragments (_merged=True)
```

### Function Decomposition

| Function | Type | Input | Output |
|----------|------|-------|--------|
| `detect_gap_outlier(active_items)` | pure | `[(index, bounds), ...]` | trim position or None |
| `find_fragment_indices(active_items, excess)` | pure | active items + count | set of indices |
| `mark_trimmed(lines, active_items, pos)` | mutation | line dicts + position | mutates in-place |
| `merge_fragments(lines, fragment_indices)` | mutation | line dicts + index set | mutates in-place |
| `merge_excess_lines(lines, expected_count)` | orchestrator | line dicts + count | mutates in-place |

Detection functions return positions/indices only — no side effects. Mutation is explicit and separate. Each algorithm is independently testable.

### Post-Merge Filtering

After `merge_excess_lines` runs, absorbed lines have `_merged=True`. The pipeline (`v3_pipeline.py`) removes these from both section data and `all_lines`:

```python
sections['enchant']['lines'] = [l for l in ... if not l.get('_merged')]
all_lines = [l for l in all_lines if not l.get('_merged')]
```

This filtering is a pipeline-level concern, not part of the merge algorithm itself.

---

## 13. Prefix Detection — Column Projection + Width Classification (Detect Bullet)

**File:** `frontend/packages/misc/src/pages/image_process_lab.jsx`
**Functions:** `detectBullets()`, `detectSubbullets()`, `_detectPrefixes()`

### Problem

Mabinogi tooltip lines use small prefix marks to indicate structure:
- `·` (bullet) — enchant effects, reforge options, stat lines (blue/red/grey)
- `ㄴ` (subbullet) — reforge sub-effects at current level (white)

These 2-7px marks are frequently misread by OCR (`·` → `.`, `-`, `,` or dropped; `ㄴ` → `L` or dropped). Visual detection bypasses OCR entirely.

### Algorithm

Two stages: **isolation** via column projection, then **classification** by width and vertical ink extent.

#### Stage 1: Column Projection — Isolate the Prefix Cluster

Operates on a single-line color mask (e.g., blue+red for bullets, white for subbullets).

```
Input: line mask (1 = ink, 0 = background)

Column projection — sum ink pixels per column:

  col:  0 1 2 3 4 5 6 7 8 9 10 11 12 13 ...
  proj: 0 0 3 3 0 0 0 0 0 5  8  7  6  9 ...
            ^^^             ^^^^^^^^^^^^^^^^
          prefix    gap         main text

State machine (left → right):
  1. first_start: first column with ink
  2. first_end:   first column without ink after first_start
  3. main_start:  first column with ink after first_end

Reject if:
  - first_w (= first_end - first_start) > max(8, h * 0.7)  — too wide for a prefix
  - gap_w (= main_start - first_end) < max(2, h * 0.2)     — no clear separation
```

#### Stage 2: Width + Vertical Ink Classification

After isolating the first cluster, classify by its dimensions:

```
Count inkRows: number of rows in the cluster region that contain any ink pixel.

  If first_w ≤ max(3, h * 0.25):
      → Bullet candidate (narrow dot)
      → Confirm: inkRows ≤ max(4, h * 0.5)  — must be vertically small
      → Type: 'bullet'

  Else if first_w ≤ max(8, h * 0.7):
      → Subbullet candidate (wider ㄴ shape)
      → Confirm: inkRows ≤ max(8, h * 0.75)  — can be taller but not full-height
      → Type: 'subbullet'

  Else:
      → Too wide, not a prefix
```

This is a **size heuristic** — it does not examine the actual shape of the ink pixels. A narrow cluster is assumed to be `·`, a wider one is assumed to be `ㄴ`.

### Color Masks

Each detection runs on a specific color mask:
- **Bullet detection:** blue RGB(74,149,238) + red RGB(255,103,103) + grey RGB(128,128,128)
- **Subbullet detection:** white RGB(255,255,255) + red RGB(255,103,103)

### Current Performance

- Bullet (·) detection: **working** — blue/red mask isolates dots cleanly, width heuristic is reliable for dots
- Subbullet (ㄴ) detection: **not working** — white mask includes main text (same color), so the column projection sees one giant cluster with no gap, preventing isolation

---

## 14. Shape Walker — Directional Shape Classification

**Files:** `backend/lib/shape_walker.py`, `backend/lib/prefix_detector.py`
**Frontend port:** `image_process_lab.jsx` → `detectPrefixesShapeWalker()`, `_detectPrefixesShapeWalker()`

### Problem

The width-based classification (Section 13) cannot distinguish shapes — it only measures cluster dimensions. A noise cluster of the right width gets misclassified. The shape walker replaces the width heuristic with actual shape tracing.

### Relationship to Detect Bullet

Both approaches share the same Stage 1 (column projection to isolate the prefix cluster). They differ only in Stage 2:

| | Detect Bullet (Section 13) | Shape Walker (Section 14) |
|---|---|---|
| **Stage 1** | Column projection | Column projection (identical) |
| **Stage 2** | Width + ink height heuristic | Directional walk + flood fill |
| **Color masks** | Separate per type (blue+red for ·, white for ㄴ) | All colors combined |
| **Classification** | Narrow → bullet, wider → subbullet | Walk DOWN→RIGHT → ㄴ, flood fill ≤4px → · |

### Shape Definitions

```python
SHAPE_NIEUN = ShapeDef('ㄴ', segments=[
    Segment(DOWN,  min_px=3),    # vertical stroke ≥ 3px
    Segment(RIGHT, min_px=3),    # horizontal stroke ≥ 3px
])

SHAPE_DOT = ShapeDef('·', segments=[
    Segment(DOT, min_px=1, max_px=4),   # blob with extent 1-4px
])
```

### Algorithm: ㄴ Detection — Directional Walk

```
Cluster mask (7×5 example):

  col: 0 1 2 3 4
       . . . . .    row 0
       . x . . .    row 1  ← seed (topmost ink in leftmost ink column)
       . x . . .    row 2  ↓ walk DOWN
       . x . . .    row 3  ↓ walk DOWN (length=3, meets min_px=3)
       . x x x .    row 4  → walk RIGHT from corner (length=3, meets min_px=3)
       . . . . .    row 5
       . . . . .    row 6

Step 1: find_seeds() — scan leftmost column with ink (col 1),
        return topmost pixel of each vertical run → seed = (1, 1)

Step 2: _walk_segment(DOWN, min_px=3)
        From seed (1,1), step down one row at a time.
        At each step, check a perpendicular band (horizontal, stroke-width thick).
        Continue while any pixel in the band is ink.
        → walks rows 2, 3, 4 → length=3 ≥ 3 ✓
        → end position = (4, 1)

Step 3: Corner transition
        From end (4,1), look one step RIGHT at (4,2).
        Search within ±(stroke_width // 2) perpendicular tolerance for ink.
        → found ink at (4, 2)

Step 4: _walk_segment(RIGHT, min_px=3)
        From (4,2), step right one column at a time.
        Check perpendicular band (vertical) for ink.
        → walks cols 3, 4 → length=3 ≥ 3 ✓

All segments satisfied → match: ㄴ
```

### Algorithm: · Detection — Flood Fill

```
Cluster mask (3×3 example):

  col: 0 1 2
       . . .    row 0
       . x .    row 1  ← seed
       . . .    row 2

Step 1: find_seeds() → seed = (1, 1)

Step 2: _check_dot(min_px=1, max_px=4)
        4-connected flood fill from seed.
        Measure bounding box of all connected ink pixels.
        extent = max(height, width) of bounding box.
        → extent = 1 (single pixel), 1 ≤ 1 ≤ 4 ✓

Match: ·
```

### Thick Stroke Handling

Real tooltip prefixes are 2-3px wide strokes, not single-pixel lines. The walker handles this with `_measure_stroke_width()` — at the seed, it measures the perpendicular extent of ink. During walking, it checks a band of that width, not just a single pixel. This allows the walker to follow strokes of any width without hardcoded size assumptions.

### Why Subbullet (ㄴ) Detection Fails

This is a shared problem between both approaches — it's a Stage 1 (isolation) failure, not a Stage 2 (classification) failure.

The column projection assumes the prefix is the **first** ink cluster from the left. On the white text mask, the ㄴ prefix AND all the white main text appear as ink. The state machine sees one giant continuous cluster with no gap — the ㄴ is never isolated. Neither the width heuristic nor the shape walker ever gets to run.

The bullet mask (blue+red) doesn't have this problem because `·` bullets use a different color than the main text, so the mask naturally contains only the prefix mark and bullet-colored text, with a clear gap between them.

### Current Performance

- Bullet (·): **working** — both approaches detect correctly; shape walker has fewer false positives due to shape verification
- Subbullet (ㄴ): **not working in either approach** — Stage 1 isolation fails on white mask

### Backend Integration

The backend `detect_prefix()` (`prefix_detector.py`) already uses the shape walker for classification (calls `classify_cluster()` from `shape_walker.py`). The width-based classification only exists in the frontend.

### Visualization

```bash
python3 scripts/v3/test_prefix_detector.py data/sample_images/dropbell_original.png
# Output: /tmp/prefix_viz/<stem>_{bullet,subbullet,shapewalk}.png
```

Three images per input compare the approaches:
1. `_bullet.png` — detect bullet (blue+red mask, width classification)
2. `_subbullet.png` — detect subbullet (white mask, width classification)
3. `_shapewalk.png` — shape walker (all colors combined, directional walk classification)
