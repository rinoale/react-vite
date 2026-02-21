#!/usr/bin/env python3
"""Find black squares/rectangles in tooltip theme images.

A black square is defined as:
- Four straight sides (two vertical, two horizontal)
- Interior color is near-black (max(R,G,B) < threshold)
- Minimum width: 10px, minimum height: 5px

Logic: find connected near-black regions, then check each has
continuous near-black runs both horizontally (>=10px) and vertically (>=5px).

Usage:
    python3 scripts/find_black_squares.py "data/themes/screenshot.png" split_result/
    python3 scripts/find_black_squares.py "data/themes/screenshot.png" split_result/ --threshold 25
"""

import argparse
import os
import sys

import cv2
import numpy as np

MIN_HEIGHT = 5
MIN_WIDTH = 10
DEFAULT_THRESHOLD = 5   # max(R,G,B) < threshold → near black
                        # Must stay in sync with tooltip_segmenter.NEAR_BLACK_THRESHOLD=5.
                        # Threshold=20 causes dark tooltip backgrounds (max≈13) to merge
                        # with the black square, producing oversized bounding boxes.


def find_black_squares(img, threshold):
    """Find rectangular near-black regions.

    For each connected near-black component meeting min size:
    - Horizontal check: at least one row must have a continuous run >= MIN_WIDTH
    - Vertical check: at least one column must have a continuous run >= MIN_HEIGHT
    Returns list of (x, y, w, h).
    """
    mask = (img.max(axis=2) < threshold).astype(np.uint8)

    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)

    squares = []
    for i in range(1, n_labels):
        x, y, w, h = stats[i, cv2.CC_STAT_LEFT], stats[i, cv2.CC_STAT_TOP], \
                     stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
        area = stats[i, cv2.CC_STAT_AREA]

        if w < MIN_WIDTH or h < MIN_HEIGHT:
            continue

        region = mask[y:y + h, x:x + w]

        # At least one row must have a continuous horizontal run >= MIN_WIDTH
        has_h_run = any(max_consecutive(region[r]) >= MIN_WIDTH for r in range(h))
        if not has_h_run:
            continue

        # At least one column must have a continuous vertical run >= MIN_HEIGHT
        has_v_run = any(max_consecutive(region[:, c]) >= MIN_HEIGHT for c in range(w))
        if not has_v_run:
            continue

        squares.append((x, y, w, h))

    return squares


def max_consecutive(arr):
    """Return the length of the longest consecutive run of 1s in a 1D array."""
    if arr.sum() == 0:
        return 0
    max_run = 0
    current = 0
    for v in arr:
        if v:
            current += 1
            if current > max_run:
                max_run = current
        else:
            current = 0
    return max_run


def main():
    parser = argparse.ArgumentParser(description='Find black squares in tooltip images')
    parser.add_argument('image', help='Path to original color screenshot')
    parser.add_argument('output', help='Directory to save results')
    parser.add_argument('--threshold', type=int, default=DEFAULT_THRESHOLD,
                        help=f'max(R,G,B) threshold for near-black (default: {DEFAULT_THRESHOLD})')
    args = parser.parse_args()

    if not os.path.isfile(args.image):
        print(f"Error: {args.image} not found")
        sys.exit(1)

    os.makedirs(args.output, exist_ok=True)

    img = cv2.imread(args.image)
    base = os.path.splitext(os.path.basename(args.image))[0]

    squares = find_black_squares(img, args.threshold)

    print(f"Found {len(squares)} black squares (threshold max(RGB)<{args.threshold}):\n")
    for i, (x, y, w, h) in enumerate(squares):
        print(f"  {i+1:3d}. x={x:4d} y={y:4d}  w={w:4d} h={h:3d}")

    # Visualize on original image
    vis = img.copy()
    for (x, y, w, h) in squares:
        cv2.rectangle(vis, (x, y), (x + w, y + h), (0, 255, 0), 1)

    vis_path = os.path.join(args.output, f"{base}_black_squares.png")
    cv2.imwrite(vis_path, vis)
    print(f"\nVisualization saved: {vis_path}")


if __name__ == '__main__':
    main()
