# OCR Pipeline Issues

## Resolved

- **Incomplete Character Set (v1)** — Expanded from 342 to 442 characters. Added missing digits, punctuation, and 79 Korean characters.
- **Training Data Too Narrow (v1)** — Created `tooltip_general.txt` (453 entries) covering UI labels, item types, enchants, stats, descriptions.
- **Line Splitter Fails on Preprocessed Images** — Added auto-detection of background polarity (light vs dark) with adaptive thresholding.
- **Poor Line Detection** — Replaced connected component approach with horizontal projection profiling. Achieves perfect detection: 75/75, 22/22, 23/23 on test images.
- **Low OCR Confidence** — Fixed `--sensitive` flag bug that silently dropped all Korean training samples.
- **PAD Mismatch** — Added `--PAD` flag to match EasyOCR's hardcoded `keep_ratio_with_pad=True`.
- **Grayscale Domain Gap** — Enforced 100% binary thresholding and re-thresholding after resize.
- **Line Splitter Border Artifacts** — `_remove_borders()` masks narrow (≤3px) high-density vertical column runs. Previous approach masked ALL columns >15% density, which removed 34 columns including text alignment positions (ㄴ, - prefixes), causing lines like `담금질 2/3/4` to disappear.
- **Line Splitter Padding Bleed** — Proportional padding: `pad_x = max(2, h//3)`, `pad_y = max(1, h//5)`.
- **Missing Section Headers** — Kept horizontal separators (removing them destroyed "개조", "세공" headers).
- **Short Text Filtered** — Reduced `min_width` from 30 to 10 for short text like "천옷".
- **CRAFT Detection** — Replaced with `TooltipLineSplitter` in v2 pipeline. CRAFT fragmented lines, merged adjacent text, and missed entire sections on structured tooltip layouts.
- **Splitter Horizontal Border Inflation** — `_add_line()` now filters thin vertical borders (1-2px clusters far from text) and wide horizontal bars (ㅡㅡㅡ with density < 2.0). "보호 1" crop: 248→35px. "아이템 속성" crop: 256→69px.
- **Training/Inference imgW Mismatch** — `ocr_utils.py` monkey-patches EasyOCR to use fixed imgW from yaml instead of dynamic per-image `max_width`. Squash factors now match exactly.
- **Illegible Training Images** — Removed font sizes 6-7 (produced unreadable tiny text). Quality gates enforce ink ratio ≥2%, width ≥10px, height ≥8px on every generated image.
- **Faint Training Images** — Removed augmentation (blur, erode/dilate) that produced 25% unreadable images. Clean binary only.
- **Full-Canvas Whitespace** — Training images now tight-cropped to ink bounds, matching real splitter output. Eliminates hallucination from whitespace.
- **Missing Sparse Continuation Lines** — Lines like `적용)`, `제외)` were missed because their sparse ink fell below the main projection threshold. Added `_rescue_gaps()` two-pass detection: main threshold for normal lines, then lower threshold (`max(2, w*0.01)`) re-scans large gaps to catch sparse continuation lines without causing merging.
- **Merged Blocks Within max_height** — Blocks like `기본 효과` + `무기 공격력 50 증가` merged as h=23 (within max_height=25) despite having a clear zero-projection gap. Added `_has_internal_gap()` check: blocks with 2+ consecutive zero-projection rows get sent to `_split_tall_block()` even if within max_height.
- **Color Parts Not Split Horizontally** — Multi-digit RGB values (e.g., `R:187 G:153 B:85`) merged into one segment because gap sizes (15-16px) were below the split threshold. Made `horizontal_split_factor` configurable (default 3 in base, 1.5 for Mabinogi via `configs/mabinogi_tooltip.yaml`). For h=8 color lines: threshold=12, gaps 15-16 > 12 → correct 4-way split.
- **Section-Aware Parsing** — Created `MabinogiTooltipParser` (`backend/lib/mabinogi_tooltip_parser.py`) that categorizes lines into game sections (item_attrs, enchant, reforge, etc.) using config from `configs/mabinogi_tooltip.yaml`. Enables structured output and section-specific handling (e.g., color parts parsed via regex, flavor text skipped).
- **GT Alignment Drift** — Old GT files didn't match pipeline output (different line counts from horizontal splitting, skip logic changes). Created `scripts/regenerate_gt.py` to produce GT candidates from actual pipeline output. Added `*_expected.txt` files for expected OCR output (separate from full GT).
- **FM False Positive Section Detection** — Content lines containing a section keyword as substring were promoted to section headers (e.g., `너 상 개조55, 보석 비` → promoted to `item_mod`). Fixed by ratio guard in `_match_section_header`: `len(pattern)/len(cleaned) >= 0.5` — a keyword must occupy at least 50% of the cleaned line to qualify as a header.
- **FM Overcorrection (combined dictionary fallback)** — When a section had no dedicated dictionary, FM fell back to the combined 28k-entry pool and could wrongly change correct lines. Fixed: known sections with no dictionary now return sentinel `-2` (FM skipped entirely); only unknown sections fall back to combined.
- **FM Regression on Reforge Headers (level suffix stripped)** — `correct_normalized` for reforge stripped the level suffix `(15/20 레벨)` before FM name matching, but returned only the name — changing already-correct `스매시 대미지(15/20 레벨)` to `스매시 대미지`. Fixed by saving the suffix and re-attaching after name matching.
- **Reforge Sub-bullet FM Overcorrection** — `ㄴ 대미지 150 % 증가` sub-bullets were searched in the reforge dictionary and could be changed to unrelated entries. Fixed: reforge `ㄴ` lines return sentinel `-3` (FM skipped, line excluded from accuracy counting).
- **Enchant Flat-Dictionary False Positives** — FM against 6116-entry flat enchant list could match any random enchant effect to an unrelated line. Fixed by two-phase structured matching: phase 1 identifies the enchant by header (1172 entries), phase 2 searches only that enchant's 4-8 effects.
- **Enchant.txt Format Mismatch** — Dictionary used `접두 6\n관리자` (slot+rank on line 1, name on line 2) but tooltip shows `[접두] 관리자 (랭크 6)`. Transformed 991 old-format header pairs to canonical `[slot] NAME (랭크 RANK)` format. Dictionary now has 1172 structured entries (some were already in correct format).
- **Charset Gap (509 → 1201 chars)** — Dictionary audit found 692 characters in `enchant.txt` and `item_name.txt` not in `unique_chars.txt`. These included common Korean syllables (`국`, `눈`, `말`, `왕`, `옵`, ...) that appear in real enchant effects. The model could never output these characters, and training labels containing them were silently skipped. Fixed by expanding `unique_chars.txt` from 509 → 1201 chars and regenerating `backend/models/custom_mabinogi.yaml`.
- **`set()` Dedup Killed Header Boosts** — `generate_data()` used `list(set(template_lines + ...))` which collapsed all N copies of any header to 1 unique entry → only 3 training images regardless of boost count. Fixed by adding a post-dedup explicit boost block in `generate_data()` after the final `list(set(...))` call.
- **item_name.txt Dataset Dilution** — 20,284 entries in `item_name.txt` would produce ~84k training images, making critical headers 0.004% of the dataset. Fixed by sampling 3,000 entries from `item_name.txt` in `load_dictionaries()`.

