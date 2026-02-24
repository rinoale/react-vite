#!/usr/bin/env python3
"""Detect tooltip border columns and visualize them.

Finds vertical border lines at RGB(132,132,132) ± tolerance,
draws red lines on the detected boundaries, and saves the result.

Usage:
    python3 scripts/ocr/detect_borders.py <image_or_glob>...
    python3 scripts/ocr/detect_borders.py 'data/practical_samples/*.png'
"""

import glob
import os
import sys

import cv2
import numpy as np

BORDER_RGB = 132
TOLERANCE = 5
MIN_DENSITY = 0.10  # column must have border pixels in >10% of rows


def detect_border_cols(img, border_val=BORDER_RGB, tol=TOLERANCE, min_density=MIN_DENSITY):
    """Return (left_col, right_col) or None if not detected."""
    r, g, b = img[:, :, 2], img[:, :, 1], img[:, :, 0]
    h = img.shape[0]

    border = (
        (np.abs(r.astype(int) - border_val) <= tol) &
        (np.abs(g.astype(int) - border_val) <= tol) &
        (np.abs(b.astype(int) - border_val) <= tol)
    )

    col_density = border.sum(axis=0) / h
    border_cols = np.where(col_density > min_density)[0]

    if len(border_cols) < 2:
        return None

    return int(border_cols[0]), int(border_cols[-1])


def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: python3 scripts/ocr/detect_borders.py <image_or_glob>...")
        sys.exit(1)

    paths = []
    for pattern in args:
        expanded = sorted(glob.glob(pattern))
        paths.extend(expanded if expanded else [pattern])

    out_dir = os.path.join('tmp', 'border_detect')
    os.makedirs(out_dir, exist_ok=True)

    print(f"Processing {len(paths)} image(s)...\n")

    for path in paths:
        img = cv2.imread(path)
        if img is None:
            print(f"  SKIP {path}")
            continue

        result = detect_border_cols(img)
        basename = os.path.splitext(os.path.basename(path))[0]

        if result is None:
            print(f"  {basename:40s}  NO BORDER DETECTED")
            continue

        left, right = result

        # Draw red lines on borders
        vis = img.copy()
        cv2.line(vis, (left, 0), (left, img.shape[0] - 1), (0, 0, 255), 1)
        cv2.line(vis, (right, 0), (right, img.shape[0] - 1), (0, 0, 255), 1)

        out_path = os.path.join(out_dir, f'{basename}_borders.png')
        cv2.imwrite(out_path, vis)

        print(f"  {basename:40s}  left={left:3d}  right={right:3d}  → {out_path}")


if __name__ == "__main__":
    main()
