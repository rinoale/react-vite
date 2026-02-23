#!/usr/bin/env python3
"""OCR oreo_flipped enchant header crops using the enchant header model.

Takes image files (already preprocessed black-on-white crops) and runs
the enchant header OCR model on each.

Usage (from project root):
    python3 scripts/ocr/enchant_header_model/test_ocr.py tmp/enchant_header_samples2/*.png
    python3 scripts/ocr/enchant_header_model/test_ocr.py tmp/enchant_header_samples2/293_enchant_hdr.png
"""

import glob
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'backend'))

from lib.tooltip_segmenter import init_enchant_header_reader

MODELS_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'backend', 'ocr', 'models')


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/ocr/enchant_header_model/test_ocr.py <image>...")
        sys.exit(1)

    # Expand globs
    paths = []
    for arg in sys.argv[1:]:
        expanded = sorted(glob.glob(arg))
        paths.extend(expanded if expanded else [arg])

    print("Loading enchant header reader...")
    reader = init_enchant_header_reader(models_dir=os.path.abspath(MODELS_DIR))
    print(f"Processing {len(paths)} image(s)...\n")

    for path in paths:
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            print(f"  {os.path.basename(path):40s}  FAILED to load")
            continue

        h, w = img.shape
        result = reader.recognize(img, horizontal_list=[[0, w, 0, h]], free_list=[])

        if result:
            text, conf = result[0][1], result[0][2]
            print(f"  {os.path.basename(path):40s}  {w:3d}x{h}  conf={conf:.3f}  → {text}")
        else:
            print(f"  {os.path.basename(path):40s}  {w:3d}x{h}  (no result)")


if __name__ == "__main__":
    main()
