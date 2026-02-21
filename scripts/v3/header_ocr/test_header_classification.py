#!/usr/bin/env python3
"""Test header OCR → section label assignment (new segment-first pipeline).

Pipeline:
  1. Original color image → detect_headers() → build_segments()
  2. Each header crop → preprocess (BT.601 + threshold) → recognize()
  3. Fuzzy match OCR text against section header_patterns from YAML
  4. Output: segment index → section name → raw OCR

Usage:
    python3 scripts/test_header_classification.py data/themes/screenshot_2026-02-20_200924.png
    python3 scripts/test_header_classification.py data/themes/  # run on all images in dir
"""

import argparse
import os
import sys

import cv2
import numpy as np
import yaml

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'backend'))

MODELS_DIR  = os.path.join(PROJECT_ROOT, 'backend', 'ocr', 'models')
CONFIG_PATH = os.path.join(PROJECT_ROOT, 'configs', 'mabinogi_tooltip.yaml')

FRONTEND_THRESHOLD = 80  # BT.601 grayscale > this → black (0), else white (255)

# Black-square segmentation parameters (tuned for 22/26 theme images)
NEAR_BLACK_THRESHOLD = 5
MIN_HEIGHT = 16
MIN_WIDTH  = 25


# ---------------------------------------------------------------------------
# Segmentation (from test_segmentation.py)
# ---------------------------------------------------------------------------

def max_consecutive(arr):
    max_run = cur = 0
    for v in arr:
        if v: cur += 1; max_run = max(max_run, cur)
        else: cur = 0
    return max_run


def detect_headers(img):
    mask = (img.max(axis=2) < NEAR_BLACK_THRESHOLD).astype(np.uint8)
    n_labels, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    headers = []
    for i in range(1, n_labels):
        x = stats[i, cv2.CC_STAT_LEFT]
        y = stats[i, cv2.CC_STAT_TOP]
        w = stats[i, cv2.CC_STAT_WIDTH]
        h = stats[i, cv2.CC_STAT_HEIGHT]
        if w < MIN_WIDTH or h < MIN_HEIGHT:
            continue
        region = mask[y:y + h, x:x + w]
        if not any(max_consecutive(region[r]) >= MIN_WIDTH for r in range(h)):
            continue
        if not any(max_consecutive(region[:, c]) >= MIN_HEIGHT for c in range(w)):
            continue
        headers.append({'y': y, 'h': h, 'x': x, 'w': w, 'content_y': y + h})
    headers.sort(key=lambda hdr: hdr['y'])
    return headers


def build_segments(img, headers):
    h_img, w_img = img.shape[:2]
    segments = []
    if headers and headers[0]['y'] > 0:
        segments.append({'index': 0, 'header': None,
                         'content': {'y': 0, 'h': headers[0]['y'], 'x': 0, 'w': w_img}})
    for i, hdr in enumerate(headers):
        next_y = headers[i + 1]['y'] if i + 1 < len(headers) else h_img
        content_h = next_y - hdr['content_y']
        segments.append({'index': i + 1, 'header': hdr,
                         'content': {'y': hdr['content_y'], 'h': content_h, 'x': 0, 'w': w_img}})
    return segments


# ---------------------------------------------------------------------------
# Config: load section header_patterns → section name lookup table
# ---------------------------------------------------------------------------

def load_section_patterns(config_path):
    """Return list of (pattern, section_name) from YAML header_patterns fields."""
    with open(config_path, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f)
    entries = []
    for section_name, section_cfg in cfg.get('sections', {}).items():
        for pattern in section_cfg.get('header_patterns', []):
            entries.append((pattern, section_name))
    return entries  # e.g. [("아이템 속성", "item_attrs"), ("인챈트", "enchant"), ...]


# ---------------------------------------------------------------------------
# Header crop preprocessing (matches frontend BT.601 + threshold pipeline)
# ---------------------------------------------------------------------------

def preprocess_header(crop_bgr):
    """Convert color header crop to binary: BT.601 → threshold(>80 → black)."""
    gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, FRONTEND_THRESHOLD, 255, cv2.THRESH_BINARY_INV)
    return binary  # black text (0) on white (255)


# ---------------------------------------------------------------------------
# Section label matching
# ---------------------------------------------------------------------------

