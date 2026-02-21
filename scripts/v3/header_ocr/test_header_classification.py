#!/usr/bin/env python3
"""Test header OCR → section label assignment (new segment-first pipeline).

Pipeline:
  1. Original color image → detect_headers() → build_segments()
  2. Each header crop → preprocess (BT.601 + threshold) → recognize()
  3. Fuzzy match OCR text against section header_patterns from YAML
  4. Output: segment index → section name → raw OCR

Usage:
    python3 scripts/v3/header_ocr/test_header_classification.py data/themes/screenshot_2026-02-20_200924.png
    python3 scripts/v3/header_ocr/test_header_classification.py data/themes/  # run on all images in dir
"""

import argparse
import os
import sys

import cv2

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'backend'))

CONFIG_PATH = os.path.join(PROJECT_ROOT, 'configs', 'mabinogi_tooltip.yaml')

from lib.tooltip_segmenter import (
    load_config, load_section_patterns, detect_headers, build_segments,
    init_header_reader, classify_header,
)


def classify_image(image_path, reader, patterns, config):
    img = cv2.imread(image_path)
    if img is None:
        print(f"  ERROR: cannot read {image_path}")
        return

    headers = detect_headers(img, config)
    segments = build_segments(img, headers)
    name = os.path.basename(image_path)

    print(f"\n{'='*60}")
    print(f"{name}: {len(headers)} headers, {len(segments)} segments")
    print(f"{'='*60}")

    for seg in segments:
        idx = seg['index']
        if seg['header'] is None:
            print(f"  Seg {idx:02d}  [pre-header]  → section: item_name/item_attrs")
            continue

        hdr = seg['header']
        crop_color = img[hdr['y']:hdr['y'] + hdr['h'], :]
        section, ocr_text, conf, score = classify_header(
            crop_color, reader, patterns, config
        )

        status = '✓' if section else '✗'
        print(f"  Seg {idx:02d}  y={hdr['y']:4d}  "
              f"OCR: '{ocr_text}'  conf={conf:.2f}  "
              f"→ {status} {section or 'UNKNOWN'}  "
              f"(score={score})")


def main():
    parser = argparse.ArgumentParser(description='Header OCR → section label classifier')
    parser.add_argument('path', help='Image file or directory of images')
    args = parser.parse_args()

    config = load_config(CONFIG_PATH)
    patterns = load_section_patterns(CONFIG_PATH)
    print(f"Loaded {len(patterns)} header patterns from config")

    print("\nInitializing OCR reader...")
    reader = init_header_reader()
    print("Ready.\n")

    if os.path.isdir(args.path):
        images = sorted(
            os.path.join(args.path, f)
            for f in os.listdir(args.path)
            if f.endswith('.png')
        )
    else:
        images = [args.path]

    for img_path in images:
        classify_image(img_path, reader, patterns, config)


if __name__ == '__main__':
    main()
