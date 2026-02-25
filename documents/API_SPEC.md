# API Specification (Mabinogi Marketplace)

This document serves as the contract between the Backend AI Agent and the Frontend AI Agent.

## Communication Protocol
- **Frontend Agent Mandate:** Before making significant UI changes dependent on data, consult this document. If a required field is missing, request the Backend Agent to update the specification here first.
- **Backend Agent Mandate:** Any change to endpoint paths, methods, or JSON response structures **MUST** be reflected in this document immediately.

---

## 1. Item Recognition (V3 Pipeline)

**Endpoint:** `/upload-item-v3`
**Method:** `POST`
**Content-Type:** `multipart/form-data`

### Request Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `file` | `File` (Binary) | Yes | Original color screenshot of the item tooltip. |

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
        { "text": "Dragon Blade", "confidence": 0.99, "is_header": true, "global_index": 0 }
      ]
    },
    "item_attrs": {
      "lines": [
        { "text": "공격 15~30", "confidence": 0.85, "global_index": 2 },
        { "text": "부상률 0~10%", "confidence": 0.92, "global_index": 3 }
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
        { "text": "[접두] 충격을 (랭크 F)", "confidence": 0.95, "global_index": 10 },
        { "text": "최대대미지 5 증가", "confidence": 0.88, "global_index": 11 }
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
        { "text": "스매시 대미지 15 (Max 20)", "confidence": 0.90, "global_index": 15 }
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
  "all_lines": [
    { "text": "Dragon Blade", "confidence": 0.99, "is_header": true, "global_index": 0 },
    { "text": "공격 15~30", "confidence": 0.85, "global_index": 2 }
  ]
}
```

#### Section Keys
`pre_header`, `item_name`, `item_type`, `item_grade`, `item_attrs`, `enchant`, `item_mod`, `reforge`, `erg`, `set_item`, `item_color`, `ego`, `flavor_text`, `shop_price`.

#### Line Object Properties
| Property | Type | Present | Description |
| :--- | :--- | :--- | :--- |
| `text` | `string` | Always | Best available text (FM-corrected if matched, otherwise raw OCR). |
| `confidence` | `float` | Always | OCR confidence (0.0 to 1.0), rounded to 4 decimal places. |
| `global_index` | `int` | Always | Unique line index within the session. Sent back in `/register-item` for correction mapping. |
| `is_header` | `boolean` | Optional | Present and `true` only for orange section header lines (e.g. "인챈트"). Absent for content lines. |

#### Section Object Properties
All sections contain `lines` (array of Line objects) unless `skipped: true`.

| Property | Type | Sections | Description |
| :--- | :--- | :--- | :--- |
| `lines` | `Line[]` | All (unless skipped) | Editable text lines for the section. |
| `text` | `string` | `item_name`, `item_type`, `pre_header` | Section-level summary text. |
| `prefix` | `object\|null` | `enchant` | Structured prefix enchant (`name`, `rank`, `effects[]`). |
| `suffix` | `object\|null` | `enchant` | Structured suffix enchant (`name`, `rank`, `effects[]`). |
| `options` | `object[]` | `reforge` | Structured reforge options (`name`, `level`, `max_level`, `effect`). |
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

**Endpoint:** `/register-item`
**Method:** `POST`
**Content-Type:** `application/json`

### Request Body
```json
{
  "name": "Dragon Blade",
  "session_id": "abc123",
  "lines": [
    { "global_index": 0, "text": "Dragon Blade" },
    { "global_index": 2, "text": "공격 15~30" }
  ]
}
```

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `name` | `string` | Yes | Item name for registration. |
| `session_id` | `string` | No | Session ID from `/upload-item-v3`. Enables correction capture. |
| `lines` | `array` | No | Final line texts. Each has `global_index` (int) and `text` (string). Lines where `text` differs from the original OCR are saved as correction training data. |

### Response
```json
{
  "registered": true,
  "name": "Dragon Blade",
  "corrections_saved": 2
}
```

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
    "reforge_options": 527
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

These endpoints allow reviewing and approving user-submitted OCR corrections captured during `/register-item`.

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
| `session_id` | `string` | Yes | Session from `/upload-item-v3`. Maps to crop dir `tmp/ocr_crops/{session_id}/`. |
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
