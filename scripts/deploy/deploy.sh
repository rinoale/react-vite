#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Load target-specific config (gitignored)
ENV_CONF="$SCRIPT_DIR/deploy.staging.env"
if [ ! -f "$ENV_CONF" ]; then
  echo "Error: $ENV_CONF not found. Copy deploy.staging.env.example and fill in your values."
  exit 1
fi
source "$ENV_CONF"

SSH="ssh -i $PK"
SCP="scp -i $PK"
RSYNC="rsync -az --delete --exclude='__pycache__' --exclude='logs' --exclude='backend/ocr' --exclude='tmp' --exclude='data/' -e 'ssh -i $PK'"

# ---------------------------------------------------------------------------
# Usage:  ./deploy.sh [--backend] [--worker] [--models]
#   --backend  Rebuild and transfer the backend image (slim Python deps).
#              Only needed when requirements.txt changes.
#   --worker   Rebuild and transfer the worker image (full OCR/ML deps + models).
#              Only needed when requirements-worker.txt or models change.
#   --models   Rebuild and transfer the OCR models image first.
#   Default    Rsync source code + frontend dist, restart containers.
# ---------------------------------------------------------------------------
BUILD_BACKEND=false
BUILD_WORKER=false
PUSH_MODELS=false
for arg in "$@"; do
  case $arg in
    --backend) BUILD_BACKEND=true ;;
    --worker) BUILD_WORKER=true ;;
    --models) PUSH_MODELS=true ;;
  esac
done

# --- 1. Build frontends ---
echo "==> Building frontend (trade)..."
cd "$PROJECT_ROOT/frontend"
npm run build -w @mabi/trade

echo "==> Building frontend (admin)..."
npm run build -w @mabi/admin

# --- 2. Optionally build & push OCR models image ---
if $PUSH_MODELS; then
  echo "==> Building OCR models image (${PLATFORM})..."
  bash "$PROJECT_ROOT/infra/ocr-models/build.sh" "$PLATFORM"

  echo "==> Saving and transferring models image (~1.3GB)..."
  docker save mabi-ocr-models | gzip | \
    $SSH "$TARGET" "cat > /tmp/mabi-ocr-models.tar.gz && docker load < /tmp/mabi-ocr-models.tar.gz && rm /tmp/mabi-ocr-models.tar.gz"

  echo "==> Extracting data files from models image..."
  $SSH "$TARGET" "mkdir -p $REMOTE_DIR/app/data && CID=\$(docker create mabi-ocr-models true) && docker cp \$CID:/data/. $REMOTE_DIR/app/data/ && docker rm \$CID"
  echo "==> Models image + data transferred."
fi

# --- 3. Optionally build & push backend image (slim) ---
if $BUILD_BACKEND; then
  echo "==> Building backend image (${PLATFORM})..."
  STAGING=$(mktemp -d)
  trap 'rm -rf "$STAGING"' EXIT
  cp "$PROJECT_ROOT/backend/requirements.txt" "$STAGING/requirements.txt"
  cp "$PROJECT_ROOT/infra/deploy/Dockerfile.backend" "$STAGING/Dockerfile"
  docker buildx build --platform "$PLATFORM" --load -t mabi-backend:latest "$STAGING"
  rm -rf "$STAGING"
  trap - EXIT

  echo "==> Saving and transferring backend image..."
  docker save mabi-backend:latest | gzip | \
    $SSH "$TARGET" "cat > /tmp/mabi-backend.tar.gz && docker load < /tmp/mabi-backend.tar.gz && rm /tmp/mabi-backend.tar.gz"
  echo "==> Backend image transferred."
fi