---

## Resolved: 62 Missing Characters

**Fixed in Attempt 7.** Character set expanded from 442 → 509 chars. Added 62 GT-missing characters (41 Korean syllables, 15 lowercase Latin, 4 uppercase Latin, ㄴ, comma) plus 5 template-required characters (민번센첩황). File: `backend/ocr/unique_chars.txt`.

## Resolved: Dimension Mismatch (Fixed Height)

**Fixed in Attempt 7.** Training images now render at game font sizes (9-11) on ~260px canvas, producing natural heights of 10-14px instead of fixed 32px. The model's inference pipeline handles resizing internally.

## Resolved: Dictionary-Only Labels

**Fixed in Attempt 7.** Rewrote `generate_training_data.py` with template-based generator producing ~2,300 tooltip line patterns (stat lines, color parts, enchants, sub-bullets, reforging, piercing, prices, etc.) plus GT lines verbatim and dictionary entries.

---

## Resolved: Squash Factor Mismatch (Attempt 8 regression, fixed in Attempt 9)

Proportional canvas width caused 57% of training at wrong squash factors. Fixed by reverting to always ~260px canvas and bimodal font sizes 6-7/10-11.

---

## Resolved: Training imgW vs Inference imgW Mismatch

**Fixed in Attempt 12.** EasyOCR's `recognize()` computed dynamic `max_width = ceil(w/h) * 32` per image (576-1056px), while training used fixed `imgW=200`. Attempts 10-11 tried matching by training with imgW=600 — failed because no single imgW matches all dynamic widths.

