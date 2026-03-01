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

For backend/training commands and full project documentation, see the [root README](../README.md).

## Static Configs (Prerequisites)

The trade app depends on three static JS config files generated from the database. These must be exported before running the dev server for the first time, and re-exported whenever the database or source data changes.

### Quick Start

```bash
# Prerequisites: PostgreSQL running, dictionaries imported (see project root CLAUDE.md)
npm run export-configs    # Generates all three config files
npm run dev:trade         # Now the app has data to work with
```

### What It Generates

| File | Global Variable | Source | Records |
| :--- | :--- | :--- | :--- |
| `packages/trade/public/enchants_config.js` | `window.ENCHANTS_CONFIG` | `enchant.yaml` + DB | ~1170 enchants |
| `packages/trade/public/reforges_config.js` | `window.REFORGES_CONFIG` | DB `reforge_options` | ~530 options |
| `packages/trade/public/game_items_config.js` | `window.GAME_ITEMS_CONFIG` | DB `game_items` | ~20k items |

Each file is included via `<script>` tags in `packages/trade/index.html` and exposes a global `window.*` variable for zero-latency client-side searching.

### Individual Export Scripts

To regenerate a single config, run from the project root:

```bash
python3 scripts/frontend/configs/export_enchant_config.py
python3 scripts/frontend/configs/export_reforge_config.py
python3 scripts/frontend/configs/export_game_items_config.py
```

### When to Re-export

- After running `python3 scripts/db/import_dictionaries.py`
- After editing `data/source_of_truth/enchant.yaml`
- After any DB migration that changes enchants, reforge_options, or game_items tables
