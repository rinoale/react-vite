#!/usr/bin/env python3
"""Test the full segment-first pipeline: detect → segment → OCR header → tag content.

Usage:
    python3 scripts/test_segmentation_pipeline.py data/themes/screenshot_2026-02-20_200924.png
    python3 scripts/test_segmentation_pipeline.py data/themes/  # all images in dir
"""

import argparse
import os
import sys

import cv2

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'backend'))

CONFIG_PATH = os.path.join(PROJECT_ROOT, 'configs', 'mabinogi_tooltip.yaml')


def init_reader():
    from lib.tooltip_segmenter import init_header_reader
    return init_header_reader()


def test_image(image_path, reader, patterns, config):
    img = cv2.imread(image_path)
    if img is None:
        print(f"  ERROR: cannot read {image_path}")
        return

    from lib.tooltip_segmenter import segment_and_tag
    tagged = segment_and_tag(img, reader, patterns, config)

    name = os.path.basename(image_path)
    n_headers = sum(1 for s in tagged if s['header_crop'] is not None)
    print(f"\n{'='*60}")
    print(f"{name}: {n_headers} headers, {len(tagged)} segments")
    print(f"{'='*60}")

    ok = 0
    for seg in tagged:
        idx     = seg['index']
        section = seg['section'] or 'UNKNOWN'
        ocr     = seg['header_ocr_text']
        conf    = seg['header_ocr_conf']
        score   = seg['header_match_score']
        cnt_h   = seg['content_crop'].shape[0]

        if seg['header_crop'] is None:
            print(f"  [{idx:02d}] pre_header          content_h={cnt_h}")
            ok += 1
        else:
            status = '✓' if seg['section'] else '✗'
            print(f"  [{idx:02d}] {status} {section:<18} "
                  f"ocr='{ocr}'  conf={conf:.2f}  score={score}  content_h={cnt_h}")
            if seg['section']:
                ok += 1

    total = len(tagged)
    print(f"  Result: {ok}/{total} segments tagged")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('path', help='Image file or directory')
    parser.add_argument('--cutoff', type=int, default=50)
    args = parser.parse_args()

    from lib.tooltip_segmenter import load_section_patterns, load_config
    patterns = load_section_patterns(CONFIG_PATH)
    config = load_config(CONFIG_PATH)
    print(f"Loaded {len(patterns)} header patterns")

    print("Initializing OCR reader...")
    reader = init_reader()
    print("Ready.")

    if os.path.isdir(args.path):
        images = sorted(
            os.path.join(args.path, f)
            for f in os.listdir(args.path)
            if f.endswith('.png')
        )
    else:
        images = [args.path]

    for img_path in images:
        test_image(img_path, reader, patterns, config)


if __name__ == '__main__':
    main()
