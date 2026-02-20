#!/usr/bin/env python3
"""Segment a tooltip image into header+content sections using the original color image.

Strategy:
  1. Find near-black (max(R,G,B) < threshold) connected regions — these are header bands.
  2. Each qualifying region (w>=10, h>=5, with continuous runs in both axes) is a header.
  3. Content regions are defined between consecutive headers.

Usage:
    python3 scripts/test_segmentation.py "data/themes/screenshot.png" split_result/
"""

import argparse
import os
import sys

import cv2
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

NEAR_BLACK_THRESHOLD = 5   # max(R,G,B) < this → near black
MIN_HEIGHT = 16            # minimum consecutive vertical run (matches header band height)
MIN_WIDTH = 25             # minimum consecutive horizontal run


def max_consecutive(arr):
    """Length of the longest consecutive run of 1s in a 1D binary array."""
    max_run = cur = 0
    for v in arr:
        if v:
            cur += 1
            if cur > max_run:
                max_run = cur
        else:
            cur = 0
    return max_run


def detect_headers(img, threshold=NEAR_BLACK_THRESHOLD,
                   min_height=MIN_HEIGHT, min_width=MIN_WIDTH):
    """Find header bands as near-black rectangular regions.

    For each connected near-black component:
      - bounding box must be w >= min_width and h >= min_height
      - at least one row must have a horizontal run >= min_width
      - at least one column must have a vertical run >= min_height

    Returns list of {'y', 'h', 'x', 'w', 'content_y'} sorted by y.
    """
    mask = (img.max(axis=2) < threshold).astype(np.uint8)
    n_labels, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)

    headers = []
    for i in range(1, n_labels):
        x = stats[i, cv2.CC_STAT_LEFT]
        y = stats[i, cv2.CC_STAT_TOP]
        w = stats[i, cv2.CC_STAT_WIDTH]
        h = stats[i, cv2.CC_STAT_HEIGHT]

        if w < min_width or h < min_height:
            continue

        region = mask[y:y + h, x:x + w]

        if not any(max_consecutive(region[r]) >= min_width for r in range(h)):
            continue
        if not any(max_consecutive(region[:, c]) >= min_height for c in range(w)):
            continue

        headers.append({
            'y': y, 'h': h, 'x': x, 'w': w,
            'content_y': y + h,  # content starts right after the black band
        })

    headers.sort(key=lambda hdr: hdr['y'])
    return headers


def build_segments(img, headers):
    """Pair each header with the content region below it until the next header.

    Returns list of:
      {'index', 'header': {y,h,x,w} or None, 'content': {y,h,x,w}}
    """
    h_img, w_img = img.shape[:2]
    segments = []

    # Pre-header content (item name area)
    if headers and headers[0]['y'] > 0:
        segments.append({
            'index': 0,
            'header': None,
            'content': {'y': 0, 'h': headers[0]['y'], 'x': 0, 'w': w_img},
        })

    for i, hdr in enumerate(headers):
        next_y = headers[i + 1]['y'] if i + 1 < len(headers) else h_img
        content_h = next_y - hdr['content_y']
        segments.append({
            'index': i + 1,
            'header': hdr,
            'content': {'y': hdr['content_y'], 'h': content_h, 'x': 0, 'w': w_img},
        })

    return segments


def main():
    parser = argparse.ArgumentParser(description='Segment tooltip into header+content sections')
    parser.add_argument('image', help='Path to original color screenshot')
    parser.add_argument('output', help='Directory to save results')
    parser.add_argument('--threshold', type=int, default=NEAR_BLACK_THRESHOLD,
                        help=f'max(R,G,B) threshold for near-black (default: {NEAR_BLACK_THRESHOLD})')
    parser.add_argument('--min-height', type=int, default=MIN_HEIGHT,
                        help=f'min consecutive vertical run (default: {MIN_HEIGHT})')
    parser.add_argument('--min-width', type=int, default=MIN_WIDTH,
                        help=f'min consecutive horizontal run (default: {MIN_WIDTH})')
    args = parser.parse_args()

    if not os.path.isfile(args.image):
        print(f"Error: {args.image} not found")
        sys.exit(1)

    os.makedirs(args.output, exist_ok=True)

    img = cv2.imread(args.image)
    base = os.path.splitext(os.path.basename(args.image))[0]

    headers = detect_headers(img, args.threshold, args.min_height, args.min_width)
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
