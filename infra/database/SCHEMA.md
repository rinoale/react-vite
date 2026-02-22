# Enchant Database Schema Design

## Context

Mabinogi enchant system: each enchant scroll has a fixed set of effects, but some effects roll a random value within a range when applied to an item. The marketplace needs to store both the **definitions** (what an enchant *can* do) and the **instances** (what an enchant *actually rolled* on a specific item).

Source data: `data/source_of_truth/enchant.yaml` (1,168 enchants, 4,934 effect lines) and `data/source_of_truth/effects.txt` (68 unique effect names).

## Table Overview

```
enchants              1 ──< enchant_effects >── 1  effects
                                  │
                                  │ (definition)
                                  │
items 1 ──< item_enchants >── 1 enchants
  │
  └──< item_enchant_effects >── 1 enchant_effects
         (rolled values)
```

**Definition tables** (populated from yaml/txt, read-only after import):
- `enchants` — 1,168 enchant scrolls
- `effects` — 68 unique effect names
- `enchant_effects` — 4,934 links (what effects each enchant has)

**Instance tables** (populated from OCR'd item screenshots):
- `items` — user-registered items
- `item_enchants` — which enchant is applied to an item (max one prefix + one suffix)
- `item_enchant_effects` — actual rolled values per effect

**Standalone:**
- `reforge_options` — 527 reforge option names

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

The `item_enchant_effects.value` stores the actual rolled number within `[min_value, max_value]`.

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

### One prefix + one suffix per item

`item_enchants` has `UNIQUE (item_id, slot)` — an item can have at most one prefix (slot=0) and one suffix (slot=1) enchant, matching the game rule.

## Import Pipeline

```bash
# Source files
data/source_of_truth/effects.txt    →  effects table (68 rows)
data/source_of_truth/enchant.yaml   →  enchants + enchant_effects tables
data/dictionary/reforge.txt         →  reforge_options table (527 rows)

# Command
python3 scripts/db/import_dictionaries.py
```

Import is idempotent (upsert on unique keys, effects deleted and re-inserted per enchant).

## Current Counts

| Table | Rows |
|-------|------|
| `enchants` | 1,168 |
| `effects` | 68 |
| `enchant_effects` | 4,934 |
| `reforge_options` | 527 |

Of the 4,934 effect lines:
- **3,537** matched to an effect name with signed values
- **836** of those have ranged values (min != max)
- **1,397** are restrictions/flags (effect_id = NULL)
- **7** valued lines unmatched due to edge-case patterns (unit suffixes like `2초`, composite names); preserved in `raw_text`

## Schema Migration (old → new)

| Old Table | New Table |
|-----------|-----------|
| `enchant_entries` | `enchants` |
| `enchant_effects` | `effects` |
| `enchant_entry_effect_links` | `enchant_effects` |

Dropped columns: `effect_direction`, `normalized_text`. Added columns: `min_value`, `max_value`, `is_pct`. New tables: `items`, `item_enchants`, `item_enchant_effects`.
