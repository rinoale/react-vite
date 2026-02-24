"""Tooltip segmenter — segment-first pipeline.

Determines section labels BEFORE running content OCR:
  1. detect_headers()     — orange text detection + black-square boundary expansion
  2. build_segments()     — pair each header with its content region
  3. classify_header()    — preprocess header crop → header OCR model → section name
  4. segment_and_tag()    — full pipeline, returns list of tagged segments
  5. init_header_reader() — create EasyOCR reader with the dedicated header model

All detection parameters are read from configs/mabinogi_tooltip.yaml
(header_detection section). No hardcoded thresholds.

Each tagged segment:
  {
    'index':             int,
    'section':           str or None,   # canonical section name from yaml
    'header_crop':       np.ndarray or None,  # tight black-square crop (original color)
    'content_crop':      np.ndarray,    # content region (original color, full width)
    'header_ocr_text':   str,
    'header_ocr_conf':   float,
    'header_match_score': int,
  }
"""

import os
from pathlib import Path

import cv2
import numpy as np
import yaml
from rapidfuzz import fuzz

# Header model location (relative to this file's directory)
_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_LIB_DIR)
_MODELS_DIR = os.path.join(_BACKEND_DIR, 'ocr', 'models')


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def load_config(config_path):
    """Load full config from mabinogi_tooltip.yaml."""
    return yaml.safe_load(Path(config_path).read_text())


def _get_header_detection_config(config):
    """Extract header_detection sub-config with defaults."""
    hd = config.get('header_detection', {})
    orange = hd.get('orange', {})
    boundary = hd.get('boundary', {})
    ocr = hd.get('ocr', {})
    return {
        'orange': {
            'r_min': orange.get('r_min', 150),
            'g_min': orange.get('g_min', 50),
            'g_max': orange.get('g_max', 180),
            'b_max': orange.get('b_max', 80),
            'min_band_height': orange.get('min_band_height', 8),
            'min_band_pixels': orange.get('min_band_pixels', 40),
        },
        'boundary': {
            'pure_black_max': boundary.get('pure_black_max', 0),
            'ref_columns': boundary.get('ref_columns', 10),
            'density_threshold': boundary.get('density_threshold', 0.2),
            'max_expansion': boundary.get('max_expansion', 40),
        },
        'ocr': {
            'threshold': ocr.get('threshold', 50),
            'match_cutoff': ocr.get('match_cutoff', 50),
        },
    }


# ---------------------------------------------------------------------------
# 1. Header detection (orange-anchored + boundary expansion)
# ---------------------------------------------------------------------------

