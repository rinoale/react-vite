#!/bin/bash
# Run a local GPU worker connected to staging via SSH tunnel.
#
# Usage:
#   bash scripts/worker/run-remote.sh              # gpu queue only
#   bash scripts/worker/run-remote.sh default gpu   # both queues
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Load deploy config for SSH credentials
DEPLOY_CONF="$PROJECT_ROOT/scripts/deploy/deploy.staging.env"
if [ ! -f "$DEPLOY_CONF" ]; then
  echo "Error: $DEPLOY_CONF not found."
  exit 1
fi
source "$DEPLOY_CONF"

# Load staging .env for REDIS_PASSWORD and DB_PASSWORD
if [ ! -f "$ENV_FILE" ]; then
  echo "Error: $ENV_FILE not found."
  exit 1
fi

QUEUES="${@:-gpu}"

LOCAL_REDIS_PORT=16379
LOCAL_DB_PORT=15432

echo "==> Opening SSH tunnel to $TARGET..."
echo "    Redis: localhost:$LOCAL_REDIS_PORT -> remote:6379"
echo "    DB:    localhost:$LOCAL_DB_PORT -> remote:5432"

ssh -i "$PK" \
  -L "$LOCAL_REDIS_PORT:localhost:6379" \
  -L "$LOCAL_DB_PORT:localhost:5432" \
  -N -f "$TARGET"

SSH_PID=$!
trap "echo '==> Closing SSH tunnel...'; kill $SSH_PID 2>/dev/null; exit" EXIT INT TERM

# Wait for tunnel
sleep 1

echo "==> Starting worker (queues: $QUEUES)..."
cd "$PROJECT_ROOT/backend"

# Load all staging env vars, then override connection settings for tunnel
set -a
source "$ENV_FILE"
set +a

REDIS_HOST=localhost \
REDIS_PORT=$LOCAL_REDIS_PORT \
DB_HOST=localhost \
DB_PORT=$LOCAL_DB_PORT \
  python worker.py --queues $QUEUES
