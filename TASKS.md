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

## Background Jobs

Jobs are registered in `backend/jobs/__init__.py` and manageable from the admin page (Jobs tab). Redis-based broker with queue routing (`default`, `gpu`). Worker process (`worker.py`) dequeues and executes jobs, records payload/result in `job_runs` table.

### Implemented
- [x] **cleanup_zero_weight_tags** — Delete user-created tags with weight 0 (queue: `default`)
- [x] **run_v3_pipeline** — Run V3 OCR pipeline on uploaded image (queue: `gpu`, lazy import)
- [x] **Worker heartbeat** — Redis SET-based heartbeat (`jobs:{queue}:workers`, 60s TTL, 30s refresh). Broker rejects jobs with `NoWorkerError` (HTTP 503) when no worker is listening.
- [x] **Admin worker count** — Jobs panel shows live worker count per queue with green/red badges
- [x] **Remote worker via SSH tunnel** — `scripts/worker/run-remote.sh` opens SSH tunnel to staging (Redis + DB), loads staging env, runs worker locally with GPU
- [x] **Pipeline init singleton** — `init_pipeline()` guard prevents reloading all OCR models (~10s) on every job
- [x] **Worker logging fix** — Alembic's `fileConfig()` disables pre-existing loggers; worker restores them after migration

### Planned
- [ ] **gather_discord_images** — Collect item screenshots uploaded to connected Discord channels (better UX for users)
- [ ] **create_recommendation_data** — Generate recommendation model data (TF-IDF vectors, similarity matrices)
- [ ] **get_horn_bugle** — Fetch in-game chat data every 2 minutes (scheduled, needs APScheduler or similar)

### Tech Stack
- **Current:** Redis broker + standalone worker process (`worker.py --queues ...`), `job_runs` DB table, heartbeat-based worker presence detection
- **Queue routing:** `default` (lightweight), `gpu` (OCR pipeline). Worker accepts `--queues` to select which queues to handle.
- **Remote worker:** SSH tunnel approach — Redis and DB bound to localhost on staging, remote worker tunnels through SSH. No ports exposed publicly.
- **Future (when scheduling needed):** Add APScheduler with PostgreSQL job store for periodic jobs (horn_bugle every 2 min, etc.)

---

## Product Features

### Subscribe / Regular Listing

Listings have an expiration model. Sellers can keep a listing active until:
- The listing reaches its end date, OR
- The seller manually finishes (marks as sold/deletes)

**Evaluation:** This is a core marketplace feature. Requires listing status (see below), a `expires_at` column on listings, and a background job to expire stale listings. Medium complexity — mostly backend + minor frontend for date picker and status display.

### User Activity Logs (for Recommendation)

Log user actions to feed the recommendation algorithm:
- **Search history** — what terms users search for
- **Listing detail views** — which listings users click into
- **Contact events** — when a user initiates contact with a seller
- **Transaction done** — when a deal completes

**Evaluation:** Requires a new `user_activity_logs` table (`user_id, action_type, target_id, metadata, created_at`). Low insert cost (append-only). The recommendation engine (`backend/lib/recommendation.py`) currently uses a mock `ITEMS_DB` with TF-IDF — these logs would replace it with real collaborative filtering signals. Backend-only, no frontend changes needed except wiring `onClick`/`onContact` to POST endpoints.

### Discord Image Scan

Can we save image upload traffic by scanning Discord channels for item screenshots?
- Users paste screenshots in a connected Discord channel
- A bot/webhook collects them and feeds into the OCR pipeline
- Reduces friction (no manual upload step)

**Evaluation:** Feasible via Discord bot API (`discord.py`). The bot watches specific channels, downloads images, and queues them for the V3 pipeline. Saves user effort but adds complexity: bot hosting, channel permissions, mapping Discord user → app user. Already have a planned `gather_discord_images` background job. Medium-high complexity — needs Discord bot setup + user linking.

