#!/usr/bin/env python3
"""Test alternative thresholding for enchant header crops.

Approach: keep only near-white pixels (>= 250) on grayscale,
then invert to get black text on white background.

Usage (from project root):
    python3 scripts/v3/enchant_ocr/test_enchant_threshold.py <image_or_glob> <output_dir>
"""

import glob
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'backend'))

from backend.lib.pipeline.segmenter import (
    segment_and_tag,
    load_section_patterns,
    load_config,
    init_header_reader,
)
from backend.lib.image_processors.mabinogi_processor import detect_enchant_slot_headers
from backend.lib.patches import patch_reader_imgw

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
CONFIG_PATH = os.path.join(PROJECT_ROOT, 'configs', 'mabinogi_tooltip.yaml')
MODELS_DIR = os.path.join(PROJECT_ROOT, 'backend', 'ocr', 'models')


def process_image(image_path, header_reader, patterns, config, output_dir):
    name = os.path.splitext(os.path.basename(image_path))[0]
    img = cv2.imread(image_path)
    if img is None:
        print(f"Cannot read: {image_path}")
        return

    segments = segment_and_tag(img, header_reader, patterns, config)

    for seg in segments:
        if seg['section'] != 'enchant':
            continue

        content_bgr = seg['content_crop']
        if content_bgr is None or content_bgr.shape[0] == 0:
            continue

        bands = detect_enchant_slot_headers(content_bgr)
        if not bands:
            print(f"  {name}: no enchant bands found")
            continue

        # White mask: bright + balanced RGB
        r = content_bgr[:, :, 2].astype(np.float32)
        g = content_bgr[:, :, 1].astype(np.float32)
        b = content_bgr[:, :, 0].astype(np.float32)
        max_ch = np.maximum(np.maximum(r, g), b)
        min_ch = np.minimum(np.minimum(r, g), b)
        white_mask = ((max_ch > 150) & ((max_ch / (min_ch + 1)) < 1.4))
        white_on_black = (white_mask.astype(np.uint8) * 255)
        black_on_white = cv2.bitwise_not(white_on_black)

        # Old: BT.601 grayscale → threshold=80 → BINARY_INV
        gray = cv2.cvtColor(content_bgr, cv2.COLOR_BGR2GRAY)
        _, old_binary = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY_INV)

        img_h, img_w = white_on_black.shape
        for bi, (bs, be) in enumerate(bands):
            text_h = be - bs

            band_region = white_on_black[bs:be, :]
            col_counts = band_region.sum(axis=0) // 255
            white_cols = np.where(col_counts >= 3)[0]
            if len(white_cols) == 0:
                continue

            x_start = int(white_cols[0])
            x_end = int(white_cols[-1]) + 1

            pad_x = max(2, text_h // 3)
            pad_y = max(1, text_h // 5)
            x0 = max(0, x_start - pad_x)
            y0 = max(0, bs - pad_y)
            x1 = min(img_w, x_end + pad_x)
            y1 = min(img_h, be + pad_y)

            crop_mask = white_on_black[y0:y1, x0:x1]
            crop_inv = black_on_white[y0:y1, x0:x1]
            crop_old = old_binary[y0:y1, x0:x1]

            fname_mask = f"{name}_b{bi}_whitemask.png"
            fname_inv = f"{name}_b{bi}_inverted.png"
            fname_old = f"{name}_b{bi}_old.png"
            cv2.imwrite(os.path.join(output_dir, fname_mask), crop_mask)
            cv2.imwrite(os.path.join(output_dir, fname_inv), crop_inv)
            cv2.imwrite(os.path.join(output_dir, fname_old), crop_old)

            h_c, w_c = crop_inv.shape[:2]
            ink_inv = (crop_inv < 128).sum() / crop_inv.size
            ink_old = (crop_old < 128).sum() / crop_old.size
            print(f"  b{bi}  {w_c:3d}x{h_c}  ink: whitemask_inv={ink_inv:.3f}  old={ink_old:.3f}")


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <image_or_glob> <output_dir>")
        sys.exit(1)

    pattern = sys.argv[1]
    output_dir = sys.argv[2]
    os.makedirs(output_dir, exist_ok=True)

    images = sorted(glob.glob(pattern)) if '*' in pattern else [pattern]
    images = [p for p in images if p.lower().endswith('.png')]
    if not images:
        print(f"No images found: {pattern}")
        sys.exit(1)

    # Init header reader for segmentation
    header_reader = init_header_reader(models_dir=MODELS_DIR)
    patch_reader_imgw(header_reader, MODELS_DIR, recog_network='custom_header')
    patterns = load_section_patterns(CONFIG_PATH)
    config = load_config(CONFIG_PATH)

    print(f"Processing {len(images)} image(s) → {output_dir}\n")
    for img_path in images:
        print(f"{os.path.basename(img_path)}:")
        process_image(img_path, header_reader, patterns, config, output_dir)
        print()


if __name__ == '__main__':
    main()
