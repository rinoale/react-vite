#!/usr/bin/env python3
"""Test prefix detector on tooltip images.

Usage:
    python3 scripts/v3/test_prefix_detector.py <image> [<image> ...]

Generates three visualization images per input:
  1. *_bullet.png     — bullet (·) via blue+red mask
  2. *_subbullet.png  — subbullet (ㄴ) via white mask
  3. *_shapewalk.png  — shape walker on all colors combined

Output saved to /tmp/prefix_viz/
"""
import sys, os, glob
import numpy as np
import cv2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
from backend.lib.prefix_detector import (
    bullet_text_mask, white_text_mask, detect_prefix,
    BULLET_DETECTOR, SUBBULLET_DETECTOR,
)
from backend.lib.tooltip_line_splitter import TooltipLineSplitter
from backend.lib.tooltip_segmenter import detect_bottom_border, detect_vertical_borders


# --- Detection ---

def _detect_on_mask(mask, img_h, img_w, label, splitter, config=None):
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
        info = detect_prefix(line_mask, config=config)
        results.append({
            'color': label,
            'y': y, 'h': lh,
            'crop_x0': x0, 'crop_y0': y0,
            'crop_w': x1 - x0, 'crop_h': y1 - y0,
            **info,
        })

    return results, ink_pct


# --- Visualization ---

COLOR_BULLET    = (0, 255, 0)    # green
COLOR_SUBBULLET = (255, 255, 0)  # cyan
COLOR_LINE      = (0, 200, 255)  # yellow
COLOR_NONE      = (128, 128, 128)  # grey
TYPE_COLORS = {'bullet': COLOR_BULLET, 'subbullet': COLOR_SUBBULLET}


def _draw_results(img, results, out_path, title=None):
    """Draw detection boxes on image and save."""
    vis = img.copy()

    for r in results:
        x0, y0 = r['crop_x0'], r['crop_y0']
        cw, ch = r['crop_w'], r['crop_h']

        # Line bounding box
        cv2.rectangle(vis, (x0, y0), (x0 + cw, y0 + ch), COLOR_LINE, 1)

        # Prefix cluster box
        if r['x'] >= 0:
            px = x0 + r['x']
            pw = r['w']
            color = TYPE_COLORS.get(r['type'], COLOR_NONE)
            cv2.rectangle(vis, (px, y0), (px + pw, y0 + ch), color, 2)

        # Label
        label = r['type'] or 'none'
        color = TYPE_COLORS.get(r['type'], COLOR_NONE)
        cv2.putText(vis, label, (x0 + cw + 4, y0 + ch - 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)

    # Title bar
    if title:
        cv2.putText(vis, title, (4, 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)

    cv2.imwrite(out_path, vis)


# --- Border crop ---

def _crop_tooltip_border(img):
    """Crop to tooltip boundary (same as V3 pipeline Stage 1)."""
    bottom_y = detect_bottom_border(img)
    left_x, right_x = detect_vertical_borders(img)
    y1 = (bottom_y + 1) if bottom_y is not None else img.shape[0]
    x0 = (left_x + 1) if left_x is not None else 0
    x1 = right_x if right_x is not None else img.shape[1]
    return img[0:y1, x0:x1]


# --- Main ---

def _summary_str(results):
    b = sum(1 for r in results if r['type'] == 'bullet')
    s = sum(1 for r in results if r['type'] == 'subbullet')
    n = sum(1 for r in results if r['type'] is None)
    parts = []
    if b: parts.append(f"{b} bullet")
    if s: parts.append(f"{s} subbullet")
    if n: parts.append(f"{n} none")
    return ', '.join(parts) if parts else 'nothing'


def run_on_image(path, out_dir):
    img = cv2.imread(path)
    if img is None:
        print(f"  ERROR: cannot read {path}")
        return

    name = os.path.basename(path)
    stem = os.path.splitext(name)[0]
    orig_h, orig_w = img.shape[:2]

    # Stage 1: crop to tooltip boundary
    img = _crop_tooltip_border(img)
    h, w = img.shape[:2]
    print(f"\n{'='*60}")
    print(f"  {name}  ({orig_w}x{orig_h} -> {w}x{h} cropped)")
    print(f"{'='*60}")

    splitter = TooltipLineSplitter(output_dir='/tmp/prefix_test')
    os.makedirs(out_dir, exist_ok=True)

    # --- 1. Bullet: config-driven mask + shape ---
    b_mask = BULLET_DETECTOR.build_mask(img)
    bullet_all, bullet_ink = _detect_on_mask(b_mask, h, w, 'bullet', splitter,
                                             config=BULLET_DETECTOR)
    bullet_found = [r for r in bullet_all if r['type'] == 'bullet']
    bullet_found.sort(key=lambda r: r['y'])

    out1 = os.path.join(out_dir, f"{stem}_bullet.png")
    _draw_results(img, bullet_found, out1,
                  title=f"Bullet (config): {len(bullet_found)} found")
    print(f"  [1] Bullet    : {_summary_str(bullet_all):30s}  -> {out1}")

    # --- 2. Subbullet: config-driven mask + shape ---
    s_mask = SUBBULLET_DETECTOR.build_mask(img)
    sub_all, white_ink = _detect_on_mask(s_mask, h, w, 'subbullet', splitter,
                                         config=SUBBULLET_DETECTOR)
    sub_found = [r for r in sub_all if r['type'] == 'subbullet']
    sub_found.sort(key=lambda r: r['y'])

    out2 = os.path.join(out_dir, f"{stem}_subbullet.png")
    _draw_results(img, sub_found, out2,
                  title=f"Subbullet (config): {len(sub_found)} found")
    print(f"  [2] Subbullet : {_summary_str(sub_all):30s}  -> {out2}")

    # --- 3. Shape Walker: all colors combined, classify both types ---
    combined = np.zeros((h, w), dtype=np.uint8)
    for mask in [b_mask, w_mask]:
        combined = np.maximum(combined, mask)
    sw_all, _ = _detect_on_mask(combined, h, w, 'combined', splitter)
    sw_found = [r for r in sw_all if r['type'] is not None]
    sw_found.sort(key=lambda r: r['y'])

    out3 = os.path.join(out_dir, f"{stem}_shapewalk.png")
    _draw_results(img, sw_found, out3,
                  title=f"Shape Walker (all colors): {len(sw_found)} found")
    print(f"  [3] ShapeWalk : {_summary_str(sw_all):30s}  -> {out3}")

    # --- Comparison ---
    print()
    print(f"  Bullet ink: {bullet_ink:.1f}%  White ink: {white_ink:.1f}%")
    print(f"  Lines scanned: bullet={len(bullet_all)}, white={len(sub_all)}, combined={len(sw_all)}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/v3/test_prefix_detector.py <image> [<image> ...]")
        print("  Output: /tmp/prefix_viz/<stem>_{bullet,subbullet,shapewalk}.png")
        sys.exit(1)

    paths = []
    for arg in sys.argv[1:]:
        paths.extend(glob.glob(arg))

    if not paths:
        print(f"No files matched: {sys.argv[1:]}")
        sys.exit(1)

    out_dir = '/tmp/prefix_viz'
    for path in sorted(paths):
        run_on_image(path, out_dir)


if __name__ == '__main__':
    main()
