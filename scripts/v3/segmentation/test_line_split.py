#!/usr/bin/env python3
"""Validate line splitting on each content segment of the v3 pipeline.

For each content segment:
  1. Save the original color crop
  2. Save the preprocessed binary image (BT.601 + threshold=80)
  3. Run detect_text_lines() on the binary
  4. Draw detected line bounding boxes on both the original and binary crops
  5. Save the annotated visualizations

Output directory structure:
  <output>/
    <image_name>/
      seg_00_cnt_original.png         — raw color content crop
      seg_00_cnt_binary.png           — preprocessed binary (black text on white)
      seg_00_cnt_lines_original.png   — color crop with detected line boxes drawn
      seg_00_cnt_lines_binary.png     — binary crop with detected line boxes drawn
      seg_01_hdr.png                  — header crop (tight black-square)
      seg_01_cnt_original.png
      seg_01_cnt_binary.png
      seg_01_cnt_lines_original.png
      seg_01_cnt_lines_binary.png
      ...
      overview.png                    — full image with all segments and lines drawn

Usage:
    python3 scripts/v3/segmentation/test_line_split.py data/sample_images/captain_suit_original.png split_result/
    python3 scripts/v3/segmentation/test_line_split.py data/sample_images/ split_result/
"""

import argparse
import os
import sys

import cv2
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'backend'))

CONFIG_PATH = os.path.join(PROJECT_ROOT, 'configs', 'mabinogi_tooltip.yaml')

from lib.tooltip_segmenter import load_config, detect_headers, build_segments
from lib.tooltip_line_splitter import TooltipLineSplitter


SEGMENT_COLORS = [
    (0, 200, 0), (255, 200, 0), (200, 0, 255), (0, 255, 255),
    (255, 100, 100), (100, 255, 100), (100, 100, 255), (200, 200, 0),
]
HEADER_COLOR = (0, 127, 255)
LINE_COLOR = (0, 255, 0)
LINE_COLOR_BINARY = (0, 0, 255)


def preprocess_content(content_bgr):
    """BT.601 grayscale → threshold=80 → binary (black text on white)."""
    gray = cv2.cvtColor(content_bgr, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY_INV)
    return binary


def detect_lines_on_content(binary, splitter):
    """Run line detection on a binary content crop.

    binary: black text on white (from preprocess_content)
    Returns list of {'x', 'y', 'width', 'height'} dicts.
    """
    # detect_text_lines expects white-on-black (foreground = white)
    binary_detect = cv2.bitwise_not(binary)
    return splitter.detect_text_lines(binary_detect)


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


def process_image(image_path, output_root, config):
    """Process a single image: segment → line split → save visualizations."""
    img = cv2.imread(image_path)
    if img is None:
        print(f"  ERROR: cannot read {image_path}")
        return

    base = os.path.splitext(os.path.basename(image_path))[0]
    out_dir = os.path.join(output_root, base)
    os.makedirs(out_dir, exist_ok=True)

    headers = detect_headers(img, config)
    segments = build_segments(img, headers)
    splitter = TooltipLineSplitter()

    h_img, w_img = img.shape[:2]
    overview = img.copy()

    print(f"\n{'='*60}")
    print(f"  {os.path.basename(image_path)}")
    print(f"  {len(headers)} headers → {len(segments)} segments")
    print(f"{'='*60}")

    total_lines = 0

    for seg in segments:
        idx = seg['index']
        seg_color = SEGMENT_COLORS[idx % len(SEGMENT_COLORS)]

        # --- Header crop ---
        if seg['header'] is not None:
            hdr = seg['header']
            hdr_crop = img[hdr['y']:hdr['y'] + hdr['h'],
                           hdr['x']:hdr['x'] + hdr['w']]
            cv2.imwrite(os.path.join(out_dir, f"seg_{idx:02d}_hdr.png"), hdr_crop)

            # Draw header on overview
            cv2.rectangle(overview, (0, hdr['y']),
                          (w_img - 1, hdr['y'] + hdr['h'] - 1), HEADER_COLOR, 2)
            cv2.putText(overview, f"HDR {idx}",
                        (hdr['x'] + hdr['w'] + 4, hdr['y'] + hdr['h'] - 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, HEADER_COLOR, 1)

        # --- Content crop ---
        cnt = seg['content']
        if cnt['h'] <= 0:
            print(f"  Seg {idx:02d}  content: (empty)")
            continue

        content_crop = img[cnt['y']:cnt['y'] + cnt['h'], :]

        # Preprocess
        binary = preprocess_content(content_crop)

        # Detect lines
        lines = detect_lines_on_content(binary, splitter)
        total_lines += len(lines)

        # Draw on content crops
        vis_original = draw_lines_on_image(content_crop, lines, LINE_COLOR)
        vis_binary = draw_lines_on_image(binary, lines, LINE_COLOR_BINARY)

        # Save all content images
        cv2.imwrite(os.path.join(out_dir, f"seg_{idx:02d}_cnt_original.png"),
                    content_crop)
        cv2.imwrite(os.path.join(out_dir, f"seg_{idx:02d}_cnt_binary.png"),
                    binary)
        cv2.imwrite(os.path.join(out_dir, f"seg_{idx:02d}_cnt_lines_original.png"),
                    vis_original)
        cv2.imwrite(os.path.join(out_dir, f"seg_{idx:02d}_cnt_lines_binary.png"),
                    vis_binary)

        # Draw content region + lines on overview
        cv2.rectangle(overview, (0, cnt['y']),
                      (w_img - 1, cnt['y'] + cnt['h'] - 1), seg_color, 1)
        for line in lines:
            abs_y = cnt['y'] + line['y']
            cv2.rectangle(overview,
                          (line['x'], abs_y),
                          (line['x'] + line['width'] - 1, abs_y + line['height'] - 1),
                          LINE_COLOR, 1)

        # Print summary
        hdr_label = "(pre-header)" if seg['header'] is None else ""
        print(f"  Seg {idx:02d}  content y={cnt['y']:4d} h={cnt['h']:3d}  "
              f"→ {len(lines):2d} lines detected  {hdr_label}")
        for i, line in enumerate(lines):
            print(f"           line {i:2d}: y={line['y']:3d} x={line['x']:3d} "
                  f"w={line['width']:3d} h={line['height']:2d}")

    # Save overview
    overview_path = os.path.join(out_dir, "overview.png")
    cv2.imwrite(overview_path, overview)

    print(f"\n  Total lines detected: {total_lines}")
    print(f"  Output saved to: {out_dir}/")


def main():
    parser = argparse.ArgumentParser(
        description='Validate v3 line splitting with visual output')
    parser.add_argument('path', help='Image file or directory of images')
    parser.add_argument('output', help='Output directory for results')
    args = parser.parse_args()

    config = load_config(CONFIG_PATH)

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
        process_image(image_path, args.output, config)


if __name__ == '__main__':
    main()
