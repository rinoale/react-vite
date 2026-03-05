# Project Tasks

## Backend

### Unify header models into a single `header_model` (nanum gothic)

Headers in the tooltip (category headers, enchant slot headers, item_mod special upgrade line) are always rendered in NanumGothic font regardless of the item's font config. Currently we have separate models (`category_header_model`, `enchant_header_model`) trained on nanum gothic. These should be consolidated into a single `header_model` trained with nanum gothic font covering all header types. The item_mod handler already hardcodes `content_ng_reader`; a unified header model would make the pipeline simpler — just find the header line and OCR it with the one header model.
Or at least two models, category header model and subheader model.

### Structural line grouping and subheader detection within segments

#### Background

Our tooltip parsing has evolved through increasingly deeper structural understanding:
1. **Line split + OCR** — flat list of lines, no structure
2. **Category header segmentation** — orange headers divide tooltip into labeled segments
3. **Prefix detection** — bullet/subbullet filtering decides what to OCR per segment
4. **Subheader models** — enchant_header_model recognizes slot headers inside enchant segment

The next step is to detect structure *within* a segment without relying on OCR or color masks — purely from spatial geometry of the line crops.

#### Line grouping by inter-group gaps

Lines within a segment naturally cluster into groups separated by larger gaps. The gap between groups is noticeably wider than the gap between lines within a group.

```
---- ← group A
----

---- ← group B
---
----

--- ← group C
--
```

Measure the vertical distance (gap) between consecutive lines. Gaps above a threshold (e.g. median gap × 1.5) indicate group boundaries. This gives us semantic clusters without OCR — each group likely represents a distinct sub-section (e.g. a subheader followed by its content lines).

#### Subheader detection by line height clustering

Subheaders and plain content lines are rendered at different font sizes, producing measurably different line heights in the binary crops:

```
|||| ← subheader (taller)
lll  ← plain lines (shorter)
lllll
lllll
```

Rather than comparing against a fixed pixel threshold, cluster all line heights within a segment into 2-3 groups (e.g. k-means or simple gap detection on sorted heights). The tallest cluster = subheaders, the shorter cluster(s) = content lines.

**Prerequisites:**
- Accurate line split logic — line crops must have consistent, tight bounding boxes for height measurements to be reliable
- Border removal and padding must not inflate heights inconsistently

**What this enables:**
- Generic subheader detection that works across all segments (not just enchant)
- Eliminates need for per-segment subheader OCR models — detect first, then route to appropriate model
- Combined with line grouping: automatically identify `[subheader] + [content lines]` blocks within any segment

### Merge prefix detection + filtering into a single decorator

Currently handlers chain `@detect_prefix('bullet')` + `@filter_prefix('bullet')` or `@plain_lines_only` as separate decorators. These could be a single decorator like `@select_lines('bullet')` / `@select_lines(None)` that detects and filters in one pass.

### Replace `sys.path` hacks with `PROJECT_ROOT` env var
**Context:** Scripts under `scripts/ocr/` currently use `sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))` to reach the project root for imports (e.g. `from scripts.ocr.lib.model_version import ...`). Going up 3 directory levels is fragile and will break if scripts move again.

**Approach:** Define a `PROJECT_ROOT` environment variable (via `.env` file, shell profile, or a small bootstrap script) so all scripts can do:
```python
import os
PROJECT_ROOT = os.environ['PROJECT_ROOT']
sys.path.insert(0, PROJECT_ROOT)
```

**Alternatives considered:**
- **Root marker file**: Walk up directories looking for `.git/` or a sentinel file. More automatic but adds boilerplate to every script.
- **Installable package** (`pyproject.toml`): Make `scripts/` a proper Python package. Cleanest long-term but heavier setup.

**Affected files:** All 9 Python scripts under `scripts/ocr/` and `scripts/ocr/lib/model_version.py`.

### Resolved: Enchant Effect Line Continuation Merge

Implemented in attempt 22. Continuation lines (no bullet prefix) are merged into the preceding bullet-prefixed anchor by `merge_continuations()` in `line_processing.py`. Both `text` and `raw_text` are merged; `_is_stitched=True` flags the anchor. Runs BEFORE FM so merged text has all rolled numbers available for matching. The `_is_stitched` flag propagates through `ocr_results.json` → `OcrCorrection.is_stitched` → admin badge.

### Blue Mask: Color-Based Effect Line Detection

#### Discovery

