# API Specification (Mabinogi Marketplace)

This document serves as the contract between the Backend AI Agent and the Frontend AI Agent.

## Communication Protocol
- **Frontend Agent Mandate:** Before making significant UI changes dependent on data, consult this document. If a required field is missing, request the Backend Agent to update the specification here first.
- **Backend Agent Mandate:** Any change to endpoint paths, methods, or JSON response structures **MUST** be reflected in this document immediately.

---

## 1. Item Examination (V3 Pipeline)

### Upload

**Endpoint:** `POST /examine-item`
**Content-Type:** `multipart/form-data`
**Auth:** Required (signed-in users only)

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `file` | `File` (Binary) | Yes | Original color screenshot of the item tooltip. |

**Response:** `{ "job_id": "uuid" }`

The backend uploads the image to file storage and enqueues a `run_v3_pipeline` job on the `gpu` queue. The web server does NOT run the pipeline — a worker process handles it.

### SSE Stream

**Endpoint:** `GET /examine-item/{job_id}/stream`
**Content-Type:** `text/event-stream`
**Auth:** Required (signed-in users only)

Subscribes to Redis pub/sub for pipeline progress and result. Events:

| Event | Data | Description |
| :--- | :--- | :--- |
| `progress` | `{ "step": "..." }` | Pipeline progress update |
| `result` | `ExamineItemResponse` | Final OCR result (see below) |
| `error` | `{ "message": "..." }` | Pipeline failure |

### Response Structure (JSON)
The response follows a "Section-First" architecture. Internal pipeline fields (`bounds`, `ocr_model`, `fm_applied`, `section`, `sub_lines`, etc.) are stripped — the frontend receives only the fields it needs.

**FM Decision:** The server applies fuzzy matching (FM) against section-specific dictionaries.
If a match is found, `text` is silently replaced with the FM result.
The frontend should always read `text` directly — it is the best available value.

```json
{
  "filename": "item_screenshot.png",
  "session_id": "abc123",
  "sections": {
    "item_name": {
      "text": "Dragon Blade",
      "lines": [
        { "text": "Dragon Blade", "confidence": 0.99, "is_header": true, "line_index": 0 }
      ]
    },
    "item_attrs": {
      "lines": [
        { "text": "공격 15~30", "confidence": 0.85, "line_index": 2 },
        { "text": "부상률 0~10%", "confidence": 0.92, "line_index": 3 }
      ]
    },
    "enchant": {
      "prefix": {
        "text": "[접두] 충격을 (랭크 F)",
        "name": "충격을",
        "rank": "F",
        "effects": [
          { "text": "최대대미지 5 증가", "option_name": "최대대미지", "option_level": 5 },
          { "text": "활성화된 아르카나의 전용 옵션일 때 효과 발동" }
        ]
      },
      "suffix": null,
      "lines": [
        { "text": "[접두] 충격을 (랭크 F)", "confidence": 0.95, "line_index": 10 },
        { "text": "최대대미지 5 증가", "confidence": 0.88, "line_index": 11 }
      ]
    },
    "reforge": {
      "options": [
        {
          "name": "스매시 대미지",
          "level": 15,
          "max_level": 20,
          "effect": "대미지 150% 증가"
        }
      ],
      "lines": [
        { "text": "스매시 대미지 15 (Max 20)", "confidence": 0.90, "line_index": 15 }
      ]
    },
    "item_mod": {
      "has_special_upgrade": true,
      "special_upgrade_type": "R",
      "special_upgrade_level": 7,
      "lines": [
        { "text": "특별 개조 R (7단계)", "confidence": 0.85, "line_index": 0 }
      ]
    },
    "erg": {
      "erg_grade": "S",
      "erg_level": 50,
      "erg_max_level": 50,
      "lines": [
        { "text": "등급 S (50/50 레벨)", "confidence": 0.90, "line_index": 0 }
      ]
    },
    "set_item": {
      "set_effects": [
        { "set_name": "스매시 강화", "set_level": 7 },
        { "set_name": "윈드밀 강화", "set_level": 6 }
      ],
      "lines": [
        { "text": "스매시 강화 +7", "confidence": 0.89, "line_index": 0 },
        { "text": "윈드밀 강화 +6", "confidence": 0.73, "line_index": 1 }
      ]
    },
    "item_color": {
      "parts": [
        { "part": "A", "r": 255, "g": 255, "b": 255 }
      ]
    },
    "flavor_text": {
      "skipped": true
    }
  },
  "tagged_segments": [...],
  "abbreviated": false
}
```

