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

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `file` | `File` (Binary) | Yes | Original color screenshot of the item tooltip. |

**Response:** `{ "job_id": "uuid" }`

The backend uploads the image to file storage and enqueues a `run_v3_pipeline` job on the `gpu` queue. The web server does NOT run the pipeline — a worker process handles it.

### SSE Stream

**Endpoint:** `GET /examine-item/{job_id}/stream`
**Content-Type:** `text/event-stream`

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

### Request Body
```json
{
  "session_id": "abc123",
  "name": "Dragon Blade",
  "price": "50000",
  "category": "weapon",
  "game_item_id": 1234,
  "item_type": "양손 검",
  "item_grade": "에픽",
  "erg_grade": "S",
  "erg_level": 25,
  "lines": [
    { "line_index": 0, "text": "Dragon Blade" },
    { "line_index": 2, "text": "공격 15~30" }
  ],
  "enchants": [
    {
      "slot": 0,
      "name": "충격을",
      "rank": "F",
      "effects": [
        { "text": "최대대미지 5 증가", "option_name": "최대대미지", "option_level": 5 }
      ]
    }
  ],
  "reforge_options": [
    {
      "name": "스매시 대미지",
      "reforge_option_id": 42,
      "level": 15,
      "max_level": 20
    }
  ]
}
```

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `session_id` | `string` | No | Session ID from `/examine-item`. Enables correction capture. |
| `name` | `string` | No | User-editable listing display name. |
| `price` | `string` | No | Price string. |
| `category` | `string` | No | Category. Default `weapon`. |
| `game_item_id` | `int` | No | FK to `game_items`. Resolved from static config on the client. Falls back to name match on server. |
| `item_type` | `string` | No | Equipment type, e.g. `양손 검`, `경갑옷`. Extracted from OCR `item_type` section. |
| `item_grade` | `string` | No | Item grade, e.g. `에픽`, `레어`. Extracted from OCR `item_grade` section. |
| `erg_grade` | `string` | No | ERG grade letter, e.g. `S`, `A`. Extracted from OCR `erg` section. |
| `erg_level` | `int` | No | ERG level number, e.g. `25`. Extracted from OCR `erg` section. |
| `lines` | `array` | No | Final line texts. Each has `section` (string), `line_index` (int), and `text` (string). Lines where `text` differs from the original OCR are saved as correction training data. |
| `enchants` | `array` | No | Structured enchant data per slot. Each has `slot` (0=prefix, 1=suffix), `name`, `rank`, `effects[]`. |
| `reforge_options` | `array` | No | Structured reforge options. Each has `name`, optional `reforge_option_id` (from static config), `level`, `max_level`. |

### Response
```json
{
  "registered": true,
  "name": "Dragon Blade",
  "listing_id": 7,
  "corrections_saved": 2
}
```

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
  "reforge_options": [
    { "option_name": "스매시 대미지", "level": 15, "max_level": 20 }
  ]
}
```

#### Enchant effect display logic
- `value` is non-null only for rolled (ranged) effects stored in `listing_enchant_effects`
- `value` is null for fixed effects where `min_value == max_value` — the client displays `min_value` as the fixed value
- All effects are returned (via LEFT JOIN from `enchant_effects`), not just rolled ones

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