The game renders effect/stat lines in a fixed RGB color: **RGB(74, 149, 238) ±1 tolerance**. This is consistent across all 26 theme images in `data/themes/`. The color acts as a semantic label — it marks the lines that carry actual stat data.

Verified with: `python3 scripts/ocr/rgb_mask_test.py "data/themes/*.png" --rgb 74,149,238 --tolerance 1`

#### What it captures

- Enchant effects (e.g. `크리티컬 대미지 3% 증가`)
- Reforge options with levels (e.g. `듀얼건 최소 대미지(20/20 레벨)`)
- Reforge main effects (e.g. `무기 공격력 20 증가`)
- Set item bonuses
- Stat modifiers (e.g. `피어싱 레벨 1+ 3`)

#### What it excludes

- Sub-explanation lines (gray/white, different color)
- Section headers (orange)
- Enchant slot headers (white)
- Flavor text, shop price, gray descriptive text

#### Why this matters

- **No position heuristics needed**: main effect vs sub-line is determined by color, not x-offset or `ㄴ` prefix detection
- **No OCR dependency for classification**: color masking is pixel-exact, zero error rate
- **Theme-independent**: same RGB across all 26 backgrounds — a game engine constant
- **Potential as a 4th preprocessing path**: alongside BT.601+threshold (content), threshold=50 (headers), and oreo_flip (enchant headers), a blue mask could isolate effect lines for targeted OCR or structured extraction

#### Next Steps

- Investigate if blue-masked lines can replace or supplement current content OCR for enchant/reforge sections
- Test if line splitting on blue-masked images gives cleaner crops (no adjacent non-effect lines to confuse splitter)
- Consider using blue mask to tag lines as "effect" before OCR, eliminating need for post-hoc sub-line detection

### Better Crops → Better Training Data → Better Models

Attempt 19 proved that real samples dramatically improve model accuracy. This means **crop quality is upstream of everything** — better crops produce better training data, which produce better models, which produce better OCR output.

```
Color pattern discovery (rgb_mask_test.py)
    → improved crop/segmentation logic
        → cleaner line crops
            → better real training samples
                → better models
                    → better OCR → user corrections → more real samples → ...
```

#### Improving Crop Logic via Color Patterns

Using `scripts/ocr/rgb_mask_test.py`, general color rules are being discovered across all 26 theme images:

| Color | RGB | What it marks |
|-------|-----|---------------|
| Blue | (74, 149, 238) ±1 | Effect/stat lines (enchant effects, reforge options, set bonuses) |
| Orange | R>150, 50<G<180, B<80 | Section headers |
| White (balanced channels) | max/min < 1.4 | Enchant slot headers, general text |

These color constants are game engine invariants — they work across all themes and resolutions. Each discovered pattern can improve how we crop, classify, and preprocess lines before OCR.

#### What This Enables

- **Line-type tagging before OCR**: Color tells us what a line IS (effect, header, sub-line) without reading it
- **Targeted preprocessing per line type**: Different preprocessing for blue effect lines vs white text vs orange headers
- **Cleaner training crops**: Isolate exactly the pixels that matter, remove noise from adjacent lines
- **Same approach for content models**: What worked for enchant headers (real sample mixing) should work for content OCR too — once we have clean, well-classified crops

### Per-Segment Dedicated Content Models

#### Background

