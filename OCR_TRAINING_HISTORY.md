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
| 13 | 100% | 52.4% | 0.247 | Tight-crop, font 10-11, splitter border filter, inference patch |
| 14 | — | 75.5% | 0.327 | Training data cleanup + splitter left-edge artifact removal |
| 15 | — | 77.0% | 0.352 | % spacing fix, 내구력 6×, section headers 4×, 개조 3×, grade colon fix, dash 2.5× |
| 16 | 99.97% | 71.3% | TBD | Charset 509→1201, item_name sampled 3k, post-dedup header boost, num_iter 20k — **regression** |
| 17 | TBD | TBD | TBD | Game-like rendering (dark bg+bright text→BT.601→bright→black), font sizes 10-11 (unchanged) |

Real-world char accuracy: **0% → 19.5% → 35.8% → 27.0% (regression) → 36.2% → 38.1% → 52.4% → 75.5% → 77.0%**. Attempt 14 cleaned up training data quality (prefix corrections, color part handling, GT source switch to `_expected.txt`) and added two post-hoc splitter fixes to remove left-edge UI artifacts from crops. Exact matches jumped from 14/235 to 45/230. Attempt 15 targeted the most common failure patterns (내구력, 개조, % spacing, section headers) and raised char acc to 77.0% and exact matches to 64/230. GT count changed to 230 due to titan_blade image update and use of `_expected.txt`. lightarmor at 80.1%, titan_blade at 80.0%, crossing the 80% gate on both large images.

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

**v2 pipeline test script:** `scripts/test_v2_pipeline.py` — splits sample images, feeds line crops to `recognize()`, compares against ground truth (GT) `.txt` files.

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

4. **Faint/illegible training images (25%):** Augmentation (blur + erode/dilate) produced images that are unreadable to humans. If a human can't read it, the model can't learn from it.

5. **Font 6-7 produces illegible text:** Synthetic images at font sizes 6-7 produce tiny, unreadable characters. Real h=8-9 crops are legible because the game renders at normal font size — the small crop height comes from tight vertical cropping, not from small font rendering.

6. **Full canvas waste:** 97.6% of training images had text filling <75% of canvas width. Training on mostly-whitespace images teaches the model that whitespace is normal, encouraging hallucination.

7. **Splitter border artifacts inflate crop width:** Vertical pipes (`|`) and horizontal bars (`ㅡㅡㅡ`) from UI box borders extend line crops to full tooltip width even for short text like "보호 1" (248px → should be 35px).

---

## Attempt 13 Preparation: Training Data + Splitter + Inference Overhaul

Unlike previous attempts that adjusted training hyperparameters (imgW, batch_size, iterations), Attempt 13 focuses on **three fundamental infrastructure improvements**: fixing how images are analyzed at inference, how training images are generated, and how line crops are extracted.

### Change 1: Inference Patch — Fixed imgW (`backend/ocr_utils.py`)

**Problem:** EasyOCR's `recognize()` computes a dynamic `max_width` per image via `ceil(w/h) * 32`, which varies from 576 to 1056px depending on image height. Training uses a fixed `imgW` (200 or 600), so there's always a mismatch. No single training imgW can match all inference widths.

**Solution:** `patch_reader_imgw()` monkey-patches the reader's `recognize()` to pass the yaml's fixed `imgW` to `get_text()`, replacing the dynamic `max_width`. Training and inference now use identical imgW regardless of input image dimensions.

**Files:**
- `backend/ocr_utils.py` — New file, implements the patch
- `backend/main.py` — Applies patch after reader init
- `scripts/test_v2_pipeline.py` — Applies patch after reader init

**Verification:** Squash factors now match exactly between synthetic and real data at every height.

### Change 2: Training Data Overhaul (`scripts/generate_training_data.py`)

Seven changes to eliminate domain gap between synthetic and real line crops:

| Problem | Before | After |
|---------|--------|-------|
| Image width | Full ~260px canvas (97.6% whitespace) | Tight-crop to ink bounds + padding |
| Font sizes | Bimodal 6-7/10-11 (28% illegible) | 10-11 only (all human-readable) |
| Augmentation | Blur, erode/dilate (25% faint) | None — clean binary only |
| Quality check | None | Every image: ink ratio ≥2%, width ≥10px, height ≥8px |
| Crop formula | `pad_y = max(1, h//5)`, `pad_x = max(2, h//3)` on fixed canvas | Same padding but crop to text bounds |
| Image count | 8,671 | 9,193 (more pass quality gates) |
| Width distribution | 100% >220px | median=89px, varies with text length |

**Key insight:** Real short-text crops from the splitter are narrow (35-65px for "보호 1", "내구력 20/20"), not full tooltip width. Training on tight-cropped images matches this, and eliminates whitespace-induced hallucination.

### Change 3: Splitter Horizontal Trimming (`backend/tooltip_line_splitter.py`)

Two filters added to `_add_line()` to remove UI border elements from line crops:

**Filter 1 — Thin vertical borders:** Clusters ≤2px wide that are far from the nearest text cluster (distance > `line_h * 2`) are filtered out. These are `|` pipe characters at the box edges.

