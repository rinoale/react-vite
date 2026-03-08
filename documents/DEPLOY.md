# Deployment

## Overview

| Component | Target | Method |
|-----------|--------|--------|
| Frontend (trade) | Cloudflare Pages | `wrangler pages deploy` |
| Backend (FastAPI) | OCI server `ubuntu@64.110.116.116` | Docker image via `docker save`/`scp` |
| Database (PostgreSQL) | OCI server (Docker container) | `docker compose` |
| OCR Models (~1.3GB) | OCI server (baked into Docker image) | Separate image, transferred once |

## Quick Deploy

```bash
# Standard deploy (backend + frontend):
bash scripts/hidden/deploy.sh

# First deploy or when OCR models change:
bash scripts/hidden/deploy.sh --models

# Frontend only (Cloudflare Pages):
cd frontend && npm run build -w @mabi/trade
wrangler pages deploy packages/trade/dist --project-name=mabinogi-trade
```

## Frontend — Cloudflare Pages

**Project:** `mabinogi-trade`
**URL:** https://mabinogi-trade.pages.dev (custom domain can be added in dashboard)

SPA routing handled by `frontend/packages/trade/public/_redirects` which Vite copies into `dist/` on build.

### Setup (already done)

```bash
npm install -g wrangler
wrangler login
wrangler pages project create mabinogi-trade --production-branch main
```

### Deploy

```bash
cd frontend && npm run build -w @mabi/trade
wrangler pages deploy packages/trade/dist --project-name=mabinogi-trade
```

### Custom Domain

1. Buy a domain (Cloudflare Registrar or any registrar)
2. Add the domain to Cloudflare (set nameservers if external registrar)
3. Cloudflare Pages dashboard → Custom domains → Add domain

## Backend — OCI Server

**Server:** `ubuntu@64.110.116.116`
**Remote dir:** `/home/ubuntu/mabinogi`

### Architecture

Two Docker images:

| Image | Contents | Size | Rebuild frequency |
|-------|----------|------|-------------------|
| `mabi-ocr-models` | 7 `.pth` model files + `.py`/`.yaml` configs | ~1.3GB | Only when models retrained |
| `mabi-backend` | Python app + deps + configs + data + models + frontend dist | ~2GB+ | Every code deploy |

The backend image uses a multi-stage `COPY --from=mabi-ocr-models` to pull in model files. This way, model transfer (~1.3GB) only happens when models change.

### Deploy Script: `scripts/hidden/deploy.sh`

```
Usage: bash scripts/hidden/deploy.sh [--models]

Flags:
  --models    Rebuild and transfer OCR models image (slow, ~1.3GB)
              Only needed on first deploy or when models are retrained.

Steps:
  1. Build frontend (npm run build -w @mabi/trade)
  2. [--models] Build mabi-ocr-models image, docker save | gzip | ssh docker load
  3. Stage clean build context (backend source, configs, data, frontend dist)
  4. Build mabi-backend image locally
  5. docker save | gzip | ssh docker load to server
  6. scp docker-compose.yml to server
  7. docker compose up -d on server
```

### OCR Models Image: `infra/ocr-models/`

Build separately via `infra/ocr-models/build.sh`:

```bash
bash infra/ocr-models/build.sh
```

The script:
1. Copies `backend/ocr/models/` to a temp dir, resolving all symlinks (`cp -rL`)
2. Builds a minimal `FROM scratch` image containing only the resolved model files

### Production Dockerfile: `infra/deploy/Dockerfile`

```
FROM mabi-ocr-models AS models        ← pulls model files
FROM python:3.14.2-slim               ← production base

Layers:
  - System deps (build-essential, libgl1, etc.)
  - pip install requirements.txt
  - backend/ source code
  - configs/
  - data/dictionary/ + data/source_of_truth/
  - COPY --from=models /models/ → /app/backend/ocr/models/
  - frontend/ (pre-built dist for SPA serving)

CMD: alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000
```

### Staging Compose: `infra/deploy/docker-compose.stg.yml`

