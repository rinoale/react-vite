# OCR Training History

## Progress Summary

Each attempt has identified and fixed a specific bottleneck, steadily raising real-world accuracy:

| Attempt | Synthetic Acc | Real Char Acc | Real Confidence | Bottleneck Fixed |
|---------|--------------|---------------|-----------------|------------------|
| 1-4 | 99% | ~0% | ~0.01 | Charset, --sensitive bug, --PAD mismatch |
| 5 | 100% | ~0% | ~0.05 | imgW=200, augmentation |
| 6 | 97.4% | 19.5% | 0.039 | Binary domain gap, v2 pipeline (bypass CRAFT) |
| 7 | 97.7% | 35.8% | 0.097 | +67 chars, templates, natural height |
| 8 (5k iter) | 56.2% | 28.3% | 0.004 | Squash factor, proportional canvas width (underfit) |
| 8b | Pending | Pending | Pending | Continue training from 8 checkpoint (+10k iter) |

Real-world char accuracy: **0% → 19.5% → 35.8% → 28.3%** (Attempt 8 regressed due to underfitting — more varied data needs more iterations). Attempt 8b continues training from checkpoint.

**Training strategy:** Two-stage approach — Stage 1: synthetic-only training until **60% real char accuracy**. Stage 2: fine-tune with real GT line crops mixed into training data.

---

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

**Implementation:** Use EasyOCR's `recognize()` method with `horizontal_list=[[0, w, 0, h]]` and `free_list=[]` to bypass CRAFT and recognize pre-cropped line images directly.

**v2 pipeline test script:** `scripts/test_v2_pipeline.py` — splits sample images, feeds line crops to `recognize()`, compares against GT `.txt` files.

---

## Domain Gap Analysis (v2 Pipeline Baseline)

Ran `test_v2_pipeline.py` on all 5 GT pairs (235 total lines). **Result: 0/235 exact matches (0%), 19.5% char accuracy, avg confidence 0.039.** The model outputs random dictionary fragments.

Three root causes identified:

### Problem 1: 62 Missing Characters (Critical)

The character set (`unique_chars.txt`, 442 chars) is missing **62 characters** that appear in ground truth text. The model physically cannot output these characters.

| Category | Missing | Examples |
|----------|---------|---------|
| Korean syllables (41) | `축`, `캡`, `싱`, `픽`, `받`, `뎌`, `균`, `멸`, `글`, `낸`, `녔`, `딘`, `떠`, `떤`, `롬`, `루`, `릴`, `멘`, `선`, `습`, `얌`, `염`, `족`, `존`, `쪽`, `착`, `참`, `출`, `칠`, `케`, `탄`, `탓`, `텐`, `틴`, `팩`, `같`, `것`, `관`, `권` | Can't recognize "축복받은", "캡틴", "피어싱", "에픽" |
| Lowercase Latin (15) | `a, c, e, g, h, i, l, m, n, o, p, r, t, x, y` | Can't recognize "Copyright", "MABINOGI" lowercase |
| Uppercase Latin (4) | `I, M, N, O` | Can't recognize "MABINOGI" |
| Hangul jamo (1) | `ㄴ` | Can't recognize sub-bullet marker "ㄴ" |
| Punctuation (1) | `,` (comma) | Can't recognize comma-separated values |

### Problem 2: Dimension Mismatch (3x scale error)

| Metric | Real line crops | Synthetic training |
|--------|-----------------|-------------------|
| Height | 6-14px (median **10px**) | Fixed **32px** |
| Width | 22-269px (median **261px**) | 24-488px (median 213px) |
| Aspect ratio (w/h) | 2.8-33.4 (median **18.8**) | 0.8-15.2 (median **6.3**) |

Real crops are ~10px tall with extreme aspect ratios (19:1). Synthetic images are 32px tall with moderate ratios (6:1). When the model resizes a 10px-tall real crop to 32px, the upscaling artifacts differ completely from what was seen during training.