def detect_headers(img, config):
    """Find header bands using orange text detection + black-square expansion.

    Algorithm:
      1. Build orange color mask from config thresholds
      2. Horizontal projection → cluster consecutive rows into bands
      3. Filter bands by min height and min pixel count
      4. For each band, expand outward checking reference columns (right of
         orange text) for pure-black density until the black square ends

    Args:
        img:    BGR image (original color screenshot)
        config: Full config dict from load_config()

    Returns:
        List of dicts sorted by y:
          {'y', 'h', 'x', 'w', 'content_y'}
    """
    hd = _get_header_detection_config(config)
    orange_cfg = hd['orange']
    boundary_cfg = hd['boundary']

    h_img, w_img = img.shape[:2]
    b, g, r = img[:, :, 0], img[:, :, 1], img[:, :, 2]

    # Step 1: orange mask
    orange_mask = (
        (r > orange_cfg['r_min']) &
        (g > orange_cfg['g_min']) &
        (g < orange_cfg['g_max']) &
        (b < orange_cfg['b_max'])
    ).astype(np.uint8)

    # Step 2: horizontal projection → bands
    row_counts = orange_mask.sum(axis=1)
    min_h = orange_cfg['min_band_height']
    min_px = orange_cfg['min_band_pixels']

    in_band = False
    bands = []  # (y_start, height, ox_min, ox_max)
    for y in range(h_img):
        if row_counts[y] > 0:
            if not in_band:
                band_start = y
                in_band = True
        else:
            if in_band:
                bh = y - band_start
                px = int(row_counts[band_start:y].sum())
                if bh >= min_h and px >= min_px:
                    cols = np.where(orange_mask[band_start:y, :].any(axis=0))[0]
                    bands.append((band_start, bh, int(cols[0]), int(cols[-1])))
                in_band = False
    if in_band:
        bh = h_img - band_start
        px = int(row_counts[band_start:h_img].sum())
        if bh >= min_h and px >= min_px:
            cols = np.where(orange_mask[band_start:h_img, :].any(axis=0))[0]
            bands.append((band_start, bh, int(cols[0]), int(cols[-1])))

    # Step 3: expand each band to find black-square boundaries
    pb_max = boundary_cfg['pure_black_max']
    ref_cols = boundary_cfg['ref_columns']
    density_thr = boundary_cfg['density_threshold']
    max_exp = boundary_cfg['max_expansion']

    pure_black = (img.max(axis=2) <= pb_max)

    headers = []
    for oy, oh, ox_min, ox_max in bands:
        # Reference columns: right of orange text, avoids left-border interference
        x_ref_start = ox_max
        x_ref_end = min(w_img, ox_max + ref_cols)
        ref_width = x_ref_end - x_ref_start
        if ref_width < 3:
            x_ref_end = min(w_img, ox_max + ref_cols + 3)
            ref_width = x_ref_end - x_ref_start

        # Expand upward
        top = oy
        for y in range(oy - 1, max(0, oy - max_exp) - 1, -1):
            frac = pure_black[y, x_ref_start:x_ref_end].sum() / ref_width
            if frac >= density_thr:
                top = y
            else:
                break

        # Expand downward
        bottom = oy + oh - 1
        for y in range(oy + oh, min(h_img, oy + oh + max_exp)):
            frac = pure_black[y, x_ref_start:x_ref_end].sum() / ref_width
            if frac >= density_thr:
                bottom = y
            else:
                break

        # Find horizontal extent of the black square.
        # Use a margin row (above orange text, inside the square).
        # Scan outward from the orange text CENTER until pure-black ends,
        # avoiding edge artifacts where ox_min/ox_max touch borders.
        margin_y = max(top, oy - 2)
        row_pb = pure_black[margin_y, :]
        ox_center = (ox_min + ox_max) // 2

        # Scan left from center
        x_left = ox_center
        for x in range(ox_center - 1, max(0, ox_center - max_exp) - 1, -1):
            if row_pb[x]:
                x_left = x
            else:
                break

        # Scan right from center
        x_right = ox_center + 1
        for x in range(ox_center + 1, min(w_img, ox_center + max_exp)):
            if row_pb[x]:
                x_right = x + 1
            else:
                break

        headers.append({
            'y': top, 'h': bottom - top + 1,
            'x': x_left, 'w': x_right - x_left,
            'content_y': bottom + 1,
        })

    headers.sort(key=lambda hdr: hdr['y'])
    return headers


# ---------------------------------------------------------------------------
# 1b. Border detection
# ---------------------------------------------------------------------------

def detect_bottom_border(img, border_val=132, tolerance=5, min_density=0.3):
    """Find the y-coordinate of the bottom horizontal border line.

    Mabinogi tooltips have section borders at RGB(132,132,132). The bottom
    horizontal border marks where tooltip content ends. Detecting it gives
    a clean processing cutoff so noise below the tooltip (game world
    background, UI elements) is excluded.

    Scans rows from bottom upward looking for rows where >min_density of
    pixels match the border color (±tolerance on each channel).

    Args:
        img:         BGR image (original color screenshot)
        border_val:  Expected grayscale value of border pixels (default 132)
        tolerance:   Per-channel tolerance around border_val (default 5)
        min_density: Fraction of image width that must be border-colored (default 0.3)

    Returns:
        y-coordinate of the bottom border row, or None if not detected.
    """
    h_img, w_img = img.shape[:2]
    lo = border_val - tolerance
    hi = border_val + tolerance

    # Per-channel range check: all of B, G, R must be within [lo, hi]
    border_mask = (
        (img[:, :, 0] >= lo) & (img[:, :, 0] <= hi) &
        (img[:, :, 1] >= lo) & (img[:, :, 1] <= hi) &
        (img[:, :, 2] >= lo) & (img[:, :, 2] <= hi)
    )

    threshold = int(w_img * min_density)

    for y in range(h_img - 1, -1, -1):
        if border_mask[y].sum() >= threshold:
            return y

    return None


def detect_vertical_borders(img, border_val=132, tolerance=5, min_density=0.3):
    """Find x-coordinates of left and right vertical border lines.

    Same color matching as detect_bottom_border() but scans columns instead
    of rows. Scans inward from each edge to find the first column where
    >min_density of pixels match the border color.

    Args:
        img:         BGR image (original color screenshot)
        border_val:  Expected grayscale value of border pixels (default 132)
        tolerance:   Per-channel tolerance around border_val (default 5)
        min_density: Fraction of image height that must be border-colored (default 0.3)

    Returns:
        (left_x, right_x) — x-coordinates of borders, each may be None.
    """
    h_img, w_img = img.shape[:2]
    lo = border_val - tolerance
    hi = border_val + tolerance

    border_mask = (
        (img[:, :, 0] >= lo) & (img[:, :, 0] <= hi) &
        (img[:, :, 1] >= lo) & (img[:, :, 1] <= hi) &
        (img[:, :, 2] >= lo) & (img[:, :, 2] <= hi)
    )

    col_counts = border_mask.sum(axis=0)
    threshold = int(h_img * min_density)

    # Scan from left edge inward
    left_x = None
    for x in range(w_img):
        if col_counts[x] >= threshold:
            left_x = x
            break

    # Scan from right edge inward
    right_x = None
    for x in range(w_img - 1, -1, -1):
        if col_counts[x] >= threshold:
            right_x = x
            break

    return left_x, right_x


