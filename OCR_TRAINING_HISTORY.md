# OCR Training History

## Attempt 1: Initial Model (Pre-existing)

The project shipped with a pre-trained model trained only on `reforging_options.txt` entries.

**Problems found:**
1. **Incomplete character set (342 chars)** — Missing digits 0,3,5,8, punctuation #%+-., and 30+ Korean characters. Only 72% of ground truth characters covered.
2. **Training data too narrow** — Only reforging stat names. No item names, enchants, UI labels, numeric values, or descriptions.
3. **Line splitter broken on preprocessed images** — `TooltipLineSplitter` used `THRESH_BINARY` assuming dark background. Frontend outputs white background, so 0 lines detected.
4. **Poor line detection (29/84 lines)** — Connected component approach couldn't merge individual character strokes into lines.
5. **Near-zero OCR confidence (0.01-0.55)** — Downstream of all above issues.

---

## Attempt 2: Retrain with Expanded Data

**Changes made:**
- Created `tooltip_general.txt` dictionary (453 entries) covering all tooltip text categories
- Expanded character set from 342 to 442 characters
- Generated 3,714 training samples using both dictionaries
- Training images: white background, black text (matching frontend output)
- Font: `data/fonts/mabinogi_classic.ttf` (the actual game font)

**Training command:**
```
python3 train.py --train_data ../backend/train_data_lmdb \
  --valid_data ../backend/train_data_lmdb \
  --select_data / --batch_ratio 1.0 \
  --Transformation TPS --FeatureExtraction ResNet \
  --SequenceModeling BiLSTM --Prediction CTC \
  --batch_max_length 30 --imgH 32 --imgW 100 \
  --num_iter 10000 --valInterval 500 \
  --batch_size 64 --workers 0 --sensitive \
  --character "$(cat ../backend/unique_chars.txt | tr -d '\n')"
```

**Problem: `--workers 0` required** — LMDB dataset can't be pickled for multiprocessing. `TypeError: cannot pickle 'Environment' object`.

**Problem: `--sensitive` flag required** — Without it, `dataset.py` lowercases all labels, converting R,G,B,L,A-F to lowercase which aren't in the character set. `KeyError: 'c'`.

**Problem: `--sensitive` flag silently overwrites character set** — `train.py` line 289 had `opt.character = string.printable[:-6]` which replaced the entire 442-char Korean set with 94 ASCII characters. All Korean labels were silently filtered out during training. The model trained to 100% accuracy on ASCII-only entries (numbers, percentages) while learning zero Korean.

