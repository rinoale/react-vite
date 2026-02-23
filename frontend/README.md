# Mabinogi Marketplace - Frontend

This directory contains the React/Vite source code for the marketplace frontend.

## 1. Static Configuration (Enchants)

For zero-latency searching, the enchant dictionary is available as a static configuration file.

### Static Configuration File
- **Path:** `public/enchants_config.js`
- **Global Variable:** `window.ENCHANTS_CONFIG` (Array of objects)

### Data Structure
Each object in `window.ENCHANTS_CONFIG` contains:
| Property | Type | Description |
| :--- | :--- | :--- |
| `id` | `integer` | Database ID (required for fetching details). |
| `name` | `string` | Enchant name. |
| `slot` | `integer` | `0` = 접두 (Prefix), `1` = 접미 (Suffix). |
| `rank` | `integer` | Numeric rank (1-15). |
| `rank_label` | `string` | Display rank (1-9, A-F). |
| `synonym` | `string` | (Optional) Alternative name for searching. |

### Usage Workflow
1. **Include Script:** Ensure the config is included in `index.html` via `<script src="/enchants_config.js"></script>`.
2. **Search Locally:** Perform all filtering and searching using `window.ENCHANTS_CONFIG`.
3. **Fetch Details:** When a user expands an entry, call the API: `GET /admin/enchant-entries/{id}/effects`.

## 2. Generating Static Config

The static configuration file (`public/enchants_config.js`) should be regenerated whenever the database or `data/source_of_truth/enchant.yaml` is updated.

### Export Script
Run the following script from the project root:

```bash
python3 scripts/frontend/configs/export_enchant_config.py
```

This script:
1.  Reads enchant metadata from `data/source_of_truth/enchant.yaml`.
2.  Fetches matching database IDs for each entry.
3.  Exports the combined data as a static JavaScript configuration file for the frontend.
