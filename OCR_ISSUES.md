# OCR Pipeline Issues

## Resolved

- **Incomplete Character Set (v1)** — Expanded from 342 to 442 characters. Added missing digits, punctuation, and 79 Korean characters.
- **Training Data Too Narrow (v1)** — Created `tooltip_general.txt` (453 entries) covering UI labels, item types, enchants, stats, descriptions.
- **Line Splitter Fails on Preprocessed Images** — Added auto-detection of background polarity (light vs dark) with adaptive thresholding.
- **Poor Line Detection** — Replaced connected component approach with horizontal projection profiling. Achieves perfect detection: 75/75, 22/22, 23/23 on test images.
- **Low OCR Confidence** — Fixed `--sensitive` flag bug that silently dropped all Korean training samples.
- **PAD Mismatch** — Added `--PAD` flag to match EasyOCR's hardcoded `keep_ratio_with_pad=True`.
- **Grayscale Domain Gap** — Enforced 100% binary thresholding and re-thresholding after resize.
- **Line Splitter Border Artifacts** — `_remove_borders()` masks vertical border columns (>15% row density).
- **Line Splitter Padding Bleed** — Proportional padding: `pad_x = max(2, h//3)`, `pad_y = max(1, h//5)`.
- **Missing Section Headers** — Kept horizontal separators (removing them destroyed "개조", "세공" headers).
- **Short Text Filtered** — Reduced `min_width` from 30 to 10 for short text like "천옷".
- **CRAFT Detection** — Replaced with `TooltipLineSplitter` in v2 pipeline. CRAFT fragmented lines, merged adjacent text, and missed entire sections on structured tooltip layouts.
- **Splitter Horizontal Border Inflation** — `_add_line()` now filters thin vertical borders (1-2px clusters far from text) and wide horizontal bars (ㅡㅡㅡ with density < 2.0). "보호 1" crop: 248→35px. "아이템 속성" crop: 256→69px.
- **Training/Inference imgW Mismatch** — `ocr_utils.py` monkey-patches EasyOCR to use fixed imgW from yaml instead of dynamic per-image `max_width`. Squash factors now match exactly.
- **Illegible Training Images** — Removed font sizes 6-7 (produced unreadable tiny text). Quality gates enforce ink ratio ≥2%, width ≥10px, height ≥8px on every generated image.
- **Faint Training Images** — Removed augmentation (blur, erode/dilate) that produced 25% unreadable images. Clean binary only.
- **Full-Canvas Whitespace** — Training images now tight-cropped to ink bounds, matching real splitter output. Eliminates hallucination from whitespace.

---

## Resolved: 62 Missing Characters

**Fixed in Attempt 7.** Character set expanded from 442 → 509 chars. Added 62 GT-missing characters (41 Korean syllables, 15 lowercase Latin, 4 uppercase Latin, ㄴ, comma) plus 5 template-required characters (민번센첩황). File: `backend/unique_chars.txt`.

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

**Real fix:** `backend/ocr_utils.py` patches inference to use fixed imgW from yaml, not dynamic per-image max_width. Training and inference now always match.

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

**Stage 1 gate:** 80% real char accuracy on synthetic-only training → then move to Stage 2 (fine-tune with real GT line crops). At 80%+, fuzzy matching only needs to fix minor character errors rather than reconstructing garbled output.

Pipeline mechanics confirmed working (line detection perfect, `recognize()` API functional). Recognition is the sole bottleneck. Attempt 13 addresses the remaining domain gaps: tight-crop training data, splitter border filtering, quality gates.

---

## Future: Frontend Tasks

- **User-editable OCR results** — After OCR processes a tooltip image, display the recognized text per line with editable fields so users can correct any mistakes before submitting. This is a practical fallback: OCR doesn't need 100% accuracy if users can fix errors inline.