# ---------------------------------------------------------------------------
# 2. Segmentation
# ---------------------------------------------------------------------------

def build_segments(img, headers, bottom_y=None, left_x=None, right_x=None):
    """Pair each header with its content region below it.

    Args:
        img:      BGR image
        headers:  List of header dicts from detect_headers()
        bottom_y: Optional y-coordinate of the bottom tooltip border.
                  If provided, the last segment is clamped to this boundary
                  instead of extending to the full image height.
        left_x:   Optional x-coordinate of the left vertical border.
                  Content regions start at left_x+1 (inside the border).
        right_x:  Optional x-coordinate of the right vertical border.
                  Content regions end at right_x (exclusive, inside the border).

    Returns list of dicts:
      {'index', 'header': dict or None, 'content': {'y','h','x','w'}}
    """
    h_img, w_img = img.shape[:2]
    effective_bottom = bottom_y if bottom_y is not None else h_img
    content_x = (left_x + 1) if left_x is not None else 0
    content_x_end = right_x if right_x is not None else w_img
    content_w = content_x_end - content_x
    segments = []

    if headers and headers[0]['y'] > 0:
        segments.append({
            'index': 0,
            'header': None,
            'content': {'y': 0, 'h': headers[0]['y'], 'x': content_x, 'w': content_w},
        })

    for i, hdr in enumerate(headers):
        next_y = headers[i + 1]['y'] if i + 1 < len(headers) else effective_bottom
        content_h = next_y - hdr['content_y']
        segments.append({
            'index': i + 1,
            'header': hdr,
            'content': {'y': hdr['content_y'], 'h': content_h, 'x': content_x, 'w': content_w},
        })

    return segments


# ---------------------------------------------------------------------------
# 3. Header classification
# ---------------------------------------------------------------------------

def load_section_patterns(config_path):
    """Load (pattern, section_name) pairs from mabinogi_tooltip.yaml.

    Returns list of (pattern_str, section_name_str).
    """
    cfg = yaml.safe_load(Path(config_path).read_text())
    entries = []
    for section_name, section_cfg in cfg.get('sections', {}).items():
        for pattern in section_cfg.get('header_patterns', []):
            entries.append((pattern, section_name))
    return entries


def init_header_reader(models_dir=None, gpu=True):
    """Create an EasyOCR reader loaded with the dedicated header OCR model.

    Uses custom_header.pth (imgW=128, 22-char charset) trained on the 9
    section header labels.

    Args:
        models_dir: Directory containing custom_header.{py,yaml,pth}.
                    Defaults to backend/ocr/models/ next to this file.
        gpu:        Whether to use GPU inference.

    Returns:
        EasyOCR Reader with imgW patched to 128.
    """
    import easyocr
    from lib.ocr_utils import patch_reader_imgw

    if models_dir is None:
        models_dir = _MODELS_DIR

    reader = easyocr.Reader(
        ['ko'],
        model_storage_directory=models_dir,
        user_network_directory=models_dir,
        recog_network='custom_header',
        gpu=gpu,
        verbose=False,
    )
    patch_reader_imgw(reader, models_dir, recog_network='custom_header')
    return reader


def init_enchant_header_reader(models_dir=None, gpu=True):
    """Create an EasyOCR reader for enchant slot header OCR.

    Uses custom_enchant_header.pth (imgW=200, 627-char charset) trained on
    enchant slot header lines like '[접두] 마법의 (랭크 A)'.

    Args:
        models_dir: Directory containing custom_enchant_header.{py,yaml,pth}.
                    Defaults to backend/ocr/models/ next to this file.
        gpu:        Whether to use GPU inference.

    Returns:
        EasyOCR Reader with imgW patched to 200.
    """
    import easyocr
    from lib.ocr_utils import patch_reader_imgw

    if models_dir is None:
        models_dir = _MODELS_DIR

    reader = easyocr.Reader(
        ['ko'],
        model_storage_directory=models_dir,
        user_network_directory=models_dir,
        recog_network='custom_enchant_header',
        gpu=gpu,
        verbose=False,
    )
    patch_reader_imgw(reader, models_dir, recog_network='custom_enchant_header')
    return reader