Real height distribution: 6px (14), **7px (53)**, 8px (9), 9px (5), **10px (120)**, 11px (29), 13px (4), 14px (1). Two dominant clusters at 7px and 10px.

### Problem 3: Dictionary-Only Labels (12% coverage)

Training labels come exclusively from dictionary entries. Only **25/210** (12%) unique GT lines have an exact dictionary match. The model has never seen:
- Stat lines: `방어력 14`, `내구력 32/32`, `공격 107~189`
- Color parts: `- 파트 A R:0 G:0 B:0`, `파트 B    R:187 G:153 B:85`
- Hashtag lines: `#인챈트 실패 시 아이템 보호 #남성 전용 #대장장이`
- Piercing: `(피어싱이 부여된 장비를 양 쪽에 착용 시, 높은 쪽 적용)`
- Multi-value: `- 방어 20, 보호 15 차감`
- Price: `상점판매가 : 4597 골드`
- Item names: `축복받은 새끼너구리 파이릿 캡틴 수트`
- Flavor text / descriptions

---

## Attempt 7: Fix All Three Root Causes

**Changes:**
1. **Character set expanded**: 442 → 509 chars (+62 from GT, +5 from templates: 민번센첩황)
2. **Template-based generator**: Rewrote `generate_training_data.py` with ~2,300 template lines covering stat lines, color parts, enchant headers/effects, sub-bullets, reforging, crafting, set items, piercing, hashtags, prices, grades, ergo, flavor text. Plus GT lines verbatim and dictionary entries.
3. **Natural image dimensions**: Render at font sizes 9-11 on ~260px canvas → natural height 10-14px (no pre-resize to 32px)
4. **Binary enforcement**: Re-threshold after all augmentations. Blank image detection added.
5. Generated **8,665 images** (509-char set, 3 variations per label)

**Training:** 10,000 iterations. Best accuracy: **97.725%** on synthetic validation.

**v2 Pipeline Result:**

| Image | Lines | Exact | Char Acc | Confidence |
|-------|-------|-------|----------|------------|
| captain_suit | 23 | 0 | 29.9% | 0.067 |
| dropbell | 36 | 0 | 35.9% | 0.071 |
| lightarmor | 75 | 0 | 38.3% | 0.118 |
| lobe | 22 | 0 | 32.2% | 0.077 |
| titan_blade | 79 | 1 | 35.0% | 0.099 |
| **TOTAL** | **235** | **1** | **35.8%** | **0.097** |

**Improvement over baseline:** Char accuracy 19.5% → 35.8% (1.8x), confidence 0.039 → 0.097 (2.5x). The model now produces recognizable Korean fragments, but accuracy remains poor.

### Attempt 7 Analysis: Squash Factor Mismatch

**Root cause:** EasyOCR's `AlignCollate` preprocessing resizes images to `imgH=32` maintaining aspect ratio, then if the resulting width exceeds `imgW=200`, it **squashes** horizontally to fit 200px. This squash factor depends on the original image height:

| Source | Height | Resize to h=32 | Resulting width (260px canvas) | Squash to 200px |
|--------|--------|-----------------|-------------------------------|-----------------|
| Real 7px crop | 7px | 4.6x upscale | 260 × (32/7) = **1,189px** | **5.9x squash** |
| Real 10px crop | 10px | 3.2x upscale | 260 × (32/10) = **832px** | **4.2x squash** |
| Synthetic (Att 7) | 14px | 2.3x upscale | 260 × (32/14) = **594px** | **3.0x squash** |

The model trained on 3.0x squash but encounters 4.2x–5.9x squash at inference. Lines at 10-15px height (where squash is closest to training) achieve 80-93% char accuracy, confirming the mismatch.

**Second issue: Short text hallucination.** Short text like "세공" (4 chars) rendered on a 260px canvas = 80% whitespace. After squashing, the model sees a long input and hallucinates extra characters to fill it. Real short-text crops from the splitter are narrow (22-100px), not full tooltip width.