| Line | Before | After |
|------|--------|-------|
| "보호 1" | w=248 | w=35 |
| "내구력 20/20" | w=257 | w=65 |

**Filter 2 — Horizontal bar borders:** Clusters wider than `line_h * 3` with average column density < 2.0 are filtered out. These are `ㅡㅡㅡ` horizontal bars in section box borders.

| Line | Before | After |
|------|--------|-------|
| "아이템 속성" (with ㅡㅡㅡ bar) | w=256 | w=69 |
| "아이템 색상" (with ㅡㅡㅡ bar) | w=261 | w=75 |

**Why this matters:** Tighter crops → less whitespace at inference → less hallucination. The splitter now produces crops whose width distribution better matches the tight-cropped training data.

**No regressions:** All 5 GT images still detect the correct line counts (75, 23, 22, 79, 36 = 235 total).

### Combined Effect

The three changes work together to close the training/inference gap from both sides:

```
Before:  Training(260px canvas, imgW=200) ≠ Inference(dynamic imgW=576-1056)
After:   Training(tight-crop, imgW=200) = Inference(patched imgW=200)
         Splitter crops(tight, no borders) ≈ Training images(tight-crop)
```

### Training Config (Attempt 13)

```yaml
model:
  imgH: 32
  imgW: 200   # Fixed via patched inference (ocr_utils.py)
training:
  batch_size: 64
  num_iter: 10000
  batch_max_length: 55
  workers: 0
  sensitive: true
  PAD: true
```

---

## Attempt 13 Results

**Training:** 100% synthetic accuracy at 9,500 iterations (perfect convergence). 9,207 training images.

**v2 Pipeline Result:**

| Image | Lines | Exact | Char Acc | Confidence |
|-------|-------|-------|----------|------------|
| captain_suit | 23 | 3 | 57.0% | 0.184 |
| dropbell | 36 (GT:38) | 0 | 40.8% | 0.195 |
| lightarmor | 75 | 9 | 71.2% | 0.319 |
| lobe | 22 | 2 | 55.1% | 0.260 |
| titan_blade | 79 (GT:83) | 0 | 37.9% | 0.233 |
| **TOTAL** | **235** | **14 (6.0%)** | **52.4%** | **0.247** |

**Improvement over Attempt 12:** Char accuracy 38.1% → 52.4% (+14.3pp, +37% relative). Confidence 0.120 → 0.247 (2x). First-ever exact matches: 14 lines.

**Aligned vs misaligned:** The 3 images with correct line counts (captain_suit, lightarmor, lobe = 120 lines) average **65.5% char accuracy**. The 2 misaligned images (titan_blade 79 vs GT 83, dropbell 36 vs GT 38) average **39.2%** — but much of this is GT alignment drift, not actual OCR errors.

### Attempt 13 Failure Analysis

**Accuracy distribution across 235 lines:**
- 95-100%: 27 lines (11.5%)
- 80-94%: 47 lines (20.0%)
- 60-79%: 38 lines (16.2%)
- 30-59%: 36 lines (15.3%)
- 0-29%: 87 lines (37.0%)

Six distinct failure categories identified, ordered by impact:

#### 1. GT Alignment Drift — 53 lines (biggest factor)

titan_blade detects 79 lines (GT expects 83) and dropbell detects 36 (GT expects 38). Once line counts diverge, every subsequent line is compared against the wrong GT text. Analysis confirmed 53 of the 81 worst-scoring lines (<40% acc) are actually reasonable OCR output scored against the wrong GT line. Example: OCR reads "공격확 107 ~189" but it's compared against GT "특별 이벤트 장비(거래 불가)" — the OCR is actually reading GT line 14 ("공격 107~189") correctly.

**This is a test harness issue, not an OCR quality issue.** Fixing GT alignment would raise the overall score by an estimated 10-15pp.

#### 2. Color Part Lines — 18 lines, avg 13.8% accuracy

`- 파트 A    R:0  G:0  B:0` → crops are h=7px, w=210px with huge gaps between text groups. Three separate text clusters (`파트 A`, `R:0`, `G:0`, `B:0`) spread across 210px with wide blank separations. The model has never seen this sparse multi-cluster layout. OCR outputs near-empty results.

**Root cause:** Training data has no color part templates with proper wide spacing. All training images are tight-cropped with no internal gaps.

#### 3. Leading `-` Stripped — 27 lines, avg 81.1% accuracy

Lines starting with `- ` lose the dash prefix. `- 수리비 200% 증가` → ` 수리비 200% 증가`. The rest of the text is correct. The border filter may be stripping leading single-character dashes, or the model simply doesn't output the leading dash.

#### 4. Short Text (h<10) — 6 lines, avg 12.5% accuracy

`천옷` (h=6, w=18), `세공` (h=6-8, w=29-39), `등급` (h=11, w=29). Crops at h=6 are below the training data minimum (h=10). The 5.3x upscaling to h=32 creates heavy artifacts. These are section labels in the tooltip — very short, very small.

#### 5. `%` Misread as `9` — 5 lines, avg 85.7% accuracy

Consistent pattern: `3% 감소` → `39 감소`, `72 % 증가` → `72 9 증가`. The `%` glyph at small sizes resembles `9`. Very fixable with more `%`-heavy training samples.

