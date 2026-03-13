# Deployment

## Overview

| Component | Dev | Staging | Production |
|-----------|-----|---------|------------|
| **Domain** | `dev.mabitra.local` | `stg.mabitra.com` | TBD (Cloudflare CDN) |
| **Frontend (trade)** | Vite dev server `:5173` | Served by FastAPI (SPA mode) | Cloudflare CDN |
| **Frontend (admin)** | Vite dev server `:5174` | Served by FastAPI at `/admin/` | Cloudflare CDN |
| **Backend (FastAPI)** | Local uvicorn `:8000` | OCI server, Docker container | OCI server |
| **Database** | Docker `postgres:16-alpine` | Docker `postgres:16-alpine` | Managed Postgres |
| **SSL** | Self-signed cert | Let's Encrypt (certbot) | Cloudflare |
| **Reverse proxy** | Nginx (Docker, local) | Nginx (Docker, server) | Cloudflare / Nginx |

**Server:** OCI `ubuntu@<server-ip>` (see `deploy.staging.env`)
**Remote dir:** `/home/ubuntu/mabinogi`

## Architecture: Single-Domain, Path-Based Routing

All environments use a single domain with path-based routing — no per-app subdomains.

```
https://{domain}/           → Frontend (trade)
https://{domain}/admin/     → Frontend (admin), auth-gated (master/admin roles)
https://{domain}/api/...    → Backend API (FastAPI)
```

In staging, FastAPI serves all three (SPA mode). In dev, Nginx routes to individual Vite dev servers.

## Quick Deploy

```bash
# Standard deploy (code + frontend, ~30s):
bash scripts/deploy.sh

# When requirements.txt or OCR models change:
bash scripts/deploy.sh --base

# When OCR models are retrained:
bash scripts/deploy.sh --models --base
```

## Deploy Script: `scripts/deploy.sh`

Rsync-based deploy. Source code is synced to the server and volume-mounted into the container — no full Docker image rebuild for code changes.

### Prerequisites

Create `scripts/deploy.env` (gitignored) from `scripts/deploy.env.example`:

```bash
PK=~/.ssh/your_key           # SSH private key
TARGET=ubuntu@<server-ip>     # SSH target
REMOTE_DIR=/home/ubuntu/mabinogi
PLATFORM=linux/amd64          # Docker buildx platform
ENV_FILE=~/workspace/ocr_training_data/env/.env.staging
```

### Flags

| Flag | When needed | What it does |
|------|-------------|--------------|
| *(none)* | Every code deploy | Build frontends → stage app → rsync → restart container |
| `--base` | `requirements.txt` changes | Build `mabi-base` image → transfer → rsync → restart |
| `--models` | OCR models retrained | Build `mabi-ocr-models` image → transfer (~1.3GB) |

### Deploy Flow

```
1. Build frontends
   npm run build -w @mabi/trade
   npm run build -w @mabi/admin

2. [--models] Build & transfer mabi-ocr-models image
   bash infra/ocr-models/build.sh $PLATFORM
   docker save | gzip | ssh docker load

3. [--base] Build & transfer mabi-base image
   Temp staging dir with only requirements.txt + Dockerfile.base
   docker buildx build → docker save | gzip | ssh docker load

4. Stage app directory (local tmpdir)
   rsync backend/ (excluding __pycache__, .env*, ocr/)
   cp configs/, data/dictionary/, data/source_of_truth/
   cp frontend dist → frontend/
   cp admin dist → frontend-admin/
   cp scripts/db/, scripts/frontend/configs/
   cp infra/deploy/startup.sh

5. Rsync staged dir → server:/home/ubuntu/mabinogi/app/
   rsync -az --delete --exclude='__pycache__'

6. SCP config files to server
   docker-compose.stg.yml → docker-compose.yml
   .env.staging → .env
   infra/nginx/stg.conf → nginx.conf

7. Restart
   docker compose up -d --force-recreate backend worker
```

## Docker Images

### `mabi-ocr-models` (~1.3GB)

Minimal `FROM scratch` image containing OCR model `.pth` files, configs, and data files (dictionary, source_of_truth, fonts).

```
infra/ocr-models/
├── Dockerfile          # FROM scratch, COPY /models/ + /data/
└── build.sh            # Resolves symlinks, stages data files → docker build
```

Built and transferred only when OCR models are retrained or data files change (rare).

