# Tasks

## Deferred: Enchant Effect Line Continuation Merge

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

## Detect Abbreviated vs Full Enchant Effect Lines

### Background

Enchant effects with conditions can appear in two forms depending on whether the user has met the condition:

- **Full (condition not met):** `· 원소 연마 특성 8레벨 이상일 때 최대대미지 16 증가`
- **Abbreviated (condition met):** `· 최대대미지 16 증가`

Currently the pipeline doesn't track which form the tooltip showed. This matters for:
- **Admin review**: knowing whether a correction should include the condition text or not
- **Training data quality**: abbreviated crops should not be trained against full-text GT, and vice versa
- **FM accuracy**: condition-stripped DB effects match abbreviated lines well but score poorly against full lines (fuzz.ratio penalizes length mismatch)

### Approach

Detect abbreviation per line by comparing OCR text length against the DB effect's full form (condition + effect). If the OCR text is significantly shorter than `condition + effect` but matches `effect` alone, the line is abbreviated.

Store a flag per line (e.g. `is_abbreviated: bool`) so downstream consumers (correction system, admin UI, FM) can handle both forms correctly.

### Prerequisites

- `enchant.yaml` already separates `condition` and `effect` fields — the data is available
- `raw_text` is now always persisted in `ocr_results.json` (pre-FM snapshot) — detection can run on raw OCR text

### Open Questions

- Should FM use different templates for abbreviated vs full lines?
- Should the admin UI show the abbreviation flag to help reviewers?
- Can we use line length ratio alone, or do we need fuzzy matching against both forms?

## User Guidance for Better Recognition

Tips to show users for optimal OCR results:

- **Crop tightly**: Crop the screenshot to show only the item tooltip, removing surrounding game UI as much as possible
- **Use simple tooltip**: Press **ALT** in-game to show the abbreviated tooltip — fewer lines means fewer OCR errors (e.g. plate_helmet: 42 lines → 33 lines, no sub-line descriptions to misread)

