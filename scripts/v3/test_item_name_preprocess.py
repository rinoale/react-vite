#!/usr/bin/env python3
"""Compare item_name preprocessing: BT.601+threshold=80 vs color mask for RGB(255,252,157).

Extracts the pre_header (item name) region from each theme image,
applies multiple preprocessing methods, and runs OCR on each.

Usage:
    python3 scripts/v3/test_item_name_preprocess.py 'data/themes/*.png'
"""
import sys, os, glob
import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
from lib.tooltip_segmenter import segment_and_tag
from lib.tooltip_line_splitter import TooltipLineSplitter
from lib.v3_pipeline import init_pipeline

# Expected item name text (line 1 of pre_header)
EXPECTED = '각인된 회오리 퓨리 정령 나이트브링어 뱅퀴셔'


def preprocess_bt601(content_bgr, threshold=80):
    """Current method: BT.601 grayscale + threshold."""
    gray = cv2.cvtColor(content_bgr, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY_INV)
    return binary


def preprocess_color_mask(content_bgr, target_rgb=(255, 252, 157), tolerance=40):
    """Euclidean distance color mask."""
    r = content_bgr[:, :, 2].astype(np.float32)
    g = content_bgr[:, :, 1].astype(np.float32)
    b = content_bgr[:, :, 0].astype(np.float32)
    tr, tg, tb = target_rgb
    dist = np.sqrt((r - tr)**2 + (g - tg)**2 + (b - tb)**2)
    mask = (dist < tolerance).astype(np.uint8) * 255
    return cv2.bitwise_not(mask)


def detect_lines(binary):
    """Run line splitter on binary (black-on-white) and return line dicts."""
    binary_detect = cv2.bitwise_not(binary)  # white-on-black for detection
    splitter = TooltipLineSplitter()
    return splitter.detect_text_lines(binary_detect)


def run_ocr_on_crop(reader, crop_binary):
    """Run OCR on a single binary crop (black text on white)."""
    if crop_binary is None or crop_binary.size == 0:
        return '', 0.0
    h, w = crop_binary.shape[:2]
    results = reader.recognize(
        crop_binary,
        horizontal_list=[[0, w, 0, h]],
        free_list=[],
        batch_size=1,
    )
    if results and results[0]:
        return results[0][1], results[0][2]
    return '', 0.0


def main():
    pattern = sys.argv[1] if len(sys.argv) > 1 else 'data/themes/*.png'
    images = sorted(glob.glob(pattern))
    if not images:
        print(f'No images found: {pattern}')
        return

    print(f'Found {len(images)} theme images\n')

    pipeline = init_pipeline()
    reader = pipeline['content_reader']
    header_reader = pipeline['header_reader']
    patterns = pipeline['section_patterns']
    config = pipeline['config']

    out_dir = os.path.join('tmp', 'item_name_preprocess')
    os.makedirs(out_dir, exist_ok=True)

    # Methods to compare
    METHODS = [
        ('BT601_80',  lambda bgr: preprocess_bt601(bgr, 80)),
        ('BT601_50',  lambda bgr: preprocess_bt601(bgr, 50)),
        ('Color_t40', lambda bgr: preprocess_color_mask(bgr, tolerance=40)),
        ('Color_t60', lambda bgr: preprocess_color_mask(bgr, tolerance=60)),
        ('Color_t80', lambda bgr: preprocess_color_mask(bgr, tolerance=80)),
    ]

    exact_counts = {name: 0 for name, _ in METHODS}
    total = 0

    print(f'{"Image":<42} {"Method":<12} {"Lines":>5} {"1st_h":>5} {"Conf":>5}  Text')
    print('-' * 130)

    for img_path in images:
        fname = os.path.basename(img_path)
        img_bgr = cv2.imread(img_path, cv2.IMREAD_COLOR)
        if img_bgr is None:
            continue

        segments = segment_and_tag(img_bgr, header_reader, patterns, config)
        pre_header = next((s for s in segments if s.get('section') == 'pre_header'), None)
        if pre_header is None or pre_header.get('content_crop') is None:
            print(f'{fname:<42} SKIP (no pre_header)')
            continue

        content_bgr = pre_header['content_crop']
        total += 1

        for method_name, preprocess_fn in METHODS:
            binary = preprocess_fn(content_bgr)
            lines = detect_lines(binary)
            n_lines = len(lines)

            if lines:
                first = lines[0]
                y, h = first['y'], first['height']
                crop = binary[y:y+h, :]
                text, conf = run_ocr_on_crop(reader, crop)
                line_h = h
            else:
                text, conf, line_h = '', 0.0, 0

            match = text.strip() == EXPECTED
            if match:
                exact_counts[method_name] += 1

            marker = 'OK' if match else 'XX'
            label = fname if method_name == METHODS[0][0] else ''
            print(f'{label:<42} {method_name:<12} {n_lines:>5} {line_h:>5} {conf:>5.2f}  [{marker}] {text}')

            # Save first-line crop and full binary for first image only
            if total == 1:
                base = fname.replace('.png', '')
                cv2.imwrite(os.path.join(out_dir, f'{base}_{method_name}_full.png'), binary)
                if lines:
                    cv2.imwrite(os.path.join(out_dir, f'{base}_{method_name}_crop.png'), crop)

        print()

    print('-' * 130)
    print(f'\nResults ({total} images):')
    for name, _ in METHODS:
        print(f'  {name:<12}: {exact_counts[name]:>2}/{total} exact')


if __name__ == '__main__':
    main()