#### Section Keys
`pre_header`, `item_name`, `item_type`, `item_grade`, `item_attrs`, `enchant`, `item_mod`, `reforge`, `erg`, `set_item`, `item_color`, `ego`, `flavor_text`, `shop_price`.

#### Line Object Properties
| Property | Type | Present | Description |
| :--- | :--- | :--- | :--- |
| `text` | `string` | Always | Best available text (FM-corrected if matched, otherwise raw OCR). |
| `confidence` | `float` | Always | OCR confidence (0.0 to 1.0), rounded to 4 decimal places. |
| `line_index` | `int` | Always | 0-based position within the section's lines[]. Sent back with `section` in `/register-listing` for correction mapping. |

#### Section Object Properties
All sections contain `lines` (array of Line objects) unless `skipped: true`.

| Property | Type | Sections | Description |
| :--- | :--- | :--- | :--- |
| `lines` | `Line[]` | All (unless skipped) | Editable text lines for the section. |
| `text` | `string` | `item_name`, `item_type`, `pre_header` | Section-level summary text. |
| `prefix` | `object\|null` | `enchant` | Structured prefix enchant (`name`, `rank`, `effects[]`). |
| `suffix` | `object\|null` | `enchant` | Structured suffix enchant (`name`, `rank`, `effects[]`). |
| `options` | `object[]` | `reforge` | Structured reforge options (`name`, `level`, `max_level`, `effect`). |
| `has_special_upgrade` | `boolean` | `item_mod` | `true` when a pink special upgrade line is detected. |
| `special_upgrade_type` | `string\|null` | `item_mod` | `R` or `S`. `null` when detected but OCR failed. |
| `special_upgrade_level` | `int\|null` | `item_mod` | Level 1-8. `null` when detected but OCR failed. |
| `erg_grade` | `string\|null` | `erg` | `S`, `A`, or `B`. |
| `erg_level` | `int\|null` | `erg` | Current erg level (1-50). |
| `erg_max_level` | `int\|null` | `erg` | Maximum erg level (1-50). |
| `set_effects` | `object[]` | `set_item` | Set effects (`set_name`, `set_level`). |
| `parts` | `object[]` | `item_color` | Color parts (`part`, `r`, `g`, `b`). |
| `skipped` | `boolean` | `flavor_text`, `shop_price` | `true` when the section is intentionally omitted. |

#### EnchantSlotResponse (`prefix` / `suffix`)
| Property | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `text` | `string` | Yes | Header text, e.g. `[접두] 충격을 (랭크 F)`. |
| `name` | `string` | Yes | Enchant name, e.g. `충격을`. |
| `rank` | `string` | Yes | Rank label, e.g. `F`, `9`, `A`. |
| `effects` | `EnchantEffectResponse[]` | Yes | List of effect lines. |

#### EnchantEffectResponse (each element in `effects`)
| Property | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `text` | `string` | Yes | Full effect text, e.g. `최대대미지 5 증가`. |
| `option_name` | `string` | No | Extracted option name, e.g. `최대대미지`. Absent for non-numeric effects. |
| `option_level` | `int\|float` | No | Extracted numeric value, e.g. `5`. Absent for non-numeric effects. |

