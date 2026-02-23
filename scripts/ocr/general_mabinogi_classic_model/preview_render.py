#!/usr/bin/env python3
"""
Preview training image rendering for a given text string.

Generates VARIATIONS_PER_LABEL (3) images using the same rendering pipeline
as generate_training_data.py, saving them to the specified output directory.

Usage (from project root):
    python3 scripts/ocr/general_mabinogi_classic_model/preview_render.py ". 최대대미지 55 증가 (50~55)" /tmp/preview
    python3 scripts/ocr/general_mabinogi_classic_model/preview_render.py "세공" /tmp/preview
"""

import argparse
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from scripts.ocr.lib.render_utils import render_line_gamelike

FONT_PATH = "data/fonts/mabinogi_classic.ttf"
FONT_SIZES = [11, 11, 12, 12, 13, 13]
CANVAS_WIDTH = 400
VARIATIONS = 3


def main():
    parser = argparse.ArgumentParser(description='Preview training image rendering')
    parser.add_argument('text', help='Text string to render')
    parser.add_argument('output_dir', help='Output directory for preview images')
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    for i in range(VARIATIONS):
        font_size = random.choice(FONT_SIZES)
        cw = CANVAS_WIDTH + random.randint(-10, 10)

        img, ok = render_line_gamelike(args.text, FONT_PATH, font_size, cw)
        if not ok:
            print(f"  variation {i}: FAILED")
            continue

        out_path = os.path.join(args.output_dir, f"preview_{i}.png")
        img.convert('RGB').save(out_path)
        w, h = img.size
        import numpy as np
        arr = np.array(img)
        ink = (arr == 0).sum() / arr.size
        print(f"  variation {i}: {w}x{h}  ink={ink:.3f}  → {out_path}")


if __name__ == "__main__":
    main()
