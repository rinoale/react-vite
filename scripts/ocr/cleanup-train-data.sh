#!/bin/bash
# Remove train_data and train_data_lmdb from inactive model versions.
# Active versions (determined by symlinks in backend/ocr/models/) are preserved.
#
# Usage:
#   bash scripts/ocr/cleanup-train-data.sh          # dry run (show what would be deleted)
#   bash scripts/ocr/cleanup-train-data.sh --force   # actually delete
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
OCR_DIR="$PROJECT_ROOT/backend/ocr"
MODELS_DIR="$OCR_DIR/models"

DRY_RUN=true
[ "${1:-}" = "--force" ] && DRY_RUN=false

# Build set of active model_type/version from symlinks
declare -A ACTIVE
for link in "$MODELS_DIR"/*.pth; do
  target=$(readlink -f "$link" 2>/dev/null) || continue
  # e.g. .../backend/ocr/enchant_header_model/v3/custom_enchant_header.pth
  version=$(basename "$(dirname "$target")")
  model_type=$(basename "$(dirname "$(dirname "$target")")")
  # Only track *_model directories (skip self-referencing symlinks like craft_mlt_25k.pth)
  [[ "$model_type" == *_model ]] || continue
  ACTIVE["$model_type/$version"]=1
done

echo "Active versions:"
for key in $(echo "${!ACTIVE[@]}" | tr ' ' '\n' | sort); do
  echo "  $key"
done
echo ""

targets=()

for model_dir in "$OCR_DIR"/*_model; do
  model_type=$(basename "$model_dir")
  for version_dir in "$model_dir"/*/; do
    version=$(basename "$version_dir")
    key="$model_type/$version"

    if [ -n "${ACTIVE[$key]:-}" ]; then
      continue
    fi

    for subdir in train_data train_data_lmdb; do
      target="$version_dir$subdir"
      [ -d "$target" ] || continue
      size_h=$(du -sh "$target" | cut -f1)
      targets+=("$target")

      if $DRY_RUN; then
        echo "[dry run] would delete: $key/$subdir ($size_h)"
      else
        echo "deleting: $key/$subdir ($size_h)"
        rm -rf "$target"
      fi
    done
  done
done

echo ""
if [ ${#targets[@]} -eq 0 ]; then
  echo "Nothing to clean up."
elif $DRY_RUN; then
  total_h=$(du -shc "${targets[@]}" | tail -1 | cut -f1)
  echo "Would free: $total_h (${#targets[@]} directories)"
  echo "Run with --force to delete."
else
  echo "Freed ${#targets[@]} directories."
fi
