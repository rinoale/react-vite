"""Mabinogi-specific image processing for tooltip OCR pipeline.

Functions that operate on BGR image data to classify, mask, and detect
structural elements of Mabinogi game tooltips.
"""

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Enchant line classification
# ---------------------------------------------------------------------------

# Minimum brightness (max channel) for a pixel to count as foreground text.
# Pixels below this are dark background.
_TEXT_BRIGHTNESS_THRESHOLD = 40

# Mean saturation boundary between grey (description) and colored (effect) text.
# Grey lines: sat < 0.15 (인챈트 추출 불가, empty-slot explanations).
# Effect lines: sat > 0.2 (blue/red enchant effects).
_GREY_SATURATION_CUTOFF = 0.15

# ---------------------------------------------------------------------------
# White-text mask (oreo_flip)
# ---------------------------------------------------------------------------

# Minimum per-channel brightness to qualify as "white" text.
_WHITE_MIN_BRIGHTNESS = 150

# Maximum channel ratio (max/min) for balanced (white) pixels.
# Colored pixels (blue, red, yellow) have ratio > 2; white text < 1.4.
_WHITE_MAX_CHANNEL_RATIO = 1.4

# Border column stripping: number of edge columns and density threshold.
_BORDER_EDGE_COLUMNS = 3
_BORDER_DENSITY_THRESHOLD = 0.5

# ---------------------------------------------------------------------------
# HSV yellow isolation (nanum_gothic preprocessing)
# ---------------------------------------------------------------------------

# HSV saturation floor (~15% of 255). Pixels below this are white/black
# (no hue information), so they're excluded from the "not-yellow" reject mask.
_HSV_SATURATION_THRESHOLD = 38

# Yellow hue range on OpenCV's 0-180 scale.
# Covers the yellow band used in game tooltip text.
_HSV_YELLOW_HUE_MIN = 25
_HSV_YELLOW_HUE_MAX = 40

# Binary threshold applied after yellow-masked grayscale conversion.
_YELLOW_BINARY_THRESHOLD = 120

# ---------------------------------------------------------------------------
# Enchant slot header band detection
# ---------------------------------------------------------------------------

# Minimum white pixels per row to count as part of a slot header band.
_HEADER_ROW_THRESHOLD = 10

# Gap tolerance (rows) for merging adjacent white-pixel runs into one band.
_HEADER_GAP_TOLERANCE = 2

# Valid header band height range (pixels).
_HEADER_MIN_HEIGHT = 8
_HEADER_MAX_HEIGHT = 15

# Minimum total white pixel count within a band to accept it as a header.
_HEADER_MIN_WHITE_PIXELS = 150


def classify_enchant_line(content_bgr, bounds, bands):
    """Classify an enchant line as 'header', 'effect', or 'grey'.

    Uses band overlap for headers, mean text-pixel saturation for grey vs effect.
    Grey lines (descriptions, "인챈트 추출 불가", empty-slot explanations) have
    desaturated text (sat < 0.15) while effect lines are colored (sat > 0.2).

    Args:
        content_bgr: BGR numpy array of the enchant content region
        bounds:      dict with 'x', 'y', 'width', 'height'
        bands:       list of (y_start, y_end) from detect_enchant_slot_headers()

    Returns:
        'header', 'effect', or 'grey'
    """
    y, h = bounds['y'], bounds['height']
    x, w = bounds['x'], bounds['width']

    # Band overlap → header
    if any(min(y + h, be) - max(y, bs) > 0 for bs, be in bands):
        return 'header'

    # Saturation of text pixels (foreground only, bg excluded)
    roi = content_bgr[y:y + h, x:x + w]
    roi_max = roi.max(axis=2)
    text_mask = roi_max > _TEXT_BRIGHTNESS_THRESHOLD
    if text_mask.sum() == 0:
        return 'grey'

    text_px = roi[text_mask].astype(np.float32)
    max_ch = text_px.max(axis=1)
    min_ch = text_px.min(axis=1)
    mean_sat = ((max_ch - min_ch) / (max_ch + 1)).mean()

    return 'grey' if mean_sat < _GREY_SATURATION_CUTOFF else 'effect'


def _strip_border_cols(white_mask, edge_cols=_BORDER_EDGE_COLUMNS,
                       density_threshold=_BORDER_DENSITY_THRESHOLD):
    """Mask out edge columns with high white pixel density (border artifacts).

    Checks the leftmost and rightmost `edge_cols` columns. If the fraction
    of white pixels exceeds `density_threshold`, that column is cleared.
    Border columns have near-continuous bright pixels (50-90% density),
    while text in edge columns has sparse, short bursts (~10-15px per line).
    """
    h, w = white_mask.shape
    cols_to_check = list(range(min(edge_cols, w))) + \
                    list(range(max(0, w - edge_cols), w))

    for c in cols_to_check:
        density = white_mask[:, c].sum() / h
        if density > density_threshold:
            white_mask[:, c] = False

    return white_mask


