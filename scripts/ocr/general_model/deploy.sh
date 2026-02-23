#!/usr/bin/env bash
# Deploy trained OCR model + config to a versioned folder, then update symlinks.
# Run from project root after training completes.
#
# Usage:
#   bash scripts/ocr/general_model/deploy.sh <version>    # e.g. a19
#   Copies saved_models/ artifacts into backend/ocr/general_model/<version>/
#   and updates symlinks via switch_model.sh.
set -euo pipefail

VERSION="${1:-}"
if [ -z "$VERSION" ]; then
  echo "Usage: bash scripts/ocr/general_model/deploy.sh <version>"
  echo "  e.g.: bash scripts/ocr/general_model/deploy.sh a19"
  exit 1
fi

DST_DIR="backend/ocr/general_model/${VERSION}"
if [ ! -d "$DST_DIR" ]; then
  echo "Error: version directory not found: $DST_DIR" >&2
  echo "Create it first with the training data and config." >&2
  exit 1
fi

SRC_PTH="saved_models/TPS-ResNet-BiLSTM-CTC-Seed1111/best_accuracy.pth"
SRC_YAML="saved_models/custom_mabinogi.yaml"
SRC_CHARS="${DST_DIR}/unique_chars.txt"
SRC_PY="backend/ocr/models/custom_mabinogi.py"

for f in "$SRC_PTH" "$SRC_YAML" "$SRC_CHARS"; do
  if [ ! -f "$f" ]; then
    echo "Error: $f not found" >&2
    exit 1
  fi
done

cp "$SRC_PTH"  "$DST_DIR/custom_mabinogi.pth"
cp "$SRC_YAML" "$DST_DIR/custom_mabinogi.yaml"
# Resolve symlink to get the actual .py file
cp "$(readlink -f "$SRC_PY")" "$DST_DIR/custom_mabinogi.py"

echo "Deployed to $DST_DIR/"

# Update symlinks to point to the new version
bash scripts/ocr/switch_model.sh general "$VERSION"
