#!/usr/bin/env python3
"""
Preview enchant header training image rendering for a given text string.

Generates VARIATIONS (3) images using the same rendering pipeline
as generate_training_data.py, saving them to the specified output directory.

Usage (from project root):
    python3 scripts/ocr/enchant_header_model/preview_render.py "[접두] 사라진 (랭크 5)" /tmp/preview_enchant
    python3 scripts/ocr/enchant_header_model/preview_render.py "[접미] 성단 (랭크 A)" /tmp/preview_enchant
"""

import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from scripts.ocr.lib.render_utils import render_enchant_header

FONT_PATH = "data/fonts/NanumGothicBold.ttf"
FONT_SIZE = 11
VARIATIONS = 3


def main():
    parser = argparse.ArgumentParser(description='Preview enchant header rendering')
    parser.add_argument('text', help='Text string to render')
    parser.add_argument('output_dir', help='Output directory for preview images')
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    for i in range(VARIATIONS):
        img, ok = render_enchant_header(args.text, FONT_PATH, FONT_SIZE)
        if not ok:
            print(f"  variation {i}: FAILED")
            continue

        out_path = os.path.join(args.output_dir, f"preview_{i}.png")
        img.convert('RGB').save(out_path)
        w, h = img.size
        arr = np.array(img)
        ink = (arr == 0).sum() / arr.size
        print(f"  variation {i}: {w}x{h}  ink={ink:.3f}  → {out_path}")


if __name__ == "__main__":
    main()
