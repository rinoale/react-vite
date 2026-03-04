#!/usr/bin/env python3
"""Validate line splitting on each content segment of the v3 pipeline.

Reproduces the exact V3 pipeline path up to line detection:
  1. Border detection (bottom, left, right) → crop to tooltip
  2. Orange header detection → black-square expansion
  3. build_segments with border coordinates
  4. Header classification via header OCR model + fuzzy match
  5. BT.601 + threshold=80 → ocr_binary (same as BaseHandler.process())
  6. detect_text_lines() on ocr_binary
  7. group_by_y() on detected lines

Output directory structure:
  <output>/
    <image_name>/
      seg_00_pre_header_cnt_original.png
      seg_00_pre_header_cnt_binary.png
      seg_00_pre_header_cnt_detect.png
      seg_00_pre_header_cnt_lines.png
      seg_01_item_attrs_hdr.png
      seg_01_item_attrs_cnt_original.png
      seg_01_item_attrs_cnt_binary.png
      seg_01_item_attrs_cnt_detect.png
      seg_01_item_attrs_cnt_lines.png
      ...
      overview.png

Usage:
    python3 scripts/v3/segmentation/test_line_split.py data/sample_images/captain_suit_original.png split_result/
    python3 scripts/v3/segmentation/test_line_split.py data/sample_images/ split_result/
"""

import argparse
import os
import sys

import cv2
import numpy as np
import yaml

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'backend'))

CONFIG_PATH = os.path.join(PROJECT_ROOT, 'configs', 'mabinogi_tooltip.yaml')
LINE_SPLIT_CONFIG_PATH = os.path.join(PROJECT_ROOT, 'configs', 'line_split.yaml')
MODELS_DIR = os.path.join(PROJECT_ROOT, 'backend', 'ocr', 'models')

from lib.pipeline.segmenter import (
    load_config, load_section_patterns, init_header_reader,
    segment_and_tag,
)
from lib.pipeline.section_handlers._helpers import bt601_binary
from lib.pipeline.line_split import MabinogiTooltipSplitter, group_by_y


SEGMENT_COLORS = [
    (0, 200, 0), (255, 200, 0), (200, 0, 255), (0, 255, 255),
    (255, 100, 100), (100, 255, 100), (100, 100, 255), (200, 200, 0),
]
HEADER_COLOR = (0, 127, 255)
LINE_COLOR = (0, 255, 0)
LINE_COLOR_BINARY = (0, 0, 255)


def draw_lines_on_image(img, lines, color, thickness=1):
    """Draw line bounding boxes on an image copy. Returns the annotated copy."""
    vis = img.copy()
    if len(vis.shape) == 2:
        vis = cv2.cvtColor(vis, cv2.COLOR_GRAY2BGR)
    for i, line in enumerate(lines):
        x, y, w, h = line['x'], line['y'], line['width'], line['height']
        cv2.rectangle(vis, (x, y), (x + w - 1, y + h - 1), color, thickness)
        cv2.putText(vis, str(i), (x + w + 2, y + h - 1),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.3, color, 1)
    return vis


def process_image(image_path, output_root, header_reader, patterns, config):
    """Process a single image: segment_and_tag → line split → save visualizations."""
    img = cv2.imread(image_path)
    if img is None:
        print(f"  ERROR: cannot read {image_path}")
        return

    base = os.path.splitext(os.path.basename(image_path))[0]
    out_dir = os.path.join(output_root, base)
    os.makedirs(out_dir, exist_ok=True)

    # Exact V3 pipeline: segment_and_tag does border detection + header
    # detection + build_segments + header classification in one call.
    tagged = segment_and_tag(img, header_reader, patterns, config)

    with open(LINE_SPLIT_CONFIG_PATH, 'r') as f:
        line_split_cfg = yaml.safe_load(f) or {}
    game_split = config.get('horizontal_split_factor')
    if game_split is not None:
        line_split_cfg.setdefault('horizontal', {})['split_factor'] = game_split
    splitter = MabinogiTooltipSplitter(config=line_split_cfg)

    print(f"\n{'='*60}")
    print(f"  {os.path.basename(image_path)}")
    sections = [s['section'] or '???' for s in tagged]
    print(f"  {len(tagged)} segments: {sections}")
    print(f"{'='*60}")

    total_lines = 0

    for seg in tagged:
        idx = seg['index']
        section = seg['section'] or 'unknown'
        prefix = f"seg_{idx:02d}_{section}"
        seg_color = SEGMENT_COLORS[idx % len(SEGMENT_COLORS)]

        # --- Header crop ---
        if seg['header_crop'] is not None:
            cv2.imwrite(os.path.join(out_dir, f"{prefix}_hdr.png"),
                        seg['header_crop'])

        # --- Content crop ---
        content_crop = seg['content_crop']
        if content_crop is None or content_crop.shape[0] == 0:
            print(f"  Seg {idx:02d} [{section:16s}]  content: (empty)")
            continue

        # BT.601 binary — same as BaseHandler.process()
        ocr_binary = bt601_binary(content_crop)

        # Line detection — same as BaseHandler.process()
        detected = splitter.detect_text_lines(ocr_binary)
        grouped = group_by_y(detected)
        total_lines += len(grouped)

        # Save content images
        cv2.imwrite(os.path.join(out_dir, f"{prefix}_cnt_original.png"),
                    content_crop)
        cv2.imwrite(os.path.join(out_dir, f"{prefix}_cnt_binary.png"),
                    ocr_binary)
        cv2.imwrite(os.path.join(out_dir, f"{prefix}_cnt_detect.png"),
                    ocr_binary)

        # Draw lines on content crop
        vis = draw_lines_on_image(content_crop, detected, LINE_COLOR)
        cv2.imwrite(os.path.join(out_dir, f"{prefix}_cnt_lines.png"), vis)

        # Print summary
        hdr_text = seg.get('header_ocr_text', '')
        hdr_info = f"  hdr='{hdr_text}'" if hdr_text else ""
        print(f"  Seg {idx:02d} [{section:16s}]  "
              f"h={content_crop.shape[0]:3d}  "
              f"→ {len(detected):2d} lines ({len(grouped):2d} grouped){hdr_info}")
        for i, line in enumerate(detected):
            print(f"           line {i:2d}: y={line['y']:3d} x={line['x']:3d} "
                  f"w={line['width']:3d} h={line['height']:2d}")

    print(f"\n  Total: {total_lines} grouped lines")
    print(f"  Output: {out_dir}/")


def main():
    parser = argparse.ArgumentParser(
        description='Validate v3 line splitting with visual output')
    parser.add_argument('path', help='Image file or directory of images')
    parser.add_argument('output', help='Output directory for results')
    args = parser.parse_args()

    config = load_config(CONFIG_PATH)
    patterns = load_section_patterns(CONFIG_PATH)
    header_reader = init_header_reader(models_dir=MODELS_DIR)

    if os.path.isdir(args.path):
        images = sorted(
            os.path.join(args.path, f)
            for f in os.listdir(args.path)
            if f.endswith('_original.png')
        )
        if not images:
            images = sorted(
                os.path.join(args.path, f)
                for f in os.listdir(args.path)
                if f.endswith('.png')
            )
    else:
        images = [args.path]

    os.makedirs(args.output, exist_ok=True)

    for image_path in images:
        process_image(image_path, args.output, header_reader, patterns, config)


if __name__ == '__main__':
    main()
