import sys
import os
# Add backend to path so we can import the splitter
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from tooltip_line_splitter import TooltipLineSplitter
import easyocr
import shutil

def test_pipeline():
    image_path = "data/sample_images/lightarmor_processed_2.png"

    if not os.path.exists(image_path):
        print(f"Error: Image not found at {image_path}")
        return

    print(f"Testing OCR on: {image_path}")

    # Initialize EasyOCR
    print("Loading EasyOCR model...")
    BASE_DIR = os.path.join(os.getcwd(), 'backend')
    MODELS_DIR = os.path.join(BASE_DIR, 'models')

    reader = easyocr.Reader(
        ['ko'],
        model_storage_directory=MODELS_DIR,
        user_network_directory=MODELS_DIR,
        recog_network='custom_mabinogi'
    )

    # Run OCR directly on the full image (let CRAFT handle text detection)
    print("Running readtext on full image...")
    results = reader.readtext(image_path)

    print(f"\nDetected {len(results)} text regions.")
    print("\n--- Extracted Text ---")

    # Load ground truth for comparison
    gt_path = image_path.replace('.png', '').replace('_processed_2', '_sarajin_gwejuk_refined_majestic_for_male') + '.txt'
    gt_lines = []
    if os.path.exists(gt_path):
        with open(gt_path, 'r', encoding='utf-8') as f:
            gt_lines = [line.strip() for line in f if line.strip()]
        print(f"Ground truth: {len(gt_lines)} lines")

    for i, (bbox, text, prob) in enumerate(results):
        print(f"  [{i+1:2d}] '{text}' (Conf: {prob:.4f})")

    print("\n----------------------")

if __name__ == "__main__":
    test_pipeline()
