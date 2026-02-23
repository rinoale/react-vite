#!/usr/bin/env bash
# Deploy trained category header OCR model + config to a versioned folder, then update symlinks.
# Run from project root after training completes.
#
# Usage:
#   bash scripts/ocr/category_header_model/deploy.sh <version>    # e.g. v1
set -euo pipefail

VERSION="${1:-}"
if [ -z "$VERSION" ]; then
  echo "Usage: bash scripts/ocr/category_header_model/deploy.sh <version>"
  echo "  e.g.: bash scripts/ocr/category_header_model/deploy.sh v1"
  exit 1
fi

DST_DIR="backend/ocr/category_header_model/${VERSION}"
if [ ! -d "$DST_DIR" ]; then
  echo "Error: version directory not found: $DST_DIR" >&2
  echo "Create it first with the training data and config." >&2
  exit 1
fi

# Use exp_name from training config for checkpoint directory
EXP_NAME="header_ocr"
SRC_PTH="saved_models/${EXP_NAME}/best_accuracy.pth"
SRC_YAML="saved_models/custom_header.yaml"
SRC_CHARS="${DST_DIR}/unique_chars.txt"

for f in "$SRC_PTH" "$SRC_YAML" "$SRC_CHARS"; do
  if [ ! -f "$f" ]; then
    echo "Error: $f not found" >&2
    exit 1
  fi
done

cp "$SRC_PTH"  "$DST_DIR/custom_header.pth"
cp "$SRC_YAML" "$DST_DIR/custom_header.yaml"
if [ ! -f "$DST_DIR/custom_header.py" ]; then
  echo "Warning: $DST_DIR/custom_header.py not found, copying from models dir"
  cp "$(readlink -f backend/ocr/models/custom_header.py)" "$DST_DIR/custom_header.py"
fi

echo "Deployed to $DST_DIR/"

# Update symlinks to point to the new version
bash scripts/ocr/switch_model.sh category_header "$VERSION"