The v3 pipeline now detects the tooltip font from the pre_header region (mabinogi_classic vs nanum_gothic) and routes all content segments to a single font-matched model. Currently using preheader models (trained on item names only) as a stopgap — they have good charset coverage (1181 chars, superset of general's 554) but lack content-specific training data.

Results: **193/313 exact, 87.6% char_acc** — improved item_attrs (+4), enchant (+2) vs DualReader, but regressed item_mod (-2) and erg (-1) due to missing content patterns.

#### What's Needed

Train per-segment models for each font (mabinogi_classic + nanum_gothic):

| Segment | Key Patterns |
|---------|-------------|
| item_attrs | 공격, 부상률, 크리티컬, 밸런스, 내구력, 피어싱, 성수 효과, hashtag lines |
| item_mod | 일반 개조, 보석 강화, 특별 개조, 강화N, 최소/최대 공격력, 밸런스 |
| erg | 등급 S, 최종 단계, 기본/추가 효과, skill cooldowns |
| set_item | 발동 조건, skill 강화, 최종 대미지 증가 |
| item_grade | 마스터, 장비 레벨, 등급 보너스 |
| ego | spirit weapon 레벨, 최대 레벨 |

#### Key Constraints

- **Keep BT.601 grayscale preprocessing** for content — color-based preprocessing (detect_cm/detect_ng) kills too many lines due to diverse text colors (grey, blue, colored stats)
- Font decision is already wired: pre_header detects font → single reader passed to content OCR
- Enchant and reforge currently use DualReader — may switch to font-matched once models are ready

### Digit Confusion in OCR (6↔8, 8↔9)

#### Problem

OCR frequently confuses digits with similar stroke structures: `6↔8` (open vs closed top loop) and `8↔9` (bottom loop vs tail). This is a universal OCR problem — not Korean-specific — caused by 1-2 pixel differences at small font sizes.

#### Approaches (ordered by effort)

1. **Game knowledge constraints (no retraining):** Each enchant in `enchant.yaml` has known effect value ranges. After FM matches the effect template (e.g. `최대대미지 N 증가`), validate the OCR'd number against the expected range. If the value is out of range, try swapping confusing digits (6↔8, 8↔9) and check again.

2. **Training data weighting (retraining):** Oversample synthetic lines containing confusing digit pairs (6/8/9). Current templates generate numbers uniformly — biasing toward hard pairs gives the model more signal on the distinguishing pixels.

3. **Template matching for mabinogi_classic (no retraining):** Since mabinogi_classic has no anti-aliasing, each digit at game font size is an exact pixel pattern. A pixel template lookup on the binary crop would be 100% reliable for that font. Does not help nanum_gothic.

4. **Higher effective resolution (retraining):** Current `imgH=32` downscale may compress the 1-2 pixel difference between 6/8 into nothing. Increasing `imgH` gives the model more pixels but increases training/inference cost.

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

### Detect Abbreviated vs Full Enchant Effect Lines

#### Background

Enchant effects with conditions can appear in two forms depending on whether the user has met the condition:

- **Full (condition not met):** `· 원소 연마 특성 8레벨 이상일 때 최대대미지 16 증가`
- **Abbreviated (condition met):** `· 최대대미지 16 증가`

Currently the pipeline doesn't track which form the tooltip showed. This matters for:
- **Admin review**: knowing whether a correction should include the condition text or not
- **Training data quality**: abbreviated crops should not be trained against full-text GT, and vice versa
- **FM accuracy**: condition-stripped DB effects match abbreviated lines well but score poorly against full lines (fuzz.ratio penalizes length mismatch)

#### Approach

Detect abbreviation per line by comparing OCR text length against the DB effect's full form (condition + effect). If the OCR text is significantly shorter than `condition + effect` but matches `effect` alone, the line is abbreviated.

Store a flag per line (e.g. `is_abbreviated: bool`) so downstream consumers (correction system, admin UI, FM) can handle both forms correctly.

#### Prerequisites

- `enchant.yaml` already separates `condition` and `effect` fields — the data is available
- `raw_text` is now always persisted in `ocr_results.json` (pre-FM snapshot) — detection can run on raw OCR text

#### Open Questions

- Should FM use different templates for abbreviated vs full lines?
- Should the admin UI show the abbreviation flag to help reviewers?
- Can we use line length ratio alone, or do we need fuzzy matching against both forms?

### User Guidance for Better Recognition

Tips to show users for optimal OCR results:

- **Crop tightly**: Crop the screenshot to show only the item tooltip, removing surrounding game UI as much as possible
- **Use simple tooltip**: Press **ALT** in-game to show the abbreviated tooltip — fewer lines means fewer OCR errors (e.g. plate_helmet: 42 lines → 33 lines, no sub-line descriptions to misread)

### v1 Content Model Training Pending

Both font-specific models (mabinogi_classic, nanum_gothic_bold) training with new data: 748-char charset, enchant.yaml-sourced effects, no bullet prefixes, reduced threshold noise. Deploy and evaluate after training completes.

### Write Tests for Backend

**Infrastructure: pytest (done)**
- [x] `pyproject.toml` with `pythonpath = ["backend"]` — run via `python -m pytest tests/ -v`
- [x] `tests/conftest.py` — shared fixtures: `make_line_dict`, `make_bounds`, `make_classification`, `mini_text_corrector`

**Unit tests (done — 287 tests passing):**
- [x] `tests/test_data_structures.py` — pipeline data structure examples, HTTP response schema validation, ocr_results.json shape, stitch flag contracts (14 tests)
- [x] `tests/test_line_processing.py` — `merge_group_bounds`, `trim_outlier_tail`, `determine_enchant_slots`, `merge_continuations`, `count_effects_per_header` (13 tests)
- [x] `tests/test_line_merge.py` — `detect_gap_outlier` (5 tests)
- [x] `tests/test_parse_effect_number.py` — `_parse_effect_number` (6 tests)
- [x] `tests/test_text_corrector.py` — `correct_normalized`, `parse_item_name`, `match_enchant_effect` (11 tests)
- [x] `tests/test_tooltip_parser.py` — `build_enchant_structured`, `build_reforge_structured` (7 tests)
- [x] `tests/test_prefix_detector.py` — `detect_prefix` with synthetic numpy arrays (6 tests)
- [x] `tests/test_line_splitter.py` — `detect_text_lines` with synthetic binary images (4 tests)
- [x] Bullet prefix detection and trimming
- [x] Effect number extraction (`_parse_effect_number`)
- [x] FM matching for enchant effects (condition-aware number selection)
- [x] Enchant structured rebuild (`build_enchant_structured`)

**Remaining (not yet implemented):**
- [ ] Write a test verifying the entire v3 pipeline with one or more `data/sample_images/*_original.png`, comparing against expected results
- [ ] Write tests verifying category header functionalities (detection, OCR, classification), comparing against expected results
- [ ] Enchant header detection (white-mask band detection)
- [ ] Enchant line classification (header/effect/grey)
- [ ] Enchant resolution (P1/P2/P3 competition)
- [ ] Templated effect text generation

---

## Frontend

### V3 UI Implementation

#### 1. Image Upload & Preprocessing
- [x] Switch to Color Uploads
- [x] Multi-Step Progress State
- [ ] Error Handling for segmentation failure

#### 2. Structured Item Registration Form
- [x] Header Section (Item Name, Grade)
- [x] Dynamic Category Cards (Attributes, Enchant, Upgrade, Reforge, Erg, Set Item, Item Color)
- [x] Reforge Row mapping

#### 3. Data Integration (API)
- [x] Update Endpoint to `/upload-item-v3`
- [x] JSON Mapping for structured response
- [ ] Segment Previews (base64 crops next to input fields)

#### 4. UX & Validation
- [x] Confidence Highlighting
- [ ] Fuzzy Search Pickers for enchant/reforge autocomplete
- [x] Mabinogi Theming

#### 5. Admin Dashboard
- [x] Enchant List with Effects
- [x] Expandable Detail
- [ ] Dynamic Link Filtering (`?enchant_entry_id=N`)
- [ ] Reforge Validation view

### Write Tests for Frontend

**Infrastructure: vitest (done)**
- [x] `frontend/vitest.config.js` — jsdom environment, react plugin
- [x] `frontend/test-setup.js` — i18n mock, window globals (`GAME_ITEMS_CONFIG`, `ENCHANTS_CONFIG`, `REFORGES_CONFIG`)
- [x] `frontend/test-utils.js` — re-export `@testing-library/react`
- [x] `npm test` / `npm run test:watch` scripts in `frontend/package.json`

**Unit tests (done — 29 tests passing):**
- [x] `packages/shared/src/lib/__tests__/gameItems.test.js` — `getGameItemsConfig`, `findGameItemByName`, `searchGameItemsLocal` (8 tests)
- [x] `packages/shared/src/lib/__tests__/examineResult.test.js` — `parseExamineResult` (5 tests)
- [x] `packages/shared/src/components/__tests__/SectionCard.test.jsx` — rendering, toggle, remove (5 tests)
- [x] `packages/shared/src/components/__tests__/ConfigSearchInput.test.jsx` — rendering, filtering, selection, escape (4 tests)
- [x] `packages/shared/src/components/sections/__tests__/EnchantSection.test.jsx` — prefix/suffix slots, empty data, rank/effects (3 tests)
- [x] `packages/shared/src/components/sections/__tests__/ReforgeSection.test.jsx` — option list, level display, fallback inputs, add button (4 tests)

**Remaining (not yet implemented):**
- [ ] Write a test comparing expected form submit payload for given HTML form data (RegisterListingRequest)
- [ ] Write tests for expected behavior on HTML events:
  - Enchant name selection (editingName flow)
  - Effect level commit (commitLevel)
  - Reforge option editing
  - `abbreviated` flag toggle behavior on effect text rebuilding

#### Installed Test Libraries

**Backend:** `pytest`
**Frontend:** `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `jsdom`

---

## Infrastructure

### Replace `sys.path` hacks with `PROJECT_ROOT` env var
(See Backend section above — affects both backend and scripts infrastructure.)