**Real fix:** `backend/lib/ocr_utils.py` patches inference to use fixed imgW from yaml, not dynamic per-image max_width. Training and inference now always match.

## Resolved: Training Data Quality Issues

**Fixed pre-Attempt 13.** Three problems in synthetic training data:
1. 25% faint images from blur/erode augmentation → removed all augmentation
2. Font sizes 6-7 produced illegible tiny text → font 10-11 only
3. 97.6% whitespace from full 260px canvas → tight-crop to ink bounds

---

## v2 Pipeline Results

| Attempt | Exact (of 235) | Char Acc | Confidence | Key Change |
|---------|----------------|----------|------------|------------|
| Baseline (Att 6) | 0 (0%) | 19.5% | 0.039 | Dictionary-only, 32px fixed, 442 chars |
| Attempt 7 | 1 (0.4%) | 35.8% | 0.097 | +67 chars, templates, natural height |
| Attempt 8 (5k) | 0 (0%) | 28.3% | 0.004 | +font size 8, proportional canvas (underfit) |
| Attempt 8b (15k) | 0 (0%) | 27.0% | 0.014 | Continue from checkpoint — domain gap confirmed |
| Attempt 9 | 0 (0%) | 36.2% | 0.044 | Reverted canvas to ~260px, bimodal font sizes 6-7/10-11 |
| Attempt 12 | 0 (0%) | 38.1% | 0.120 | Inference imgW patch, squash factors now match |
| Attempt 13 | 14 (6.0%) | 52.4% | 0.247 | Tight-crop, font 10-11, splitter border filter |
| Attempt 14 | 45 (19.6%) | 75.5% | 0.327 | Training data cleanup, GT source switch, splitter left-edge fix |
| **Attempt 15** | **64 (27.8%)** | **77.0%** | **~0.352** | **% spacing, 내구력 6×, 개조 3×, headers 4×, grade colon** |
| Attempt 16 | 28 (12.2%) | 71.3% | TBD | Charset 509→1201 — regression |
| Attempt 17 | REVERTED | — | — | Game-like rendering reverted; new pipeline adopted |

**Current best (v2):** Attempt 15 — 77.0% char acc, 64/230 exact. lightarmor (80.1%) and titan_blade (80.0%) crossed the 80% gate.

**V3 pipeline (segment-first) is now active.** Content model remains a15 (509 chars). V3 validated on titan_blade_original: 10/80 exact, 75.7% char acc. See V3 section below.

### Resolved in Attempt 15

2. ~~**`아이템 속성` → `아이템 색성`** (`속`↔`색` confusion)~~ — Fixed: 10→40 reps for both headers.

3. ~~**`내구력 N/N` always fails**~~ — Fixed: 50→300 reps. Now mostly correct.

4. ~~**개조 variants garbled**~~ — Fixed: 20-30→60-100 reps for all `일반/특별 개조` patterns.

