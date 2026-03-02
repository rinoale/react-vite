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

from dataclasses import dataclass

import numpy as np

from lib.shape_walker import classify_cluster, SHAPE_NIEUN, SHAPE_DOT

# Blue effect text — game engine constant across all 26 themes.
# Marks enchant effects, reforge options, set bonuses, stat modifiers.
EFFECT_BLUE_RGB = (74, 149, 238)

# Red effect text — negative enchant effects.
EFFECT_RED_RGB = (255, 103, 103)

# Grey effect text — disabled/conditional effects not meeting requirements.
EFFECT_GREY_RGB = (128, 128, 128)

# Light grey effect text — partially disabled/conditional effects (brighter shade).
EFFECT_LIGHT_GREY_RGB = (167, 167, 167)

# White text — subbullet ㄴ prefix in reforge sub-lines.
WHITE_TEXT_RGB = (255, 255, 255)

# All bullet (·) colors — blue (positive) + red (negative) + grey (disabled) + light grey.
BULLET_COLORS = [EFFECT_BLUE_RGB, EFFECT_RED_RGB, EFFECT_GREY_RGB, EFFECT_LIGHT_GREY_RGB]

# All subbullet (ㄴ) colors — white (reforge sub-lines) + red (negative effects)
# + grey (disabled/conditional effects).
SUBBULLET_COLORS = [WHITE_TEXT_RGB, EFFECT_RED_RGB, EFFECT_GREY_RGB]


@dataclass(frozen=True)
class PrefixDetectorConfig:
    """Declarative (colors, shapes, name) binding for prefix detection.

    Each config specifies which colors to mask and which shapes to look for,
    making prefix detection a swappable, testable unit.
    """
    name: str              # 'bullet' or 'subbullet'
    colors: tuple          # RGB tuples for mask building
    shapes: tuple          # ShapeDef instances to try

    def build_mask(self, img_bgr, tolerance=15):
        """Combined binary mask for all configured colors."""
        mask = np.zeros(img_bgr.shape[:2], dtype=np.uint8)
        for rgb in self.colors:
            mask = np.maximum(mask, _color_mask(img_bgr, rgb, tolerance))
        return mask


BULLET_DETECTOR = PrefixDetectorConfig(
    name='bullet',
    colors=(EFFECT_BLUE_RGB, EFFECT_RED_RGB, EFFECT_GREY_RGB, EFFECT_LIGHT_GREY_RGB),
    shapes=(SHAPE_DOT,),
)

SUBBULLET_DETECTOR = PrefixDetectorConfig(
    name='subbullet',
    colors=(WHITE_TEXT_RGB, EFFECT_RED_RGB, EFFECT_GREY_RGB),
    shapes=(SHAPE_NIEUN,),
)


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


def _classify_ink(cluster_region, h, first_w, config, col_proj_slice=None):
    """Classify prefix by cluster width + vertical ink extent.

    bullet  (-) : width ≤ max(3, h*0.25), ink rows ≤ max(4, h*0.5),
                  uniform column projection (rejects bracket '[' FPs)
    subbullet (ㄴ) : wider, ink rows ≤ max(8, h*0.75)

    Returns prefix type string or None.
    """
    ink_rows = int(np.sum(np.any(cluster_region > 0, axis=1)))
    bullet_max_w = max(3, int(h * 0.25))

    if first_w <= bullet_max_w:
        if ink_rows > max(4, int(h * 0.5)):
            return None
        # Uniform column check: real '-' has similar ink count per column.
        # '[' has e.g. [4, 2] — vertical bar vs horizontal tip.
        if col_proj_slice is not None and len(col_proj_slice) > 1:
            mn, mx = int(col_proj_slice.min()), int(col_proj_slice.max())
            if mn > 0 and mx > mn * 2:
                return None
        prefix_type = 'bullet'
    else:
        if ink_rows > max(8, int(h * 0.75)):
            return None
        prefix_type = 'subbullet'

    if config is not None and prefix_type != config.name:
        return None
    return prefix_type


