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

## Next: Attempt 4

Retrain with `--PAD` flag to match EasyOCR's `keep_ratio_with_pad=True` inference preprocessing.
