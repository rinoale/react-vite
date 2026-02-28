#!/usr/bin/env python3
"""Test prefix detector on tooltip images.

Usage:
    python3 scripts/v3/test_prefix_detector.py <image> [<image> ...]

Detects:
  - Blue bullet (·) prefixes — RGB(74, 149, 238)
  - White subbullet (ㄴ) prefixes — RGB(255, 255, 255)

Accepts either:
  - Pre-masked images (colored text on black bg)
  - Original color BGR images (masks created internally)
"""
import sys, os, glob
import numpy as np
import cv2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from backend.lib.prefix_detector import blue_text_mask, white_text_mask, detect_prefix
from backend.lib.tooltip_line_splitter import TooltipLineSplitter


def _detect_on_mask(mask, img_h, img_w, label, splitter):
    """Run line detection + prefix detection on a single color mask."""
    ink_pct = 100.0 * np.sum(mask > 0) / mask.size
    lines = splitter.detect_text_lines(mask)

    if not lines:
        return [], ink_pct

    results = []
    for line in lines:
        x, y, lw, lh = line['x'], line['y'], line['width'], line['height']
        pad_x = max(2, lh // 3)
        pad_y = max(1, lh // 5)
        y0 = max(0, y - pad_y)
        y1 = min(img_h, y + lh + pad_y)
        x0 = max(0, x - pad_x)
        x1 = min(img_w, x + lw + pad_x)

        line_mask = mask[y0:y1, x0:x1]
        info = detect_prefix(line_mask)
        results.append({
            'color': label,
            'y': y, 'h': lh,
            'crop_w': x1 - x0, 'crop_h': y1 - y0,
            **info,
        })

    return results, ink_pct


def run_on_image(path):
    img = cv2.imread(path)
    if img is None:
        print(f"  ERROR: cannot read {path}")
        return

    name = os.path.basename(path)
    h, w = img.shape[:2]
    print(f"\n{'='*60}")
    print(f"  {name}  ({w}x{h})")
    print(f"{'='*60}")

    splitter = TooltipLineSplitter(output_dir='/tmp/prefix_test')

    # Blue mask — bullet (·) detection
    b_mask = blue_text_mask(img)
    blue_results, blue_ink = _detect_on_mask(b_mask, h, w, 'blue', splitter)

    # White mask — subbullet (ㄴ) detection
    w_mask = white_text_mask(img)
    white_results, white_ink = _detect_on_mask(w_mask, h, w, 'white', splitter)

    print(f"  blue ink: {blue_ink:.1f}%  white ink: {white_ink:.1f}%")

    # Merge and sort by y position
    all_results = sorted(blue_results + white_results, key=lambda r: r['y'])

    # Filter: blue → only bullets, white → only subbullets
    filtered = []
    for r in all_results:
        if r['color'] == 'blue' and r['type'] == 'bullet':
            filtered.append(r)
        elif r['color'] == 'white' and r['type'] == 'subbullet':
            filtered.append(r)

    if not filtered:
        print(f"  lines scanned: {len(all_results)}  (no prefixes found)")
        return

    bullet_count = sum(1 for r in filtered if r['type'] == 'bullet')
    sub_count = sum(1 for r in filtered if r['type'] == 'subbullet')

    print(f"  lines scanned: {len(all_results)}  prefixes found: {len(filtered)}")
    print()

    for i, r in enumerate(filtered):
        tag = f"{r['color']}_{r['type']}"
        detail = f"  w={r['w']}  gap={r['gap']}  main_x={r['main_x']}"
        print(f"  [{i+1:2d}] y={r['y']:4d}  {tag:18s}  h={r['h']:2d}  crop={r['crop_w']:3d}x{r['crop_h']:2d}{detail}")

    print(f"\n  Summary: {bullet_count} blue_bullet, {sub_count} white_subbullet")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/v3/test_prefix_detector.py <image> [<image> ...]")
        sys.exit(1)

    paths = []
    for arg in sys.argv[1:]:
        paths.extend(glob.glob(arg))

    if not paths:
        print(f"No files matched: {sys.argv[1:]}")
        sys.exit(1)

    for path in sorted(paths):
        run_on_image(path)


if __name__ == '__main__':
    main()
