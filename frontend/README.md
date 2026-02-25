```
            |
            |          input beam (screenshot)
           /\
          /  \
         / /\ \        prism (OCR engine)
        / /  \ \
       / /  <> \ \     core (recognition)
      / /______\ \
     /____________\
     |  |  |  |  |
    /  /   |   \  \    output rays (structured data)
   /  /    |    \  \
```

The favicon is a **prism** — a single beam of light enters from above and splits into
multiple colored rays below. This represents the core function of the app: a raw item
screenshot goes in, and the OCR pipeline decomposes it into structured, categorized data
(enchants, reforge options, attributes, colors, etc.).

---

# Frontend — npm Workspaces Monorepo

## Structure

```
frontend/
├── package.json                 ← workspace root (deps hoisted here)
├── .env                         ← shared env vars (MABINOGI_TRADE_API_URL)
├── eslint.config.js             ← single flat config covers all packages
├── packages/
│   ├── shared/                  ← @mabi/shared (no build step, raw source)
│   │   └── src/
│   │       ├── api/             ← client.js, items.js, recommend.js, admin.js
│   │       └── components/      ← SectionCard, ConfigSearchInput, sections/*
│   ├── trade/                   ← @mabi/trade — Marketplace + Sell (port 5173)
│   ├── admin/                   ← @mabi/admin — Admin Dashboard (port 5174)
│   └── misc/                    ← @mabi/misc — Navigate + Image Process (port 5175)
```

## Commands

```bash
npm install              # Install all workspaces (run from frontend/)
npm run dev:trade        # Dev server on port 5173
npm run dev:admin        # Dev server on port 5174
npm run dev:misc         # Dev server on port 5175
npm run build            # Production build all three apps
npm run lint             # ESLint across all packages
```

## How Shared Works

`@mabi/shared` has **no build step**. Apps import raw `.jsx` source via the package's `exports` map:

```js
import { uploadItemV3 } from '@mabi/shared/api/items'
import SectionCard from '@mabi/shared/components/SectionCard'
```

Each app's Vite resolves the source directly — React plugin transpiles JSX, Tailwind scans classes. No separate compilation needed.

## Env Vars

Each app's `vite.config.js` sets `envDir` to the workspace root (`frontend/`), so a single `.env` file is shared. Only vars prefixed with `MABINOGI_` are exposed to client code.

## Docker

A single `frontend` service in `docker-compose.yml` runs all three dev servers concurrently.

```bash
docker compose up -d --build frontend   # Build image & start
docker compose logs -f frontend         # Watch logs
```

- **Ports:** trade:5173, admin:5174, misc:5175
- The Dockerfile CMD runs `npm install` (to create workspace symlinks from the volume mount), then backgrounds all three `npm run dev:*` commands.
- `--host` is baked into each package's `dev` script so Vite binds to `0.0.0.0` inside the container. Do **not** pass `-- --host 0.0.0.0` from compose — npm intercepts the flag and Vite receives `0.0.0.0` as a positional root-dir argument, causing 404s.

## Static Configuration (Enchants)

For zero-latency searching, the enchant dictionary is available as a static configuration file.

### Static Configuration File
- **Path:** `packages/trade/public/enchants_config.js`
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
1. **Include Script:** Ensure the config is included in `packages/trade/index.html` via `<script src="/enchants_config.js"></script>`.
2. **Search Locally:** Perform all filtering and searching using `window.ENCHANTS_CONFIG`.
3. **Fetch Details:** When a user expands an entry, call the API: `GET /admin/enchant-entries/{id}/effects`.

## Generating Static Config

The static configuration file should be regenerated whenever the database or `data/source_of_truth/enchant.yaml` is updated.

### Export Script
Run the following script from the project root:

```bash
python3 scripts/frontend/configs/export_enchant_config.py
```

This script:
1.  Reads enchant metadata from `data/source_of_truth/enchant.yaml`.
2.  Fetches matching database IDs for each entry.
3.  Exports the combined data as a static JavaScript configuration file for the frontend.
