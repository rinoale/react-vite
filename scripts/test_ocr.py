#!/usr/bin/env python3
"""
Run the v2 OCR pipeline on a single image and print recognized text.

Usage:
    python3 scripts/test_ocr.py <image_path>
    python3 scripts/test_ocr.py data/sample_images/lightarmor_processed_3.png
"""

import os
import sys
import argparse

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'backend'))

from mabinogi_tooltip_parser import MabinogiTooltipParser
from ocr_utils import patch_reader_imgw

MODELS_DIR  = os.path.join(PROJECT_ROOT, 'backend', 'models')
CONFIG_PATH = os.path.join(PROJECT_ROOT, 'configs', 'mabinogi_tooltip.yaml')


def main():
    parser = argparse.ArgumentParser(description='Run v2 OCR pipeline on a single image')
    parser.add_argument('image', help='Path to tooltip image (preprocessed binary PNG)')
    args = parser.parse_args()

    if not os.path.exists(args.image):
        print(f"Error: image not found: {args.image}")
        sys.exit(1)

    import easyocr
    reader = easyocr.Reader(
        ['ko'],
        model_storage_directory=MODELS_DIR,
        user_network_directory=MODELS_DIR,
        recog_network='custom_mabinogi',
        verbose=False,
    )
    patch_reader_imgw(reader, MODELS_DIR)

    import cv2
    import numpy as np
    img = cv2.imread(args.image)
    h, w = img.shape[:2]

    # Small single-line crop (synthetic training image or splitter output):
    # skip the line splitter and recognize the whole image directly.
    if h < 40 or w < 100:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        results = reader.recognize(gray, horizontal_list=[[0, w, 0, h]], free_list=[])
        for _, text, conf in results:
            print(f"{text}  (conf={conf:.3f})")
    else:
        tooltip = MabinogiTooltipParser(config_path=CONFIG_PATH)
        result = tooltip.parse_tooltip(args.image, reader)
        for line in result['all_lines']:
            print(f"{line['text']}  (conf={line['confidence']:.3f})")


if __name__ == '__main__':
    main()
