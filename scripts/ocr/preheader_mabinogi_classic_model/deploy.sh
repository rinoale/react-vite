#!/usr/bin/env bash
# Deploy trained preheader_mabinogi_classic OCR model + config to a versioned folder, then update symlinks.
# Run from project root after training completes.
#
# Usage:
#   bash scripts/ocr/preheader_mabinogi_classic_model/deploy.sh <version>    # e.g. v1
set -euo pipefail

VERSION="${1:-}"
if [ -z "$VERSION" ]; then
  echo "Usage: bash scripts/ocr/preheader_mabinogi_classic_model/deploy.sh <version>"
  echo "  e.g.: bash scripts/ocr/preheader_mabinogi_classic_model/deploy.sh v1"
  exit 1
fi

DST_DIR="backend/ocr/preheader_mabinogi_classic_model/${VERSION}"
if [ ! -d "$DST_DIR" ]; then
  echo "Error: version directory not found: $DST_DIR" >&2
  echo "Create it first with the training data and config." >&2
  exit 1
fi

# Use exp_name from training config for checkpoint directory
EXP_NAME="preheader_mabinogi_classic_ocr_${VERSION}"
SRC_PTH="saved_models/${EXP_NAME}/best_accuracy.pth"
SRC_YAML="saved_models/custom_preheader_mabinogi_classic.yaml"
SRC_CHARS="${DST_DIR}/unique_chars.txt"

for f in "$SRC_PTH" "$SRC_YAML" "$SRC_CHARS"; do
  if [ ! -f "$f" ]; then
    echo "Error: $f not found" >&2
    exit 1
  fi
done

cp "$SRC_PTH"  "$DST_DIR/custom_preheader_mabinogi_classic.pth"
cp "$SRC_YAML" "$DST_DIR/custom_preheader_mabinogi_classic.yaml"
# Copy the .py model file from version folder (already there from setup)
if [ ! -f "$DST_DIR/custom_preheader_mabinogi_classic.py" ]; then
  echo "Warning: $DST_DIR/custom_preheader_mabinogi_classic.py not found, copying from models dir"
  cp "$(readlink -f backend/ocr/models/custom_preheader_mabinogi_classic.py)" "$DST_DIR/custom_preheader_mabinogi_classic.py"
fi

echo "Deployed to $DST_DIR/"

# Update symlinks to point to the new version
bash scripts/ocr/switch_model.sh preheader_mabinogi_classic "$VERSION"
