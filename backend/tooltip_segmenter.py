"""Tooltip segmenter — segment-first pipeline.

Determines section labels BEFORE running content OCR:
  1. detect_headers()     — near-black connected components on original color image
  2. build_segments()     — pair each header with its content region
  3. classify_header()    — preprocess header crop → header OCR model → section name
  4. segment_and_tag()    — full pipeline, returns list of tagged segments
  5. init_header_reader() — create EasyOCR reader with the dedicated header model

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
import sys

import cv2
import numpy as np
import yaml
from rapidfuzz import fuzz

# ---------------------------------------------------------------------------
# Black-square header detection parameters (tuned for 22/26 theme images)
# ---------------------------------------------------------------------------
NEAR_BLACK_THRESHOLD = 5   # max(R,G,B) < this → near black
MIN_HEIGHT           = 16  # minimum consecutive vertical run
MIN_WIDTH            = 25  # minimum consecutive horizontal run
MAX_ASPECT           = 5.0 # w/h upper bound — real headers ≤3.7; wider blobs are false positives

# Preprocessing (orange text on black: threshold=50 captures 100% of text pixels)
HEADER_THRESHOLD     = 50  # grayscale > this → black (text), else white (background)

# Fuzzy matching fallback (guards against minor OCR errors on 9-class model output)
MATCH_CUTOFF         = 50  # minimum partial_ratio score to accept a section label

# Header model location (relative to this file's directory)
_BACKEND_DIR  = os.path.dirname(os.path.abspath(__file__))
_MODELS_DIR   = os.path.join(_BACKEND_DIR, 'ocr', 'models')


# ---------------------------------------------------------------------------
# 1. Header detection
# ---------------------------------------------------------------------------

def _max_consecutive(arr):
    max_run = cur = 0
    for v in arr:
        if v:
            cur += 1
            if cur > max_run:
                max_run = cur
        else:
            cur = 0
    return max_run


def detect_headers(img,
                   threshold=NEAR_BLACK_THRESHOLD,
                   min_height=MIN_HEIGHT,
                   min_width=MIN_WIDTH,
                   max_aspect=MAX_ASPECT):
    """Find header bands as near-black rectangular connected components.

    Args:
        img: BGR image (original color screenshot)

    Returns:
        List of dicts sorted by y:
          {'y', 'h', 'x', 'w', 'content_y'}
    """
    mask = (img.max(axis=2) < threshold).astype(np.uint8)
    n_labels, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)

    headers = []
    for i in range(1, n_labels):
        x = stats[i, cv2.CC_STAT_LEFT]
        y = stats[i, cv2.CC_STAT_TOP]
        w = stats[i, cv2.CC_STAT_WIDTH]
        h = stats[i, cv2.CC_STAT_HEIGHT]

        if w < min_width or h < min_height:
            continue

        if w / h > max_aspect:
            continue

        region = mask[y:y + h, x:x + w]
        if not any(_max_consecutive(region[r]) >= min_width for r in range(h)):
            continue
        if not any(_max_consecutive(region[:, c]) >= min_height for c in range(w)):
            continue

        headers.append({'y': y, 'h': h, 'x': x, 'w': w, 'content_y': y + h})

    headers.sort(key=lambda hdr: hdr['y'])
    return headers


# ---------------------------------------------------------------------------
# 2. Segmentation
# ---------------------------------------------------------------------------

def build_segments(img, headers):
    """Pair each header with its content region below it.

    Returns list of dicts:
      {'index', 'header': dict or None, 'content': {'y','h','x','w'}}
    """
    h_img, w_img = img.shape[:2]
    segments = []

    if headers and headers[0]['y'] > 0:
        segments.append({
            'index': 0,
            'header': None,
            'content': {'y': 0, 'h': headers[0]['y'], 'x': 0, 'w': w_img},
        })

    for i, hdr in enumerate(headers):
        next_y = headers[i + 1]['y'] if i + 1 < len(headers) else h_img
        content_h = next_y - hdr['content_y']
        segments.append({
            'index': i + 1,
            'header': hdr,
            'content': {'y': hdr['content_y'], 'h': content_h, 'x': 0, 'w': w_img},
        })

    return segments


# ---------------------------------------------------------------------------
# 3. Header classification
# ---------------------------------------------------------------------------

def load_section_patterns(config_path):
    """Load (pattern, section_name) pairs from mabinogi_tooltip.yaml.

    Returns list of (pattern_str, section_name_str).
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f)
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
    # ocr_utils.py lives in the same backend/ directory
    sys.path.insert(0, _BACKEND_DIR)
    from ocr_utils import patch_reader_imgw

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


def _preprocess_header_crop(crop_bgr):
    """Convert color header crop to binary suitable for the header OCR model.

    BT.601 grayscale → threshold(>50 → black, else white).
    Threshold=50 (vs frontend's 80) captures 100% of orange text pixels
    which can go as low as L≈55 due to anti-aliasing.
    """
    gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, HEADER_THRESHOLD, 255, cv2.THRESH_BINARY_INV)
    return binary  # black text on white background


def classify_header(crop_bgr, header_reader, patterns, cutoff=MATCH_CUTOFF):
    """OCR a header crop and fuzzy-match against section patterns.

    Args:
        crop_bgr:      Tight header crop from original color image (the black square)
        header_reader: EasyOCR reader loaded with custom_header model (imgW=128 patched)
        patterns:      List of (pattern_str, section_name) from load_section_patterns()
        cutoff:        Minimum partial_ratio score to accept

    Returns:
        (section_name, ocr_text, conf, match_score)
        section_name is None if no pattern scores >= cutoff.
    """
    binary = _preprocess_header_crop(crop_bgr)
    h, w = binary.shape

    if h == 0 or w == 0:
        return None, '', 0.0, 0

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

def segment_and_tag(img, header_reader, patterns, cutoff=MATCH_CUTOFF):
    """Run the full segment-first pipeline on an original color image.

    Args:
        img:           BGR image loaded from original color screenshot
        header_reader: EasyOCR reader loaded with custom_header model (from init_header_reader())
        patterns:      List of (pattern_str, section_name) from load_section_patterns()
        cutoff:        Fuzzy match cutoff score

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
    headers  = detect_headers(img)
    segments = build_segments(img, headers)
    tagged   = []

    for seg in segments:
        idx = seg['index']
        cnt = seg['content']
        content_crop = img[cnt['y']:cnt['y'] + cnt['h'], :]

        if seg['header'] is None:
            # Pre-header region: item name + item attrs (no header to classify)
            tagged.append({
                'index':              idx,
                'section':            'pre_header',
                'header_crop':        None,
                'content_crop':       content_crop,
                'header_ocr_text':    '',
                'header_ocr_conf':    0.0,
                'header_match_score': 0,
            })
            continue

        hdr = seg['header']
        header_crop = img[hdr['y']:hdr['y'] + hdr['h'],
                          hdr['x']:hdr['x'] + hdr['w']]

        section, ocr_text, ocr_conf, match_score = classify_header(
            header_crop, header_reader, patterns, cutoff=cutoff
        )

        tagged.append({
            'index':              idx,
            'section':            section,
            'header_crop':        header_crop,
            'content_crop':       content_crop,
            'header_ocr_text':    ocr_text,
            'header_ocr_conf':    ocr_conf,
            'header_match_score': match_score,
        })

    return tagged
