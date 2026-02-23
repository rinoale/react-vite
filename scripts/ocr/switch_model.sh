#!/usr/bin/env bash
# Switch active OCR model version by updating symlinks in backend/ocr/models/.
# Usage:
#   bash scripts/ocr/switch_model.sh general <version>          # e.g. a18
#   bash scripts/ocr/switch_model.sh category_header <version>  # e.g. v1
#   bash scripts/ocr/switch_model.sh enchant_header <version>   # e.g. v1
set -euo pipefail

MODEL_TYPE="${1:-}"
VERSION="${2:-}"
MODELS_DIR="backend/ocr/models"

if [ -z "$MODEL_TYPE" ] || [ -z "$VERSION" ]; then
  echo "Usage: bash scripts/ocr/switch_model.sh <model_type> <version>"
  echo "  model_type: general | category_header | enchant_header"
  echo "  version:    e.g. a18, v1, v2"
  exit 1
fi

update_symlink() {
  local target="$1"    # relative symlink target (relative to link location)
  local link="$2"      # link path
  local real_path
  real_path="$(dirname "$link")/$target"
  if [ ! -e "$real_path" ]; then
    echo "Error: target does not exist: $real_path" >&2
    exit 1
  fi
  rm -f "$link"
  ln -s "$target" "$link"
}

case "$MODEL_TYPE" in
  general)
    SRC_DIR="../general_model/${VERSION}"
    REAL_DIR="backend/ocr/general_model/${VERSION}"
    if [ ! -d "$REAL_DIR" ]; then
      echo "Error: version directory not found: $REAL_DIR" >&2
      exit 1
    fi
    update_symlink "${SRC_DIR}/custom_mabinogi.pth"  "${MODELS_DIR}/custom_mabinogi.pth"
    update_symlink "${SRC_DIR}/custom_mabinogi.py"   "${MODELS_DIR}/custom_mabinogi.py"
    update_symlink "${SRC_DIR}/custom_mabinogi.yaml" "${MODELS_DIR}/custom_mabinogi.yaml"
    echo "Switched general model → ${VERSION}"
    ;;
  category_header)
    SRC_DIR="../category_header_model/${VERSION}"
    REAL_DIR="backend/ocr/category_header_model/${VERSION}"
    if [ ! -d "$REAL_DIR" ]; then
      echo "Error: version directory not found: $REAL_DIR" >&2
      exit 1
    fi
    update_symlink "${SRC_DIR}/custom_header.pth"  "${MODELS_DIR}/custom_header.pth"
    update_symlink "${SRC_DIR}/custom_header.py"   "${MODELS_DIR}/custom_header.py"
    update_symlink "${SRC_DIR}/custom_header.yaml" "${MODELS_DIR}/custom_header.yaml"
    echo "Switched category_header model → ${VERSION}"
    ;;
  enchant_header)
    SRC_DIR="../enchant_header_model/${VERSION}"
    REAL_DIR="backend/ocr/enchant_header_model/${VERSION}"
    if [ ! -d "$REAL_DIR" ]; then
      echo "Error: version directory not found: $REAL_DIR" >&2
      exit 1
    fi
    update_symlink "${SRC_DIR}/custom_enchant_header.pth"  "${MODELS_DIR}/custom_enchant_header.pth"
    update_symlink "${SRC_DIR}/custom_enchant_header.py"   "${MODELS_DIR}/custom_enchant_header.py"
    update_symlink "${SRC_DIR}/custom_enchant_header.yaml" "${MODELS_DIR}/custom_enchant_header.yaml"
    echo "Switched enchant_header model → ${VERSION}"
    ;;
  *)
    echo "Unknown model type: $MODEL_TYPE" >&2
    echo "Valid types: general, category_header, enchant_header" >&2
    exit 1
    ;;
esac

echo "Symlinks in ${MODELS_DIR}/:"
ls -la "${MODELS_DIR}/" | grep '^l'