Transfer via rclone + Google Drive:
```bash
bash scripts/ocr/sync-image.sh upload     # docker save → gzip → rclone to gdrive
bash scripts/ocr/sync-image.sh download   # rclone → docker load
bash scripts/ocr/sync-image.sh extract    # docker create → docker cp to project dirs
```

### `mabi-backend` (~300MB)

Slim Python runtime for the web server. No OCR/ML packages, no models.

```dockerfile
# infra/deploy/Dockerfile.backend
FROM python:3.14.2-slim
RUN apt-get install build-essential gcc g++ pkg-config rustc cargo
COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt
WORKDIR /app/backend
CMD ["/app/startup.sh"]
```

Fast to build (~30s) since it only installs web dependencies.

### `mabi-worker` (~2GB)

Full OCR/ML runtime with PyTorch, EasyOCR, and all ML dependencies. Includes models and data from `mabi-ocr-models`.

```dockerfile
# infra/deploy/Dockerfile.base (worker image)
FROM mabi-ocr-models AS models
FROM python:3.14.2-slim
RUN apt-get install build-essential gcc g++ pkg-config rustc cargo libgl1 libglib2.0-0
COPY requirements.txt requirements-worker.txt /app/
RUN pip install -r /app/requirements-worker.txt
COPY --from=models /models/ /models/
COPY --from=models /data/ /data/
WORKDIR /app/backend
CMD ["python", "worker.py", "--queues", "default", "gpu"]
```

**Why models at `/models/` and data at `/data/`?** The docker-compose mounts `./app:/app`, which hides anything baked into `/app/` in the image.

Slow to build under ARM64 QEMU cross-compilation (~15min) due to PyTorch + Rust packages.

### Legacy `Dockerfile` (superseded)

`infra/deploy/Dockerfile` bakes everything (source + deps + models + frontend) into one image. Superseded by split images + rsync approach. Kept for reference.

## Container Startup: `infra/deploy/startup.sh`

Runs inside the `mabi-backend` container on every start:

```bash
#!/bin/bash
set -e

# 1. Symlink OCR models from separate volume into backend
mkdir -p /app/backend/ocr
ln -sfn /models /app/backend/ocr/models

# 2. Run database migrations
alembic upgrade head

# 3. Import dictionaries (all defaults point to data/source_of_truth/*.yaml)
python /app/scripts/db/import_dictionaries.py \
  --db-host "$DB_HOST" --db-port "$DB_PORT" --db-name "$DB_NAME" \
  --db-user "$DB_USER" --db-password "$DB_PASSWORD"

# 4. Export frontend configs (generated JS files from DB data)
export FRONTEND_DIST_DIR=/app/frontend
python /app/scripts/frontend/configs/export_all.py

# 5. Start server
exec uvicorn main:app --host 0.0.0.0 --port 8000
```

## Staging Compose: `infra/deploy/docker-compose.stg.yml`

```yaml
services:
  db:           # postgres:16-alpine, port 5432 (localhost only), db_data volume
  redis:        # redis:7-alpine, port 6379 (localhost only), password-protected
  backend:      # mabi-backend:latest, volume-mounts ./app:/app (no OCR deps)
  worker:       # mabi-worker:latest, runs `python worker.py`, ./app + ocr_models:/models
  nginx:        # nginx:alpine, ports 80+443, certbot volumes (ro)
  certbot:      # certbot/certbot, auto-renewal loop (every 12h)

volumes:
  db_data:
  redis_data:
  ocr_models:
  certbot_www:  # Shared webroot for ACME challenges
  certbot_certs: # Let's Encrypt certificates
```

Key details:
- `backend` uses `mabi-backend:latest` (slim, no OCR packages) — reads `env_file: .env`
- `worker` uses `mabi-worker:latest` (full ML deps + models) — runs `python worker.py` (dequeue loop + scheduler thread)
- `redis` bound to `127.0.0.1:6379` (not exposed publicly), password-protected. Remote workers connect via SSH tunnel.
- `nginx` bind-mounts `./nginx.conf` (copied from `infra/nginx/stg.conf` during deploy). Blocks `.php/.cgi/.asp/.aspx` probes with `return 444`.
- `certbot` runs an infinite renewal loop: `certbot renew; sleep 12h`

## SSL / HTTPS

### Development: Self-Signed Certificate

```
infra/nginx/certs/
├── dev.crt     # Self-signed cert for dev.mabitra.local
└── dev.key
```