# --- 3b. Optionally build & push worker image (full OCR/ML deps) ---
if $BUILD_WORKER; then
  echo "==> Building worker image (${PLATFORM})..."
  STAGING=$(mktemp -d)
  trap 'rm -rf "$STAGING"' EXIT
  cp "$PROJECT_ROOT/backend/requirements.txt" "$STAGING/requirements.txt"
  cp "$PROJECT_ROOT/backend/requirements-worker.txt" "$STAGING/requirements-worker.txt"
  cp "$PROJECT_ROOT/infra/deploy/Dockerfile.base" "$STAGING/Dockerfile"
  docker buildx build --platform "$PLATFORM" --load -t mabi-worker:latest "$STAGING"
  rm -rf "$STAGING"
  trap - EXIT

  echo "==> Saving and transferring worker image..."
  docker save mabi-worker:latest | gzip | \
    $SSH "$TARGET" "cat > /tmp/mabi-worker.tar.gz && docker load < /tmp/mabi-worker.tar.gz && rm /tmp/mabi-worker.tar.gz"
  echo "==> Worker image transferred."
fi

# --- 4. Stage app directory ---
echo "==> Staging app directory..."
STAGING=$(mktemp -d)
trap 'rm -rf "$STAGING"' EXIT

# Backend source (no __pycache__, no .env, no ocr model/training dirs)
rsync -a \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.env*' \
  --exclude='ocr/' \
  "$PROJECT_ROOT/backend/" "$STAGING/backend/"

# Configs
cp -r "$PROJECT_ROOT/configs" "$STAGING/configs"

# Frontend dist (remove stale configs — startup.sh generates them from server DB)
cp -r "$PROJECT_ROOT/frontend/packages/trade/dist" "$STAGING/frontend"
rm -f "$STAGING/frontend/enchants_config.js" "$STAGING/frontend/reforges_config.js" "$STAGING/frontend/game_items_config.js"

# Admin dist
cp -r "$PROJECT_ROOT/frontend/packages/admin/dist" "$STAGING/frontend-admin"

# Scripts (import dictionaries + export configs, run at container startup)
mkdir -p "$STAGING/scripts/db" "$STAGING/scripts/frontend/configs"
cp "$PROJECT_ROOT/scripts/db/import_dictionaries.py" "$STAGING/scripts/db/"
cp "$PROJECT_ROOT/scripts/frontend/configs/"*.py "$STAGING/scripts/frontend/configs/"

# Startup script
cp "$PROJECT_ROOT/infra/deploy/startup.sh" "$STAGING/startup.sh"
chmod +x "$STAGING/startup.sh"

# --- 5. Rsync app to server ---
echo "==> Syncing app to server..."
$SSH "$TARGET" "mkdir -p $REMOTE_DIR/app"
eval $RSYNC "$STAGING/" "$TARGET:$REMOTE_DIR/app/"

# --- 6. Sync config files ---
echo "==> Syncing config files..."
$SCP "$PROJECT_ROOT/infra/deploy/docker-compose.stg.yml" "$TARGET:$REMOTE_DIR/docker-compose.yml"
$SCP "$ENV_FILE" "$TARGET:$REMOTE_DIR/.env"
$SCP "$PROJECT_ROOT/infra/nginx/stg.conf" "$TARGET:$REMOTE_DIR/nginx.conf"

# --- 7. Restart on server ---
echo "==> Restarting services..."
# up -d: creates new services (redis on first deploy) or recreates if config changed
# restart: picks up new code from volume mount without changing container IP
$SSH "$TARGET" "cd $REMOTE_DIR && docker compose up -d && docker compose restart backend worker"

# --- 8. Wait for backend health ---
echo "==> Waiting for backend..."
for i in $(seq 1 60); do
  STATUS=$($SSH "$TARGET" "curl -sfk https://localhost/health 2>/dev/null" || true)
  if echo "$STATUS" | grep -q '"ok"'; then
    echo "==> Backend healthy (${i}s)"
    break
  fi
  sleep 1
done

echo ""
echo "==> Done."
echo "  ssh -i $PK $TARGET"
echo "  cd $REMOTE_DIR && docker compose logs -f"