#### ReforgeOptionResponse (each element in `options`)
| Property | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `name` | `string` | Yes | Option name, e.g. `스매시 대미지`. |
| `level` | `int` | Yes | Current level, e.g. `15`. |
| `max_level` | `int` | Yes | Maximum level, e.g. `20`. |
| `effect` | `string` | No | Effect description, e.g. `대미지 150% 증가`. |

#### ColorPartResponse (each element in `parts`)
| Property | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `part` | `string` | Yes | Part label (`A`-`F`). |
| `r` | `int` | No | Red channel (0-255). |
| `g` | `int` | No | Green channel (0-255). |
| `b` | `int` | No | Blue channel (0-255). |

---

## 1b. Item Registration

**Endpoint:** `/register-listing`
**Method:** `POST`
**Content-Type:** `application/json`

> **Convention:** All entity IDs for source-of-truth data (enchants, effects, reforge options, etc.) are pre-assigned in `data/source_of_truth/*.yaml` and exported to frontend config files. The frontend sends these IDs directly — the backend never resolves IDs by name for static entities. See [ARCHITECTURE.md § Source of Truth: Pre-Assigned IDs](ARCHITECTURE.md) for details.

### Request Body
```json
{
  "session_id": "abc123",
  "name": "Dragon Blade",
  "description": "설명",
  "price": "50000",
  "category": "weapon",
  "game_item_id": "019c...",
  "item_type": "양손 검",
  "item_grade": "에픽",
  "erg_grade": "S",
  "erg_level": 25,
  "special_upgrade_type": "R",
  "special_upgrade_level": 7,
  "attrs": { "damage": "15~30", "balance": "40" },
  "lines": [
    { "section": "item_attrs", "line_index": 0, "text": "공격 15~30" },
    { "section": "enchant", "line_index": 2, "text": "최대대미지 5 증가" }
  ],
  "enchants": [
    {
      "id": "019c...",
      "slot": 0,
      "name": "충격을",
      "rank": "F"
    }
  ],
  "listing_options": [
    {
      "option_type": "enchant_effects",
      "option_name": "최대대미지",
      "option_id": "019ce59d-a63d-...",
      "rolled_value": 5
    },
    {
      "option_type": "reforge_options",
      "option_name": "스매시 대미지",
      "option_id": "019c...",
      "rolled_value": 15,
      "max_level": 20
    }
  ],
  "tags": ["풀피어싱", "S르그50"]
}
```

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `session_id` | `string` | No | Session ID from `/examine-item`. Enables correction capture. |
| `name` | `string` | No | User-editable listing display name. |
| `description` | `string` | No | Short description (max 50 chars). HTML tags stripped. |
| `price` | `string` | No | Price string. |
| `category` | `string` | No | Category. Default `weapon`. |
| `game_item_id` | `UUID` | No | FK to `game_items`. Resolved from static config on the client. |
| `item_type` | `string` | No | Equipment type, e.g. `양손 검`, `경갑옷`. From OCR `item_type` section. |
| `item_grade` | `string` | No | Item grade, e.g. `에픽`, `레어`. From OCR `item_grade` section. |
| `erg_grade` | `string` | No | ERG grade letter, e.g. `S`, `A`. From OCR `erg` section. |
| `erg_level` | `int` | No | ERG level number, e.g. `25`. From OCR `erg` section. |
| `special_upgrade_type` | `string` | No | `R` or `S`. From OCR `item_mod` section. |
| `special_upgrade_level` | `int` | No | Level 1-8. From OCR `item_mod` section. |
| `attrs` | `dict` | No | Structured key-value pairs from `item_attrs` section. |
| `lines` | `array` | No | Final line texts. Each has `section`, `line_index`, `text`. Lines differing from original OCR are saved as correction training data. |
| `enchants` | `array` | No | Enchant slots. See `RegisterEnchantSlot` below. |
| `listing_options` | `array` | No | Unified options (all types). See `RegisterListingOption` below. |
| `tags` | `string[]` | No | User-assigned tags (max 3, each max 5 chars). |

