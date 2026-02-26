#!/usr/bin/env python3
"""Color masking test tool for Mabinogi tooltip screenshots.

Keeps pixels within a given RGB range, masks everything else to black.
Outputs both the color mask (white on black) and the binarized result
(black text on white background) for OCR input.

Usage:
    python3 scripts/ocr/color_mask_test.py <image_or_glob>... [--low N] [--high N]

    --low N   keep pixels >= N (default 200)
    --high N  keep pixels <= N (default 255)

Examples:
    python3 scripts/ocr/color_mask_test.py chainblade_16.png
    python3 scripts/ocr/color_mask_test.py chainblade_16.png --low 180
    python3 scripts/ocr/color_mask_test.py chainblade_16.png --low 200 --high 240
    python3 scripts/ocr/color_mask_test.py 'data/practical_samples/*.png' --low 200
    python3 scripts/ocr/color_mask_test.py 'data/themes/*.png' --low 0 --high 150
"""

import glob
import os
import sys

import cv2
import numpy as np


def process(path, low, high, out_dir):
    img = cv2.imread(path)
    if img is None:
        print(f"  SKIP {path} (could not read)")
        return

    b, g, r = img[:, :, 0], img[:, :, 1], img[:, :, 2]
    mask = (r >= low) & (r <= high) & (g >= low) & (g <= high) & (b >= low) & (b <= high)

    # Color mask: white text on black background
    color_masked = np.zeros_like(img)
    color_masked[mask] = [255, 255, 255]

    # Binarization: black text on white background (OCR input)
    binarized = np.full_like(img, 255)
    binarized[mask] = [0, 0, 0]

    basename = os.path.splitext(os.path.basename(path))[0]
    label = f'{low}' if high == 255 else f'{low}_{high}'

    mask_path = os.path.join(out_dir, f'{basename}_color_mask_{label}.png')
    bin_path = os.path.join(out_dir, f'{basename}_binarized_{label}.png')
    cv2.imwrite(mask_path, color_masked)
    cv2.imwrite(bin_path, binarized)

    total = mask.size
    kept = mask.sum()
    print(f"  {os.path.basename(path):40s}  {kept:6d} px ({100*kept/total:.1f}%)")
    print(f"    mask → {mask_path}")
    print(f"    bin  → {bin_path}")


def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: python3 scripts/ocr/color_mask_test.py <image_or_glob>... [--low N] [--high N]")
        sys.exit(1)

    low = 200
    high = 255
    patterns = []

    i = 0
    while i < len(args):
        if args[i] == '--low' and i + 1 < len(args):
            low = int(args[i + 1])
            i += 2
        elif args[i] == '--high' and i + 1 < len(args):
            high = int(args[i + 1])
            i += 2
        else:
            patterns.append(args[i])
            i += 1

    # Expand globs
    paths = []
    for pattern in patterns:
        expanded = sorted(glob.glob(pattern))
        paths.extend(expanded if expanded else [pattern])

    if not paths:
        print("No images found.")
        sys.exit(1)

    out_dir = 'tmp'
    os.makedirs(out_dir, exist_ok=True)

    label = f'[{low}, {high}]'
    print(f"Range: {label}  |  {len(paths)} image(s)\n")

    for path in paths:
        process(path, low, high, out_dir)


if __name__ == "__main__":
    main()
