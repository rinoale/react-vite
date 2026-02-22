#!/usr/bin/env bash
# Deploy trained OCR model + config to production paths.
# Run from project root after training completes.
set -euo pipefail

SRC_PTH="saved_models/TPS-ResNet-BiLSTM-CTC-Seed1111/best_accuracy.pth"
SRC_YAML="saved_models/custom_mabinogi.yaml"
DST_DIR="backend/ocr/models"

for f in "$SRC_PTH" "$SRC_YAML"; do
  if [ ! -f "$f" ]; then
    echo "Error: $f not found" >&2
    exit 1
  fi
done

cp "$SRC_PTH" "$DST_DIR/custom_mabinogi.pth"
cp "$SRC_YAML" "$DST_DIR/custom_mabinogi.yaml"
echo "Deployed model + config to $DST_DIR/"