#### RegisterEnchantSlot (each element in `enchants`)
| Property | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | Yes | Enchant PK from `enchants` table. Resolved from frontend config (`window.ENCHANTS_CONFIG`). |
| `slot` | `int` | Yes | `0` = prefix, `1` = suffix. |
| `name` | `string` | Yes | Enchant name (display/auto-tagging). |
| `rank` | `string` | Yes | Rank label (display). |

#### RegisterListingOption (each element in `listing_options`)

Polymorphic option entry. All option types use the same shape — `option_id` points to the source table's PK.

| Property | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `option_type` | `string` | Yes | Discriminator: `enchant_effects`, `reforge_options`, `echostone_options`, `murias_relic_options`. |
| `option_name` | `string` | Yes | Display name (denormalized). Avoids polymorphic JOIN for display. |
| `option_id` | `UUID` | Yes | Source table PK from frontend config. `enchant_effects.id` for enchant effects, `reforge_options.id` for reforge, etc. |
| `rolled_value` | `int\|float` | No | User's rolled/selected value. |
| `max_level` | `int` | No | Maximum possible level (for reforge/echostone/murias). |

### Response
```json
{
  "registered": true,
  "name": "Dragon Blade",
  "listing_id": 7,
  "short_code": "abc123",
  "corrections_saved": 2
}
```

> **Note:** `create_listing_tags` (user tags + auto tags) runs as a background task and does not block the response. Tags are available shortly after registration completes.

---

## 1c. Listings

### `GET /listings`
Returns all listings, optionally filtered by game item.

**Query params:**

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `game_item_id` | `int` | (none) | Filter by game item FK. |

**Response:** `Array<ListingOut>`
```json
[
  {
    "id": 7,
    "name": "Dragon Blade",
    "game_item_id": 1234,
    "game_item_name": "드래곤 블레이드",
    "prefix_enchant_name": "충격을",
    "suffix_enchant_name": null,
    "item_type": "양손 검",
    "item_grade": "에픽",
    "erg_grade": "S",
    "erg_level": 25,
    "seller_verified": false,
    "created_at": "2026-02-26T12:00:00+00:00",
    "reforge_count": 3
  }
]
```

### `GET /listings/{listing_id}`
Returns full detail for a single listing, including enchant effects and reforge options.

**Response:** `ListingDetailOut`
```json
{
  "id": 7,
  "name": "Dragon Blade",
  "game_item_id": 1234,
  "game_item_name": "드래곤 블레이드",
  "item_type": "양손 검",
  "item_grade": "에픽",
  "erg_grade": "S",
  "erg_level": 25,
  "seller_verified": false,
  "prefix_enchant": {
    "slot": 0,
    "enchant_name": "충격을",
    "rank": 15,
    "effects": [
      { "raw_text": "최대대미지 16 증가", "min_value": 14, "max_value": 17, "value": 16 },
      { "raw_text": "체력 40 감소", "min_value": -40, "max_value": -40, "value": null }
    ]
  },
  "suffix_enchant": null,
  "listing_options": [
    { "option_type": "reforge_options", "option_name": "스매시 대미지", "rolled_value": 15, "max_level": 20 },
    { "option_type": "echostone_options", "option_name": "최대대미지", "rolled_value": 8, "max_level": 10 }
  ]
}
```

#### Enchant effect display logic
- `value` is non-null only for rolled (ranged) effects stored in `listing_enchant_effects`
- `value` is null for fixed effects where `min_value == max_value` — the client displays `min_value` as the fixed value
- All effects are returned (via LEFT JOIN from `enchant_effects`), not just rolled ones

### `GET /listings/search`
Search listings by text query, tag chips, and/or game item. All provided filters are intersected (AND).

