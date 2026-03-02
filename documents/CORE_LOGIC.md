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

## 13. Prefix Detection — Combined Classifier

**Files:** `backend/lib/prefix_detector.py`, `backend/lib/shape_walker.py`
**Tests:** `tests/test_finding_bullet_images.py`, `tests/test_prefix_detector.py`
**Ground truth:** `tests/sample_images/*_original.meta.json`

### Problem

Mabinogi tooltip lines use small prefix marks to indicate structure:
- `·` (bullet) — enchant effects, reforge options, stat lines (blue/red/grey/light grey)
- `ㄴ` (subbullet) — reforge sub-effects at current level (white)

These 2-7px marks are frequently misread by OCR (`·` → `.`, `-`, `,` or dropped; `ㄴ` → `L` or dropped). Visual detection bypasses OCR entirely.

### Architecture Overview

Detection runs in three stages, each solving a specific class of false positives discovered during iterative debugging:

```
Stage 1: Column Projection — isolate [prefix cluster] [gap] [main text]
Stage 2: Shape Walker     — confirm shape (flood fill for ·, directional walk for ㄴ)
Stage 3: Size + Isolation  — reject character fragments by size and vertical padding
```

### Config-Driven Detection

Each prefix type is a declarative config binding color masks to shape definitions:

```python
BULLET_DETECTOR = PrefixDetectorConfig(
    name='bullet',
    colors=(EFFECT_BLUE_RGB, EFFECT_RED_RGB, EFFECT_GREY_RGB, EFFECT_LIGHT_GREY_RGB),
    shapes=(SHAPE_DOT,),
)
SUBBULLET_DETECTOR = PrefixDetectorConfig(
    name='subbullet',
    colors=(WHITE_TEXT_RGB, EFFECT_RED_RGB, EFFECT_GREY_RGB),
    shapes=(SHAPE_NIEUN,),
)
```

`config.build_mask(img_bgr)` builds the combined color mask. `detect_prefix(mask, config)` restricts classification to only the config's shapes. Adding a new prefix type = adding a new config with colors and shapes.

### Stage 1: Column Projection — Isolate the Prefix Cluster

Operates on a single-line binary mask. Sums ink pixels per column, then scans left to right for the pattern `[small ink cluster] → [clear gap] → [main text]`.

```
Input: line mask (255 = ink, 0 = background)

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

### Stage 2: Shape Walker — Confirm Shape

After isolating the cluster region, the shape walker verifies it matches a known prefix shape.

#### · Detection — 8-Connected Flood Fill

```
Cluster mask (3×3 example):

  . . .    row 0
  . x .    row 1  ← seed (topmost ink in leftmost ink column)
  . . .    row 2

_check_dot(min_px=1, max_px=4):
  8-connected flood fill from seed.
  Measure bounding box extent = max(height, width).
  → extent=1, within [1, 4] ✓ → match: ·
```

#### ㄴ Detection — Directional Walk

```
Cluster mask (7×5 example):

  . . . . .    row 0
  . x . . .    row 1  ← seed
  . x . . .    row 2  ↓ walk DOWN
  . x . . .    row 3  ↓ (length=3 ≥ min_px=3 ✓)
  . x x x .    row 4  → walk RIGHT (length=2 ≥ min_px=2 ✓)
  . . . . .    row 5

  _walk_segment(DOWN) from seed → end at corner
  _walk_segment(RIGHT) from corner → all segments satisfied → match: ㄴ
```

### Stage 3: Size Constraints + Vertical Isolation

Shape walker alone can't distinguish a real dot from a character fragment that happens to be ≤4px. Two additional checks filter these false positives:

#### Ink Size Constraints (from width-based classification)

```
bullet:    first_w ≤ max(3, h * 0.25) AND ink_rows ≤ max(4, h * 0.5)
subbullet: ink_rows ≤ max(8, h * 0.75)
```

#### Vertical Isolation Check (`_is_dot_isolated`)

A real `·` sits alone with empty space all around it. Character fragments (bracket corners, anti-aliased edges) have nearby ink above or below.

```
Bracket '[' on mask — TWO corner pixels in same column:

  row  2: #     ← top corner of '['
  row  3: .
  ...
  row 12: #     ← bottom corner of '['

  ink_span = 12 - 2 + 1 = 11  →  exceeds max(4, h * 0.4)  → REJECTED

