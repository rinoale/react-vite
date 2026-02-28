#!/usr/bin/env python3
"""Test prefix detector on tooltip images.

Usage:
    python3 scripts/v3/test_prefix_detector.py <image> [<image> ...]

Detects:
  - Bullet (·) prefixes — blue RGB(74, 149, 238) + red RGB(255, 103, 103)
  - Subbullet (ㄴ) prefixes — white RGB(255, 255, 255)

Accepts either:
  - Pre-masked images (colored text on black bg)
  - Original color BGR images (masks created internally)
"""
import sys, os, glob
import numpy as np
import cv2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from backend.lib.prefix_detector import bullet_text_mask, white_text_mask, detect_prefix
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

    # Bullet (·) mask — blue + red combined
    b_mask = bullet_text_mask(img)
    bullet_results, bullet_ink = _detect_on_mask(b_mask, h, w, 'bullet', splitter)

    # Subbullet (ㄴ) mask — white
    w_mask = white_text_mask(img)
    sub_results, white_ink = _detect_on_mask(w_mask, h, w, 'subbullet', splitter)

    print(f"  bullet ink (blue+red): {bullet_ink:.1f}%  white ink: {white_ink:.1f}%")

    # Filter: bullet mask → only bullets, white mask → only subbullets
    filtered = []
    for r in bullet_results:
        if r['type'] == 'bullet':
            filtered.append(r)
    for r in sub_results:
        if r['type'] == 'subbullet':
            filtered.append(r)

    all_results = bullet_results + sub_results
    if not filtered:
        print(f"  lines scanned: {len(all_results)}  (no prefixes found)")
        return

    filtered.sort(key=lambda r: r['y'])

    bullet_count = sum(1 for r in filtered if r['type'] == 'bullet')
    sub_count = sum(1 for r in filtered if r['type'] == 'subbullet')

    print(f"  lines scanned: {len(all_results)}  prefixes found: {len(filtered)}")
    print()

    for i, r in enumerate(filtered):
        detail = f"  w={r['w']}  gap={r['gap']}  main_x={r['main_x']}"
        print(f"  [{i+1:2d}] y={r['y']:4d}  {r['type']:10s}  h={r['h']:2d}  crop={r['crop_w']:3d}x{r['crop_h']:2d}{detail}")

    print(f"\n  Summary: {bullet_count} bullet, {sub_count} subbullet")


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