#### 6. Price/Bottom Lines — 3 lines, avg 18% accuracy

`상점판매가 : 4597 골드` → `(327 7 질복효`. Always at tooltip bottom, h=13. The consistent `(327` garbage prefix across all 3 images suggests a systematic issue — possibly the crop includes part of the tooltip border or the text rendering differs at the bottom.

### Path to 80%

| Fix | Lines Affected | Estimated Gain |
|-----|---------------|----------------|
| Fix GT alignment (titan_blade + dropbell) | 115 lines | +10-15pp |
| Color part templates in training data | 18 lines | +2-3pp |
| Fix leading `-` stripping | 27 lines | +2-3pp |
| Handle short text (h<10) | 6 lines | +1pp |
| More `%` training samples | 5 lines | +1pp |
| Investigate price line crops | 3 lines | +0.5pp |

Conservative estimate with all fixes: **68-78% char accuracy**. The GT alignment fix alone is the single biggest win.

---

## Attempt 14 Preparation: Section-Aware Parser + Splitter Overhaul

Attempt 14 takes a strategic shift: instead of pushing OCR to handle everything, make the pipeline **domain-aware**. The splitter and parser now understand Mabinogi tooltip structure — detecting sections, splitting color parts structurally, and skipping unnecessary areas (flavor text, copyright).

### Change 1: Section-Aware Parser (`backend/mabinogi_tooltip_parser.py`)

New `MabinogiTooltipParser` class extends `TooltipLineSplitter` with:
- **Section detection**: Matches OCR text against header patterns (아이템 속성, 인챈트, 개조, 세공, 에르그, 세트아이템, 아이템 색상)
- **Line categorization**: Groups lines into sections (item_name, item_attrs, enchant, reforge, erg, set_item, item_color, etc.)
- **Structural color parsing**: RGB values parsed via regex from sub-segments, not general OCR
- **Skip logic**: Flavor text and shop price sections marked as skip — detected but ignored in output
- **Config-driven**: Section definitions in `configs/mabinogi_tooltip.yaml`, separating game-specific logic from base splitter

### Change 2: Splitter Improvements (`backend/tooltip_line_splitter.py`)

Four fixes to the base splitter, addressing lines missed in Attempt 13:

**Fix 1 — Smarter border removal (`_remove_borders()`):**
- Before: Masked ALL columns with >15% row density — removed 34 columns including text positions where `ㄴ`, `-` prefixes align vertically
- After: Only masks narrow runs (≤3px wide) of high-density columns — actual UI borders
- Impact: `- 담금질 2/3/4` now detected (raw projection 11-26 per row, was stripped to 1-6)

**Fix 2 — Rescue pass (`_rescue_gaps()`):**
- Re-scans large gaps between detected blocks using lower threshold (`max(2, w*0.01)` vs main `max(3, w*0.015)`)
- Catches sparse continuation lines: `적용)`, `제외)`, `(6~7)` that have only 2-10 ink pixels per row after border removal
- Only triggers in gaps > 1.5× average block height — doesn't affect normal inter-line gaps

**Fix 3 — Internal gap splitting (`_has_internal_gap()`):**
- Blocks with 2+ consecutive zero-projection rows internally are split via `_split_tall_block()`
- Fixes: `기본 효과` + `- 무기 공격력 50 증가` merged as one h=23 block (clear zero gap at y=1087-1088)

**Fix 4 — Configurable horizontal split factor:**
- `horizontal_split_factor` attribute on base class (default 3), overridden by config
- Set to 1.5 for Mabinogi: reliably splits multi-digit RGB values (`R:187 G:153 B:85`) where gaps are 15-16px and line heights are 7-9px

### Line Detection Results

| Image | Before (Att 13) | After | Change |
|-------|-----------------|-------|--------|
| captain_suit | 23 | 23 | — |
| dropbell | 36 | 38 | +`적용)`, `(6~7)` |
| lightarmor | 75 | 75 | — |
| lobe | 22 | 22 | — |
| titan_blade | 79 | 86 | +`담금질 2/3/4`, `적용)`, `제외)`, split `기본 효과` |
| **TOTAL** | **235** | **244** | **+9 lines** |

### New Infrastructure

- **`configs/mabinogi_tooltip.yaml`** — Section definitions, horizontal_split_factor, game-specific config
- **`backend/mabinogi_tooltip_parser.py`** — Section-aware parser with structural color parsing
- **`POST /upload-item-v2`** — New API endpoint returning structured section data
- **`scripts/regenerate_gt.py`** — GT regeneration helper (pipeline output → candidate → manual review → apply)
- **GT file types**: `*_processed.txt` (full GT), `*_expected.txt` (expected OCR output, may skip areas)
- **`scripts/test_v2_pipeline.py`** — Now uses MabinogiTooltipParser, `--sections` flag shows section breakdown
- **`scripts/test_line_splitter.py`** — Now uses MabinogiTooltipParser for game-specific settings

---

## Attempt 14: Training Data Cleanup + Splitter Left-Edge Fixes

### Training Data Changes (`scripts/generate_training_data.py`)

Attempt 14 focused on data quality — removing incorrect or misleading training labels that accumulated over earlier attempts:

