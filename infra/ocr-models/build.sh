#!/bin/bash
# Build the OCR models Docker image.
# Resolves symlinks so the image contains only real model files (~1.3GB).
#
# Usage: bash build.sh [platform]
#   platform   e.g. linux/arm64 (default: local platform)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MODELS_SRC="$PROJECT_ROOT/backend/ocr/models"
PLATFORM="${1:-}"

STAGING=$(mktemp -d)
trap 'rm -rf "$STAGING"' EXIT

echo "==> Staging model files (resolving symlinks)..."
# cp -L follows symlinks, copies real files
cp -rL "$MODELS_SRC" "$STAGING/models"
rm -rf "$STAGING/models/__pycache__"

echo "==> Staging data files..."
DATA_SRC="$PROJECT_ROOT/data"
mkdir -p "$STAGING/data"
cp -r "$DATA_SRC/dictionary" "$STAGING/data/"
cp -r "$DATA_SRC/source_of_truth" "$STAGING/data/"
cp -r "$DATA_SRC/fonts" "$STAGING/data/"

echo "==> Building mabi-ocr-models image..."
if [ -n "$PLATFORM" ]; then
  docker buildx build --platform "$PLATFORM" --load -t mabi-ocr-models -f "$SCRIPT_DIR/Dockerfile" "$STAGING"
else
  docker build -t mabi-ocr-models -f "$SCRIPT_DIR/Dockerfile" "$STAGING"
fi

echo "==> Done. Image: mabi-ocr-models"
docker images mabi-ocr-models --format '  Size: {{.Size}}'