Generate (already done):
```bash
openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
  -keyout infra/nginx/certs/dev.key \
  -out infra/nginx/certs/dev.crt \
  -subj '/CN=dev.mabitra.local' \
  -addext 'subjectAltName=DNS:dev.mabitra.local'
```

Browser will show a cert warning — accept once.

### Staging: Let's Encrypt

**Initial setup** (run once on the server before first deploy):

```bash
# On the server:
bash /home/ubuntu/mabinogi/app/scripts/server_setup.sh stg.mabitra.com your@email.com
```

The script (`scripts/server_setup.sh`):
1. Starts a temporary Nginx container on port 80 for the ACME challenge
2. Runs `certbot certonly --webroot` to obtain the certificate
3. Stores certs in the `mabinogi_certbot_certs` Docker volume
4. Cleans up temporary container

After initial setup, the `certbot` service in docker-compose handles automatic renewal every 12 hours.

**Certificate location (inside Docker volume):**
```
/etc/letsencrypt/live/stg.mabitra.com/fullchain.pem
/etc/letsencrypt/live/stg.mabitra.com/privkey.pem
```

### Production: Cloudflare (planned)

- Point `mabitra.com` nameservers to Cloudflare (free plan)
- Cloudflare CDN caches static assets at edge nodes — frontend still deployed to server, served by FastAPI (same as staging)
- Cloudflare handles SSL termination; origin server uses a Cloudflare origin certificate
- No architecture change from staging — single domain, path-based routing, everything on one server

## Nginx Configuration

### Development: `infra/nginx/dev.conf`

Single domain `dev.mabitra.local`, routes to local Vite dev servers:

```
                       ┌─ /api/    → host.docker.internal:8000 (FastAPI)
dev.mabitra.local:443 ─┼─ /admin/  → host.docker.internal:5174 (Vite admin)
                       └─ /        → host.docker.internal:5173 (Vite trade)
```

- HTTP (port 80) → 301 redirect to HTTPS
- WebSocket upgrade headers for Vite HMR on trade and admin
- `client_max_body_size 10M` for image uploads
- `/api/` strips the prefix: `proxy_pass http://api/` (trailing slash = strip `/api/`)

### Staging: `infra/nginx/stg.conf`

Single domain `stg.mabitra.com`, everything proxied to FastAPI:

```
stg.mabitra.com:443 → backend:8000 (FastAPI handles all routing)
```

- HTTP (port 80): ACME challenge path + 301 redirect
- Let's Encrypt cert from Docker volume
- FastAPI serves frontend SPAs, API, and admin — all path routing handled by `main.py`

## SPA Serving (Staging/Production)

FastAPI detects SPA mode when `../frontend/` directory exists (set by volume mount).

### Route resolution in `backend/main.py`:

```
/api/...              → API routers (auth, admin, corrections, misc, trade)
/assets/*             → StaticFiles from frontend/assets/
/admin/assets/*       → StaticFiles from frontend-admin/assets/
/admin/{path}         → Admin SPA (auth-gated: master/admin roles only)
/{path}               → Trade SPA fallback (index.html)
```

### Admin Auth Gate

`/admin/*` routes use `Depends(is_admin_user)` from `backend/auth/dependencies.py`:
- Static files (`/admin/assets/*`, `/admin/locales/*`) served without auth
- HTML fallback (`index.html`) requires master or admin role
- Non-authenticated users redirected to `/`
- Auth checked via JWT (Bearer header or `access_token` cookie)

## Networking & Firewall

### OCI Server Firewall (iptables)

Required ports:
```bash
sudo iptables -I INPUT 5 -p tcp --dport 80 -m state --state NEW -j ACCEPT
sudo iptables -I INPUT 6 -p tcp --dport 443 -m state --state NEW -j ACCEPT
sudo netfilter-persistent save
```

### Docker Networking

- Staging: `backend` and `worker` connect to `db` via Docker DNS (`db:5432`) and `redis` via (`redis:6379`)
- Dev: Nginx connects to host services via `host.docker.internal` (set by `extra_hosts`)
- DB port 5432 bound to `127.0.0.1` only (staging) — not exposed to public
- Redis port 6379 exposed in dev, internal-only in staging (Docker DNS)

## Environment Configuration

### Config Loading