**Fix:** Changed the `--sensitive` block to `pass` (just preserve case, don't override characters).

---

## Attempt 3: Retrain with Fixed `--sensitive`

**Changes:** Only the `train.py` fix above. Same data and config.

**Result:** 99.246% accuracy on training data after 10,000 iterations (~29 min on RTX 3070 Ti). Korean text correctly learned — "블레이즈 폭발 대미지", "핸즈 오브 카오스 [변신 중] 솜씨", etc.

**Testing on real game screenshot:**

Using `readtext()` on the full processed tooltip image, EasyOCR detected 81 text regions. Some correct results:
- "최대생명력 25 증가" (0.64)
- "윈드밀 대미지" (0.73)
- "불 속성" (0.78)
- "표면 강화3" (0.68)
- "(2/20 레벨)" (0.79)

But most results were wrong or fragmented. Initially attributed to "font domain gap", but the training script was already using the actual Mabinogi game font.

**Actual root cause: Preprocessing mismatch (PAD)**

EasyOCR inference always uses `keep_ratio_with_pad=True` (resize maintaining aspect ratio, then pad to target width). But the model was trained without `--PAD`, which uses simple resize (stretch to 32x100 regardless of aspect ratio).

- Training: text stretched/distorted to fit 32x100
- Inference: text properly proportioned, padded on the right to 32x100

The model learned to recognize distorted text but receives properly-proportioned text at inference. This explains why training accuracy is 99.2% but real-world accuracy is poor.

**Fix needed:** Retrain with `--PAD` flag so training preprocessing matches EasyOCR inference.

---

## Other Fixes Applied

- **Line splitter auto-detect polarity** — Added mean-based check to use `THRESH_BINARY_INV` for light backgrounds.
- **Horizontal projection profiling** — Replaced connected component line detection. Improved from 29 to 57 lines detected.
- **Backend simplified** — Removed line splitter from OCR pipeline. Now uses `readtext()` directly on full image, letting CRAFT handle detection.
- **Both dictionaries loaded** — Text corrector uses `reforging_options.txt` + `tooltip_general.txt` combined.

---

## Attempt 4: Retrain with --PAD

**Changes:** Added `--PAD` flag. Same data (3,714 samples), same imgW=100.

**Training command:**
```
python3 train.py --train_data ../backend/train_data_lmdb \
  --valid_data ../backend/train_data_lmdb \
  --select_data / --batch_ratio 1.0 \
  --Transformation TPS --FeatureExtraction ResNet \
  --SequenceModeling BiLSTM --Prediction CTC \
  --batch_max_length 30 --imgH 32 --imgW 100 \
  --num_iter 10000 --valInterval 500 \
  --batch_size 64 --workers 0 --sensitive --PAD \
  --character "$(cat ../backend/unique_chars.txt | tr -d '\n')"
```

**Result:** 99.246% best accuracy at 10,000 iterations. Notably faster convergence — 68% at iteration 500 (vs 15% without `--PAD`), confirming the preprocessing mismatch was a real problem.

---

## Attempt 5: Enhanced Augmentation + imgW=200

**Changes:**
- **`imgW` increased to 200** — Accommodates longer text (up to 55 chars). Reduces aspect ratio distortion during resize+pad.
- **`batch_max_length` increased to 55** — Matches the longest labels in the expanded training set.
- **`valInterval` increased to 2000** — Fewer validation checkpoints (5 vs 20).
- **Overhauled `generate_training_data.py`:**
  - 5 variations per word (was 2), producing ~9,285 training samples
  - Variable font sizes (12-26pt) instead of fixed
  - Random thresholding (30% chance, thresh 100-200) — mimics jagged-pixel look of browser-preprocessed screenshots
  - Random dilate/erode (30% chance) — simulates font weight variation
  - Random Gaussian blur (50% chance, radius 0.1-1.0)
  - Random interpolation (NEAREST/BILINEAR/BICUBIC) during resize
  - Aspect-ratio-preserving resize to 32px height (matches inference PAD behavior)
  - Variable padding (0-15px left/right)
- **Fixed `create_model_config.py`:** Uses `.replace('\n', '')` instead of `.strip()` to preserve leading space character in character set (prevents 344 vs 343 class count mismatch).
- **Refactored `custom_mabinogi.py`:** Handles both `opt` namespace and `**kwargs` initialization for EasyOCR compatibility. Architecture params moved into `network_params` block in yaml.

**Training command:**
```
python3 train.py --train_data ../backend/train_data_lmdb \
  --valid_data ../backend/train_data_lmdb \
  --select_data / --batch_ratio 1.0 \
  --Transformation TPS --FeatureExtraction ResNet \
  --SequenceModeling BiLSTM --Prediction CTC \
  --batch_max_length 55 --imgH 32 --imgW 200 \
  --num_iter 10000 --valInterval 2000 \
  --batch_size 64 --workers 0 --sensitive --PAD \
  --character "$(cat ../backend/unique_chars.txt | tr -d '\n')"
```

**Result:** **100% accuracy** at 10,000 iterations (~43 min). Reached 96% by iteration 2000, 99.5% by 4000, 99.9% by 8000. Confidence scores also notably higher (0.5-0.9 range vs 0.1-0.5 in Attempt 4).

---

## Training Flags Reference

| Flag | Why Required |
|------|-------------|
| `--workers 0` | LMDB can't be pickled for multiprocessing |
| `--sensitive` | Prevents lowercasing R,G,B,L,A-F characters |
| `--PAD` | Matches EasyOCR's hardcoded `keep_ratio_with_pad=True` inference |
| `--batch_max_length 55` | Longest labels are ~55 chars |
| `--character "$(cat ...)"` | Full 442-char Korean set (train.py patched so `--sensitive` no longer overrides) |

**Note:** EasyOCR ignores the `PAD` field in the yaml config. It always uses `keep_ratio_with_pad=True` during inference (hardcoded in `recognition.py`). The `PAD: true` in the yaml is for documentation accuracy only — training must always use `--PAD` to match.

---

## Attempt 6: Binary Training Data (Domain Gap Fix)

**Problem diagnosed:** Despite 100% training accuracy (Attempt 5), the model failed on real screenshots. Investigation revealed a domain gap: 78% of synthetic training images were grayscale anti-aliased (255 unique pixel values), while real frontend-preprocessed screenshots are strictly binary (only 0 and 255).

**Root cause:** `generate_training_data.py` only applied thresholding 70% of the time, and BILINEAR/BICUBIC interpolation during resize reintroduced gray pixels even after thresholding.

**Changes to `generate_training_data.py`:**
- Thresholding applied 100% of the time (was 70%)
- Threshold value: `FRONTEND_THRESHOLD(80) + random(-10, +40)` matching the frontend
- Added re-threshold after resize: `img.point(lambda x: 0 if x < 128 else 255)` to guarantee binary output
- Background canvas hardcoded to 255 (white)

**Result:** 97.4% best accuracy at 10,000 iterations. All 9,285 training images verified as strictly binary (only 0 and 255 pixel values).

**Still failed on real screenshots.** Despite matching pixel value distribution, the model produced mostly garbage output on real tooltip images. This pointed to additional problems beyond pixel-level domain gap — specifically CRAFT text detection being unsuitable for structured tooltip layouts.

---

## Diagnosis: CRAFT Detection is the Wrong Tool

After 6 training attempts, a key insight emerged: the problem is not just recognition accuracy — **CRAFT text detection is fundamentally wrong for this use case**.

CRAFT was designed for natural scene text (signs, labels, handwriting in photos). Mabinogi tooltips are structured UI elements with:
- Consistent layout and font
- Known line spacing and borders
- Section headers with box decorations

CRAFT fragments tooltip lines into irregular polygonal regions, merges adjacent lines, and misses section boundaries. Meanwhile, our custom `TooltipLineSplitter` using horizontal projection profiling achieves **perfect** line detection:
- `lightarmor_processed`: 75/75 lines
- `lobe_processed`: 22/22 lines
- `captain_suit_processed`: 23/23 lines

---

## New Strategy: Line Splitter + Direct Recognition (v2 Pipeline)

**Architecture change:** Replace CRAFT detection with the proven `TooltipLineSplitter`, then feed individual line crops directly to the recognition model via EasyOCR's low-level `recognize()` API.

```
Old: Frontend → Full image → EasyOCR readtext() [CRAFT + Recognition] → Text correction
New: Frontend → Full image → TooltipLineSplitter → Line crops → EasyOCR recognize() [Recognition only] → Text correction
```

**Benefits:**
1. Detection is solved — line splitter is proven accurate
2. Training data naturally matches line crops (single-line images)
3. Bypasses CRAFT entirely — eliminates fragmentation and merging errors
4. Recognition model sees clean, rectangular, single-line inputs
5. Each line maps to a known tooltip field for structured data extraction

**Training data adjustments needed:**
- Match real line crop dimensions (full tooltip width ~250px, variable height)
- Generate from actual tooltip text patterns, not just dictionary words
- Include structured patterns: `R:0 G:0 B:12`, `내구력 20/20`, `- 피어싱 레벨 3`

**Implementation:** Use EasyOCR's `recognize()` method (bypasses CRAFT) or call the recognition model directly on pre-cropped line images.