def oreo_flip(content_bgr):
    """BGR → white mask (bright & balanced) → strip border cols → invert to black-on-white.

    bright-on-dark → white mask (max_ch>150, ratio<1.4) → strip border cols → invert
    """
    r = content_bgr[:, :, 2].astype(np.float32)
    g = content_bgr[:, :, 1].astype(np.float32)
    b = content_bgr[:, :, 0].astype(np.float32)
    max_ch = np.maximum(np.maximum(r, g), b)
    min_ch = np.minimum(np.minimum(r, g), b)
    white_mask = (max_ch > _WHITE_MIN_BRIGHTNESS) & ((max_ch / (min_ch + 1)) < _WHITE_MAX_CHANNEL_RATIO)
    white_mask = _strip_border_cols(white_mask)
    ocr_input = cv2.bitwise_not(white_mask.astype(np.uint8) * 255)
    return white_mask, ocr_input


def hsv_yellow_binary(content_bgr):
    """HSV yellow-isolate + threshold 120 BINARY_INV for enchant slot headers.

    Isolates yellow-hued pixels (H=25-40, OpenCV scale) while preserving
    white/gray text (low saturation → skipped). All other colored pixels
    (pink rank text, blue, etc.) are set to black.

    Returns:
        (detect_mask, ocr_binary)
        - detect_mask: boolean mask of text pixels (for band detection)
        - ocr_binary: black text on white background (for OCR)
    """
    hsv = cv2.cvtColor(content_bgr, cv2.COLOR_BGR2HSV)
    h = hsv[:, :, 0]  # 0-180 in OpenCV
    s = hsv[:, :, 1]  # 0-255 in OpenCV

    # Isolate yellow hue, skip low-saturation pixels (white/black)
    sat_mask = s >= _HSV_SATURATION_THRESHOLD
    not_yellow = ~((h >= _HSV_YELLOW_HUE_MIN) & (h <= _HSV_YELLOW_HUE_MAX))
    reject_mask = sat_mask & not_yellow

    masked = content_bgr.copy()
    masked[reject_mask] = 0

    gray = cv2.cvtColor(masked, cv2.COLOR_BGR2GRAY)
    _, ocr_binary = cv2.threshold(gray, _YELLOW_BINARY_THRESHOLD, 255, cv2.THRESH_BINARY_INV)

    detect_mask = ocr_binary == 0  # ink pixels = True
    detect_mask = _strip_border_cols(detect_mask)

    return detect_mask, ocr_binary


def detect_enchant_slot_headers(content_bgr):
    """Detect enchant slot header lines using white-text color mask.

    Slot headers (e.g., '[접두] 충격을 (랭크 F)') use balanced white text
    that is distinguishable from colored effect text on any background theme.

    Algorithm:
      1. oreo_flip: white-pixel mask (bright & balanced) → invert
      2. Horizontal projection → run detection → merge with gap tolerance 2
      3. Filter: 8 <= height <= 15 AND total_white_px >= 150

    Args:
        content_bgr: BGR numpy array of the enchant content region

    Returns:
        List of (y_start, y_end) tuples (y_end exclusive) for detected bands.
    """
    white_mask, _ = oreo_flip(content_bgr)

    wpr = white_mask.sum(axis=1)

    ROW_THRESHOLD = _HEADER_ROW_THRESHOLD
    GAP_TOLERANCE = _HEADER_GAP_TOLERANCE

    # Find runs of rows with sufficient white pixels
    runs = []
    in_run = False
    run_start = 0
    for y in range(len(wpr)):
        if wpr[y] >= ROW_THRESHOLD:
            if not in_run:
                run_start = y
                in_run = True
        else:
            if in_run:
                runs.append((run_start, y))
                in_run = False
    if in_run:
        runs.append((run_start, len(wpr)))

    # Merge runs separated by small gaps
    merged = []
    for start, end in runs:
        if merged and start - merged[-1][1] <= GAP_TOLERANCE:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append([start, end])

    # Filter by height and total white pixel count
    bands = []
    for start, end in merged:
        h = end - start
        total_px = int(wpr[start:end].sum())
        if _HEADER_MIN_HEIGHT <= h <= _HEADER_MAX_HEIGHT and total_px >= _HEADER_MIN_WHITE_PIXELS:
            bands.append((start, end))

    return bands
