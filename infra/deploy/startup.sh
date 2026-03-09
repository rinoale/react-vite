#!/bin/bash
set -e

# Link OCR models from separate volume into backend
mkdir -p /app/backend/ocr
ln -sfn /models /app/backend/ocr/models

echo "==> Running migrations..."
alembic upgrade head

echo "==> Importing dictionaries..."
python /app/scripts/db/import_dictionaries.py \
  --db-host "$DB_HOST" \
  --db-port "$DB_PORT" \
  --db-name "$DB_NAME" \
  --db-user "$DB_USER" \
  --db-password "$DB_PASSWORD" \
  --enchant-path /app/data/source_of_truth/enchant.yaml \
  --effects-path /app/data/source_of_truth/effects.txt \
  --reforge-path /app/data/dictionary/reforge.txt \
  --item-names-path /app/data/dictionary/item_name.txt

echo "==> Exporting frontend configs..."
export FRONTEND_DIST_DIR=/app/frontend
python /app/scripts/frontend/configs/export_all.py

echo "==> Starting server..."
exec uvicorn main:app --host 0.0.0.0 --port 8000