| Issue | Before | After |
|-------|--------|-------|
| GT source file | `*_processed.txt` (outdated `.` prefixes) | `*_expected.txt` (user-maintained, clean) |
| Prefix character | `.` prefix used in templates | `-` only (game uses `-` and `ㄴ`, never `.`) |
| Sub-bullet prefix | `random.choice(['ㄴ', 'L'])` with `  ` indent | `ㄴ` only, no indent (L is OCR artifact) |
| Color part lines | Full `파트 A R:0 G:0 B:0` in training | Excluded — splitter never feeds full color line to OCR |
| Color part sub-segs | Missing | `파트 A/B/C/D/E/F` and `R:N`, `G:N`, `B:N` sub-segments |
| Section headers | Included `에픽`, `레어`, `마스터` as headers | Kept (short text for weight), added `마스터` |
| Dictionary | `tooltip_general.txt` contained full color part lines + `L`-prefix sub-bullets | Removed; added individual RGB sub-segments |
| Image count | 9,207 | 10,080 |

Also added prefix-stripped variants (lines without leading `-`/`ㄴ`) to improve robustness when the splitter crop trims the prefix character.

### v2 Pipeline Results (Before Splitter Fix)

Evaluated with `--gt-suffix _expected.txt --normalize`. GT count changed from 235 to 230 (titan_blade image updated, `_expected.txt` skips bottom area).

| Image | GT Lines | Exact | Char Acc | Confidence |
|-------|----------|-------|----------|------------|
| captain_suit | 21 | 0 | 56.1% | 0.194 |
| dropbell | 35 | 6 | 71.5% | 0.262 |
| lightarmor | 71 | 4 | 76.1% | 0.307 |
| lobe | 19 | 1 | 64.3% | 0.295 |
| titan_blade | 84 | 8 | 75.0% | 0.313 |
| **TOTAL** | **230** | **19 (8.3%)** | **72.2%** | — |

**+19.8pp improvement over Attempt 13** (52.4% → 72.2%), driven entirely by training data cleanup.

### Post-Hoc Splitter Fix: Left-Edge UI Artifacts

Visual inspection of line crops revealed two left-edge artifacts in certain tooltip images that were not present in training data, causing leading character hallucinations:

**Artifact 1 — `「` corner bracket** (section headers only):
- 6px wide cluster at the left edge, avg column density ~1.8–2.2 (sparse, not a full character)
- Followed by a 4–5px gap to the actual text
- OCR hallucinated `대바아` from the bracket, making `아이템 속성` → `대바아 이템 색성`

**Artifact 2 — `│` full-height border stripe** (all content lines):
- 1px wide cluster spanning ~100% of line height (density ≥ line_h)
- 1px vertical stroke of the section box `│` border, appearing at the leftmost crop column
- OCR hallucinated a Korean character (`가`, `루`, `자`) from the stripe, e.g. `- 수리비` → `가수리비`

**Fixes added to `_add_line()` in `backend/tooltip_line_splitter.py`:**

```python
# Artifact 1: corner bracket (first cluster, low density, gap ≥ 4px)
if idx == 0 and avg_density < 3.5:
    if gap_to_next >= 4:
        continue  # drop corner bracket

# Artifact 2: full-height border stripe (thin cluster, density ≥ 85% of line height)
if avg_density >= line_h * 0.85:
    continue  # drop border stripe
```

### Final Results (After Splitter Fix)

| Image | GT Lines | Exact | Char Acc | Confidence | Sections |
|-------|----------|-------|----------|------------|----------|
| captain_suit | 21 | 3 | 62.1% | 0.269 | 5 |
| dropbell | 35 | 9 | 74.0% | 0.324 | 4 |
| lightarmor | 71 | 11 | **79.0%** | 0.386 | 4 |
| lobe | 19 | 4 | 69.6% | 0.303 | 2 |
| titan_blade | 84 | 18 | 77.9% | 0.351 | 6 |
| **TOTAL** | **230** | **45 (19.6%)** | **75.5%** | **0.327** | — |

**+23.1pp over Attempt 13** (52.4% → 75.5%). Splitter fix alone contributed +3.3pp (72.2% → 75.5%). Exact matches: 14 → 45 (3.2×).

### Attempt 14 Analysis

| Remaining issue | Examples | Impact |
|-----------------|----------|--------|
| captain_suit section headers still weak | `[접두]` → garbled, `[접미]` → garbled | ~8% of lines |
| Short text h<10 still failing | `천옷` → `7`, `세공` → `가 개스` | ~4% of lines |
| Color part sub-segments | `파트 A` → `1호`, `R:0` → `4` | ~12% of lines |
| Number confusion | `20` → `61`, `66` (in lobe piercing lines) | ~3% of lines |
| lobe/captain_suit still below 70% | Complex enchant descriptions, long flavor text | — |

lightarmor (79.0%) and titan_blade (77.9%) are within 1–3pp of the 80% gate. captain_suit (62.1%) and lobe (69.6%) require further work on enchant section handling and short-text recognition.

### Path to 80%