def match_section(ocr_text, patterns, cutoff=50):
    """Fuzzy match OCR text against section header patterns.

    Uses rapidfuzz partial_ratio so that a short pattern like '세공' can match
    even if OCR added surrounding noise characters.

    Returns (section_name, pattern, score) or (None, None, 0) if no match.
    """
    from rapidfuzz import fuzz
    text = ocr_text.strip()
    best_score = 0
    best_section = None
    best_pattern = None
    for pattern, section_name in patterns:
        # partial_ratio: score of best substring alignment
        score = fuzz.partial_ratio(pattern, text)
        if score > best_score:
            best_score = score
            best_section = section_name
            best_pattern = pattern
    if best_score >= cutoff:
        return best_section, best_pattern, best_score
    return None, None, best_score


# ---------------------------------------------------------------------------
# OCR reader init
# ---------------------------------------------------------------------------

def init_reader():
    import easyocr
    from ocr_utils import patch_reader_imgw
    reader = easyocr.Reader(
        ['ko'],
        model_storage_directory=MODELS_DIR,
        user_network_directory=MODELS_DIR,
        recog_network='custom_mabinogi',
        gpu=True,
        verbose=False,
    )
    patch_reader_imgw(reader, MODELS_DIR)
    return reader


def ocr_header_crop(reader, binary_crop):
    """Run recognize() on a preprocessed (binary) header crop.

    Returns (text, confidence).
    """
    h, w = binary_crop.shape
    if h == 0 or w == 0:
        return '', 0.0

    # recognize() expects a BGR image; convert binary grayscale to BGR
    bgr = cv2.cvtColor(binary_crop, cv2.COLOR_GRAY2BGR)
    results = reader.recognize(
        bgr,
        horizontal_list=[[0, w, 0, h]],
        free_list=[],
        detail=1,
        paragraph=False,
    )
    if results:
        _, text, conf = results[0]
        return text.strip(), float(conf)
    return '', 0.0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def classify_image(image_path, reader, patterns, cutoff=50):
    img = cv2.imread(image_path)
    if img is None:
        print(f"  ERROR: cannot read {image_path}")
        return

    headers = detect_headers(img)
    segments = build_segments(img, headers)
    name = os.path.basename(image_path)

    print(f"\n{'='*60}")
    print(f"{name}: {len(headers)} headers, {len(segments)} segments")
    print(f"{'='*60}")

    if len(headers) != 9:
        print(f"  WARNING: expected 9 headers, got {len(headers)} — dark theme?")

    for seg in segments:
        idx = seg['index']
        if seg['header'] is None:
            print(f"  Seg {idx:02d}  [pre-header]  → section: item_name/item_attrs")
            continue

        hdr = seg['header']
        crop_color = img[hdr['y']:hdr['y'] + hdr['h'], :]
        binary = preprocess_header(crop_color)
        ocr_text, conf = ocr_header_crop(reader, binary)
        section, pattern, score = match_section(ocr_text, patterns, cutoff=cutoff)

        status = '✓' if section else '✗'
        print(f"  Seg {idx:02d}  y={hdr['y']:4d}  "
              f"OCR: '{ocr_text}'  conf={conf:.2f}  "
              f"→ {status} {section or 'UNKNOWN'}  "
              f"(pattern='{pattern}' score={score})")


def main():
    parser = argparse.ArgumentParser(description='Header OCR → section label classifier')
    parser.add_argument('path', help='Image file or directory of images')
    parser.add_argument('--cutoff', type=int, default=50,
                        help='Minimum fuzzy match score to accept a section label (default: 50)')
    args = parser.parse_args()

    patterns = load_section_patterns(CONFIG_PATH)
    print(f"Loaded {len(patterns)} header patterns from config:")
    for p, s in patterns:
        print(f"  '{p}' → {s}")

    print("\nInitializing OCR reader...")
    reader = init_reader()
    print("Ready.\n")

    if os.path.isdir(args.path):
        images = sorted(
            os.path.join(args.path, f)
            for f in os.listdir(args.path)
            if f.endswith('.png')
        )
    else:
        images = [args.path]

    for img_path in images:
        classify_image(img_path, reader, patterns, cutoff=args.cutoff)


if __name__ == '__main__':
    main()