Real dot '·':

  row  5: .
  row  6: #     ← dot pixel
  row  7: #     ← dot pixel
  row  8: .

  ink_span = 2, padding zone above (rows 4-5) and below (rows 8-9) are empty → PASS
```

The check verifies:
1. **Span**: ink rows must be compact (not scattered across the line)
2. **Padding**: no ink in the vertical padding zone above/below the cluster

### Evolution: How the Combined Classifier Was Developed

The current three-stage classifier was built through iterative debugging, where each new false positive class revealed a limitation in the previous approach.

#### Attempt 1: Width-Based Classification Only

The initial approach used only column projection + cluster width to classify prefixes. Narrow clusters → bullet, wider → subbullet. This worked for obvious cases but had no shape verification.

**Failure:** Any noise cluster of the right width was classified as a prefix.

#### Insight: Column Projection Loses Row Position

Debugging revealed that column projection sums pixels vertically, discarding row positions:

```
Scattered pixels:         Real dot:
  . g . .                   . . . .
  . . . .                   . g . .
  . . . .                   . g . .
  . . g .                   . . . .
  -----                     -----
  0 1 1 0                   0 2 0 0   ← different projections
```

But within a single column, two pixels at rows 0 and 10 produce the same count as two pixels at rows 5 and 6. The 1D projection can't tell scattered character fragments from a compact dot. This motivated adding shape walker as Stage 2.

#### Attempt 2: Shape Walker Only

Replacing width classification with shape walker (flood fill for dots, directional walk for ㄴ) improved precision by verifying actual shape. But new false positives appeared:

**FP class — Anti-aliased character edges:** Grey pixels at the edges of white characters formed small (≤4px) disconnected blobs on the grey mask that passed the 4-connected flood fill.

```
Character with anti-aliased grey edge:

  . . . . . . .
  . . g g g . .      ← grey pixels at character boundary
  . g w w w g .
  . w w w w w .      On grey-only mask, the 'g' pixels form
  . . w w w . .      small isolated blobs that look like dots
  . . . g g . .
```

**Fix — 8-connected flood fill:** Changing `_check_dot` from 4-connected (up/down/left/right) to 8-connected (+ diagonals) made anti-aliased pixels link together into larger blobs that exceed `max_px=4`. The "giant footstep" connects diagonal neighbors, so scattered edge pixels merge into a single large component and get rejected.

#### Insight: Mixed-Color False Positives

A critical realization: **there are no multi-colored prefixes.** A real `·` is always a single color (blue, red, or grey). But the combined mask (blue+red+grey) could merge fragments of different colors into a single cluster:

```
On individual masks:        On combined mask:
  blue:  . b . .              . x . .
  red:   . . r .      →      . x x .  ← looks like a prefix cluster
  grey:  . . . .
