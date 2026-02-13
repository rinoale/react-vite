# Session: Attempt 8-10, imgW Mismatch Discovery, Training Infra

Date: 2026-02-13

## Summary

Trained Attempts 8, 8b, 9, and 10. Discovered two critical domain gaps: proportional canvas width regression and imgW mismatch between training and inference. Built training infrastructure (config file, launcher script, logs folder).

## Timeline

### Attempt 8 (5k iter) — Regression
- Changes: font size 8 added, proportional canvas width (60% tight-crop for short text)
- Result: 56.2% synthetic, **28.3% real char acc** (down from 35.8%)
- Diagnosis: Underfit — only 5k iterations for more varied data

### Attempt 8b (15k iter, continued from checkpoint)
- Continued training from Attempt 8 with `--saved_model`
- Result: 93.5% synthetic, **27.0% real char acc**
- Diagnosis: High synthetic + low real = **domain gap, not underfitting**

### Regression Root Cause Analysis
Proportional canvas width was the primary cause:
- 57% of synthetic training images had squash factors 1.0-2.0x (never seen in real data)
- Real crops are 95.4% full-width (~261px) regardless of text length
- The tight-crop assumption for short text was wrong — splitter crops to ink bounds within full tooltip width
- Font size 8 also under-represented at correct height (1.6% vs 28.5% needed)

### Attempt 9 — Recovery
- Reverted canvas width to always ~260px
- Changed font sizes to `[6,7,7,7,10,10,10,10,10,10,11,11,11,11]` (bimodal matching real h=8-9 and h=14-15)
- Aligned padding formula to splitter: `pad_y = max(1, text_h // 5)`, `pad_x = max(2, text_h // 3)`
- Result: 90.0% synthetic, **36.2% real char acc**, 0.044 confidence
- Recovered from regression, slightly beat Attempt 7 (35.8%)

### imgW Mismatch Discovery (Critical)
Investigation into why 36.2% is still far from 60% target revealed:
- **Training** `AlignCollate` resizes images to h=32 (maintaining ratio), then squashes to `imgW=200` if wider
- **Inference** (EasyOCR) pre-resizes to h=32 then uses dynamic `max_width = ceil(ratio)*32` (~576px)
- A 260x10px image becomes 832x32 after resize → training squashes to 200px (4.2x), inference keeps at ~832px
- Model trained on squished characters but sees normal-width characters at inference
- Evidence: short headers hallucinate 5-17x extra characters, OCR output averages 1.6x more chars than GT

### Attempt 10 — imgW 600
- Fix: `--imgW 600` to reduce squash from 4.2x to ~1.4x
- Also updated `custom_mabinogi.yaml` (both imgW fields) — required for TPS GridGenerator buffer shape compatibility
- Problem: `batch_size=64` with `imgW=600` maxed out 8GB VRAM (7,972/8,192 MiB), zero iterations completed
- Mitigation: `batch_size=16`, estimated ~6-13 hours for 5k-10k iterations

## Two-Stage Training Strategy (Decided)
- **Stage 1:** Synthetic-only training until 60% real char accuracy
- **Stage 2:** Fine-tune with real GT line crops (235 lines from 5 images) mixed 50/50 with synthetic, using `--saved_model` to continue from Stage 1

## Infrastructure Improvements
- **`configs/training_config.yaml`** — single source of truth for all training params (model architecture, hyperparams, paths). Eliminates hardcoded values.
- **`scripts/train.py`** — launcher that reads config, prints all params + full command, then runs `deep-text-recognition-benchmark/train.py`. Supports `--resume`, `--batch_size`, `--num_iter` overrides.
- **`scripts/create_model_config.py`** — now reads from `configs/training_config.yaml` instead of hardcoding `imgW: 200`. Must re-run when model architecture params change.
- **`logs/`** — all training logs moved here
- **`scripts/preprocess_v2.py`** — added docstring explaining it's a standalone CLI tool for manual image preprocessing

## Key Lessons
1. **Always check squash factors.** The model sees images after resize+squash, not the original dimensions. `imgW` controls how much squashing happens.
2. **Proportional canvas width was wrong.** Real crops are almost always full tooltip width. Don't assume short text = narrow crop.
3. **Font sizes must match real height clusters.** Real data is bimodal (h=8-9 and h=14-15). Font sizes producing intermediate heights (h=10-13) waste training budget.
4. **yaml must match training.** TPS Spatial Transformer is built with `I_size=(imgH, imgW)`. Mismatched yaml causes shape errors.
5. **imgW=600 with batch_size=64 causes OOM on 8GB.** Use batch_size=16.

## Results Table

| Attempt | Synthetic Acc | Real Char Acc | Confidence | Key Change |
|---------|--------------|---------------|------------|------------|
| 7 | 97.7% | 35.8% | 0.097 | Baseline (templates, natural height) |
| 8 (5k) | 56.2% | 28.3% | 0.004 | Proportional canvas (regression) |
| 8b (15k) | 93.5% | 27.0% | 0.014 | Continue from 8 — domain gap confirmed |
| 9 | 90.0% | 36.2% | 0.044 | Reverted canvas, bimodal font sizes |
| 10 | Pending | Pending | Pending | imgW=600, batch_size=16 |

## ELI5: Why imgW=600?

The training images are NOT 600px wide — they're ~260px. The confusion is about what happens **after** the model resizes them.

**What happens when the model receives a 260x10px image:**

1. The model first resizes it to height=32 (keeping aspect ratio)
   - `260 × (32/10) = 832px` wide now
   - So the image is now **832x32**

2. **During training** (with `imgW=200`): "832 is too wide, squash it to 200"
   - The 832px image gets compressed to 200px — characters are **4.2x horizontally squished**

3. **During inference** (EasyOCR): "832? Fine, I'll pad to the nearest 32-step"
   - The image stays at ~832px — characters are at **natural spacing**

So the model learns squished characters in training but sees normal-width characters in production. It's like studying with a textbook that's been photocopied at 25% width, then taking the exam with normal-sized text.

**Why 600?** It's a compromise. The ideal would be `imgW=832` or higher to match inference exactly, but larger imgW = more GPU memory. 600 reduces the squash from 4.2x down to ~1.4x, which is a massive improvement while still fitting in 8GB VRAM (with `batch_size=16`).

As Codex correctly noted, 600 is a **mitigation**, not a perfect match — some resized images still exceed 600 and get slightly squashed. But it's far better than 200.
