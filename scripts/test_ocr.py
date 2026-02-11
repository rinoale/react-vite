import sys
import os
import argparse
# Add backend to path so we can import the splitter
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from tooltip_line_splitter import TooltipLineSplitter
import easyocr
import shutil

def test_pipeline(image_path):
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

    # Run OCR
    print("Running readtext on image...")
    results = reader.readtext(image_path)

    print(f"\nDetected {len(results)} text regions.")
    print("\n--- Expected Text ---")

    # Load ground truth for comparison
    gt_path = image_path.replace('.png', '.txt').replace('images', 'labels')
    gt_lines = []
    if os.path.exists(gt_path):
        with open(gt_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                print(f"  [{i+1:2d}] '{line.strip()}'")

    print("\n--- Extracted Text ---")
    for i, (bbox, text, prob) in enumerate(results):
        print(f"  [{i+1:2d}] '{text}' (Conf: {prob:.4f})")

    print("\n----------------------")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Test OCR on a specific image')
    parser.add_argument('image_path', help='Path to the image file to test')
    args = parser.parse_args()
    test_pipeline(args.image_path)