```

**Fix — Per-color detection** (`detect_prefix_per_color`): Test each color independently. A prefix must be detectable on a single-color mask. This prevents cross-color fragment merging.

#### Insight: Character Fragment ※ Problem

Even with shape walker, single-pixel character fragments could pass as SHAPE_DOT. Consider the `[` bracket character on a white mask — its top-left and bottom-left corner pixels land in the same column, separated by empty rows:

```
Full bracket:                First column on mask:
  [ 장 미 ]                   row  2: #  ← bracket corner
                               row  3: .
  Column projection:           ...         (10 empty rows)
  cluster=[1px] gap=3 text     row 12: #  ← bracket corner
```

The column projection sees `[1px cluster] [3px gap] [text]` — looks like a prefix. Shape walker's flood fill finds each corner pixel individually as a 1px dot (extent=1, passes `max_px=4`).

**Key insight from ※ analysis:** A real dot must be **isolated** — empty space all around it, not just a gap to the right. The bracket corner at row 2 has another bracket corner 10 rows below. A real `·` has no nearby ink above or below.

**Fix — Vertical isolation check** (`_is_dot_isolated`): After shape walker confirms the shape, verify the cluster's ink pixels are:
1. Vertically compact (span ≤ `max(4, h * 0.4)`) — rejects scattered pixels like bracket corners
2. Vertically isolated — no ink in the padding zone above and below the cluster

#### Result

Each fix targeted a specific false positive class:

| FP Class | Example | Fix | Stage |
|---|---|---|---|
| Noise clusters of right width | Random ink | Shape walker verification | 2 |
| Anti-aliased character edges | Grey pixels around headers | 8-connected flood fill | 2 |
| Mixed-color fragments | Blue + red pixels merging | Per-color detection | Pre-1 |
| Character fragments (brackets, ※) | `[` corner pixels | Vertical isolation check | 3 |
| Oversized character fragments | Wide anti-aliased blobs | Ink size constraints | 3 |

### Per-Color Detection

`detect_prefix_per_color(img_bgr_line, config)` iterates over each color in the config independently. Used in the production pipeline (`mabinogi_tooltip_parser.py`, `line_processing.py`) where BGR images are available.

`detect_prefix(mask_line, config)` operates on a pre-built binary mask. Used in tests and the visualization script where masks are already constructed.

### Color Masks

- **Bullet:** blue RGB(74,149,238) + red RGB(255,103,103) + grey RGB(128,128,128) + light grey RGB(167,167,167)
- **Subbullet:** white RGB(255,255,255) + red RGB(255,103,103) + grey RGB(128,128,128)

Grey RGB(128,128,128) appears in both configs: the game uses it for both disabled bullet `·` and grey subbullet `ㄴ` lines (e.g. greyed-out conditional effects). Light grey RGB(167,167,167) is bullet-only (a distinct shade for partially disabled effects).

### Per-Color Subbullet Detection — Two-Stage Fallback

#### The Problem: ㄴ Fragments in Single-Color Masks

On a **combined** mask (BT.601 binary or all-colors-merged), the ㄴ character is a solid L-shape. But `detect_prefix_per_color` tests each color independently. On a single-color mask, the ㄴ character **fragments** because anti-aliased (AA) pixels between the vertical and horizontal strokes don't match the target color:

```
Combined mask (BT.601 binary):         White-only mask (±15 tolerance):

  col:  0  1  2  3  4  5  6  ...       col:  0  1  2  3  4  5  6  ...
  row 0: .  .  .  .  .  .  .           row 0: .  .  .  .  .  .  .
  row 1: .  #  #  .  .  .  .           row 1: .  #  #  .  .  .  .
  row 2: .  #  #  .  .  .  .           row 2: .  #  #  .  .  .  .
  row 3: .  #  #  .  .  .  .           row 3: .  #  .  .  .  .  .    ← col 2 lost (AA pixel)
  row 4: .  #  #  #  #  .  .           row 4: .  .  .  #  #  .  .    ← cols 1-2 lost (AA)
  row 5: .  .  .  .  .  .  .           row 5: .  .  .  .  .  .  .

  Shape walker: DOWN(3) → RIGHT(2) ✓   Shape walker: DOWN(2) only → fails
  Result: ㄴ detected                   Vertical stub too short, no corner
```

The corner where vertical meets horizontal has sub-pixel blending. Those transitional pixels have RGB values partway between the stroke color and the background — outside the ±15 tolerance of any single color.

On the combined mask, the shape walker sees the full L-shape and classifies it as ㄴ. But per-color detection can't use the combined mask (it would re-introduce mixed-color false positives for bullets). The solution is a two-stage fallback.

#### The Solution: Color Mask Locator → BT.601 Binary Validator

The fallback uses each mask type for what it's best at:

```
Stage A: Color mask → LOCATE the prefix position
  - Scan single-color masks for a narrow first cluster at left edge
  - The fragmented vertical stub is enough to find x-position

Stage B: BT.601 binary → VALIDATE the full shape
  - At the position from Stage A, examine the binary mask
  - Binary preserves the full ㄴ including corner AA pixels
  - Validate: tall ink block + gap + main text follows
```

Why this is safe: BT.601 binary is only used for **validation at a known position** (anchored by the color mask hit), never for open-ended scanning. This prevents the "white mask sees everything as one blob" problem.

#### Algorithm: `_detect_subbullet_fallback()`

```
Input: img_bgr_line (one line crop, BGR color)
       config.colors = [WHITE, RED, GREY]

Step 1 — Find narrow cluster in any config color:
  For each color:
    mask = _color_mask(img_bgr, color, ±15)
    col_proj = sum(mask > 0, per column)
    Scan for: [first_start] → [first_end] → [main_start]
    Reject if first_start > max(10, 15% of width)    ← position check
    Reject if first_w > max(6, h * 0.5)              ← width check
    → cluster_x = first_start

Step 2 — Build BT.601 binary (lazy, shared with bullet path):
    gray = 0.299R + 0.587G + 0.114B
    binary = (gray > 80) * 255

Step 3 — Find ink block in binary near cluster_x:
    bin_col_proj = sum(binary > 0, per column)
    Search cluster_x ± 2 → bin_ink_start
    Find end of ink block → bin_ink_end
    Find main text start → bin_main_start

Step 4 — Validate:
    nieun_w = bin_ink_end - bin_ink_start    (must be ≤ 6)
    gap_w = bin_main_start - bin_ink_end     (must be ≥ max(3, h * 0.2))
    ink_rows = rows with any ink in block    (must be ≥ max(6, h * 0.5))

    All pass → return {type: 'subbullet', x, w, gap, main_x}
```

#### The Gap Discriminator

The key insight that separates real ㄴ from false positives is the **gap width**. The game renderer places a fixed-width space between the ㄴ prefix and the main text, while inter-character gaps within text are narrower:

```
Real ㄴ subbullet line:                    Text character fragment (FP):

  ㄴ  ····  재련 5 이상 일 때              세 ···  공 옵션 레벨 ...
  ^^  ^^^^  ^^^^^^^^^^^^^^^^^^^            ^^  ^^^  ^^^^^^^^^^^^^^^^
  w=4 gap=4 main text                      w=5 gap=2 continues

  first_start=2, first_end=6              first_start=134, first_end=139
  gap=4 ≥ 3 ✓                             gap=2 < 3 ✗ → rejected
  position: 2 < 15% ✓                     position: 134 > 15% ✗ → rejected
```

All verified real ㄴ have gap=4. All observed false positives have gap=1-2. The threshold gap≥3 perfectly separates them.

#### Per-Color Filter Summary

After the main detection loop and before the fallback, per-color filters reject common FP patterns:

| Filter | Threshold | Rejects |
|---|---|---|
| `total_ink < 6` | 6 pixels min | AA specks (1-3 px) in grey masks |
| `gap < 3` | 3 columns min | Inter-character gaps within text |
| `crop_h < 10` | 10 rows min | Short lines where text mimics L-shape |
| `first_w > max(6, h*0.45)` | proportional width | Multi-char fragments passing shape walker |
| `first_start > max(10, 15%)` | left-edge position | Fragments mid-line, not at prefix position |

#### No Bullet Regression

Bullet (`·`) and subbullet (`ㄴ`) detection are fully isolated by `PrefixDetectorConfig`:

```
BULLET_DETECTOR    → colors=(BLUE, RED, GREY, LIGHT_GREY), shapes=(SHAPE_DOT,)
SUBBULLET_DETECTOR → colors=(WHITE, RED, GREY),             shapes=(SHAPE_NIEUN,)
```

Each config restricts both which colors to mask and which shapes to accept. The shape walker rejects ㄴ when looking for DOT (and vice versa). The per-color filters are type-specific (`result['type'] == 'bullet'` vs `'subbullet'`). The fallback only activates for `config.name == 'subbullet'`. Changes to subbullet detection cannot affect bullet detection because they never share a code path at runtime.

### Ground Truth and Testing

Expected counts are stored in `tests/sample_images/*_original.meta.json`:

```json
{
  "prefix": {"bullets": 11, "subbullets": 0},
  "lines": {"headers": 4, "bullet_lines": 26, "white_lines": 13}
}
```

Tests auto-discover images by scanning for `.meta.json` files — adding a new test image requires only dropping the `.png` and `.meta.json` into the directory.

### Visualization

```bash
python3 scripts/ocr/prefix/test_prefix_detector.py tests/sample_images/*_original.png
# Output: tmp/prefix_viz/<stem>_{subbullet,shapewalk}.png
```

Two images per input:
1. `_subbullet.png` — per-color subbullet detection (SUBBULLET_DETECTOR config)
2. `_bullet.png` — combined mask, both shapes, no config restriction

## 14. Shape Walker — General-Purpose Shape Detection

**File:** `backend/lib/shape_walker.py`

The shape walker is a general-purpose shape detection library used by prefix detection (Section 13) but designed for reuse across other detection tasks.

### Shape Definitions

Shapes are defined declaratively as sequences of directional segments:

```python
SHAPE_NIEUN = ShapeDef('ㄴ', segments=[
    Segment(DOWN,  min_px=3),    # vertical stroke ≥ 3px
    Segment(RIGHT, min_px=2),    # horizontal stroke ≥ 2px
])

SHAPE_DOT = ShapeDef('·', segments=[
    Segment(DOT, min_px=1, max_px=4),   # blob with extent 1-4px
])
```

New shapes can be added by defining new `ShapeDef` constants — no code changes needed in the walker itself.

### Thick Stroke Handling

Real tooltip prefixes are 2-3px wide strokes, not single-pixel lines. The walker handles this with `_measure_stroke_width()` — at the seed, it measures the perpendicular extent of ink. During walking, it checks a band of that width, not just a single pixel. This allows the walker to follow strokes of any width without hardcoded size assumptions.

### 8-Connected Flood Fill

`_check_dot` uses 8-connected flood fill (including diagonal neighbors). This was changed from 4-connected to handle anti-aliased character edges — grey pixels at character boundaries form small blobs that are 4-disconnected but 8-connected. The wider connectivity merges them into larger components that exceed `max_px=4` and get rejected.

### API

```python
from lib.shape_walker import classify_cluster, SHAPE_NIEUN, SHAPE_DOT

match = classify_cluster(cluster_mask, [SHAPE_NIEUN, SHAPE_DOT])
if match:
    print(match.shape.name)   # 'ㄴ' or '·'
    print(match.extent)       # (min_row, min_col, max_row, max_col)
    print(match.seg_lengths)  # length per segment
```

### Note on Column Projection and Positional Encoding

Column projection (`col_proj[x] = sum of ink pixels in column x`) is a lossy 1D reduction — it discards row positions. Two pixels at rows 2 and 12 in the same column produce the same count (2) as two adjacent pixels at rows 5 and 6. This is why shape walker (2D) is necessary for shape verification.

A bitmask encoding (`col_proj[x] = sum of 2^y for each ink pixel at row y`) would preserve exact row positions in a single integer. For example, ink at rows 1,2,3 → `2+4+8 = 14 = 0b1110` (contiguous bits), while ink at rows 2,12 → `4+4096 = 4100 = 0b1000000000100` (gap in bits, clearly scattered). Contiguity can be checked with bit operations. This approach could replace shape walker for dot detection but would be more complex for multi-segment shapes like ㄴ.
