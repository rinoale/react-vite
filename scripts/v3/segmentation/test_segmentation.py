#!/usr/bin/env python3
"""Segment a tooltip image into header+content sections using orange-anchored detection.

Strategy (reads all thresholds from configs/mabinogi_tooltip.yaml):
  1. Orange color mask → horizontal projection → filter bands (min height, min pixels)
  2. Expand each orange band outward until black-square boundary ends
  3. Content regions are defined between consecutive headers

Saves per-segment crops and a visualization overlay to the output directory.

Usage:
    python3 scripts/v3/segmentation/test_segmentation.py "data/themes/screenshot.png" split_result/
    python3 scripts/v3/segmentation/test_segmentation.py data/sample_images/titan_blade_original.png split_result/
"""

import argparse
import os
import sys

import cv2

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'backend'))

CONFIG_PATH = os.path.join(PROJECT_ROOT, 'configs', 'mabinogi_tooltip.yaml')

from tooltip_segmenter import load_config, detect_headers, build_segments


def main():
    parser = argparse.ArgumentParser(description='Segment tooltip into header+content sections')
    parser.add_argument('image', help='Path to original color screenshot')
    parser.add_argument('output', help='Directory to save results')
    args = parser.parse_args()

    if not os.path.isfile(args.image):
        print(f"Error: {args.image} not found")
        sys.exit(1)

    os.makedirs(args.output, exist_ok=True)

    config = load_config(CONFIG_PATH)
    img = cv2.imread(args.image)
    base = os.path.splitext(os.path.basename(args.image))[0]

    headers = detect_headers(img, config)
    segments = build_segments(img, headers)

    print(f"Found {len(headers)} headers → {len(segments)} segments\n")

    vis = img.copy()
    w_img = img.shape[1]
    colors = [
        (0, 200, 0), (255, 200, 0), (200, 0, 255), (0, 255, 255),
        (255, 100, 100), (100, 255, 100), (100, 100, 255), (200, 200, 0),
    ]

    for seg in segments:
        idx = seg['index']
        color = colors[idx % len(colors)]

        if seg['header']:
            hdr = seg['header']
            cv2.rectangle(vis, (0, hdr['y']), (w_img - 1, hdr['y'] + hdr['h']),
                          (0, 127, 255), 2)
            cv2.putText(vis, f"HDR {idx}", (hdr['x'] + hdr['w'] + 4, hdr['y'] + hdr['h'] - 1),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 127, 255), 1)
            print(f"Segment {idx}  header : y={hdr['y']:4d} h={hdr['h']:2d}")
            hdr_crop = img[hdr['y']:hdr['y'] + hdr['h'], hdr['x']:hdr['x'] + hdr['w']]
            cv2.imwrite(os.path.join(args.output, f"{base}_hdr_{idx:02d}.png"), hdr_crop)
        else:
            print(f"Segment {idx}  header : (none — pre-header content)")

        cnt = seg['content']
        if cnt['h'] > 0:
            cv2.rectangle(vis, (0, cnt['y']), (w_img - 1, cnt['y'] + cnt['h']), color, 1)
            cv2.putText(vis, f"CNT {idx}", (4, cnt['y'] + 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)
            print(f"           content: y={cnt['y']:4d} h={cnt['h']:3d}")
            cnt_crop = img[cnt['y']:cnt['y'] + cnt['h'], :]
            cv2.imwrite(os.path.join(args.output, f"{base}_cnt_{idx:02d}.png"), cnt_crop)
        print()

    vis_path = os.path.join(args.output, f"{base}_segments.png")
    cv2.imwrite(vis_path, vis)
    print(f"Visualization saved: {vis_path}")


if __name__ == '__main__':
    main()