def _preprocess_header_crop(crop_bgr, config):
    """Convert color header crop to binary suitable for the header OCR model.

    BT.601 grayscale → threshold → binary.
    """
    hd = _get_header_detection_config(config)
    threshold = hd['ocr']['threshold']
    gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY_INV)
    return binary  # black text on white background


def classify_header(crop_bgr, header_reader, patterns, config, cutoff=None):
    """OCR a header crop and fuzzy-match against section patterns.

    Args:
        crop_bgr:      Tight header crop from original color image (the black square)
        header_reader: EasyOCR reader loaded with custom_header model (imgW=128 patched)
        patterns:      List of (pattern_str, section_name) from load_section_patterns()
        config:        Full config dict from load_config()
        cutoff:        Override for minimum partial_ratio score (default: from config)

    Returns:
        (section_name, ocr_text, conf, match_score)
        section_name is None if no pattern scores >= cutoff.
    """
    if cutoff is None:
        hd = _get_header_detection_config(config)
        cutoff = hd['ocr']['match_cutoff']

    binary = _preprocess_header_crop(crop_bgr, config)
    h, w = binary.shape

    if h == 0 or w == 0:
        return None, '', 0.0, 0

    _save_dir = os.environ.get('SAVE_OCR_CROPS')
    if _save_dir:
        os.makedirs(_save_dir, exist_ok=True)
        _n = len([f for f in os.listdir(_save_dir) if f.endswith('.png')])
        cv2.imwrite(os.path.join(_save_dir, f'{_n:03d}_header.png'), binary)

    bgr = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
    results = header_reader.recognize(
        bgr,
        horizontal_list=[[0, w, 0, h]],
        free_list=[],
        detail=1,
        paragraph=False,
    )

    ocr_text = results[0][1].strip() if results else ''
    ocr_conf = float(results[0][2]) if results else 0.0

    best_score = 0
    best_section = None
    for pattern, section_name in patterns:
        score = fuzz.partial_ratio(pattern, ocr_text)
        if score > best_score:
            best_score = score
            best_section = section_name

    if best_score < cutoff:
        best_section = None

    return best_section, ocr_text, ocr_conf, best_score


# ---------------------------------------------------------------------------
# 4. Full pipeline: segment + tag
# ---------------------------------------------------------------------------

def segment_and_tag(img, header_reader, patterns, config, cutoff=None):
    """Run the full segment-first pipeline on an original color image.

    Args:
        img:           BGR image loaded from original color screenshot
        header_reader: EasyOCR reader loaded with custom_header model (from init_header_reader())
        patterns:      List of (pattern_str, section_name) from load_section_patterns()
        config:        Full config dict from load_config()
        cutoff:        Override for fuzzy match cutoff score (default: from config)

    Returns:
        List of tagged segment dicts:
          {
            'index':              int,
            'section':            str or None,
            'header_crop':        np.ndarray or None,  # tight black-square crop
            'content_crop':       np.ndarray,          # content region, full width
            'header_ocr_text':    str,
            'header_ocr_conf':    float,
            'header_match_score': int,
          }
    """
    headers = detect_headers(img, config)
    bottom_y = detect_bottom_border(img)
    left_x, right_x = detect_vertical_borders(img)
    segments = build_segments(img, headers, bottom_y=bottom_y,
                              left_x=left_x, right_x=right_x)
    tagged = []

    for seg in segments:
        idx = seg['index']
        cnt = seg['content']
        content_crop = img[cnt['y']:cnt['y'] + cnt['h'],
                           cnt['x']:cnt['x'] + cnt['w']]

        if seg['header'] is None:
            # Pre-header region: item name + item attrs (no header to classify)
            tagged.append({
                'index':              idx,
                'section':            'pre_header',
                'header_crop':        None,
                'content_crop':       content_crop,
                'content_y':          cnt['y'],
                'content_h':          cnt['h'],
                'header_ocr_text':    '',
                'header_ocr_conf':    0.0,
                'header_match_score': 0,
            })
            continue

        hdr = seg['header']
        header_crop = img[hdr['y']:hdr['y'] + hdr['h'],
                          hdr['x']:hdr['x'] + hdr['w']]

        section, ocr_text, ocr_conf, match_score = classify_header(
            header_crop, header_reader, patterns, config, cutoff=cutoff
        )

        tagged.append({
            'index':              idx,
            'section':            section,
            'header_crop':        header_crop,
            'content_crop':       content_crop,
            'content_y':          cnt['y'],
            'content_h':          cnt['h'],
            'header_ocr_text':    ocr_text,
            'header_ocr_conf':    ocr_conf,
            'header_match_score': match_score,
        })

    return tagged
