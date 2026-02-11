# Mabinogi Item Trade Website

A specialized marketplace for trading in-game items with automated OCR (Optical Character Recognition) item registration and smart recommendation system.

## 🚀 Features

*   **OCR Item Registration:** Upload item screenshots to automatically fill in stats and details.
*   **Smart Marketplace:** Search items by specific attributes (e.g., "Fire Damage > 50").
*   **Recommendations:** Content-based filtering suggests items based on search and purchase history.
*   **Custom OCR Training:** Tooling to train EasyOCR on Mabinogi's specific game font.

## 🛠️ Tech Stack

*   **Frontend:** React, Vite, Tailwind CSS
*   **Backend:** Python, FastAPI, EasyOCR, scikit-learn
*   **Database:** (Mocked/SQLite)
*   **OCR:** EasyOCR (with custom trained model capabilities)

## 📂 Project Structure

```
├── backend/            # FastAPI server & OCR logic
├── data/               # Fonts and Dictionaries (Not committed)
├── scripts/            # Helper scripts (Data Gen, Testing, Config)
├── skills/             # Gemini CLI Skills (OCR Trainer)
├── src/                # React Frontend
└── README.md
```

## ⚡ Quick Start

### 1. Backend Setup

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 2. Frontend Setup

```bash
npm install
npm run dev
```

Visit `http://localhost:5173` to browse the marketplace.

---

## 📜 Scripts & Utilities

This project includes several helper scripts in the `scripts/` directory to help with development and OCR model training.

**Note:** Always run these scripts from the **project root directory**.

### 1. Generate Training Data (`scripts/generate_training_data.py`)
Generates synthetic training images using the Mabinogi font and a dictionary of item options.

```bash
# Generates images in backend/train_data/
python3 scripts/generate_training_data.py
```

### 2. Test OCR Pipeline (`scripts/test_ocr.py`)
Runs EasyOCR with the custom trained model directly on a sample image. Useful for evaluating OCR accuracy.

```bash
python3 scripts/test_ocr.py
```

### 3. Check Image Stats (`scripts/check_image_stats.py`)
Simple utility to print the dimensions and mean brightness of an image. Used to debug why OCR might be failing on dark screenshots.

```bash
python3 scripts/check_image_stats.py
```

### 4. Test Line Splitter (`scripts/test_line_splitter.py`)
Splits a tooltip image into individual text line images using horizontal projection profiling. Useful for visually verifying that line detection is working correctly.

```bash
python3 scripts/test_line_splitter.py <image_path> <output_dir>

# Example
python3 scripts/test_line_splitter.py data/sample_images/lightarmor_processed_2.png test_split_output
```

The output directory will contain:
- `*_line_001.png`, `*_line_002.png`, ... — cropped line images
- `*_visualization.png` — original image with detected line bounding boxes

### 5. Create Model Config (`scripts/create_model_config.py`)
Generates the YAML configuration file required by EasyOCR to load a custom trained model. Reads characters from `backend/unique_chars.txt`.

```bash
python3 scripts/create_model_config.py
```

---

## 🧠 Training Custom OCR Model

To improve OCR accuracy for Mabinogi fonts, use the included **OCR Trainer Skill**.

1.  **Generate Data:** `python3 scripts/generate_training_data.py`
2.  **Create LMDB:**
    ```bash
    python3 skills/ocr-trainer/scripts/create_lmdb_dataset.py --input backend/train_data --output backend/train_data_lmdb
    ```
3.  **Train:** See `skills/ocr-trainer/SKILL.md` for the full training command. Critical flags: `--sensitive --PAD --workers 0 --batch_max_length 30`.
4.  **Deploy:** `cp deep-text-recognition-benchmark/saved_models/TPS-ResNet-BiLSTM-CTC-Seed1111/best_accuracy.pth backend/models/custom_mabinogi.pth`

For training history and known pitfalls, see `OCR_TRAINING_HISTORY.md`.