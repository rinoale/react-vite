#!/usr/bin/env bash
# Create symbolic links for large data volumes that live outside the repo.
#
# Usage:
#   bash scripts/backend/link_data.sh [DATA_ROOT]
#
# DATA_ROOT defaults to ~/workspace/ocr_training_data/mabinogi
# Expected layout under DATA_ROOT:
#   ocr/   → linked as backend/ocr
#   data/  → linked as <project_root>/data

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DATA_ROOT="${1:-$HOME/workspace/ocr_training_data/mabinogi}"

LINKS=(
  "backend/ocr:ocr"
  "data:data"
)

for entry in "${LINKS[@]}"; do
  link="${PROJECT_ROOT}/${entry%%:*}"
  target="${DATA_ROOT}/${entry##*:}"

  if [ -L "$link" ]; then
    echo "  skip  $link → $(readlink "$link") (already exists)"
    continue
  fi

  if [ -e "$link" ]; then
    echo "  WARN  $link exists but is not a symlink — skipping"
    continue
  fi

  if [ ! -e "$target" ]; then
    echo "  WARN  target $target does not exist — skipping"
    continue
  fi

  ln -s "$target" "$link"
  echo "  link  $link → $target"
done

echo "Done."