**Query params:**

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `q` | `string` | `""` | Text query. Triggers cascading ILIKE search (see below). |
| `tags` | `string[]` | `[]` | Tag names. Multiple values = AND (all must match). |
| `game_item_id` | `int` | (none) | Exact game item filter. |
| `reforge_filters` | `string` (JSON) | (none) | JSON array of reforge option filters. Format: `[{"id": "uuid", "op": "gte\|lte\|eq", "level": int\|null}]`. `level=null` means existence-only. |
| `enchant_filters` | `string` (JSON) | (none) | JSON array of enchant filters. Format: `[{"id": "uuid", "effects": [{"enchant_id": "uuid", "effect_order": int, "op": "gte\|lte\|eq", "value": int}]}]`. |
| `echostone_filters` | `string` (JSON) | (none) | JSON array of echostone option filters. Same format as `reforge_filters`. |
| `murias_filters` | `string` (JSON) | (none) | JSON array of murias relic option filters. Same format as `reforge_filters`. |
| `min_{col}` | `int` | (none) | Numeric minimum filter. Supported columns: `damage`, `magic_damage`, `additional_damage`, `balance`, `defense`, `protection`, `magic_defense`, `magic_protection`, `durability`, `special_upgrade_level`, `erg_level`, `piercing_level`. |
| `max_{col}` | `int` | (none) | Numeric maximum filter. Same columns as `min_{col}`. |
| `eq_{col}` | `int` | (none) | Numeric exact match filter. Same columns as `min_{col}`. |
| `erg_grade` | `string` | (none) | String equality filter (`S`, `A`, `B`). |
| `special_upgrade_type` | `string` | (none) | String equality filter (`R`, `S`). |
| `limit` | `int` | `50` | Max results (1-200). |
| `offset` | `int` | `0` | Pagination offset. |

**Search logic:**

Three independent filters are computed, then **intersected** (`∩`):

1. **Tag filter** (`tags` param) — Exact match on `tags.name`, AND across all selected tags. Uses a CTE to resolve listings to all related entities (game_item, enchants, listing_options), so a tag on an enchant matches listings with that enchant.
   ```sql
   WHERE t.name IN (:tags) GROUP BY listing_id HAVING COUNT(DISTINCT t.name) = :tag_count
   ```

2. **Text filter** (`q` param) — Cascading 3-tier search, stops at first tier with results:
   - Tier 1: `tags.name ILIKE '%q%'` → resolve to listing IDs via CTE (same polymorphic tag resolution)
   - Tier 2: `game_items.name ILIKE '%q%'` → direct JOIN to listings (no CTE)
   - Tier 3: `listings.name ILIKE '%q%'` → direct WHERE (no CTE)

3. **Game item filter** (`game_item_id` param) — Direct exact match (no CTE):
   ```sql
   WHERE status = 1 AND game_item_id = :gi
   ```

When no filters are provided (`q` empty, no `tags`, no `game_item_id`), falls back to `GET /listings` (returns all listed items).

**Response:** `Array<ListingSummary>` — same structure as `GET /listings`, plus `tags` and `listing_options` arrays.

### `GET /tags/search`
Search tag names by substring. Used for search bar autocomplete.

**Query params:**

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `q` | `string` | `""` | Search query (ILIKE match). |
| `limit` | `int` | `10` | Max results (1-50). |

**Response:** `Array<{name, weight}>`

### `GET /game-items`
Search game items by name substring.

**Query params:**

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `q` | `string` | `""` | Search query (ILIKE match). Empty returns `[]`. |
| `limit` | `int` | `20` | Max results (1-100). |

**Response:** `Array<{id, name}>`

---

## 2. Admin Validation APIs (v2 Schema)

These endpoints provide access to the core enchant and reforge dictionaries.
All responses are validated against Pydantic models.

> **Auth:** All admin endpoints require admin role gate + audit middleware. Admin CRUD operations on audited models are automatically logged to `system_logs` with before/after diffs (see Section 6).