`backend/core/config.py` uses `pydantic_settings.BaseSettings`:
- Loads from `.env.{APP_ENV}` (e.g., `.env.development`, `.env.staging`)
- All settings have dev defaults — staging/production override via env file

### Environment Variables

| Variable | Dev Default | Staging | Notes |
|----------|-------------|---------|-------|
| `APP_ENV` | `development` | `staging` | Selects `.env.{APP_ENV}` file |
| `DB_HOST` | `localhost` | `db` | Docker service name in staging |
| `DB_PORT` | `5432` | `5432` | |
| `DB_NAME` | `mabinogi` | `mabinogi` | |
| `DB_USER` | `mabinogi` | `mabinogi` | |
| `DB_PASSWORD` | `mabinogi` | **strong password** | |
| `JWT_SECRET_KEY` | `dev-secret-change-in-production` | **generated** | `openssl rand -base64 48` |
| `DISCORD_CLIENT_ID` | from Discord dev portal | same | |
| `DISCORD_CLIENT_SECRET` | from Discord dev portal | same | |
| `DISCORD_REDIRECT_URI` | `https://dev.mabitra.local/api/auth/discord/callback` | `https://stg.mabitra.com/api/auth/discord/callback` | Must match Discord app settings |
| `FRONTEND_URL` | `https://dev.mabitra.local` | `https://stg.mabitra.com` | Discord OAuth redirect target |
| `COOKIE_DOMAIN` | `.mabitra.local` | `.mabitra.com` | See cookie isolation below |
| `COOKIE_SECURE` | `false` | `true` | HTTPS required when `true` |
| `COOKIE_SAMESITE` | `lax` | `lax` | |
| `REDIS_HOST` | `localhost` | `redis` | Docker service name in staging |
| `REDIS_PORT` | `6379` | `6379` | |
| `REDIS_PASSWORD` | `devredis` | **strong password** | Required for broker auth |
| `CORS_ORIGINS` | `["https://dev.mabitra.local"]` | `["https://stg.mabitra.com"]` | |

### Cookie Domain Isolation

Dev uses `.mabitra.local`, staging uses `.mabitra.com`. This prevents auth cookies from one environment leaking to the other (RFC 6265: cookies scoped to TLD+1 cannot cross TLDs).

### Env File Locations

