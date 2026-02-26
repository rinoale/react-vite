#!/usr/bin/env python3
"""RGB color masking test tool for Mabinogi tooltip screenshots.

Keeps pixels matching exact RGB spots, tolerance, or explicit ranges.
Outputs both the color mask (white on black) and the binarized result
(black text on white background) for OCR input.

Usage:
    python3 scripts/ocr/rgb_mask_test.py <image_or_glob>... --rgb R,G,B [--rgb R,G,B ...]
    python3 scripts/ocr/rgb_mask_test.py <image_or_glob>... --rgb R,G,B --tolerance N
    python3 scripts/ocr/rgb_mask_test.py <image_or_glob>... --range R1,G1,B1,R2,G2,B2

    --rgb R,G,B               exact RGB value to keep (repeatable)
    --tolerance N             per-channel tolerance around each --rgb value (default 0)
    --range R1,G1,B1,R2,G2,B2  keep pixels with R in [R1,R2], G in [G1,G2], B in [B1,B2] (repeatable)

Examples:
    # Exact single color
    python3 scripts/ocr/rgb_mask_test.py image.png --rgb 74,149,238

    # Multiple exact colors
    python3 scripts/ocr/rgb_mask_test.py image.png --rgb 74,149,238 --rgb 75,149,238

    # Single color with ±2 tolerance per channel
    python3 scripts/ocr/rgb_mask_test.py image.png --rgb 74,149,238 --tolerance 2

    # Range: R[70-80], G[140-160], B[230-245]
    python3 scripts/ocr/rgb_mask_test.py image.png --range 70,140,230,80,160,245

    # Mix spots and ranges
    python3 scripts/ocr/rgb_mask_test.py image.png --rgb 74,149,238 --range 200,200,200,255,255,255
"""

import glob
import os
import sys

import cv2
import numpy as np


def parse_rgb(s):
    """Parse 'R,G,B' string to (R, G, B) tuple."""
    parts = s.split(',')
    if len(parts) != 3:
        print(f"Error: invalid RGB '{s}', expected R,G,B")
        sys.exit(1)
    return tuple(int(x) for x in parts)


def parse_range(s):
    """Parse 'R1,G1,B1,R2,G2,B2' string to ((R1,G1,B1), (R2,G2,B2)) tuple."""
    parts = s.split(',')
    if len(parts) != 6:
        print(f"Error: invalid range '{s}', expected R1,G1,B1,R2,G2,B2")
        sys.exit(1)
    vals = [int(x) for x in parts]
    return (vals[0], vals[1], vals[2]), (vals[3], vals[4], vals[5])


def process(path, rgb_values, tolerance, ranges, out_dir):
    img = cv2.imread(path)
    if img is None:
        print(f"  SKIP {path} (could not read)")
        return

    b, g, r = img[:, :, 0], img[:, :, 1], img[:, :, 2]

    mask = np.zeros(r.shape, dtype=bool)

    # Exact spots with tolerance
    for rv, gv, bv in rgb_values:
        spot = ((r >= rv - tolerance) & (r <= rv + tolerance) &
                (g >= gv - tolerance) & (g <= gv + tolerance) &
                (b >= bv - tolerance) & (b <= bv + tolerance))
        mask |= spot

    # Explicit ranges
    for (r1, g1, b1), (r2, g2, b2) in ranges:
        rng = ((r >= r1) & (r <= r2) &
               (g >= g1) & (g <= g2) &
               (b >= b1) & (b <= b2))
        mask |= rng

    # Color mask: white text on black background
    color_masked = np.zeros_like(img)
    color_masked[mask] = [255, 255, 255]

    # Binarization: black text on white background (OCR input)
    binarized = np.full_like(img, 255)
    binarized[mask] = [0, 0, 0]

    basename = os.path.splitext(os.path.basename(path))[0]
    parts = []
    for rv, gv, bv in rgb_values:
        parts.append(f'{rv}.{gv}.{bv}')
    for (r1, g1, b1), (r2, g2, b2) in ranges:
        parts.append(f'{r1}.{g1}.{b1}-{r2}.{g2}.{b2}')
    label = '_'.join(parts)
    tol_label = f'_t{tolerance}' if tolerance > 0 else ''

    mask_path = os.path.join(out_dir, f'{basename}_rgb_{label}{tol_label}.png')
    bin_path = os.path.join(out_dir, f'{basename}_rgb_{label}{tol_label}_binarized.png')
    cv2.imwrite(mask_path, color_masked)
    cv2.imwrite(bin_path, binarized)

    total = mask.size
    kept = int(mask.sum())
    print(f"  {os.path.basename(path):40s}  {kept:6d} px ({100*kept/total:.1f}%)")
    print(f"    mask → {mask_path}")
    print(f"    bin  → {bin_path}")


def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: python3 scripts/ocr/rgb_mask_test.py <image_or_glob>... --rgb R,G,B [--tolerance N] [--range R1,G1,B1,R2,G2,B2]")
        sys.exit(1)

    rgb_values = []
    ranges = []
    tolerance = 0
    patterns = []

    i = 0
    while i < len(args):
        if args[i] == '--rgb' and i + 1 < len(args):
            rgb_values.append(parse_rgb(args[i + 1]))
            i += 2
        elif args[i] == '--range' and i + 1 < len(args):
            ranges.append(parse_range(args[i + 1]))
            i += 2
        elif args[i] == '--tolerance' and i + 1 < len(args):
            tolerance = int(args[i + 1])
            i += 2
        else:
            patterns.append(args[i])
            i += 1

    if not rgb_values and not ranges:
        print("Error: at least one --rgb or --range is required")
        sys.exit(1)

    paths = []
    for pattern in patterns:
        expanded = sorted(glob.glob(pattern))
        paths.extend(expanded if expanded else [pattern])

    if not paths:
        print("No images found.")
        sys.exit(1)

    out_dir = 'tmp'
    os.makedirs(out_dir, exist_ok=True)

    desc = []
    if rgb_values:
        rgb_str = ', '.join(f'({rv},{gv},{bv})' for rv, gv, bv in rgb_values)
        desc.append(f'spots: {rgb_str}  tol: ±{tolerance}')
    if ranges:
        rng_str = ', '.join(f'({r1},{g1},{b1})-({r2},{g2},{b2})' for (r1,g1,b1),(r2,g2,b2) in ranges)
        desc.append(f'ranges: {rng_str}')
    print(f"{'  '.join(desc)}  |  {len(paths)} image(s)\n")

    for path in paths:
        process(path, rgb_values, tolerance, ranges, out_dir)


if __name__ == "__main__":
    main()
