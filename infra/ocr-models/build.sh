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

# Remove unnecessary files
rm -rf "$STAGING/models/__pycache__"

echo "==> Building mabi-ocr-models image..."
if [ -n "$PLATFORM" ]; then
  docker buildx build --platform "$PLATFORM" --load -t mabi-ocr-models -f "$SCRIPT_DIR/Dockerfile" "$STAGING"
else
  docker build -t mabi-ocr-models -f "$SCRIPT_DIR/Dockerfile" "$STAGING"
fi

echo "==> Done. Image: mabi-ocr-models"
docker images mabi-ocr-models --format '  Size: {{.Size}}'