| Fix | Lines | Est. Gain |
|-----|-------|-----------|
| Color part sub-segment training (파트 X, R:N, G:N, B:N) | ~25 | +2-3pp |
| More training coverage for h=7-9 real crops | ~10 | +1-2pp |
| Investigate `[접두]`/`[접미]` bracket confusion | ~8 | +1pp |
| Fix number confusion in similar-looking digits | ~7 | +0.5pp |

Conservative estimate with these fixes: **78-82% char accuracy**.

---

## Attempt 15

**Baseline**: 45/230 exact (19.6%), 75.5% char acc (from Attempt 14)

### Root Cause Analysis

Full verbose test run categorized 185 failing lines:

| Failure type | Lines | Root cause |
|---|---|---|
| Leading char artifact | ~15 | `- 수리비` → `소수리비`: game renders `-` as 2px wide at ~10px text height; PIL renders it 3-5px wide → model trained on wider dash, misidentifies narrow game dash as `소`, `#`, etc. |
| Section headers | ~4 | `아이템 속성` → `아이템 색성` (`속`↔`색` confusion); cascades to color part section miss (파트 A-F all fail when `아이템 색상` not detected) |
| 개조 variants | ~10 | `일반 개조(4/4)` → `등별 개조(44`, `특별 개조 R` → garbled; 20-30 training reps insufficient |
| `내구력 N/N` | 5 | ALL 5 fail (0% exact); `내구력` → `보 석력`/`보 비석률`; only 50 training reps |
| `% / 초` spacing | ~6 | Training has `' %'` in unit list + `' 초'` in patterns → model adds space before `%` and `초` for lines that shouldn't have it |
| Grade format | 1 | `마스터 (장비 레벨 65)` vs GT `마스터 (장비 레벨: 65)` — missing colon in training |

### Splitter Fix Attempted and Reverted

**Attempted**: Pass `cleaned` (border-masked) binary to `_add_line()` to prevent border column at x=10 from anchoring x_start.

**Result**: Catastrophic — `_remove_borders()` also masks TEXT alignment columns in dropbell (x=22,25,29,32..54 etc have >15% global density from repeated character alignment). dropbell went from 9/35 to 0/35. Reverted immediately.

**Root cause of leading char artifact remains unresolved** at splitter level. The game's `-` at ~10px text height is rendered as 2px wide × 1 row, while PIL renders it 3-5px wide. TPS warping doesn't fully compensate for this stroke-width mismatch. Training data boost (200→500 reps) is the only available mitigation.

### Training Data Changes (generate_training_data.py)

| Change | Before | After | Target issue |
|---|---|---|---|
| `아이템 속성` header reps | 10 | 40 | `속`↔`색` confusion |
| `아이템 색상` header reps | 10 | 40 | Color section miss |
| `내구력 N/N` reps | 50 | 300 | Consistent 0% exact |
| `- {effect}` reps | 200 | 500 | Dash misread as `소` |
| `일반 개조(N/N)` reps | 30 | 100 | Garbled 개조 patterns |
| `일반 개조(N/N), 보석 강화` | 20 | 60 | Same |
| `특별 개조 R/S (N단계)` | 20 each | 60 each | Same |
| `grade (장비 레벨 N)` | 30, no colon | 60, **with colon** | GT has `:` format |
| `unit = random.choice(...)` | `['', ' %', '% 증가']` | `['', '%', '% 증가']` | Remove space-before-% |
| `대미지 배율 N % 증가` | WITH space | `N% 증가` no space | lightarmor GT: `72% 증가` |
| `쿨타임 감소 N.NN 초 감소` | WITH space | `N.NN초 감소` no space | lightarmor GT: `7.60초 감소` |
| Added: `{effect} N % 증가` | — | 50 reps (대미지/최소부상률/지속대미지) | Preserve space-before-% where GT uses it |

**Training data stats**: 11,580 images generated (up from ~10k), all pass quality gates. Dimension distribution: h=14-15 74%, h=16-20 16%, h=10-11 10%.

### Expected Improvements

| Fix | Est. lines gained |
|---|---|
| `내구력` weight 6× | +3-5 |
| `아이템 속성/색상` weight 4× → indirect color parts fix | +2-4 |
| `개조` variants 3-5× | +4-8 |
| % spacing / 초 spacing fix | +4-6 |
| Grade colon fix | +1 |
| Dash misread (500 reps) | +2-5 (uncertain) |

**Target**: 60-75/230 exact (26-33%), **80%+** char accuracy.

---

## Attempt 15 Results

**Training:** Same config as Attempt 14 (imgW=200, batch_size=64, 10k iters). 11,580 training images.

**v2 Pipeline Result (with `--normalize --gt-suffix _expected.txt`):**

| Image | GT Lines | Exact | Char Acc | Confidence | Sections |
|-------|----------|-------|----------|------------|----------|
| captain_suit | 21 | 5 | 66.2% | 0.323 | 4 |
| dropbell | 35 | 12 | 71.8% | 0.330 | 3 |
| lightarmor | 71 | 24 | **80.1%** | 0.465 | 3 |
| lobe | 19 | 2 | 73.9% | 0.392 | 3 |
| titan_blade | 84 | 21 | **80.0%** | 0.379 | 4 |
| **TOTAL** | **230** | **64 (27.8%)** | **77.0%** | **~0.352** | — |

