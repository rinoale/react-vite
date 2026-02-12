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

---

## Resolved: 62 Missing Characters

**Fixed in Attempt 7.** Character set expanded from 442 → 509 chars. Added 62 GT-missing characters (41 Korean syllables, 15 lowercase Latin, 4 uppercase Latin, ㄴ, comma) plus 5 template-required characters (민번센첩황). File: `backend/unique_chars.txt`.

## Resolved: Dimension Mismatch (Fixed Height)

**Fixed in Attempt 7.** Training images now render at game font sizes (9-11) on ~260px canvas, producing natural heights of 10-14px instead of fixed 32px. The model's inference pipeline handles resizing internally.

## Resolved: Dictionary-Only Labels

**Fixed in Attempt 7.** Rewrote `generate_training_data.py` with template-based generator producing ~2,300 tooltip line patterns (stat lines, color parts, enchants, sub-bullets, reforging, piercing, prices, etc.) plus GT lines verbatim and dictionary entries.

---

## Current: Squash Factor Mismatch (Attempt 7 → 8 Fix)

EasyOCR's `AlignCollate` resizes to `imgH=32` then squashes to `imgW=200` if too wide. The squash factor depends on original height:

| Source | Height | Squash factor |
|--------|--------|---------------|
| Real 7px crop | 7px | **5.9x** |
| Real 10px crop | 10px | **4.2x** |
| Attempt 7 synthetic | 14px | **3.0x** |

The model trained on 3.0x squash but encounters 4.2x–5.9x at inference. Lines at 10-15px height (squash ~3x) achieved 80-93% char accuracy; 7px lines performed far worse.

**Fix (Attempt 8):** Added font size 8 (~30% of images) producing 8-9px tall text. Squash factor now ranges 3.0x–5.0x, covering the real distribution.

---

## Current: Short Text Hallucination (Attempt 7 → 8 Fix)

Short text like "세공" (4 chars) on a 260px canvas is 80% whitespace. After squashing to 200px, the CTC decoder hallucinates extra characters to fill the space. Real short-text crops are narrow (22-100px) because the splitter crops to ink bounds.

**Fix (Attempt 8):** Canvas width now proportional to text length. Short text gets tight-cropped (60% of the time), matching splitter behavior. Generated images now range 22-280px wide (was always ~260px).

---

## Current: Underfitting on Varied Training Data (Attempt 8)

Attempt 8 introduced font size 8 and proportional canvas width, making training data much more varied. With only 5,000 iterations, synthetic accuracy reached just 56.2% (vs 97.7% in Attempt 7). Real-world accuracy regressed from 35.8% to 28.3%.

**Fix (Attempt 8b):** Continue training from checkpoint with `--saved_model` for 10,000 more iterations. The model needs more time to converge on the harder distribution.

**Lesson:** Always use `--batch_size 64` (not default 192) and ensure sufficient iterations when training data variety increases. Use `python3 -u` for unbuffered log output with `nohup`.

---

## v2 Pipeline Results

| Attempt | Exact (of 235) | Char Acc | Confidence | Key Change |
|---------|----------------|----------|------------|------------|
| Baseline (Att 6) | 0 (0%) | 19.5% | 0.039 | Dictionary-only, 32px fixed, 442 chars |
| Attempt 7 | 1 (0.4%) | 35.8% | 0.097 | +67 chars, templates, natural height |
| Attempt 8 (5k) | 0 (0%) | 28.3% | 0.004 | +font size 8, proportional canvas (underfit) |
| Attempt 8b | Pending | Pending | Pending | Continue from checkpoint (+10k iter) |

**Stage 1 gate:** 60% real char accuracy on synthetic-only training → then move to Stage 2 (fine-tune with real GT line crops).

Pipeline mechanics confirmed working (line detection perfect, `recognize()` API functional). Recognition is the sole bottleneck.
