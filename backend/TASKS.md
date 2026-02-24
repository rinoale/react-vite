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

### Implemented: Reforge Sub-Line Detection by X-Offset

Reforge sections have main effect lines and indented sub-explanation lines (the `ㄴ` descriptions). Detected by comparing each line's `bounds.x` against the section's minimum x — indented lines are tagged `is_reforge_sub: true`.

- **Detection**: `(line.x - min_x) > min_x` — relative threshold, no hardcoded pixel values, resolution-independent
- **FM skip**: sub-lines skip fuzzy matching (`text_corrector.py`) — only main lines are FM'd
- **Structured output**: sub-lines are associated with the preceding main option as `effect` in `build_reforge_structured()`
- **Code**: `_parse_reforge_section()` and `build_reforge_structured()` in `mabinogi_tooltip_parser.py`, FM skip in `text_corrector.py`

**Note**: May be superseded by blue mask detection (RGB 74,149,238) which distinguishes effect lines by color instead of position. If blue mask is adopted, the x-offset logic can be removed.

### Deferred: Enchant Effect Line Continuation Merge

Enchant effects can wrap across two lines. The idea is to detect continuation lines (no `-` bullet prefix) and merge them into the previous effect:
- `text_corrector.py`: tag lines with `_has_bullet` when stripping `-` prefix
- `mabinogi_tooltip_parser.py`: in `build_enchant_structured()`, merge lines without `_has_bullet` into previous effect

**Why deferred:** OCR accuracy is not yet reliable enough to distinguish whether a `-` prefix was present. Mis-detected bullets cause incorrect merges. Revisit once content OCR accuracy improves significantly (e.g. after real-crop mixed training for content models).

## Blue Mask: Color-Based Effect Line Detection

### Discovery

The game renders effect/stat lines in a fixed RGB color: **RGB(74, 149, 238) ±1 tolerance**. This is consistent across all 26 theme images in `data/themes/`. The color acts as a semantic label — it marks the lines that carry actual stat data.

Verified with: `python3 scripts/ocr/rgb_mask_test.py "data/themes/*.png" --rgb 74,149,238 --tolerance 1`

### What it captures

- Enchant effects (e.g. `크리티컬 대미지 3% 증가`)
- Reforge options with levels (e.g. `듀얼건 최소 대미지(20/20 레벨)`)
- Reforge main effects (e.g. `무기 공격력 20 증가`)
- Set item bonuses
- Stat modifiers (e.g. `피어싱 레벨 1+ 3`)

### What it excludes

- Sub-explanation lines (gray/white, different color)
- Section headers (orange)
- Enchant slot headers (white)
- Flavor text, shop price, gray descriptive text

### Why this matters

- **No position heuristics needed**: main effect vs sub-line is determined by color, not x-offset or `ㄴ` prefix detection
- **No OCR dependency for classification**: color masking is pixel-exact, zero error rate
- **Theme-independent**: same RGB across all 26 backgrounds — a game engine constant
- **Potential as a 4th preprocessing path**: alongside BT.601+threshold (content), threshold=50 (headers), and oreo_flip (enchant headers), a blue mask could isolate effect lines for targeted OCR or structured extraction

### Next Steps

- Investigate if blue-masked lines can replace or supplement current content OCR for enchant/reforge sections
- Test if line splitting on blue-masked images gives cleaner crops (no adjacent non-effect lines to confuse splitter)
- Consider using blue mask to tag lines as "effect" before OCR, eliminating need for post-hoc sub-line detection

### V3 Training Pipeline

```bash
# Steps 1-3 done. Ready for training:
nohup python3 -u scripts/ocr/enchant_header_model/train.py --version v3 --resume-from v2 > logs/training_enchant_header_v3.log 2>&1 &

# After training:
bash scripts/ocr/enchant_header_model/deploy.sh v3

# Evaluate:
python3 scripts/ocr/enchant_header_model/test_ocr.py "data/sample_enchant_headers/*.png"
```
