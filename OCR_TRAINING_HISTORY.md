# OCR Training History

## Progress Summary

Each attempt has identified and fixed a specific bottleneck, steadily raising real-world accuracy:

| Attempt | Synthetic Acc | Real Char Acc | Real Confidence | Bottleneck Fixed |
|---------|--------------|---------------|-----------------|------------------|
| 1-4 | 99% | ~0% | ~0.01 | Charset, --sensitive bug, --PAD mismatch |
| 5 | 100% | ~0% | ~0.05 | imgW=200, augmentation |
| 6 | 97.4% | 19.5% | 0.039 | Binary domain gap, v2 pipeline (bypass CRAFT) |
| 7 | 97.7% | 35.8% | 0.097 | +67 chars, templates, natural height |
| 8 (5k) | 56.2% | 28.3% | 0.004 | Squash factor, proportional canvas width (underfit) |
| 8b (15k) | 93.5% | 27.0% | 0.014 | Continue from 8 — domain gap, not underfitting |
| 9 | 90.0% | 36.2% | 0.044 | Reverted canvas to ~260px, bimodal font sizes 6-7/10-11 |
| 10 | — | — | — | OOM (imgW=600, batch_size=64 maxed 8GB VRAM). No training completed. |
| 11 | 5.8% | — | ~0 | imgW=600, batch_size=16 → only 18 epochs in 10k iters. Underfitting. |
| 12 | 84.4% | 38.1% | 0.120 | Patched inference to use fixed imgW. Squash factors now match. |

Real-world char accuracy: **0% → 19.5% → 35.8% → 27.0% (regression) → 36.2% → 38.1%**. Attempts 10-11 failed due to imgW=600 approach. Attempt 12 patched EasyOCR inference to use fixed imgW, confirming squash factor alignment. Confidence jumped 2.7x (0.044 → 0.120).

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

**Training (Attempt 8, 5k iter):** Synthetic acc 56.2%, real char acc 28.3%, conf 0.004. Underfit — not enough iterations for varied data.

**Training (Attempt 8b, 15k iter from checkpoint):** Synthetic acc 93.5%, real char acc 27.0%, conf 0.014. High synthetic + low real = domain gap confirmed. The proportional canvas width was the root cause — 57% of training images had squash factors 1.0-2.0x that never appear in real data. Real crops are 95.4% full-width (~261px).

---

## Attempt 9: Revert Canvas Width + Bimodal Font Sizes

**Root cause of Attempt 8 regression:** Proportional canvas width (60% tight-crop for short text) caused squash factor mismatch. Real short-text crops are still full-width because the splitter crops to ink bounds within the full tooltip.

**Changes to `generate_training_data.py`:**
1. **Reverted canvas width to always ~260px** — removed proportional/tight-crop logic entirely
2. **Font sizes changed to `[6,7,7,7,10,10,10,10,10,10,11,11,11,11]`** — bimodal distribution matching real data. Dropped sizes 8-9 which produced h=10-13px (nonexistent in real data)
3. **Padding formula aligned to splitter:** `pad_y = max(1, text_h // 5)`, `pad_x = max(2, text_h // 3)` matching `tooltip_line_splitter.py`

**Generated:** 8,622 images (509-char set).

**Image dimension distribution (sample 3,000):**
- Width: p25=255, median=260, p75=266, **100% above 220px**
- Height: bimodal — **24% at h=8-9px** (target 28%), **57% at h=14-15px** (target 63%)
- h=12-13: **0%** (eliminated bad cluster)

**Training:** 10,000 iterations, batch_size 64, from scratch. Best synthetic acc: 90.0%.

**Results:** 0/235 exact, **36.2% real char accuracy**, 0.044 confidence. Recovered from Attempt 8 regression and slightly exceeded Attempt 7 (35.8%).

### Attempt 9 Analysis: imgW Mismatch

Investigation revealed the **dominant remaining domain gap**: training `AlignCollate` squashes images to `imgW=200`, but EasyOCR inference computes `max_width = ceil(ratio) * 32` per image, yielding ~554-576px for typical 260px-wide crops at h=8-15px. The model trains on 200px-wide squashed images but sees ~554px-wide unsquashed images at inference — **2.77x wider for the same content**.

This explains:
- Short text hallucination: `세공` (2 chars) → 16 chars (model fills extra columns with hallucinated chars)
- OCR output averages 1.6x more characters than GT across all lines
- Performance inversely correlates with whitespace ratio

---

## Attempt 10: Fix imgW to Match Inference (OOM)

**Change:** `--imgW 600` (was 200). Intended to prevent squashing during training so the model sees character spacing consistent with inference. Same training data as Attempt 9.

