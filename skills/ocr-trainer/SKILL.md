---
name: ocr-trainer
description: Guide and tools for training custom EasyOCR models using synthetic game data. Use when you need to improve OCR accuracy for specific game fonts or UI elements.
---

# OCR Trainer Skill

This skill helps you train a custom OCR model (EasyOCR/ClovaAI) to recognize text in your specific game font (e.g., Mabinogi).

## Prerequisites

1.  **Python Environment:** Ensure Python 3.8+ is installed.
2.  **GPU (Highly Recommended):** Training on CPU is extremely slow. Use a machine with NVIDIA GPU + CUDA.
3.  **Dependencies:**
    ```bash
    pip install fire lmdb opencv-python nltk natsort torch torchvision
    ```

## Workflow

### 1. Generate Training Data
Run the generation script from the **project root**:
```bash
python3 scripts/generate_training_data.py
```
- Uses `data/fonts/mabinogi_classic.ttf` (the actual game font)
- Reads dictionaries from `data/dictionary/reforging_options.txt` and `data/dictionary/tooltip_general.txt`
- Generates black-text-on-white-background images in `backend/train_data/`
- Structure: `images/*.png` + `labels/*.txt`

### 2. Create LMDB Dataset
EasyOCR requires data in LMDB format. Use the provided script to convert your images/labels.

```bash
python3 skills/ocr-trainer/scripts/create_lmdb_dataset.py \
  --input backend/train_data \
  --output backend/train_data_lmdb
```

### 3. Setup Training Repository
The `deep-text-recognition-benchmark` repo should already be present in the project root. If not:

```bash
git clone https://github.com/ClovaAI/deep-text-recognition-benchmark.git
```

**Important patch:** In `deep-text-recognition-benchmark/train.py`, the `--sensitive` flag block (around line 287-289) must NOT override `opt.character`. It should just `pass` to preserve label case without replacing the character set.

### 4. Run Training

```bash
cd deep-text-recognition-benchmark

python3 train.py \
    --train_data ../backend/train_data_lmdb \
    --valid_data ../backend/train_data_lmdb \
    --select_data / \
    --batch_ratio 1.0 \
    --Transformation TPS \
    --FeatureExtraction ResNet \
    --SequenceModeling BiLSTM \
    --Prediction CTC \
    --batch_max_length 30 \
    --imgH 32 --imgW 100 \
    --num_iter 10000 \
    --valInterval 500 \
    --batch_size 64 \
    --workers 0 \
    --sensitive \
    --PAD \
    --character "$(cat ../backend/unique_chars.txt | tr -d '\n')"
```

**Critical flags explained:**
- `--workers 0` — LMDB datasets cannot be pickled for multiprocessing. Without this you get `TypeError: cannot pickle 'Environment' object`.
- `--sensitive` — Preserves label case. Without it, `dataset.py` lowercases labels, breaking uppercase characters (R, G, B, L, A-F) that exist in the character set.
- `--PAD` — Uses `keep_ratio_with_pad` preprocessing to match EasyOCR's inference behavior. Without it, training stretches images while inference pads them, causing a preprocessing mismatch.
- `--batch_max_length 30` — Longest label in the dictionary is 29 characters.
- `--character` — Must pass the full 442-character Korean set from `unique_chars.txt`.

*Adjust `batch_size` based on your VRAM. On RTX 3070 Ti, 64 works well. 10,000 iterations takes ~29 minutes.*

### 5. Deploy Custom Model
Once training is complete, `best_accuracy.pth` will be in `saved_models/TPS-ResNet-BiLSTM-CTC-Seed1111/`.

```bash
cp saved_models/TPS-ResNet-BiLSTM-CTC-Seed1111/best_accuracy.pth \
   ../backend/models/custom_mabinogi.pth
```

The backend (`backend/main.py`) already loads the model:
```python
reader = easyocr.Reader(
    ['ko'],
    model_storage_directory=MODELS_DIR,
    user_network_directory=MODELS_DIR,
    recog_network='custom_mabinogi'
)
```

## Troubleshooting

- **Out of Memory:** Reduce `--batch_size`.
- **Low Accuracy:** Check training images visually. Ensure labels match images. Increase `--num_iter`.
- **`TypeError: cannot pickle 'Environment' object`:** Add `--workers 0`.
- **`KeyError` on single character:** Add `--sensitive` to prevent label lowercasing.
- **High training accuracy but poor real-world results:** Ensure `--PAD` flag is set. See `OCR_TRAINING_HISTORY.md` for full history of issues encountered.
