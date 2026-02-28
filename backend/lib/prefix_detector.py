"""
Prefix detector for Mabinogi tooltip content lines.

Detects bullet (·) and subbullet (ㄴ) prefix marks using visual properties:
  - Color: blue effect text RGB(74, 149, 238) — bullet (·)
           white text RGB(255, 255, 255) — subbullet (ㄴ)
  - Shape: small isolated ink cluster at left edge, gap before main text

Bypasses OCR for these tiny characters which are frequently misread:
  · → ., -, , or dropped entirely
  ㄴ → L or dropped entirely

Usage:
    mask = blue_text_mask(content_bgr)
    for line in line_bounds:
        line_mask = mask[y0:y1, x0:x1]
        info = detect_prefix(line_mask)
        # info['type'] == 'bullet' | 'subbullet' | None
"""

import numpy as np

# Blue effect text — game engine constant across all 26 themes.
# Marks enchant effects, reforge options, set bonuses, stat modifiers.
EFFECT_BLUE_RGB = (74, 149, 238)

# Red effect text — negative enchant effects.
EFFECT_RED_RGB = (255, 103, 103)

# Grey effect text — disabled/conditional effects not meeting requirements.
EFFECT_GREY_RGB = (128, 128, 128)

# White text — subbullet ㄴ prefix in reforge sub-lines.
WHITE_TEXT_RGB = (255, 255, 255)

# All bullet (·) colors — blue (positive) + red (negative) + grey (disabled).
BULLET_COLORS = [EFFECT_BLUE_RGB, EFFECT_RED_RGB, EFFECT_GREY_RGB]

# All subbullet (ㄴ) colors — white (reforge sub-lines) + red (negative effects).
SUBBULLET_COLORS = [WHITE_TEXT_RGB, EFFECT_RED_RGB]


def _color_mask(img_bgr, rgb, tolerance):
    """Binary mask matching a specific RGB color."""
    target = np.array([rgb[2], rgb[1], rgb[0]], dtype=np.int16)
    diff = np.abs(img_bgr.astype(np.int16) - target)
    return np.all(diff <= tolerance, axis=2).astype(np.uint8) * 255


def blue_text_mask(img_bgr, tolerance=15):
    """Binary mask matching blue effect text color.

    Args:
        img_bgr: BGR color image (numpy array).
        tolerance: per-channel distance from EFFECT_BLUE_RGB.

    Returns:
        uint8 array, 255 = match, 0 = no match.
    """
    return _color_mask(img_bgr, EFFECT_BLUE_RGB, tolerance)


def red_text_mask(img_bgr, tolerance=15):
    """Binary mask matching red negative effect text color."""
    return _color_mask(img_bgr, EFFECT_RED_RGB, tolerance)


def bullet_text_mask(img_bgr, tolerance=15):
    """Binary mask matching all prefix colors (bullet + subbullet).

    Includes all colors that can carry · or ㄴ prefix marks.
    detect_prefix() classifies by cluster width, not color.
    """
    mask = np.zeros(img_bgr.shape[:2], dtype=np.uint8)
    for rgb in set(BULLET_COLORS + SUBBULLET_COLORS):
        mask = np.maximum(mask, _color_mask(img_bgr, rgb, tolerance))
    return mask


def white_text_mask(img_bgr, tolerance=15):
    """Binary mask matching white text color.

    Args:
        img_bgr: BGR color image (numpy array).
        tolerance: per-channel distance from WHITE_TEXT_RGB.

    Returns:
        uint8 array, 255 = match, 0 = no match.
    """
    return _color_mask(img_bgr, WHITE_TEXT_RGB, tolerance)


def detect_prefix(mask_line):
    """Detect a prefix mark at the left edge of a single line mask.

    Scans columns left→right for the pattern:
        [small ink cluster] → [clear gap] → [main text]

    Classifies by cluster width:
        bullet  (·) : ≤ max(3, h*0.25) px
        subbullet (ㄴ) : wider, up to max(8, h*0.7) px

    Args:
        mask_line: 2-D uint8 array of one line region (255 = ink).

    Returns:
        dict  type  : 'bullet' | 'subbullet' | None
              x     : column where prefix starts  (-1 if None)
              w     : prefix cluster width         (-1 if None)
              gap   : gap columns to main text     (-1 if None)
              main_x: column where main text starts(-1 if None)
    """
    h, w = mask_line.shape[:2]
    if w < 10 or h < 3:
        return _no_prefix()

    # Column projection — number of ink pixels per column
    col_proj = np.sum(mask_line > 0, axis=0)

    # State machine: first_cluster → gap → main_text
    first_start = first_end = main_start = -1
    for x in range(w):
        has_ink = col_proj[x] > 0
        if first_start < 0:
            if has_ink:
                first_start = x
        elif first_end < 0:
            if not has_ink:
                first_end = x
        elif main_start < 0:
            if has_ink:
                main_start = x
                break

    if first_start < 0 or first_end < 0 or main_start < 0:
        return _no_prefix()

    first_w = first_end - first_start
    gap_w = main_start - first_end

    # Adaptive thresholds relative to line height
    max_prefix_w = max(8, int(h * 0.7))
    min_gap = max(2, int(h * 0.2))

    if first_w > max_prefix_w or gap_w < min_gap:
        return _no_prefix()

    # Vertical ink extent of first cluster — reject full-height characters.
    # Real · is a small dot (ink_rows/h ≈ 0.15-0.25).
    # Real ㄴ is taller but still partial (ink_rows/h ≈ 0.35-0.55).
    # Plain text characters span most of the line (ink_rows/h ≈ 0.7-1.0).
    cluster_region = mask_line[:, first_start:first_end]
    ink_rows = int(np.sum(np.any(cluster_region > 0, axis=1)))

    # Classify by width
    bullet_max_w = max(3, int(h * 0.25))
    if first_w <= bullet_max_w:
        # Bullet (·): must be vertically small
        if ink_rows > max(4, int(h * 0.5)):
            return _no_prefix()
        prefix_type = 'bullet'
    else:
        # Subbullet (ㄴ): can be taller but not full-height
        if ink_rows > max(8, int(h * 0.75)):
            return _no_prefix()
        prefix_type = 'subbullet'

    return {
        'type': prefix_type,
        'x': first_start,
        'w': first_w,
        'gap': gap_w,
        'main_x': main_start,
    }


def _no_prefix():
    return {'type': None, 'x': -1, 'w': -1, 'gap': -1, 'main_x': -1}