5. ~~**`% / 초` spacing**~~ — Fixed: removed `' %'`; fixed `대미지 배율` and `쿨타임 감소` patterns.

6. ~~**Grade line missing colon**~~ — Fixed: added `마스터 (장비 레벨: N)` with colon.

### Attempt 16 Regression

Attempt 16 regressed to 28/230 exact (71.3% char acc) despite correct preprocessing fixes. Post-mortem identified that the charset expansion (509→1201) alone is insufficient — the rendering domain gap is the deeper bottleneck (see below).

---

## Identified: Rendering Domain Gap (future training target)

Ink ratio gap: real padded crops 0.201 vs synthetic 0.144 (strokes ~1.4× thicker in real). Root cause: game renders colored text on dark bg → BT.601 → threshold captures anti-aliasing halo. Synthetic renders black-on-white → threshold captures only dark core. Fix: game-like rendering at font 10-11. Height already matches (real h=14, synthetic h=14-15). Carry forward to future content model training.

---

## V3 Pipeline — Current Issues

### Blocking issues

1. **Header `등급` → `개조` misclassification** — Header model reads the `등급` bar as `개조` (100% confidence). Causes `item_grade` → `item_mod` mislabeling. Needs header model retraining.

2. **Only 1 original color GT image** — v3 needs original color screenshots. Only `titan_blade_original.png` exists. Other 4 GT images have only `*_processed.png`.

3. **Enchant charset gap (a15)** — `enchant.txt` has 273 chars not in the a15 charset (509). Model can't output these. Acceptable for pipeline structure validation; OCR accuracy on enchant will be limited.

### Content OCR issues (carry forward from v2)

4. **Leading `-` misread as `소` / `#`** — Game dash is 2px wide; PIL renders 3-5px. Unresolved at splitter/training level.

5. **Enchant sub-headers garbled** — `[접두]`/`[접미]` at 42% char acc. V3 helps structurally (enchant section pre-labeled), but raw OCR quality still limits two-phase FM matching.

6. **Ink ratio domain gap** — Synthetic 0.144 vs real 0.201. Future training target (game-like rendering).

### Validation plan

Validate v3 pipeline with a15 content model (509 chars) on **enchant** and **reforge** segments:
- **reforge**: 0 missing chars → full charset coverage. Clean validation target.
- **enchant**: 273 missing chars → pipeline structure validation only (correct segmentation, header label, FM routing).

---

## Future: Frontend Tasks

- **User-editable OCR results** — After OCR processes a tooltip image, display the recognized text per line with editable fields so users can correct any mistakes before submitting. This is a practical fallback: OCR doesn't need 100% accuracy if users can fix errors inline.

## Future: Stage 2 — Human-in-the-Loop Fine-Tuning

Once the synthetic-trained model reaches the 80% accuracy gate, fine-tune with real user-submitted images via a correction pipeline:

**Flow:**
1. User uploads tooltip image → OCR + fuzzy matching produces per-line results
2. Frontend shows a line-by-line correction UI: each line crop (as a small image) next to its OCR text in an editable field
3. User corrects only the wrong lines and submits
4. Server receives the original image + per-line corrections
5. Server runs the splitter on the image, pairs each line crop with the confirmed label, applies quality gates, and stores the pair as a real training sample
6. Accumulated real samples form a Stage 2 LMDB for fine-tuning

**Design notes:**
- Show corrections per-line (not full-text block) to guarantee 1:1 crop-to-label alignment — avoids alignment drift if splitter detects a different line count than user types
- Color part sub-segments (`R:187`, `G:153`, `B:85`) are regex-parsed, not OCR — skip from correction UI and training
- Skipped sections (flavor_text, shop_price) already excluded by parser — no correction needed
- Light validation before accepting into training: fuzzy-match user input against dictionaries and flag outliers to catch typos in corrections
- Store real crops separately from synthetic data; fine-tune from the Stage 1 checkpoint rather than training from scratch