def _classify_shape_walker(cluster_region, config):
    """Classify prefix by shape walker (directional ink tracing).

    Uses config.shapes when given, otherwise tries both SHAPE_NIEUN and SHAPE_DOT.

    Returns prefix type string or None.
    """
    if config is not None:
        match = classify_cluster(cluster_region, list(config.shapes))
        return config.name if match is not None else None
    else:
        match = classify_cluster(cluster_region, [SHAPE_NIEUN, SHAPE_DOT])
        if match is None:
            return None
        return 'subbullet' if match.shape.name == 'ㄴ' else 'bullet'


def _is_dot_isolated(mask_line, first_start, first_end):
    """Check that dot cluster ink is vertically isolated from other ink.

    A real dot (·) sits alone with empty space above and below.
    Character fragments (e.g. bracket corners, ※ arms) have nearby
    ink pixels in the vertical direction within the cluster columns.

    Finds the tight bounding box of ink rows in the cluster columns,
    then checks padding zones above and below for stray ink.
    """
    cluster_cols = mask_line[:, first_start:first_end]
    ink_mask = np.any(cluster_cols > 0, axis=1)
    ink_indices = np.where(ink_mask)[0]
    if len(ink_indices) == 0:
        return False

    ink_top = int(ink_indices[0])
    ink_bot = int(ink_indices[-1])
    ink_span = ink_bot - ink_top + 1
    h = mask_line.shape[0]

    # Span check: ink rows should be compact, not scattered across the line
    # A real dot spans at most ~4 rows; bracket corners span 10+
    if ink_span > max(4, int(h * 0.4)):
        return False

    # Vertical padding check: look for ink above and below the cluster
    pad = max(2, ink_span)
    above_start = max(0, ink_top - pad)
    below_end = min(h, ink_bot + pad + 1)

    # Check above: any ink in padding zone?
    if ink_top > 0:
        above = cluster_cols[above_start:ink_top]
        if np.any(above > 0):
            return False

    # Check below: any ink in padding zone?
    if ink_bot < h - 1:
        below = cluster_cols[ink_bot + 1:below_end]
        if np.any(below > 0):
            return False

    return True


def _classify_combined(cluster_region, h, first_w, config,
                       col_proj_slice=None, mask_line=None,
                       first_start=0, first_end=0):
    """Classify prefix by shape walker + ink size constraints + isolation.

    Shape walker confirms the shape (dot or ㄴ), then ink classification's
    size constraints filter out character fragments that happen to pass
    the shape check (e.g. anti-aliased pixels around header characters).
    For bullets, an isolation check rejects clusters whose ink pixels have
    nearby ink above/below (e.g. bracket corners, ※ cardinal dots).

    bullet  : shape=DOT,  width ≤ max(3, h*0.25), ink rows ≤ max(4, h*0.5),
              vertically isolated
    subbullet: shape=NIEUN, ink rows ≤ max(8, h*0.75)

    Returns prefix type string or None.
    """
    prefix_type = _classify_shape_walker(cluster_region, config)
    if prefix_type is None:
        return None

    ink_rows = int(np.sum(np.any(cluster_region > 0, axis=1)))

    if prefix_type == 'bullet':
        bullet_max_w = max(3, int(h * 0.25))
        if first_w > bullet_max_w:
            return None
        if ink_rows > max(4, int(h * 0.5)):
            return None
        if col_proj_slice is not None and len(col_proj_slice) > 1:
            mn, mx = int(col_proj_slice.min()), int(col_proj_slice.max())
            if mn > 0 and mx > mn * 2:
                return None
        if mask_line is not None:
            if not _is_dot_isolated(mask_line, first_start, first_end):
                return None
    elif prefix_type == 'subbullet':
        # A real ㄴ at game font is 3-5 cols wide in the cluster.
        # Wider clusters are multi-character fragments that happen
        # to pass the L-shape check.
        if first_w > max(6, int(h * 0.45)):
            return None
        if ink_rows > max(8, int(h * 0.75)):
            return None

    return prefix_type


