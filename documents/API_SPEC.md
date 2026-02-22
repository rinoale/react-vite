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
The response follows a "Section-First" architecture.

**FM Decision:** The server applies fuzzy matching (FM) against section-specific dictionaries.
If a match is found, `text` is replaced with the FM result and `fm_applied` is set to `true`.
Otherwise, `text` remains the raw OCR output. There is no separate `corrected_text` field —
the frontend should always read `text` directly.

```json
{
  "filename": "item_screenshot.png",
  "sections": {
    "item_name": {
      "text": "Dragon Blade",
      "lines": [ { "text": "Dragon Blade", "confidence": 0.99, "is_header": true } ]
    },
    "item_attrs": {
      "lines": [
        { "text": "공격 15~30", "confidence": 0.85, "fm_applied": true },
        { "text": "부상률 0~10%", "confidence": 0.92, "fm_applied": false }
      ]
    },
    "enchant": {
      "prefix": {
        "text": "[접두] 충격을 (랭크 F)",
        "name": "충격을",
        "rank": "F",
        "effects": [
          {
            "text": "최대대미지 5 증가",
            "option_name": "최대대미지",
            "option_level": 5
          },
          {
            "text": "활성화된 아르카나의 전용 옵션일 때 효과 발동"
          }
        ]
      },
      "suffix": null,
      "lines": [ "..." ]
    },
    "reforge": {
      "options": [
        {
          "name": "스매시 대미지",
          "level": 15,
          "max_level": 20,
          "option_name": "스매시 대미지",
          "option_level": 15,
          "effect": "대미지 150% 증가"
        }
      ],
      "lines": [ "..." ]
    },
    "item_color": {
      "parts": [
        { "part": "A", "r": 255, "g": 255, "b": 255 }
      ]
    }
  },
  "all_lines": [
    { "text": "...", "confidence": 0.0, "section": "item_name", "is_header": true, "fm_applied": false }
  ]
}
```

#### Section Keys
`pre_header`, `item_name`, `item_type`, `item_grade`, `item_attrs`, `enchant`, `item_mod`, `reforge`, `erg`, `set_item`, `item_color`, `ego`, `flavor_text`, `shop_price`.

#### Line Object Properties
| Property | Type | Description |
| :--- | :--- | :--- |
| `text` | `string` | Best available text — FM-corrected if a match was found, otherwise raw OCR. |
| `confidence` | `float` | OCR confidence (0.0 to 1.0). |
| `fm_applied` | `boolean` | `true` if `text` was replaced by a fuzzy-match result. |
| `is_header` | `boolean` | `true` if this line is the orange section header (e.g. "인챈트"). |
| `section` | `string` | Section key this line belongs to. |
| `bounds` | `object` | Bounding box `{ x, y, width, height }`. |

**Note:** `corrected_text` is no longer returned. The server makes the FM decision — `text` is the final value.

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
