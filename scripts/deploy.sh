#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load target-specific config (gitignored)
ENV_CONF="$SCRIPT_DIR/deploy.env"
if [ ! -f "$ENV_CONF" ]; then
  echo "Error: $ENV_CONF not found. Copy deploy.env.example and fill in your values."
  exit 1
fi
source "$ENV_CONF"

SSH="ssh -i $PK"
SCP="scp -i $PK"
RSYNC="rsync -az --delete --exclude='__pycache__' -e 'ssh -i $PK'"

# ---------------------------------------------------------------------------
# Usage:  ./deploy.sh [--base] [--models]
#   --base     Rebuild and transfer the base image (Python deps + OCR models).
#              Only needed when requirements.txt or models change.
#   --models   Rebuild and transfer the OCR models image first.
#   Default    Rsync source code + frontend dist, restart container.
# ---------------------------------------------------------------------------
BUILD_BASE=false
PUSH_MODELS=false
for arg in "$@"; do
  case $arg in
    --base) BUILD_BASE=true ;;
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
  echo "==> Models image transferred."
fi

# --- 3. Optionally build & push base image ---
if $BUILD_BASE; then
  echo "==> Building base image (${PLATFORM})..."
  STAGING=$(mktemp -d)
  trap 'rm -rf "$STAGING"' EXIT
  cp "$PROJECT_ROOT/backend/requirements.txt" "$STAGING/requirements.txt"
  cp "$PROJECT_ROOT/infra/deploy/Dockerfile.base" "$STAGING/Dockerfile"
  docker buildx build --platform "$PLATFORM" --load -t mabi-base:latest "$STAGING"
  rm -rf "$STAGING"
  trap - EXIT

  echo "==> Saving and transferring base image..."
  docker save mabi-base:latest | gzip | \
    $SSH "$TARGET" "cat > /tmp/mabi-base.tar.gz && docker load < /tmp/mabi-base.tar.gz && rm /tmp/mabi-base.tar.gz"
  echo "==> Base image transferred."
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

# Create minimal ocr dir (models are in the base image)
mkdir -p "$STAGING/backend/ocr/models"

# Configs
cp -r "$PROJECT_ROOT/configs" "$STAGING/configs"

# Data (dictionary + source_of_truth only)
mkdir -p "$STAGING/data/dictionary" "$STAGING/data/source_of_truth"
cp -r "$PROJECT_ROOT/data/dictionary/"* "$STAGING/data/dictionary/" 2>/dev/null || true
cp -r "$PROJECT_ROOT/data/source_of_truth/"* "$STAGING/data/source_of_truth/" 2>/dev/null || true

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
$SSH "$TARGET" "cd $REMOTE_DIR && docker compose up -d --force-recreate backend"

echo ""
echo "==> Done."
echo "  ssh -i $PK $TARGET"
echo "  cd $REMOTE_DIR && docker compose logs -f"