### Communication with Admin UI
- **Base URL:** `/admin`
- **Slot Mapping:** `0` = 접두 (Prefix), `1` = 접미 (Suffix)
- **Rank Mapping:** `1-9` = ranks 1-9, `10` = A, `11` = B, `12` = C, `13` = D, `14` = E, `15` = F

### Endpoints

#### `GET /admin/health`
Checks backend connectivity.
- **Response:** `{ "ok": true }`

#### `GET /admin/summary`
Returns counts for all core entities.
- **Response Structure:**
  ```json
  {
    "enchants": 1168,
    "effects": 68,
    "enchant_effects": 4934,
    "reforge_options": 527,
    "listings": 0,
    "game_items": 20166
  }
  ```

#### `GET /admin/enchant-entries?limit=100&offset=0`
Fetches a paginated list of enchant definitions.
- **Response Structure:**
  ```json
  {
    "limit": 100,
    "offset": 0,
    "rows": [
      {
        "id": 1,
        "slot": 0,
        "name": "강력한",
        "rank": 9,
        "header_text": "[접두] 강력한 (랭크 9)",
        "effect_count": 3
      }
    ]
  }
  ```

#### `GET /admin/enchant-entries/{enchant_id}/effects`
Fetches all effect lines for a specific enchant.
- **Response Structure:** `Array<EnchantEffect>`
  ```json
  [
    {
      "id": 101,
      "enchant_id": 1,
      "effect_id": 5,
      "effect_order": 0,
      "condition_text": "컴뱃 마스터리 랭크 9 이상일 때",
      "min_value": 15,
      "max_value": 20,
      "raw_text": "컴뱃 마스터리 랭크 9 이상일 때 최대대미지 15 ~ 20 증가",
      "enchant_name": "강력한",
      "effect_name": "최대대미지"
    }
  ]
  ```

#### `GET /admin/effects?limit=100&offset=0`
Fetches the master list of unique effect names.
- **Response Structure:**
  ```json
  {
    "limit": 100,
    "offset": 0,
    "rows": [
      { "id": 1, "name": "최대대미지", "is_pct": false },
      { "id": 2, "name": "수리비 (%)", "is_pct": true }
    ]
  }
  ```

#### `GET /admin/links?limit=100&offset=0`
Fetches a paginated list of the full `enchant_effects` link table.
- **Response Structure:** `{ "limit": 100, "offset": 0, "rows": Array<EnchantEffect> }`
- **Note:** For the frontend, it is more efficient to use `/enchant-entries/{id}/effects` when expanding a single row.

#### `GET /admin/reforge-options?limit=100&offset=0`
Fetches the master list of reforge options.
- **Response Structure:**
  ```json
  {
    "limit": 100,
    "offset": 0,
    "rows": [
      { "id": 1, "option_name": "스매시 대미지" }
    ]
  }
  ```

#### `GET /admin/auto-tag-rules?limit=100&offset=0`
Fetches a paginated list of auto-tag rules, ordered by priority.
- **Response Structure:**
  ```json
  {
    "limit": 100,
    "offset": 0,
    "rows": [
      {
        "id": "019c...",
        "name": "S등급 에르그",
        "description": "S등급 에르그 50 태그",
        "rule_type": "erg",
        "enabled": true,
        "priority": 0,
        "config": { "conditions": [...], "tag_template": "S르그{erg_level}" },
        "created_at": "2026-03-01T00:00:00+00:00",
        "updated_at": null
      }
    ]
  }
  ```

#### `POST /admin/auto-tag-rules`
Creates a new auto-tag rule. New rules are created as **disabled by default** (`enabled: false`).
- **Request Body:** `AutoTagRuleCreate`

| Property | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `name` | `string` | Yes | Rule display name. |
| `description` | `string` | No | Optional description. |
| `rule_type` | `string` | Yes | Rule type discriminator. |
| `enabled` | `bool` | No | Default `false`. |
| `priority` | `int` | No | Evaluation order. Default `0`. |
| `config` | `object` | Yes | Rule config (conditions + tag template). |

