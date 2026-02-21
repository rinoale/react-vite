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

#### Enchant Section (`sections.enchant`)
| Property | Type | Description |
| :--- | :--- | :--- |
| `prefix` | `object \| null` | Prefix enchant slot data, or `null` if no prefix enchant. |
| `suffix` | `object \| null` | Suffix enchant slot data, or `null` if no suffix enchant. |
| `lines` | `array` | All lines in the enchant section (for fallback rendering). |

Each slot object:
| Property | Type | Description |
| :--- | :--- | :--- |
| `text` | `string` | Full header text, e.g. `"[접두] 충격을 (랭크 F)"`. |
| `name` | `string` | Enchant name, e.g. `"충격을"`. |
| `rank` | `string` | Rank letter or number, e.g. `"F"`, `"6"`. |
| `effects` | `array` | Effect objects (see below). |

Each effect object:
| Property | Type | Description |
| :--- | :--- | :--- |
| `text` | `string` | Full effect text, e.g. `"최대대미지 5 증가"`. |
| `option_name` | `string` (optional) | Stat name extracted from the effect, e.g. `"최대대미지"`. Present only if a number was found. |
| `option_level` | `number` (optional) | Numeric value extracted from the effect, e.g. `5`. Present only if a number was found. |

#### Reforge Section (`sections.reforge`)
| Property | Type | Description |
| :--- | :--- | :--- |
| `options` | `array` | Parsed reforge option records. |
| `lines` | `array` | All lines in the reforge section. |

Each option object:
| Property | Type | Description |
| :--- | :--- | :--- |
| `name` | `string` | Reforge skill name (may be FM-corrected). |
| `level` | `integer` | Current reforge level. |
| `max_level` | `integer` | Maximum reforge level. |
| `option_name` | `string` | Alias for `name` (unified field for DB storage). |
| `option_level` | `integer` | Alias for `level` (unified field for DB storage). |
| `effect` | `string \| null` | Effect description from the `ㄴ` sub-bullet, or `null`. |

---

## 2. Admin Validation APIs

Simple admin endpoints for validating DB records in browser/JSON.

### HTML Page
- **Endpoint:** `/admin/validate`
- **Method:** `GET`
- **Query params:** `tab` (`entries|effects|links|reforge`), `limit`, `offset`
- **Response:** server-rendered HTML table for manual validation

### JSON Endpoints
- **`GET /admin/health`**
  - Response: `{ "ok": true }`
- **`GET /admin/summary`**
  - Response:
    ```json
    {
      "enchant_entries": 1168,
      "enchant_effects": 230,
      "enchant_links": 4934,
      "reforge_options": 527
    }
    ```
- **`GET /admin/enchant-entries?limit=100&offset=0`**
  - Response: `{ "limit": 100, "offset": 0, "rows": [...] }`
  - Row fields: `id`, `slot` (0/1), `name`, `rank`, `header_text`, `effect_count`
- **`GET /admin/effects?limit=100&offset=0`**
  - Row fields: `id`, `normalized_text`
- **`GET /admin/links?limit=100&offset=0`**
  - Row fields: `id`, `enchant_entry_id`, `enchant_effect_id`, `effect_order`, `condition_text`, `effect_value`, `effect_direction`, `raw_text`, `enchant_name`, `effect_text`
  - **Proposed Filter:** `enchant_entry_id` (Integer). If provided, returns only links for that entry. Required for efficient expansion in Admin UI.
- **`GET /admin/reforge-options?limit=100&offset=0`**
  - Row fields: `id`, `option_name`
