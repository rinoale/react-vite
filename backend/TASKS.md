# Tasks

## Improving Enchant Header Recognition

### Background

Enchant header OCR (v2) gets 46.3% exact match on real crops (106/229), despite 100% accuracy on synthetic training images. Root cause: subtle pixel-level differences between PIL-rendered synthetic training data and actual game screenshots (NanumGothicBold font is correct, but sub-pixel rendering differs).

### Two Tracks

**Track 1: Dullahan Algorithm (full automation)**

Improve the automated pipeline so enchant headers are recognized without user intervention. The Dullahan fuzzy-matching system in `text_corrector.py` already corrects OCR output against the enchant dictionary — better raw OCR accuracy means higher Dullahan hit rate.

Strategies:
- Mix real crops into synthetic training data with oversampling (~10% ratio) — v3 setup done
- Resume training from v2 checkpoint with lower LR (0.0003) for fine-tuning
- User correction feedback loop: each corrected header becomes a new real training sample for future versions

**Track 2: Enchant Header OCR + User Correction**

A pragmatic shortcut: if the header OCR correctly identifies the enchant name (e.g. `[접두] 창백한`), look up all effects from `enchant.yaml` — no need to OCR the individual effect lines. If the OCR is wrong, the user picks the correct enchant from a list. Their correction feeds back as new training data.

This approach:
- Eliminates effect-line OCR errors entirely for correctly identified enchants
- Provides a natural data collection pipeline for improving the model over time
- Gracefully degrades — worst case is the user corrects the enchant name manually

### Current State

| Version | Training Data | Real Crops | Accuracy (real) |
|---------|--------------|------------|-----------------|
| v1 | 3,504 synthetic | 0 | — |
| v2 | 11,680 synthetic | 0 | 46.3% (106/229) |
| v3 | 11,680 synthetic + 1,265 real (55 unique × 23 copies) | 55 | pending training |

### Deferred: Enchant Effect Line Continuation Merge

Enchant effects can wrap across two lines. The idea is to detect continuation lines (no `-` bullet prefix) and merge them into the previous effect:
- `text_corrector.py`: tag lines with `_has_bullet` when stripping `-` prefix
- `mabinogi_tooltip_parser.py`: in `build_enchant_structured()`, merge lines without `_has_bullet` into previous effect

**Why deferred:** OCR accuracy is not yet reliable enough to distinguish whether a `-` prefix was present. Mis-detected bullets cause incorrect merges. Revisit once content OCR accuracy improves significantly (e.g. after real-crop mixed training for content models).

### V3 Training Pipeline

```bash
# Steps 1-3 done. Ready for training:
nohup python3 -u scripts/ocr/enchant_header_model/train.py --version v3 --resume-from v2 > logs/training_enchant_header_v3.log 2>&1 &

# After training:
bash scripts/ocr/enchant_header_model/deploy.sh v3

# Evaluate:
python3 scripts/ocr/enchant_header_model/test_ocr.py "data/sample_enchant_headers/*.png"
```