### Listing Status Behavior

DB column exists (`status`: 0=draft, 1=listed, 2=sold, 3=deleted). Remaining work is status-driven behavior:
- **Draft**: editable (modify item details, re-upload image), not visible in marketplace search
- **Listed**: publicly searchable, read-only (no edits)
- **Sold**: archived, shown in seller history, not searchable
- **Deleted**: soft-deleted, hidden from all public views, visible in admin

**Done:**
- [x] Filter marketplace queries by `status = 1` (listed only)
- [x] Status transition API (`PATCH /listings/{id}/status`)

**Remaining:**
- [ ] Draft editing flow in frontend (My Listings → edit draft → publish)
- [ ] Admin: show all statuses with filter

### Background Jobs (Extended)

Expand the existing job system:
- **gather_discord_images** — already planned, see above
- **recommendation data creation** — build TF-IDF vectors / similarity matrices from activity logs
- **horn bugle collect** — fetch in-game megaphone chat every ~2 min for market price signals

**Evaluation:** Already have job infrastructure (`backend/jobs/`, `job_runs` table, admin Jobs tab). Discord + recommendation are one-shot jobs triggered manually or on schedule. Horn bugle needs periodic scheduling (APScheduler). The jobs themselves are independent — can be built incrementally.

### Tagging System Documentation

Document the tagging system for internal reference:
- Tag creation flow (user tags vs auto tags)
- Weight system (tag weight + positional weight)
- Multi-target resolution (CTE: listing → game_item → options → enchants)
- Search behavior (cascading tiers, intersection)
- Admin management (bulk create, weight editing, legends)

**Evaluation:** Pure documentation task. The system is already built — this is about writing it down for onboarding and maintenance. Can reference the code walkthrough from this conversation.

### Set Item: Show Rolled Value

Currently `set_item` section only shows existence in `item_name`. Should show actual rolled/computed values for set bonuses (e.g. `최종 대미지 증가 +5`).

**Evaluation:** Requires OCR pipeline changes — `SetItemHandler` currently uses `@filter_prefix('bullet')` + FM against set names, but doesn't extract numeric values. Need to:
1. Parse the numeric suffix from FM-corrected text (e.g. `최종대미지(강화) +5`)
2. Store as `rolled_value` in listing_options
3. Display in frontend set_item section with level badge

Medium complexity — touches pipeline handler, listing creation, and frontend display.

---

## Infrastructure

### Completed
- [x] **Docker image split** — `mabi-base` replaced by `mabi-backend` (slim, ~30s build) + `mabi-worker` (full ML deps, ~15min ARM64 build). Backend rebuilds no longer blocked by PyTorch compilation.
- [x] **OCR models + data in Docker image** — `mabi-ocr-models` bundles models, dictionary, source_of_truth, fonts. `infra/ocr-models/build.sh` stages everything.
- [x] **rclone image transfer** — `scripts/ocr/sync-image.sh` uploads/downloads Docker images via Google Drive. Replaces manual rclone commands.
- [x] **Data extraction from Docker** — `docker create mabi-ocr-models true` + `docker cp` extracts data to server. No more rsync for data files.
- [x] **Training data cleanup** — `scripts/ocr/cleanup-train-data.sh` removes train_data/train_data_lmdb from inactive model versions (~1.2GB freed). Dry run by default, `--force` to delete.
- [x] **Nginx security** — Block `.php/.cgi/.asp/.aspx` vulnerability scanner probes with `return 444` in `infra/nginx/stg.conf`
- [x] **Redis localhost binding** — Staging Redis bound to `127.0.0.1:6379` (was `0.0.0.0`). Remote workers use SSH tunnel.
- [x] **Credential cleanup** — Removed hardcoded server IP from `documents/DEPLOY.md` and `documents/ARCHITECTURE.md`

### Replace `sys.path` hacks with `PROJECT_ROOT` env var
(See Backend section above — affects both backend and scripts infrastructure.)

