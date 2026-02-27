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
| v3 | 11,680 synthetic + 1,265 real (55 unique × 23 copies) | 55 | **100% (55/55)** |

**Attempt 19 proved that real sample mixing works.** Just ~10% real crops took accuracy from 46.3% → 100%. This validates the user correction feedback pipeline as a reliable strategy for continuous improvement.

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

## Better Crops → Better Training Data → Better Models

### The Virtuous Cycle

Attempt 19 proved that real samples dramatically improve model accuracy. This means **crop quality is upstream of everything** — better crops produce better training data, which produce better models, which produce better OCR output.

```
Color pattern discovery (rgb_mask_test.py)
    → improved crop/segmentation logic
        → cleaner line crops
            → better real training samples
                → better models
                    → better OCR → user corrections → more real samples → ...
```

### Improving Crop Logic via Color Patterns

Using `scripts/ocr/rgb_mask_test.py`, general color rules are being discovered across all 26 theme images:

| Color | RGB | What it marks |
|-------|-----|---------------|
| Blue | (74, 149, 238) ±1 | Effect/stat lines (enchant effects, reforge options, set bonuses) |
| Orange | R>150, 50<G<180, B<80 | Section headers |
| White (balanced channels) | max/min < 1.4 | Enchant slot headers, general text |

These color constants are game engine invariants — they work across all themes and resolutions. Each discovered pattern can improve how we crop, classify, and preprocess lines before OCR.

### What This Enables

- **Line-type tagging before OCR**: Color tells us what a line IS (effect, header, sub-line) without reading it
- **Targeted preprocessing per line type**: Different preprocessing for blue effect lines vs white text vs orange headers
- **Cleaner training crops**: Isolate exactly the pixels that matter, remove noise from adjacent lines
- **Same approach for content models**: What worked for enchant headers (real sample mixing) should work for content OCR too — once we have clean, well-classified crops

## Per-Segment Dedicated Content Models

### Background

The v3 pipeline now detects the tooltip font from the pre_header region (mabinogi_classic vs nanum_gothic) and routes all content segments to a single font-matched model. Currently using preheader models (trained on item names only) as a stopgap — they have good charset coverage (1181 chars, superset of general's 554) but lack content-specific training data.

Results: **193/313 exact, 87.6% char_acc** — improved item_attrs (+4), enchant (+2) vs DualReader, but regressed item_mod (-2) and erg (-1) due to missing content patterns.

### What's Needed

Train per-segment models for each font (mabinogi_classic + nanum_gothic):

| Segment | Key Patterns |
|---------|-------------|
| item_attrs | 공격, 부상률, 크리티컬, 밸런스, 내구력, 피어싱, 성수 효과, hashtag lines |
| item_mod | 일반 개조, 보석 강화, 특별 개조, 강화N, 최소/최대 공격력, 밸런스 |
| erg | 등급 S, 최종 단계, 기본/추가 효과, skill cooldowns |
| set_item | 발동 조건, skill 강화, 최종 대미지 증가 |
| item_grade | 마스터, 장비 레벨, 등급 보너스 |
| ego | spirit weapon 레벨, 최대 레벨 |

### Key Constraints

- **Keep BT.601 grayscale preprocessing** for content — color-based preprocessing (detect_cm/detect_ng) kills too many lines due to diverse text colors (grey, blue, colored stats)
- Font decision is already wired: pre_header detects font → single reader passed to content OCR
- Enchant and reforge currently use DualReader — may switch to font-matched once models are ready

### Enchant Effect FM: Condition Mismatch Problem

Enchant effects with conditions (e.g. `탐험 레벨이 15 이상일때 최대대미지 15 증가`) are rejected by FM because:
- DB stores effect-only: `최대대미지 N ~ N 증가`
- OCR outputs full line: `탐험 레벨이 N 이상일때 최대대미지 N 증가 (N계~N`
- `fuzz.ratio` penalizes length mismatch → score=45 (below cutoff 75)

Attempted fix: include `condition + effect` in DB. Result: +7 FM matches but **wrong enchant entries' similar conditions** (e.g. `요리 랭크 N 이상일 때`) corrupt correct OCR text when phase-1 header is misidentified. Reverted.

**Root cause:** Phase-1 header misidentification. When header OCR picks the wrong enchant, the shared condition template (`N 랭크 N 이상일 때`) causes false high scores. Fix header accuracy first, then revisit condition matching.

### Future: Enchant Slot Filtering by Item Type

`enchant.yaml` entries include availability constraints like `~~에 인챈트 가능` (e.g., `무기에 인챈트 가능`, `방어구에 인챈트 가능`). This means some enchants can only be applied to certain item types. If we know the item type (weapon, armor, accessory, etc.), we can narrow the candidate list for enchant identification.

**Not yet usable:** We only have `item_name.txt` (pure names) — no item-type attribute mapping. Once we have an item attribute DB (name → type), this constraint can filter Dullahan candidates and reduce false matches.

## Philosophy: Two-Track Strategy

Every complementing strategy (Dullahan, item name parsing, slot filtering, effect-guided matching) exists because OCR accuracy is not yet perfect. With perfect OCR, none of these would be needed — the raw text would be the answer.

But we want to productize this service as soon as possible. Running two tracks in parallel achieves this:

1. **Track A — Improve OCR:** Better models, real-crop mixed training, per-segment dedicated models. This raises the accuracy floor over time.
2. **Track B — Complementing strategies:** Fuzzy matching, item name parsing, Dullahan, slot filtering. These compensate for current OCR gaps and make the service usable now.

Both tracks reinforce each other: better OCR makes strategies more reliable (cleaner input), and strategies provide training signal (user corrections → new real samples). The goal is convergence — as OCR improves, strategies become confirmations rather than corrections.

## User Guidance for Better Recognition

Tips to show users for optimal OCR results:

- **Crop tightly**: Crop the screenshot to show only the item tooltip, removing surrounding game UI as much as possible
- **Use simple tooltip**: Press **ALT** in-game to show the abbreviated tooltip — fewer lines means fewer OCR errors (e.g. plate_helmet: 42 lines → 33 lines, no sub-line descriptions to misread)

### V3 Training Pipeline

```bash
# Steps 1-3 done. Ready for training:
nohup python3 -u scripts/ocr/enchant_header_model/train.py --version v3 --resume-from v2 > logs/training_enchant_header_v3.log 2>&1 &

# After training:
bash scripts/ocr/enchant_header_model/deploy.sh v3

# Evaluate:
python3 scripts/ocr/enchant_header_model/test_ocr.py "data/sample_enchant_headers/*.png"
```