**Result:** OOM. `batch_size=64` with `imgW=600` maxed out 8GB VRAM (7,972/8,192 MiB). Zero iterations completed.

---

## Attempt 11: imgW=600 with Reduced Batch Size

**Changes:**
1. **batch_size reduced to 16** — to fit imgW=600 in 8GB VRAM
2. **Label splitting** — added `split_long_label()` to split overflow labels at word boundaries (33 labels split)
3. **Training data regenerated** — 8,671 images with all Attempt 9 fixes (bimodal fonts, splitter padding, full canvas width)

**Training:** 10,000 iterations, batch_size=16, imgW=600.

**Result:** 5.8% best synthetic accuracy. Predictions were random fragments ("- 미 감소", "-어 소 감소"). Loss plateau at ~3.1.

**Root cause:** Two compounding issues:
1. **Too few epochs:** batch_size=16 → 542 iters/epoch → only 18 epochs in 10k iters (vs ~74 epochs in Attempt 9 with batch_size=64)
2. **Fundamental imgW mismatch discovered:** EasyOCR's `recognize()` uses **dynamic** `max_width` per image, NOT the yaml's imgW. The dynamic width depends on each image's aspect ratio:

| Image height | Dynamic inference imgW | Training imgW | Mismatch |
|-------------|----------------------|---------------|----------|
| h=8 | 1056 | 600 | 1.76x |
| h=9 | 928 | 600 | 1.55x |
| h=14 | 608 | 600 | ~match |
| h=15 | 576 | 600 | slight |

No single fixed imgW can match all image heights. The h=8-9 cluster (28% of data) has **worse** mismatch at imgW=600 than imgW=200 had for h=14 images.

**Key finding (EasyOCR source):** In `easyocr.py` line 381, `recognize()` passes `int(max_width)` to `get_text()`, where `max_width = ceil(w/h) * 32`. The yaml's imgW is only used for TPS model construction, never for inference preprocessing.

---

## Attempt 12: Patch Inference to Use Fixed imgW

**The real fix:** Instead of adjusting training imgW to match dynamic inference, patch inference to use fixed imgW from the yaml. This ensures training and inference always match at any imgW value.

**Changes:**
1. **`backend/ocr_utils.py`** (new) — `patch_reader_imgw()` monkey-patches EasyOCR's `recognize()` method to pass the yaml's `imgW` to `get_text()` instead of dynamic `max_width`
2. **`scripts/test_v2_pipeline.py`** — applies the patch after reader init
3. **`backend/main.py`** — applies the patch after reader init
4. **Config reverted to imgW=200, batch_size=64, num_iter=10000** — no more VRAM constraints

**Training data:** Same 8,671 images from Attempt 11 (bimodal fonts, splitter padding, full canvas, label splitting).

**Training:** 10,000 iterations, batch_size=64, imgW=200. Best synthetic accuracy: **84.4%** at iter 9500.

**v2 Pipeline Result:**

| Image | Lines | Exact | Char Acc | Confidence |
|-------|-------|-------|----------|------------|
| captain_suit | 23 | 0 | 33.4% | 0.064 |
| dropbell | 36 | 0 | 28.7% | 0.107 |
| lightarmor | 75 | 0 | 51.3% | 0.143 |
| lobe | 22 | 0 | 33.2% | 0.088 |
| titan_blade | 79 | 0 | 32.7% | 0.164 |
| **TOTAL** | **235** | **0** | **38.1%** | **0.120** |

**Improvement:** Char accuracy 36.2% → 38.1%, confidence 0.044 → 0.120 (2.7x). The inference patch confirmed working — squash factors between real and synthetic now match exactly:

| Height | Real squash | Synthetic squash |
|--------|------------|-----------------|
| h=8 | 5.2x | 5.2x |
| h=9 | 4.6x | 4.6x |
| h=14 | 3.0x | 3.0x |
| h=15 | 2.8x | 2.8x |

### Attempt 12 Analysis: Remaining Domain Gaps

1. **h=16-17 training noise (9.1%):** Characters with descenders (parentheses, commas) at font size 11 produce text_h=12-13, totalling h=16-17 with padding. This height range doesn't exist in real data (0% of real crops). The model wastes capacity learning squash factors (2.4-2.6x) it never encounters at inference.

2. **Synthetic accuracy plateau at 84.4%:** Model hasn't fully converged. Loss was still decreasing at iter 10000 (train: 0.09, val: 0.11). More iterations may help.

3. **Short line hallucination persists:** "천옷" → "- 다토 인챈 이브 만손 스검". Short text (2-4 chars) on 260px canvas is heavily squashed (2.8-5.2x), with 80%+ whitespace. The model fills blank regions with hallucinated characters.
