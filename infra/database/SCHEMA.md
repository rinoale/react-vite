# Database Schema Design

## Context

Mabinogi enchant system: each enchant scroll has a fixed set of effects, but some effects roll a random value within a range when applied to an item. The marketplace needs to store both the **definitions** (what an enchant *can* do) and the **instances** (what an enchant *actually rolled* on a specific listing).

Source data: `data/source_of_truth/enchant.yaml` (1,168 enchants, 4,934 effect lines) and `data/source_of_truth/effects.txt` (68 unique effect names).

## Table Overview

```
enchants              1 ──< enchant_effects >── 1  effects
   │                           │
   │ (definition)              │ (definition)
   │                           │
listings ──< prefix/suffix FK  │
   │                           │
   └──< listing_enchant_effects >── 1 enchant_effects
   │       (rolled values)
   │
   └──< listing_reforge_options >── 1 reforge_options
   │       (rolled level/max_level)
   │
   └── 1 game_items (FK)
```

**Definition tables** (populated from yaml/txt, read-only after import):
- `enchants` — 1,168 enchant scrolls
- `effects` — 68 unique effect names
- `enchant_effects` — 4,934 links (what effects each enchant has)
- `reforge_options` — 527 reforge option names
- `game_items` — ~20K game item names (from `item_name.txt`)

**Instance tables** (populated from OCR'd item registration):
- `listings` — user-registered items for sale
- `listing_enchant_effects` — actual rolled values per effect
- `listing_reforge_options` — reforge options with rolled level/max_level

**Standalone:**
- `ocr_corrections` — user-submitted OCR correction training data

## Listings Table

```sql
listings (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,                    -- user-editable listing display name
  game_item_id  INTEGER FK → game_items, -- canonical game item (nullable)
  prefix_enchant_id INTEGER FK → enchants, -- direct FK, no join table
  suffix_enchant_id INTEGER FK → enchants, -- direct FK, no join table
  item_type TEXT,                         -- e.g. "양손 검", "경갑옷"
  item_grade TEXT,                        -- e.g. "에픽", "레어"
  erg_grade TEXT,                          -- e.g. "S", "A"
  erg_level INTEGER,                      -- e.g. 25
  created_at, updated_at
)
```

### Why direct FK instead of join table for enchants

Rule: **FK only** if the relationship just connects two tables (no extra data) → direct column on `listings`. **Join table** if it also stores rolled values or additional data.

- `prefix_enchant_id` / `suffix_enchant_id` — no rolled data, slot is implicit in column name → **direct FK**
- `listing_enchant_effects` (listing ↔ enchant_effect + rolled `value`) — has rolled data → **keep join table**
- `listing_reforge_options` (listing ↔ reforge_option + rolled `level`, `max_level`) — has rolled data → **keep join table**

## Design Decisions

### Signed values instead of direction column

Old schema had `effect_value` + `effect_direction` (0=증가, 1=감소). New schema uses signed `min_value`/`max_value`.

```
-- Old: value=40, direction=1 (감소)
-- New: min_value=-40, max_value=-40

-- "체력 40 감소"  →  min_value=-40, max_value=-40
-- "마법 공격력 8 ~ 9 증가"  →  min_value=8, max_value=9
```

Advantages: arithmetic works directly (`WHERE min_value > 0`), no need to reconstruct sign from a separate column.

### Ranged values (min/max) instead of single value

Enchant effects can roll within a range when applied. `min_value = max_value` means fixed (no separate `is_fixed` column needed).

```
-- Fixed:  "최대대미지 16 증가"  →  min=16, max=16
-- Ranged: "최대대미지 6 ~ 7 증가"  →  min=6, max=7
```

The `listing_enchant_effects.value` stores the actual rolled number within `[min_value, max_value]`.

### Nullable effect_id for restrictions and flags

Effect lines fall into 4 categories:

| Category | Example | effect_id | min/max_value |
|----------|---------|-----------|---------------|
| Valued effect | `최대대미지 16 증가` | FK to effects | signed values |
| Conditional effect | `썬더 랭크 2 이상일 때 마법 공격력 14 ~ 17 증가` | FK to effects | signed values |
| Equipment restriction | `장신구에 인챈트 가능` | NULL | NULL |
| Flag | `인챈트 장비를 전용으로 만듦` | NULL | NULL |

All four categories live in the same `enchant_effects` table. Restrictions and flags have `effect_id = NULL` and `min_value = NULL`. The `raw_text` column always preserves the original line for display.

### Rank as SMALLINT 1–15

YAML has ranks `'1'`..`'9'` and `'A'`..`'F'`. Stored as integers: 1–9 map directly, A=10, B=11, C=12, D=13, E=14, F=15. This matches the game's internal ordering and allows range queries (`WHERE rank <= 5`).

### Effects table from effects.txt

The 68 unique effect names are maintained in `data/source_of_truth/effects.txt` and imported directly into the `effects` table. The `is_pct` flag is derived from the `(%)` suffix in the name (e.g., `수리비 (%)`, `힐링 효과 (%)`).

During enchant import, each effect line is regex-matched against known effect names. Percentage effects in YAML appear as `수리비 200% 증가` and match to the `수리비 (%)` entry in effects.txt.

### Condition text split

Conditional effects are split at the `때` boundary:

```
"썬더 랭크 2 이상일 때 마법 공격력 14 ~ 17 증가"
  → condition_text: "썬더 랭크 2 이상일 때"
  → effect parsed from: "마법 공격력 14 ~ 17 증가"
```

This enables querying items by condition (e.g., find all enchants that activate with a specific skill rank).

### One prefix + one suffix per listing

`listings` has `prefix_enchant_id` and `suffix_enchant_id` as separate nullable FK columns — a listing can have at most one prefix and one suffix enchant, matching the game rule.

## Import Pipeline

```bash
# Source files
data/source_of_truth/effects.txt    →  effects table (68 rows)
data/source_of_truth/enchant.yaml   →  enchants + enchant_effects tables
data/dictionary/reforge.txt         →  reforge_options table (527 rows)
data/dictionary/item_name.txt       →  game_items table (~20K rows)

# Command
python3 scripts/db/import_dictionaries.py
```

Import is idempotent (upsert on unique keys, effects deleted and re-inserted per enchant).

## Static Frontend Configs

Generated from DB, loaded as `window.*` globals via `<script>` tags. No API calls needed for client-side search/resolution.

```bash
python3 scripts/frontend/configs/export_enchant_config.py      # → window.ENCHANTS_CONFIG [{id, name, slot, rank, effects}]
python3 scripts/frontend/configs/export_reforge_config.py      # → window.REFORGES_CONFIG [{id, option_name}]
python3 scripts/frontend/configs/export_game_items_config.py   # → window.GAME_ITEMS_CONFIG [{id, name}]
```

## Current Counts

| Table | Rows |
|-------|------|
| `enchants` | 1,168 |
| `effects` | 68 |
| `enchant_effects` | 4,934 |
| `reforge_options` | 527 |
| `game_items` | ~20,166 |

Of the 4,934 effect lines:
- **3,537** matched to an effect name with signed values
- **836** of those have ranged values (min != max)
- **1,397** are restrictions/flags (effect_id = NULL)
- **7** valued lines unmatched due to edge-case patterns (unit suffixes like `2초`, composite names); preserved in `raw_text`
