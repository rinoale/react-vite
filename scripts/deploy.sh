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

# ---------------------------------------------------------------------------
# Usage:  ./deploy.sh [--models]
#   --models   Rebuild and transfer the OCR models image (only needed when
#              models change; ~1.3GB transfer).
#   Default    Build backend image + frontend, transfer, and restart.
# ---------------------------------------------------------------------------
PUSH_MODELS=false
for arg in "$@"; do
  case $arg in
    --models) PUSH_MODELS=true ;;
  esac
done

# --- 1. Build frontend ---
echo "==> Building frontend (trade)..."
cd "$PROJECT_ROOT/frontend"
npm run build -w @mabi/trade

# --- 2. Optionally build & push OCR models image ---
if $PUSH_MODELS; then
  echo "==> Building OCR models image (${PLATFORM})..."
  bash "$PROJECT_ROOT/infra/ocr-models/build.sh" "$PLATFORM"

  echo "==> Saving and transferring models image (~1.3GB)..."
  docker save mabi-ocr-models | gzip | \
    $SSH "$TARGET" "cat > /tmp/mabi-ocr-models.tar.gz && docker load < /tmp/mabi-ocr-models.tar.gz && rm /tmp/mabi-ocr-models.tar.gz"
  echo "==> Models image transferred."
fi

# --- 3. Stage build context ---
echo "==> Staging build context..."
STAGING=$(mktemp -d)
trap 'rm -rf "$STAGING"' EXIT

# Backend source (no __pycache__, no .env, no ocr model/training dirs)
rsync -a \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.env*' \
  --exclude='ocr/' \
  "$PROJECT_ROOT/backend/" "$STAGING/backend/"

# Create minimal ocr dir (models are in the Docker image, but backend code
# may reference ocr/__init__.py or similar)
mkdir -p "$STAGING/backend/ocr/models"

# Configs
cp -r "$PROJECT_ROOT/configs" "$STAGING/configs"

# Data (dictionary + source_of_truth only)
mkdir -p "$STAGING/data/dictionary" "$STAGING/data/source_of_truth"
cp -r "$PROJECT_ROOT/data/dictionary/"* "$STAGING/data/dictionary/" 2>/dev/null || true
cp -r "$PROJECT_ROOT/data/source_of_truth/"* "$STAGING/data/source_of_truth/" 2>/dev/null || true

# Frontend dist
cp -r "$PROJECT_ROOT/frontend/packages/trade/dist" "$STAGING/frontend"

# Dockerfile
cp "$PROJECT_ROOT/infra/deploy/Dockerfile" "$STAGING/Dockerfile"

# --- 4. Build backend image (cross-platform) ---
echo "==> Building backend image (${PLATFORM})..."
docker buildx build --platform "$PLATFORM" --load -t mabi-backend:latest "$STAGING"

# --- 5. Transfer backend image ---
echo "==> Saving and transferring backend image..."
docker save mabi-backend:latest | gzip | \
  $SSH "$TARGET" "cat > /tmp/mabi-backend.tar.gz && docker load < /tmp/mabi-backend.tar.gz && rm /tmp/mabi-backend.tar.gz"

# --- 6. Transfer compose + env + nginx ---
echo "==> Syncing config files..."
$SSH "$TARGET" "mkdir -p $REMOTE_DIR/certs"
$SCP "$PROJECT_ROOT/infra/deploy/docker-compose.stg.yml" "$TARGET:$REMOTE_DIR/docker-compose.yml"
$SCP "$ENV_FILE" "$TARGET:$REMOTE_DIR/.env"
$SCP "$PROJECT_ROOT/infra/nginx/stg.conf" "$TARGET:$REMOTE_DIR/nginx.conf"
$SCP "$PROJECT_ROOT/infra/nginx/certs/dev.crt" "$PROJECT_ROOT/infra/nginx/certs/dev.key" "$TARGET:$REMOTE_DIR/certs/"

# --- 7. Restart on server ---
echo "==> Restarting services..."
$SSH "$TARGET" "cd $REMOTE_DIR && docker compose up -d"

echo ""
echo "==> Done."
echo "  ssh -i $PK $TARGET"
echo "  cd $REMOTE_DIR && docker compose logs -f"
