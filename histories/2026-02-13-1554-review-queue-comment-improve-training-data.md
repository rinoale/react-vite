# Review Queue and Comment Archive

Archived from `AI_SYNC.md` on 2026-02-13.

## Review Queue

- 2026-02-13T14:30:00Z: **Attempt 9 generator fixes** (file: `scripts/generate_training_data.py`)
  1. Revert canvas width to always ~260px. Remove proportional/tight-crop logic (the 60% short-text branch). Real crops are 95.4% full-width regardless of text length.
  2. Keep font size 8 on full 260px canvas. This produces correct 4.6-5.2x squash factor matching real h=8-9 crops.
  3. Adjust `FONT_SIZES` distribution to match real bimodal heights: ~28% size 8 (h=8-9px) and ~63% size 10-11 (h=14-15px). Current `[8,8,9,9,10,10,11]` over-produces h=12-13px (45% of training) which doesn't exist in real data. Proposed: `[8,8,8,8,10,10,10,10,10,10,11,11,11,11]` (~28% size 8, ~72% size 10-11).
  4. Acceptance check: verify synthetic image dimensions cluster at h=8-9 and h=14-15 with widths 250-270px. No h=12-13 cluster.

## Comment

- 2026-02-13T15:25:00Z (Codex): Suggested runbook commands for Attempt 9
```bash
# 1) Regenerate synthetic data after generator edits
rm -rf backend/train_data backend/train_data_lmdb
python3 scripts/generate_training_data.py

# 2) Build LMDB
python3 skills/ocr-trainer/scripts/create_lmdb_dataset.py \
  --input backend/train_data \
  --output backend/train_data_lmdb

# 3) Train Attempt 9 (Stage 1 synthetic-only)
python3 -u deep-text-recognition-benchmark/train.py \
  --train_data backend/train_data_lmdb \
  --valid_data backend/train_data_lmdb \
  --select_data / --batch_ratio 1 \
  --Transformation TPS --FeatureExtraction ResNet \
  --SequenceModeling BiLSTM --Prediction CTC \
  --sensitive --PAD --workers 0 \
  --batch_max_length 55 --batch_size 64 \
  --character "$(cat backend/unique_chars.txt | tr -d '\n')" \
  --num_iter 10000 --valInterval 500 \
  --imgH 32 --imgW 200 \
  > training_attempt9.log 2>&1

# 4) Deploy best model to backend
cp saved_models/TPS-ResNet-BiLSTM-CTC-Seed1111/best_accuracy.pth backend/models/custom_mabinogi.pth

# 5) Evaluate on 5 GT images (v2 pipeline)
python3 scripts/test_v2_pipeline.py -q
```

- 2026-02-13T15:25:00Z (Codex): Quick distribution check command (run after step 1)
```bash
python3 - <<'PY'
import os, random, numpy as np
from PIL import Image
files=[f for f in os.listdir('backend/train_data/images') if f.endswith('.png')]
random.seed(0); files=random.sample(files, min(3000, len(files)))
wh=[Image.open(os.path.join('backend/train_data/images',f)).size for f in files]
w=np.array([x for x,_ in wh]); h=np.array([y for _,y in wh])
print('n=',len(files))
print('width  p25/med/p75=',np.percentile(w,25),np.median(w),np.percentile(w,75))
print('height p25/med/p75=',np.percentile(h,25),np.median(h),np.percentile(h,75))
print('width>220 ratio=',float((w>220).mean()))
PY
```