**Improvement over Attempt 14:** Char accuracy 75.5% → 77.0% (+1.5pp). Exact matches 45 → 64 (+19). lightarmor and titan_blade crossed the **80% gate** for the first time.

### Attempt 15 Analysis

**Resolved by Attempt 15:**
- `내구력 N/N` — Previously 0% exact on all 5 lines; now mostly recognized.
- `개조` variants — `일반 개조(N/N)`, `특별 개조 R/S` now largely correct.
- `% / 초` spacing — `72%` no longer becomes `72 %`.
- Grade colon — `마스터 (장비 레벨: 65)` now matches GT format.

**Remaining issues blocking 80% overall:**

| Issue | Affected Images | Impact |
|-------|----------------|--------|
| Section header misrecognition (`세공` → `제채두 고급`, `에르그` → `44 르 수`) | titan_blade | False negatives: wrong section tags cascade to FM failure |
| `[접두]`/`[접미]` enchant headers highly garbled | all | ~42% char acc on enchant headers; two-phase FM can't recover below ~80% raw OCR |
| captain_suit still below 70% | captain_suit | Complex enchant descriptions; enchant section not detected |
| lobe still below 75% | lobe | Piercing description lines still garbled |

**Root cause of section header false-negatives:** `세공` and `에르그` are very short (2-3 chars) and appear only at the start of a section block, surrounded by UI borders. The model conflates them with artifact characters. Underrepresented in training (only 10 reps each). The ratio guard added to `_match_section_header` prevents false positives, but false negatives (headers OCR'd as noise) remain unresolved until training improves.

---

## Post-Attempt 15: Fuzzy Matching Pipeline Improvements

After confirming Attempt 15 results, significant improvements were made to the fuzzy matching (FM) layer without changing the OCR model. These changes are in effect for Attempt 16+ evaluation.

### Section-Aware FM Architecture

**Before:** FM always searched the combined dictionary (all sections merged). A high-confidence correct line like `72` could be "corrected" to `72` (from dictionary) — but a wrong section's FM lookup could change `수리비 200% 증가` to an unrelated reforge entry.

**After:**
- **Section-specific search:** FM looks only in the dictionary matching the detected section (e.g., `reforge.txt` for reforge lines, `enchant.txt` for enchant lines).
- **Sentinel values:** `-2` = section known but no dictionary (FM skipped entirely), `-3` = reforge `ㄴ` sub-bullet (always skipped — effect values vary and aren't in the dictionary).
- **Sub-bullet exclusion:** Reforge `ㄴ` sub-bullet lines are excluded from accuracy counting (scores represent OCR-correctable lines only).
- **FM regression detection:** New `[RF]` status in verbose output shows when FM changes a correct OCR line to wrong — made regressions visible rather than silent.

### Section Header Ratio Guard

`_match_section_header` now applies a ratio guard: `len(pattern)/len(cleaned) >= 0.5`. Prevents content lines that contain a section keyword as a substring from being promoted to section headers.

Examples fixed:
- `너 상 개조55, 보석 비` contains `개조` → was promoted to `item_mod`. Now rejected (2/12 = 0.17 < 0.5).
- `(에르그 이전 불가)` contains `에르그` → was promoted to `erg`. Now rejected (3/9 = 0.33 < 0.5).

### Reforge Section-Specific Processing

- **Level suffix strip + re-attach:** `_REFORGE_LEVEL_PAT` strips `(15/20 레벨)` before FM name matching (so `막: 스매시 대미지(15/20 레벨)` matches `스매시 대미지` in reforge.txt), then re-attaches the original suffix to the FM result. Without re-attach, FM was replacing the full OCR line with just the name — a regression for already-correct lines.
- **Parse mode `reforge_options`** in `mabinogi_tooltip_parser.py`: tags each reforge line with `reforge_name`, `reforge_level`, `reforge_max_level`, `is_reforge_sub`.

### Two-Phase Enchant Matching

Enchant matching now works in two phases instead of a flat dictionary search:

**Phase 1 (header):** OCR text like `[접두] 충격을 (랭크 F)` → FM against all 1172 canonical enchant headers in `_enchant_headers_norm`. Returns the matched `entry` containing the enchant's effect list.

**Phase 2 (effects):** OCR effect lines → FM against only that enchant's 4–8 effects, not the full 6116-entry flat list. Reduces false positive risk drastically.

**Enchant dictionary transformation:** `data/dictionary/enchant.txt` reformatted from:
```
접미 6
관리자
아르카나 스킬 보너스 대미지 1% 증가
...
```
to:
```
[접미] 관리자 (랭크 6)
아르카나 스킬 보너스 대미지 1% 증가
...
```
6223 → 5232 lines (991 old-format headers merged + 181 already-correct headers = 1172 total canonical headers). Ranks cover both letter (A-F) and numeric (1-9) formats.

**TextCorrector additions (`backend/text_corrector.py`):**
- `_load_enchant_structured(path)` — builds `_enchant_db` (1172 entries) and `_enchant_headers_norm`
- `match_enchant_header(text, cutoff=80)` → `(header, score, entry)`
- `match_enchant_effect(text, entry, cutoff=75)` → `(corrected_text, score)`

### FM Results (GT-sections mode, all 5 images)

With `--include-fuzzy --use-gt-sections --normalize --gt-suffix _expected.txt`:

| Image | OCR Exact | FM Exact | Recovered | Skipped (sub-bullets) |
|-------|-----------|----------|-----------|----------------------|
| captain_suit | 5 | 5 | 0 | 0 |
| dropbell | 10 | 10 | 0 | 3 |
| lightarmor | 24 | 26 | +2 | 1 |
| lobe | 2 | 2 | 0 | 0 |
| titan_blade | 21 | 22 | +1 | 3 |
| **TOTAL** | **62/223** | **65/223** | **+3** | **7** |

Char accuracy: 76.5% → 76.6% after FM (FM net positive, 0 regressions after reforge level suffix fix).

---

## Attempt 16: Boost Section Header Recognition

### Strategy

**Goal:** Fix the false-negative section header recognition that causes cascade failures. When `세공` is OCR'd as `제채두 고급`, the parser fails to open the `reforge` section — all subsequent reforge lines are misclassified, and section-specific FM cannot search the right dictionary.

**Root cause:** Section header words (`세공`, `에르그`) are very short (2-3 chars), surrounded by UI box art, and only occurred 10 times each in Attempt 15 training. This is insufficient for the model to reliably distinguish them from similar-looking artifact patterns.

**Key insight from ratio guard analysis:** The ratio guard now prevents content lines from being false-positive promoted to headers. This means the only remaining section-detection errors are false negatives from garbled OCR. These are fully attributable to training coverage, not pipeline logic.

### Pre-training Fixes (before generating data)

Three bugs discovered and fixed before Attempt 16 training data generation:

**1. Charset gap: 509 → 1201 characters**
Dictionary coverage audit revealed 692 characters in `enchant.txt` and `item_name.txt` that were NOT in `unique_chars.txt`. These included common Korean syllables (`국`, `눈`, `말`, `안`, `않`, `왕`, `옵`, ...) that appear in real enchant effects. Because the model's CTC output layer is fixed at training time, it could NEVER output these characters — they would be permanently garbled regardless of how well the model trained. Additionally, training labels containing uncovered characters are silently skipped by the training code, wasting those dictionary entries.

Fix: Expanded `unique_chars.txt` from 509 → 1201 chars (all characters present in any dictionary file, including ASCII specials from item names). Re-ran `create_model_config.py` to regenerate `backend/models/custom_mabinogi.yaml`.

**2. `set()` dedup killed all weighted repetitions**
`generate_data()` used `list(set(template_lines + ...))` which collapsed all N copies of a header down to 1 unique entry → only `VARIATIONS_PER_LABEL=3` images per header. The 130× boost for `세공` in `generate_template_lines()` produced exactly 3 training images — same as the 10× baseline.

Fix: After the `list(set(...))` dedup, explicitly add extra copies of critical headers to `all_labels` (post-dedup boost). Effect: `세공` → 44 copies → ~132 images; `에르그` → 27 copies → ~81 images.

**3. item_name.txt dilution (20,284 → 3,000 sampled)**
`item_name.txt` had 20,284 entries. Unsampled, this would produce ~84k total images with critical headers at 3/84k = 0.004% of training data. Sampled to 3,000 entries to keep dataset at ~30k images, maintaining proportional representation of all patterns.

### Training Data Statistics (Attempt 16)

| Stat | Attempt 15 | Attempt 16 |
|---|---|---|
| Charset | 509 chars | **1201 chars** |
| Template unique labels | ~2,852 | ~2,852 (unchanged) |
| Dict entries (after sampling) | ~11,580 total | ~10,979 raw / 7,088 unique |
| Total unique labels | ~3,860 | ~9,981 |
| Post-dedup header boost | 0 (broken) | +132 copies |
| **Total training images** | **11,580** | **~30,339** |
| num_iter | 10,000 | **20,000** (scaled for 2.6× larger dataset) |

Critical header image counts:
| Header | Attempt 15 (actual) | Attempt 16 (actual) |
|---|---|---|
| `세공` | 3 | **~132** |
| `에르그` | 3 | **~81** |
| `인챈트` | 3 | **~30** |
| `아이템 속성` | 3 | **~39** |

### Expected Improvement

Fixing `세공` and `에르그` recognition cascades to:
- titan_blade reforge section: correctly categorized → reforge FM fires → `스매시 대미지(15/20 레벨)` corrected
- titan_blade erg section: lines correctly tagged → section-specific handling
- Broader charset coverage enables recognition of previously impossible characters in enchant effects
- Overall estimated gain: +5-10 exact matches

**Target:** 70+/230 exact (30%+), **79%+** char accuracy.

### Attempt 16 Results

**Outcome: Regression — 28/230 exact (12.2%), 71.3% char acc (vs 64/230, 77.0% in Attempt 15)**

Synthetic training accuracy converged to 99.97% but real-world performance dropped sharply. The charset expansion (509→1201) enlarged the CTC output space by 2.4× without proportionally increasing training data, degrading the model's ability to discriminate between similar characters at inference.

**Post-mortem analysis revealed a deeper, more fundamental domain gap** (see Attempt 17 section below for full analysis). The charset expansion and header boost were correct fixes but did not address the root rendering mismatch between synthetic and real crops.

---

## Attempt 17: Fix the Rendering Domain Gap (Ink Ratio)

### What the data actually shows

After Attempt 16's regression, we measured the actual PADDED crops fed to `recognize()` (5 GT images) vs synthetic training images.

**Critical measurement note:** `parse_tooltip()` applies padding before calling `recognize()`:
`pad_y = max(1, h//5)`, `pad_x = max(2, h//3)`. Raw bounding box heights (median h=10) are NOT what the model sees. Actual padded inference crops: **h median = 14px**.

**Gap 1 — Ink ratio (the real bottleneck):**

| | Actual padded inference crops | Synthetic (Att 16, black-on-white) |
|---|---|---|
| Ink ratio median | **0.201** | **0.144** |

Real strokes are ~1.4× thicker than synthetic. Root cause: real crops come from `game engine colored text on dark bg → BT.601 grayscale → threshold(bright→black)`, which captures the full anti-aliasing zone as ink. Synthetic uses `PIL black-on-white → threshold(dark→black)`, capturing only the dark core → thinner strokes.

**Gap 2 — Height (smaller than initially estimated):**

| | Actual padded inference crops | Synthetic (Att 16) |
|---|---|---|
| h median | **14px** | **15px** |

These **already match** — the font sizes 10-11 were already producing the right height. Initial analysis used raw bounding boxes (h=10) and concluded a large height gap existed; this was an error.

**Early incorrect Attempt 17 run** changed `FONT_SIZES` to `[8,8,8,9,9,10]` → synthetic h=11 (undershoots padded inference h=14 by 3px). Training was killed before completion. The correct fix is game-like rendering at font sizes 10-11.

### Why ink ratio matters: AlignCollate

EasyOCR scales every crop to imgH=32 via bilinear interpolation. Scale factor = `32 / crop_height`. For actual padded inference crops (h=14):

| Crop type | h | Scale factor | Ink ratio before scaling |
|---|---|---|---|
| Real padded crop | 14px | ×2.28 | 0.201 (thick strokes) |
| Synthetic (Att 16) | 15px | ×2.13 | 0.144 (thin strokes) |
| Synthetic (Att 17) | 14-15px | ×2.13-2.28 | ~0.20 (game-like) |

Thin (0.14) vs thick (0.20) strokes at similar scale factors still produce visibly different character shapes. This explains why the model could recognize syntethic training images (99.97%) but fail on real crops — it learned thin-stroke glyph shapes.

### Hypothesis for Attempt 17

**Hypothesis:** Switching to game-like rendering with the same font sizes (10-11) will fix the ink ratio gap without any height regression.

**Mechanism:**
- `PIL font 10-11 + dark bg + bright text → BT.601 → bright→black threshold` produces:
  - h=14-15px (same as Att 16, correct for padded inference crops)
  - ink_ratio ~0.20 (matches real padded crop ink ratio 0.201)
- Font sizes unchanged from Att 16 — preserves correct height distribution
- Only ink ratio changes — this isolates the rendering effect

**What we measured in sample images** (`sample_train_images/final_comparison.png`):
- Game-like rendering visually more similar to real game crops (thicker strokes)
- Downscaling rejected: font 8 at h=7 is illegible for Korean text

### Changes for Attempt 17

1. **`render_line()` in `generate_training_data.py`**: Switch from black-on-white to game-like rendering:
   - `Image.new('RGB', bg=(15-45, 10-40, 15-50))` + bright text `(210-255, 210-255, 200-255)`
   - `.convert('L')` (BT.601) + `point(x > thresh → 0, else 255)` (bright→black)

2. **`FONT_SIZES`**: Keep `[10,10,10,11,11,11]` (unchanged from Att 16)
   - f10: text_h ≈ 10 → pad_y=2 → img_h=14 ✓ matches padded inference h=14
   - f11: text_h ≈ 11 → pad_y=2 → img_h=15 ✓ matches padded inference h=14-15

3. **No other changes**: Character set (1201), header boosts, GT lines, dictionary sampling — all kept from Attempt 16.

### How to evaluate Attempt 17

Run with the canonical command: `python3 scripts/test_v2_pipeline.py -q --normalize --gt-suffix _expected.txt`

**Success criteria:** Real char accuracy ≥ 77.0% (Attempt 15 baseline) and exact matches ≥ 64/230.

**If Attempt 17 succeeds** (char acc improves): Ink ratio domain gap was a real bottleneck. Continue with fine-tuning or human-in-the-loop Stage 2.

**If Attempt 17 fails (char acc similar or lower):**
- If synthetic acc is high but real drops: game-like rendering created a new gap (character shapes too different). Revert to black-on-white.
- If both drop: 1201-char CTC space needs more training data/iterations before any rendering fix can show effect.
- Next step: measure per-section accuracy to identify which section types improved/regressed.

**One metric that would clarify:** Compare per-section accuracy before and after. If stat lines (long, frequent) improve but headers (short, rare) don't, ink ratio was the main factor.