def detect_prefix(mask_line, config=None):
    """Detect a prefix mark at the left edge of a single line mask.

    Scans columns left→right for the pattern:
        [small ink cluster] → [clear gap] → [main text]

    Args:
        mask_line: 2-D uint8 array of one line region (255 = ink).
        config:    optional PrefixDetectorConfig. When given, only accepts
                   prefixes matching config.name; rejects the other type.

    Returns:
        dict  type  : 'bullet' | 'subbullet' | None
              x     : column where prefix starts  (-1 if None)
              w     : prefix cluster width         (-1 if None)
              gap   : gap columns to main text     (-1 if None)
              main_x: column where main text starts(-1 if None)
    """
    return _detect_prefix_on_mask(mask_line, config)


def detect_prefix_per_color(img_bgr_line, config, tolerance=15):
    """Detect a prefix by testing each color in config independently.

    A real prefix is always a single color. Running detection on each
    single-color mask prevents mixed-color fragments from forming
    false prefix clusters.

    Args:
        img_bgr_line: BGR color image region of one line.
        config:       PrefixDetectorConfig with colors to test.
        tolerance:    per-channel color distance.

    Returns:
        Same dict as detect_prefix.
    """
    binary = None  # lazy BT.601 binary, built once if needed
    for rgb in config.colors:
        mask = _color_mask(img_bgr_line, rgb, tolerance)
        result = _detect_prefix_on_mask(mask, config)
        if result['type'] is not None:
            cluster = mask[:, result['x']:result['x'] + result['w']]
            # A real bullet dot in any single-color mask has 2+ ink
            # pixels in exactly 1 ink row.  Anti-aliased specks are
            # either too sparse (1 pixel) or scattered across rows.
            total_ink = int(np.sum(cluster > 0))
            if result['type'] == 'bullet':
                # A real dot has 2+ ink pixels in exactly 1 row.
                if total_ink < 2:
                    continue
                ink_rows = int(np.sum(np.any(cluster > 0, axis=1)))
                if ink_rows > 1:
                    continue
                # BT.601 isolation: a real dot is isolated from all
                # text, not just same-color text.  Anti-aliased specks
                # sit at character edges and fail this check.
                if binary is None:
                    gray = np.dot(img_bgr_line[..., ::-1].astype(np.float32),
                                  [0.299, 0.587, 0.114]).astype(np.uint8)
                    binary = ((gray > 80) * 255).astype(np.uint8)
                if not _is_dot_isolated(binary, result['x'], result['x'] + result['w']):
                    continue
            elif result['type'] == 'subbullet':
                # A real ㄴ has ~10 pixels: 6 vertical + 4 horizontal.
                # Shape walker already validates the L-shape, so only
                # a minimum ink check is needed here.
                if total_ink < 6:
                    continue
                # A real ㄴ has a clear gap (≥3 cols) before main text.
                # Text character fragments have smaller gaps (1-2 cols).
                if result['gap'] < 3:
                    continue
                # A real ㄴ line is 10+ rows after padding. Short lines
                # (h<10) have text characters that mimic L-shapes.
                if img_bgr_line.shape[0] < 10:
                    continue
            return result

    # Fallback for subbullet: the ㄴ character can fragment in a
    # single-color mask (vertical stroke separated from horizontal).
    # Find the narrow cluster position from single-color mask, then
    # run shape walker on BT.601 binary where the full ㄴ is intact.
    if config.name == 'subbullet':
        result = _detect_subbullet_fallback(img_bgr_line, config, tolerance,
                                            binary)

        if result is not None:
            return result

    return _no_prefix()