### pg_trgm for ILIKE Search Optimization

**Trigger:** When slow queries are observed on listing search (ILIKE `%keyword%`).

**Problem:** `ILIKE '%keyword%'` performs a full sequential scan — B-tree indexes only help prefix matches (`LIKE 'keyword%'`). As the `listings` table grows, search queries on `listings.name` will degrade linearly.

**Solution:** PostgreSQL's `pg_trgm` extension with a GIN index:

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_listings_name_trgm ON listings USING GIN (name gin_trgm_ops);
```

After this, `ILIKE '%keyword%'` automatically uses the trigram index — **no application code changes needed**. The planner picks the GIN index over a sequential scan when it's faster.

**How it works:** `pg_trgm` decomposes text into 3-character subsequences (trigrams). For `"검색"`, trigrams are `"  검"`, `" 검색"`, `"검색 "`. The GIN index maps each trigram to the rows containing it. On query, PostgreSQL intersects the trigram posting lists to find candidate rows, then verifies with the full pattern.

**Korean text note:** Korean characters are multi-byte but `pg_trgm` operates on characters (not bytes), so trigrams work correctly for Korean. Short keywords (1-2 chars) produce fewer trigrams and may fall back to sequential scan — this is expected and acceptable.

**When to implement:** Monitor query performance via `pg_stat_statements` or application-level logging. When median search latency exceeds acceptable thresholds (e.g. >100ms), enable this. Current table size does not warrant it.

---

## Marketplace Search — Architecture & Future Design

### Completed: Search Architecture (2026-03-11)

#### Frontend Search Flow (`useListingSearch` hook)

User types in `ListingSearchBar` → debounced `fetchSuggestions()` fires 3 parallel lookups:
1. **Tags** — `GET /tags/search?q=...` (backend cascading ILIKE)
2. **Game items** — `searchGameItemsLocal()` (in-memory from `window.GAME_ITEMS_CONFIG`, no API, capped at 3)
3. **Listings** — `GET /listings/search?q=...` (backend text search)

Results merged into a single suggestion dropdown with type-specific renderers:
- `TagSuggestion` — `TagBadge` chip with weight color
- `GameItemSuggestion` — orange `Package` icon + name
- `ListingSuggestion` — name + game item label + tag badges

On selection:
- **Tag** → added as a chip (AND filter), triggers `executeSearch` with all selected tags
- **Game item** → added as orange chip (AND filter), triggers `executeSearch` with `gameItemId`
- **Listing** → navigates directly to listing detail

Chips removable by: X button click, or Backspace on empty input (tags first, then game item).

#### Backend Search Logic (`listing_service.py::search_listings`)

Three independent AND-intersected filter sets:

1. **Tag filter** (`_search_by_exact_tags`):
   - Uses `_LISTING_RESOLVE_CTE` to map tags → listings through polymorphic relations
   - CTE resolves: `listing_tags` (direct) + `game_item_tags` (via `listings.game_item_id`) + `listing_option_tags` (via `listing_options`)
   - AND intersection: `HAVING COUNT(DISTINCT tag_id) = :tag_count` ensures all tags match

2. **Text filter** (cascading 3-tier ILIKE):
   - Tier 1: Tag name ILIKE → resolve to listings via CTE
   - Tier 2: Game item name ILIKE → `listings.game_item_id`
   - Tier 3: Listing name ILIKE → direct match
   - Stops at first tier that returns results

3. **Game item filter**: `WHERE game_item_id = :gi` direct match

Final: `id_sets[0] & id_sets[1] & ...` Python set intersection across all non-empty filter sets.

#### CTE (`_LISTING_RESOLVE_CTE`)

```sql
WITH listing_resolve AS (
    SELECT listing_id, tag_id FROM listing_tags
    UNION ALL
    SELECT l.id, gt.tag_id FROM listings l JOIN game_item_tags gt ON gt.game_item_id = l.game_item_id
    UNION ALL
    SELECT lo.listing_id, ot.tag_id FROM listing_options lo JOIN listing_option_tags ot ON ot.listing_option_id = lo.id
)
```

Adding a new entity relation to listings requires only adding one more `UNION ALL` line.

#### Files Changed
- `backend/trade/services/listing_service.py` — `id_sets` refactor, `game_item_id` filter
- `backend/trade/listings.py` — `game_item_id` query param, `BackgroundTasks` for logging
- `frontend/packages/shared/src/hooks/useListingSearch.js` — game item state, handlers, Backspace removal
- `frontend/packages/shared/src/components/ListingSearchBar.jsx` — `GameItemSuggestion`, orange chip, renderers
- `frontend/packages/shared/src/api/recommend.js` — `gameItemId` param
- `frontend/packages/trade/src/pages/marketplace.jsx` — `gameItemId` in search state + pagination
- `documents/ARCHITECTURE.md` — Marketplace Search section
- `documents/API_SPEC.md` — `GET /listings/search`, `GET /tags/search` specs

### Completed: Activity Logs Monitoring (2026-03-11)

- Admin page at `/system/activity_logs` showing paginated activity logs with action/user_id filters
- Backend: `GET /admin/activity-logs` (paginated, filterable), `GET /admin/activity-logs/actions` (distinct actions with counts)
- Activity logging moved to `BackgroundTasks` — own `SessionLocal()` session, doesn't block HTTP response
- Files: `backend/admin/activity.py`, `backend/trade/services/activity_service.py`, `frontend/packages/admin/src/components/ActivityLogsPanel.jsx`

### Completed: UI Polish (2026-03-11)

- `cursor-default` on tag and game item chips, `cursor-pointer` on their X remove buttons
- `TagBadge.jsx`: `cursor-pointer` on remove button, `cursor-default`/`cursor-pointer` on span based on `onClick` prop
- `ListingSearchBar.jsx`: game item chip uses `cursor-default`, X button uses `cursor-pointer`

### Design Decision: Numeric Range Filters vs Tag System

#### Tag System (current — name-based search)
- Works well for **enchant names**, **option names**, **game item names** — any name-based entity
- Admin controls searchability via tag weight (weight 0 = hidden, weight > 0 = searchable)
- Auto-tagging at listing creation generates tags for enchants, options, etc.
- No code deploy needed to make new tags searchable — just bump weight in admin
- Example: enchant "크리티컬" tag → finds all listings with that enchant

#### Limitation: Numeric Values
- Tag system cannot express ranges like "erg level >= 50" or "special upgrade >= 7"
- Game thresholds change unpredictably (erg max level may increase to 60, special upgrade to 9)
- Hardcoding thresholds into tags (e.g. "high rolled erg") requires code updates when limits change

#### Future: Direct Numeric Input for Attributes
- For numeric attributes (erg level, special upgrade, rolled values), let users specify ranges directly
- Approach: when user selects a game item chip, expand to a form showing relevant numeric fields
  - Essential fields derived from `listings` columns + `item_attrs` segment handler
  - Echostone/murias options appear only for eligible items (from frontend constants)
  - User fills desired minimums → backend adds WHERE clauses to search query

#### CTE Compatibility
- CTE stays unchanged — it resolves tag-to-listing relationships (name-based)
- Numeric range filters are independent WHERE clauses on `listing_options` or `listings` columns
- Both can coexist: tag intersection + numeric range filters in the same query

#### Rolled Value Tiers (existing UI concept)
- Frontend already uses `getLevelBadge()` to color-code rolled values: `transcend` / `max` / `high` / `mid` / `low`
- This tier visualization could double as a search filter — "show me max-rolled listings"
- The tier boundaries are game-knowledge-specific and may need admin configurability rather than hardcoded thresholds