---

## Attempt 8: Fix Squash Factor + Canvas Width

**Changes to `generate_training_data.py`:**
1. **Font size 8 added** (~30% of images): `FONT_SIZES = [8, 8, 9, 9, 10, 10, 11]`. Size 8 produces 8-9px tall text, matching the real 7px height cluster. This teaches the model the extreme 5.9x horizontal squash it encounters on real 7px crops.
2. **Canvas width proportional to text length**: Short text gets tight-cropped (60% of the time) with width = text_width + padding + 0-10px margin. Long text still uses full ~260px canvas. This matches the splitter's ink-bound cropping for short lines (real widths range 22-269px) and prevents short-text hallucination.

**Generated:** 8,702 images (509-char set).

**Image dimension distribution (sample 500):**
- Height: 9-19px (covers both 7px and 10px real clusters after padding)
- Width: 22-280px (matches real 22-269px range)
  - <50px: 8%, 50-100px: 33%, 100-200px: 21%, 200-270px: 38%

**Training (Attempt 8, 5k iterations):** Best synthetic accuracy: **56.2%** at 5,000 iterations (~31 min with `--batch_size 64`). Model underfit — the more varied training data (variable widths, multiple font sizes) requires more iterations to converge.

**v2 Pipeline Result (Attempt 8):**

| Image | Lines | Exact | Char Acc | Confidence |
|-------|-------|-------|----------|------------|
| captain_suit | 23 | 0 | 25.6% | 0.010 |
| dropbell | 36 | 0 | 24.4% | 0.006 |
| lightarmor | 75 | 0 | 34.3% | 0.004 |
| lobe | 22 | 0 | 28.5% | 0.001 |
| titan_blade | 79 | 0 | 25.2% | 0.004 |
| **TOTAL** | **235** | **0** | **28.3%** | **0.004** |

**Regression from Attempt 7** (35.8% → 28.3%). The model didn't converge on the harder training distribution. Synthetic accuracy was only 56.2% vs 97.7% in Attempt 7.

**Fix:** Continue training from checkpoint (`--saved_model`) for 10,000 more iterations (Attempt 8b).

---

## Attempt 8b: Continue Training from Checkpoint

Resume from Attempt 8's `best_accuracy.pth` with `--saved_model`. Same data, +10,000 iterations. This avoids restarting from scratch while allowing the model to fully converge on the more varied training distribution.

**Training:** Pending.

---

## Training Strategy: Two-Stage Approach

### Stage 1: Synthetic Only (Current)
Train on synthetic data generated by `generate_training_data.py`. Measure real-world accuracy with `test_v2_pipeline.py` after each attempt.

**Gate:** Achieve **60% real-world char accuracy** on synthetic-only training.

Below 60%, there are still fundamental synthetic-vs-real gaps worth fixing in the generator (cheaper than using limited real data). Above 60%, diminishing returns from synthetic tweaks — real data becomes more valuable.

### Stage 2: Fine-tune with Real Images
Once Stage 1 gate is met:
1. Split 5 GT images through `TooltipLineSplitter` to produce ~235 real line crops
2. Pair each crop with its GT text label
3. Augment heavily (blur, threshold variation, small shifts) to prevent overfitting on 235 samples
4. Mix ~50/50 with synthetic data in a combined LMDB dataset
5. Fine-tune from the Stage 1 model using `--saved_model`
6. Use lower learning rate to avoid catastrophic forgetting of synthetic-learned features

**Why two stages?**
- Stage 1 teaches character shapes, layout patterns, and squash factors from abundant synthetic data
- Stage 2 closes the "last mile" domain gap: real pixel artifacts, actual font rendering, border residue, upscaling noise
- 235 real lines is too few for training from scratch but sufficient for fine-tuning
- Continued training (`--saved_model`) is supported by `deep-text-recognition-benchmark/train.py`