def _detect_subbullet_fallback(img_bgr_line, config, tolerance, binary):
    """Detect fragmented ㄴ by finding narrow cluster in color mask,
    then validating vertical stroke + gap on BT.601 binary.

    In some fonts/sizes the ㄴ vertical and horizontal strokes separate
    in a single-color mask.  The vertical stroke alone is too narrow
    for the shape walker.  Here we:
      1. Find a narrow first cluster in any config color mask
      2. In BT.601 binary, find the ink block near that position
      3. Validate: tall vertical stroke, gap after, text follows
    """
    # Step 1: find narrow cluster position from any config color
    cluster_x = None
    for rgb in config.colors:
        mask = _color_mask(img_bgr_line, rgb, tolerance)
        h, w = mask.shape[:2]
        if w < 10 or h < 3:
            continue
        col_proj = np.sum(mask > 0, axis=0)
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
            continue
        # Cluster must be near the left edge — a subbullet prefix
        # is always at the start of the line, not mid-text.
        if first_start > max(10, int(w * 0.15)):
            continue
        first_w = first_end - first_start
        max_prefix_w = max(6, int(h * 0.5))
        if first_w <= max_prefix_w:
            cluster_x = first_start
            break

    if cluster_x is None:
        return None

    # Step 2: build BT.601 binary
    if binary is None:
        gray = np.dot(img_bgr_line[..., ::-1].astype(np.float32),
                      [0.299, 0.587, 0.114]).astype(np.uint8)
        binary = ((gray > 80) * 255).astype(np.uint8)

    h_bin, w_bin = binary.shape[:2]
    bin_col_proj = np.sum(binary > 0, axis=0)

    # Step 3: find ink block in binary near cluster_x
    search_start = max(0, cluster_x - 2)
    bin_ink_start = -1
    for x in range(search_start, min(w_bin, cluster_x + 3)):
        if bin_col_proj[x] > 0:
            bin_ink_start = x
            break

    if bin_ink_start < 0:
        return None

    # Find end of ink block (first zero column)
    bin_ink_end = -1
    for x in range(bin_ink_start + 1, min(w_bin, bin_ink_start + 10)):
        if bin_col_proj[x] == 0:
            bin_ink_end = x
            break

    if bin_ink_end < 0:
        return None

    # Find main text start (first ink after gap)
    bin_main_start = -1
    for x in range(bin_ink_end + 1, min(w_bin, bin_ink_end + 10)):
        if bin_col_proj[x] > 0:
            bin_main_start = x
            break

    if bin_main_start < 0:
        return None

    # Step 4: validate — ink block must be a tall vertical stroke
    nieun_w = bin_ink_end - bin_ink_start
    gap_w = bin_main_start - bin_ink_end

    # Width: a real ㄴ in binary is 3-4 cols wide.
    # Text characters are 8+.
    if nieun_w > 6:
        return None

    # Gap: a real ㄴ has a clear gap (≥3 cols) before main text.
    # Text character inter-character gaps are typically 1-2 cols.
    min_gap = max(3, int(h_bin * 0.2))
    if gap_w < min_gap:
        return None

    bin_block = binary[:, bin_ink_start:bin_ink_end]
    ink_rows = int(np.sum(np.any(bin_block > 0, axis=1)))

    if ink_rows < max(6, int(h_bin * 0.5)):
        return None

    return {
        'type': 'subbullet',
        'x': bin_ink_start,
        'w': nieun_w,
        'gap': gap_w,
        'main_x': bin_main_start,
    }


def _detect_prefix_on_mask(mask_line, config):
    """Core prefix detection on a single binary mask."""
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

    cluster_region = mask_line[:, first_start:first_end]
    col_proj_slice = col_proj[first_start:first_end]

    # --- Switch classifier here ---
    prefix_type = _classify_combined(
        cluster_region, h, first_w, config, col_proj_slice,
        mask_line=mask_line, first_start=first_start, first_end=first_end,
    )

    if prefix_type is None:
        return _no_prefix()

    return {
        'type': prefix_type,
        'x': first_start,
        'w': first_w,
        'gap': gap_w,
        'main_x': main_start,
    }


def _no_prefix():
    return {'type': None, 'x': -1, 'w': -1, 'gap': -1, 'main_x': -1}
