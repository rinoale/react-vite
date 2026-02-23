#!/usr/bin/env bash
#
# Convenience wrapper: merge corrections → create model config → create LMDB → print train command
#
# Usage:
#   bash scripts/ocr/retrain_with_corrections.sh \
#       --model general_mabinogi_classic \
#       --base-version a19 --new-version a19.1 \
#       --duplication 3
#
set -euo pipefail

MODEL=""
BASE_VERSION=""
NEW_VERSION=""
DUPLICATION=3

while [[ $# -gt 0 ]]; do
    case "$1" in
        --model)       MODEL="$2"; shift 2 ;;
        --base-version) BASE_VERSION="$2"; shift 2 ;;
        --new-version)  NEW_VERSION="$2"; shift 2 ;;
        --duplication)  DUPLICATION="$2"; shift 2 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

if [[ -z "$MODEL" || -z "$BASE_VERSION" || -z "$NEW_VERSION" ]]; then
    echo "Usage: $0 --model <type> --base-version <ver> --new-version <ver> [--duplication N]"
    exit 1
fi

# Map model type to script directory name
MODEL_DIR="${MODEL}_model"

echo "=== Step 1: Merge corrections ==="
python3 scripts/ocr/merge_corrections.py \
    --model "$MODEL" \
    --base-version "$BASE_VERSION" \
    --new-version "$NEW_VERSION" \
    --duplication "$DUPLICATION"

echo ""
echo "=== Step 2: Generate model config ==="
python3 "scripts/ocr/${MODEL_DIR}/create_model_config.py" --version "$NEW_VERSION"

echo ""
echo "=== Step 3: Create LMDB dataset ==="
python3 skills/ocr-trainer/scripts/create_lmdb_dataset.py \
    --input "backend/ocr/${MODEL_DIR}/${NEW_VERSION}/train_data" \
    --output "backend/ocr/${MODEL_DIR}/${NEW_VERSION}/train_data_lmdb"

echo ""
echo "=== Ready to train ==="
echo "Run the following command in a separate terminal (to avoid OOM kills):"
echo ""
echo "  nohup python3 -u scripts/ocr/${MODEL_DIR}/train.py \\"
echo "      --version ${NEW_VERSION} --resume \\"
echo "      > logs/training_${MODEL_DIR}_${NEW_VERSION}.log 2>&1 &"
echo ""
echo "Monitor: tail -f logs/training_${MODEL_DIR}_${NEW_VERSION}.log"