| Environment | File | Stored at |
|-------------|------|-----------|
| Development | `.env.development` | `~/workspace/ocr_training_data/env/.env.development` (volume-mounted) |
| Staging | `.env.staging` | `~/workspace/ocr_training_data/env/.env.staging` (scp'd to server as `.env`) |

Both are outside the repo (gitignored).

### Discord Developer Portal

Add these redirect URIs in the Discord app settings:
- `https://dev.mabitra.local/api/auth/discord/callback` (dev)
- `https://stg.mabitra.com/api/auth/discord/callback` (staging)

## Development Setup

### Prerequisites

- Node.js, npm
- Python 3.14+
- Docker + Docker Compose
- Add to `/etc/hosts`: `127.0.0.1 dev.mabitra.local`

### Start Dev Environment

```bash
# 1. Start database + redis + nginx
docker compose up -d db redis nginx

# 2. Backend (terminal 1)
cd backend && uvicorn main:app --reload --port 8000

# 3. Frontend trade (terminal 2)
cd frontend && npm run dev -w @mabi/trade

# 4. Frontend admin (terminal 3)
cd frontend && npm run dev -w @mabi/admin
```

```bash
# 5. Worker (terminal 4, optional — for background job processing)
cd backend && python worker.py
```

Or use Docker for everything:
```bash
docker compose up -d
```

### Dev Compose: `docker-compose.yml`

Services:
- `nginx`: Routes `dev.mabitra.local` to local dev servers (self-signed cert)
- `db`: PostgreSQL 16 (`mabinogi/mabinogi/mabinogi`)
- `redis`: Redis 7, password-protected (`devredis`)
- `backend`: Hot-reload, volume-mounts source code + OCR data from host
- `worker`: Background job processor (dequeue loop + scheduler)
- `frontend`: Runs all three Vite dev servers (trade :5173, admin :5174, misc :5175)

Notable volume mounts:
- `~/workspace/ocr_training_data/mabinogi/ocr` → `/app/backend/ocr` (OCR models, outside repo)
- `~/workspace/ocr_training_data/mabinogi/data` → `/app/data` (dictionaries, outside repo)
- `~/workspace/ocr_training_data/env` → `/app/env:ro` (env files, outside repo)

## Frontend Build

### Monorepo Structure

```
frontend/packages/
├── shared/   # @mabi/shared — raw JSX source, no build step
├── trade/    # @mabi/trade — Marketplace + Sell (port 5173)
├── admin/    # @mabi/admin — Admin Dashboard (port 5174, base: /admin/)
└── misc/     # @mabi/misc — Navigate + Image Process (port 5175)
```

### Admin Subpath

Admin is served at `/admin/` in all environments:
- `vite.config.js`: `base: '/admin/'` (hardcoded, no env var)
- `App.jsx`: `<BrowserRouter basename={import.meta.env.BASE_URL}>`
- i18n `loadPath`: `` `${import.meta.env.BASE_URL}locales/{{lng}}/{{ns}}.json` ``

### API URLs

All frontend API calls use **relative paths** (no hardcoded domains):
```javascript
// Correct:
fetch('/api/examine-item', ...)
const cropUrl = `/api/admin/corrections/crop/${id}/${filename}`;

// Wrong (removed):
// fetch(`${API_BASE}/examine-item`, ...)
```

In dev, Nginx rewrites `/api/...` to the backend. In staging, FastAPI handles the `/api` prefix natively (SPA mode).

## File Layout

```
infra/
├── ocr-models/
│   ├── Dockerfile              # FROM scratch, model files only
│   └── build.sh                # Resolve symlinks + docker build
├── deploy/
│   ├── Dockerfile.base         # Base image: deps + models (active)
│   ├── Dockerfile              # Full-bake image (legacy, superseded)
│   ├── docker-compose.stg.yml  # Staging compose
│   └── startup.sh              # Container entrypoint
├── database/
│   └── Dockerfile              # postgres:16-alpine (dev)
└── nginx/
    ├── dev.conf                # Dev: single domain, path routing to Vite
    ├── stg.conf                # Staging: SSL termination → backend
    └── certs/                  # Self-signed certs (dev only)
        ├── dev.crt
        └── dev.key

scripts/
├── deploy.sh                   # Rsync-based deploy script
├── deploy.env                  # Deploy config (gitignored)
├── deploy.env.example          # Template for deploy.env
└── server_setup.sh             # One-time Let's Encrypt cert setup

docker-compose.yml              # Local dev compose
```

## Server Directory Layout

```
/home/ubuntu/mabinogi/
├── docker-compose.yml          # Copied from infra/deploy/docker-compose.stg.yml
├── .env                        # Copied from staging env file
├── nginx.conf                  # Copied from infra/nginx/stg.conf
└── app/                        # Rsynced from local staging dir
    ├── startup.sh
    ├── backend/                # Python source (no __pycache__, no .env, no ocr/)
    │   └── ocr/
    │       └── models -> /models  # Symlink created by startup.sh
    ├── configs/
    ├── data/
    │   ├── dictionary/
    │   └── source_of_truth/
    ├── frontend/               # Trade dist (configs removed, regenerated at startup)
    ├── frontend-admin/         # Admin dist
    └── scripts/
        ├── db/import_dictionaries.py
        └── frontend/configs/*.py

Docker volumes:
  db_data                       # PostgreSQL data
  redis_data                    # Redis persistence
  ocr_models                    # OCR .pth files (from mabi-ocr-models image)
  mabinogi_certbot_www          # ACME challenge webroot
  mabinogi_certbot_certs        # Let's Encrypt certificates
```

## Troubleshooting

### `__pycache__` permission errors during rsync

Root-owned `.pyc` files from the container can't be overwritten by rsync. The deploy script excludes `__pycache__` via `--exclude='__pycache__'`.

### OCR models not found after deploy

The `./app:/app` volume mount hides anything baked into `/app/` in the image. Models are stored at `/models/` in the base image and symlinked by `startup.sh`:
```bash
mkdir -p /app/backend/ocr
ln -sfn /models /app/backend/ocr/models
```

### Admin showing 404

1. Check that `frontend-admin/` exists in the staged app dir
2. Verify `/admin` (no trailing slash) redirects to `/admin/` — handled by `main.py`
3. Check auth: non-admin users are redirected to `/`

### Stale Docker images on server

```bash
docker image prune -f
```

### Certbot renewal fails

Check that port 80 is open and the ACME challenge location is configured:
```nginx
location /.well-known/acme-challenge/ { root /var/www/certbot; }
```