- **Response:** `AutoTagRuleOut` (the created rule).

#### `PATCH /admin/auto-tag-rules/{rule_id}`
Updates an existing auto-tag rule. Only provided fields are updated.
- **Request Body:** `AutoTagRuleUpdate` — all fields optional (same shape as `AutoTagRuleCreate`).
- **Response:** `AutoTagRuleOut` (the updated rule).
- **Errors:** `404` — Rule not found.

#### `DELETE /admin/auto-tag-rules/{rule_id}`
Deletes an auto-tag rule.
- **Response:** `{ "deleted": true }`
- **Errors:** `404` — Rule not found.

#### `GET /admin/system-logs?source=&action=&limit=50&offset=0`
Fetches paginated system audit logs. See [Section 6](#6-system-logs) for full details.

#### `GET /admin/system-logs/actions`
Returns distinct action names with counts, for filter dropdown population. See [Section 6](#6-system-logs).

### HTML Validation Helper
- **Endpoint:** `/admin/validate`
- **Method:** `GET`
- **Query params:** `tab` (`enchants|effects|enchant_effects|reforge`), `limit`, `offset`
- **Response:** `HTMLResponse` containing a server-rendered table for quick data auditing.

---

## 3. OCR Correction Review APIs

These endpoints allow reviewing and approving user-submitted OCR corrections captured during `/register-listing`.

### Endpoints

#### `GET /admin/corrections/list?status=pending&limit=100&offset=0`
Fetches a paginated list of OCR corrections filtered by status.
- **Query params:**

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `status` | `string` | `pending` | Filter by status (`pending`, `approved`). |
| `limit` | `int` | `100` | Max rows (up to 500). |
| `offset` | `int` | `0` | Pagination offset. |

- **Response Structure:** `Array<CorrectionOut>`
  ```json
  [
    {
      "id": 1,
      "session_id": "d87ab724-30b8-428c-9076-f73155227af5",
      "line_index": 21,
      "original_text": "최대대미지 18 증가",
      "corrected_text": "최대대미지 16 증가",
      "confidence": 0.8159,
      "section": "enchant",
      "ocr_model": "mabinogi_classic",
      "fm_applied": true,
      "status": "pending",
      "image_filename": "021.png",
      "created_at": "2026-02-25T12:00:00+00:00",
      "trained_version": null
    }
  ]
  ```

#### CorrectionOut Properties
| Property | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `id` | `int` | Yes | Correction record ID. |
| `session_id` | `string` | Yes | Session from `/examine-item`. Maps to crop dir `tmp/ocr_crops/{session_id}/`. |
| `line_index` | `int` | Yes | Global line index. Crop image: `{session_id}/{line_index:03d}.png`. |
| `original_text` | `string` | Yes | OCR output text (before user correction). |
| `corrected_text` | `string` | Yes | User-submitted corrected text. |
| `confidence` | `float` | No | OCR confidence of the original recognition. |
| `section` | `string` | No | Section the line belongs to (e.g. `enchant`, `reforge`, `item_attrs`). |
| `ocr_model` | `string` | No | Model that produced the original text (e.g. `mabinogi_classic`, `nanum_gothic_bold`). |
| `fm_applied` | `bool` | Yes | Whether fuzzy matching was applied to the original text. |
| `status` | `string` | Yes | Current status: `pending` or `approved`. |
| `image_filename` | `string` | Yes | Crop image filename (e.g. `021.png`). |
| `created_at` | `datetime` | Yes | Timestamp of correction submission. |
| `trained_version` | `string` | No | Model version this correction was used to train (null if not yet used). |

#### `POST /admin/corrections/approve/{correction_id}`
Approves a pending correction.
- **Path params:** `correction_id` (int) — The correction record ID.
- **Response:**
  ```json
  { "id": 1, "status": "approved" }
  ```
- **Errors:**
  - `404` — Correction not found.
  - `400` — Correction is not in `pending` status.

---

## 4. Usage Monitoring

### `GET /admin/usage/r2`
Returns current-month Cloudflare R2 storage and operation counts vs free tier limits.

**Response:**
```json
{
  "period": "2026-03",
  "storage": {
    "used_bytes": 319024,
    "used_gb": 0.0,
    "limit_gb": 10,
    "pct": 0.0,
    "objects": 2
  },
  "class_a_ops": { "used": 201, "limit": 1000000, "pct": 0.0 },
  "class_b_ops": { "used": 40, "limit": 10000000, "pct": 0.0 }
}
```

### `GET /admin/usage/oci`
Returns current-month OCI cost breakdown by service.

**Response:**
```json
{
  "period": "2026-03",
  "currency": "SGD",
  "total": 0.2847,
  "services": [
    { "service": "Block Storage", "cost": 0.2847, "currency": "SGD" }
  ]
}
```

---

## 5. Authentication & Verification

### `POST /auth/verify/request`
Requests an in-game verification code. The user must speak this code in the horn bugle (all-chat) for a scheduled job to match and verify them.

**Auth:** Required (signed-in users only)

**Request Body:** None

**Response:**
```json
{
  "code": "마트레-482957",
  "expires_at": "2026-03-15T12:30:00+00:00"
}
```

**Errors:**
- `400` — Server and game ID must be set before verification (`server` or `game_id` not configured on the user profile).
- `400` — Already verified.

**Verification flow:**
1. User sets their `server` and `game_id` on their profile.
2. User calls `POST /auth/verify/request` to receive a 6-digit code prefixed with `마트레-` (e.g., `마트레-482957`). Code expires after 30 minutes.
3. User speaks the code in-game via horn bugle (all-chat).
4. Scheduled job `verify_users` polls the Nexon horn bugle API every 20 minutes across 4 servers (`류트`, `만돌린`, `하프`, `울프`). If a pending user's `game_id` (character name) matches a horn bugle message containing their code, the user is marked as `verified=true`.

> **Note:** Verification is optional -- users can use all services without it. Verified users receive a badge displayed on their listings.

> **Note:** Changing `server` or `game_id` on the user profile resets `verified` to `false`.

---

## 6. System Logs

Automatic audit logging for admin/system changes. All admin CRUD operations on audited models are logged via a SQLAlchemy `before_flush` event listener. Each log entry captures the `source`, `action`, `target_type`, `target_id`, and before/after diffs of changed columns.

**Audited models:** `AutoTagRule`, `Tag`, `TagTarget`, `Listing`, `ListingOption`, `GameItem`, `User`, `Role`, `UserRole`, `FeatureFlag`, `RoleFeatureFlag`.

### `GET /admin/system-logs`
Fetches paginated system audit logs with optional source/action filters.

**Auth:** Required (master role)

**Query params:**

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `source` | `string` | `""` | Filter by source (e.g., `admin`). Empty = all sources. |
| `action` | `string` | `""` | Filter by action (e.g., `admin:create`, `admin:update`, `admin:delete`). Empty = all actions. |
| `limit` | `int` | `50` | Max rows (1-200). |
| `offset` | `int` | `0` | Pagination offset. |

**Response:**
```json
{
  "total": 142,
  "limit": 50,
  "offset": 0,
  "rows": [
    {
      "id": "019c...",
      "source": "admin",
      "user_id": "019c...",
      "action": "admin:update",
      "target_type": "auto_tag_rules",
      "target_id": "019c...",
      "before": { "enabled": false },
      "after": { "enabled": true },
      "created_at": "2026-03-15T10:00:00+00:00"
    }
  ]
}
```

### `GET /admin/system-logs/actions`
Returns distinct action names with counts, for populating filter dropdowns.

**Auth:** Required (master role)

**Response:**
```json
[
  { "action": "admin:create", "count": 45 },
  { "action": "admin:update", "count": 82 },
  { "action": "admin:delete", "count": 15 }
]
```