Services:
- **db**: `postgres:16-alpine`, data persisted in `db_data` volume, port 5432 bound to localhost only
- **backend**: `mabi-backend:latest`, reads `.env` from remote dir, port 8000 (internal)
- **nginx**: `nginx:alpine`, SSL termination, ports 80 (→ HTTPS redirect) + 443 (→ backend:8000)

### Server Setup

The server needs Docker installed. `.env` file must be placed at `/home/ubuntu/mabinogi/.env`.

Env files are stored at `~/workspace/ocr_training_data/env/` (outside repo).

### Environment Configuration

| Variable | Development | Staging | Production | Notes |
|----------|-------------|---------|------------|-------|
| `APP_ENV` | `development` | `staging` | `production` | |
| `DB_PASSWORD` | `mabinogi` | `mabinogi` | **strong password** | |
| `JWT_SECRET_KEY` | dev default | generated | **generated** | `openssl rand -base64 48` |
| `DISCORD_CLIENT_ID` | from Discord dev portal | same | same or separate app | |
| `DISCORD_CLIENT_SECRET` | from Discord dev portal | same | same or separate app | |
| `DISCORD_REDIRECT_URI` | `https://dev.trade.mabitra.com/api/auth/discord/callback` | `https://64.110.116.116/api/auth/discord/callback` | `https://<domain>/api/auth/discord/callback` | Must match Discord app settings |
| `FRONTEND_URL` | `https://dev.trade.mabitra.com` | `https://64.110.116.116` | `https://<domain>` | Used for Discord OAuth redirects back to frontend |
| `COOKIE_DOMAIN` | `.mabitra.com` (default) | `64.110.116.116` | `.<domain>` | See gotcha below |
| `COOKIE_SECURE` | `false` | `true` | `true` | Must be `true` when using HTTPS |
| `COOKIE_SAMESITE` | `lax` | `lax` | `lax` | |
| `MABINOGI_OPEN_API_KEY` | test key | test key | **production key** | |

**Cookie domain gotcha:** Browsers silently reject cookies with an explicit `Domain` attribute set to an IP address (RFC 6265). The backend detects IP-based `COOKIE_DOMAIN` values and omits the attribute, letting the browser scope cookies to the exact origin. For domain-based deployments, use the dotted form (e.g., `.mabitra.com`) to allow cookie sharing across subdomains.

### SSL

| Environment | Method | Config |
|-------------|--------|--------|
| Development | Self-signed cert via nginx | `infra/nginx/dev.conf` + `infra/nginx/certs/` |
| Staging | Self-signed cert via nginx container | `infra/nginx/stg.conf`, certs copied to server |
| Production | Real cert (Let's Encrypt / Cloudflare) | TBD |

Staging uses a self-signed certificate. Discord OAuth works with self-signed certs because the redirect is browser-side (user must accept the cert warning once).

### SPA Serving

Backend serves the frontend SPA when `../frontend/` directory exists relative to the backend working dir. In production Docker, the built frontend dist is at `/app/frontend/`.

- Static assets: `/assets/*` served via FastAPI `StaticFiles`
- All other GET routes: fall back to `index.html`
- API routes prefixed with `/api` in SPA mode (auto-detected)

## File Layout

```
infra/
├── ocr-models/
│   ├── Dockerfile          # FROM scratch, just model files
│   └── build.sh            # Resolve symlinks + docker build
├── deploy/
│   ├── Dockerfile          # Production backend (multi-stage from ocr-models)
│   └── docker-compose.stg.yml
├── database/
│   └── Dockerfile          # postgres:16-alpine (dev)
└── nginx/
    ├── dev.conf            # Dev nginx config
    ├── stg.conf            # Staging nginx config (SSL → backend)
    └── certs/              # Self-signed certs (dev + staging)

scripts/hidden/
└── deploy.sh               # Main deploy script

frontend/packages/trade/public/
└── _redirects               # Cloudflare Pages SPA fallback
```
