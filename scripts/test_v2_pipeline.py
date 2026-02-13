#!/usr/bin/env python3
"""
Test the v2 OCR pipeline: TooltipLineSplitter → EasyOCR recognize()

Splits sample images into line crops, feeds each to the recognition model,
and compares results against ground truth .txt files.

Usage:
    python3 scripts/test_v2_pipeline.py                          # Test all GT pairs
    python3 scripts/test_v2_pipeline.py data/sample_images/captain_suit_processed.png  # Single image
"""

import os
import sys
import argparse
import difflib

import cv2
import numpy as np

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'backend'))

from tooltip_line_splitter import TooltipLineSplitter

MODELS_DIR = os.path.join(PROJECT_ROOT, 'backend', 'models')
SAMPLE_DIR = os.path.join(PROJECT_ROOT, 'data', 'sample_images')


def load_ground_truth(txt_path):
    """Load ground truth text file and return non-empty lines."""
    with open(txt_path, 'r', encoding='utf-8') as f:
        lines = f.read().splitlines()
    return [line for line in lines if line.strip()]


def init_reader():
    """Initialize EasyOCR reader with custom model and fixed imgW patch."""
    import easyocr
    from ocr_utils import patch_reader_imgw
    reader = easyocr.Reader(
        ['ko'],
        model_storage_directory=MODELS_DIR,
        user_network_directory=MODELS_DIR,
        recog_network='custom_mabinogi'
    )
    fixed_imgW = patch_reader_imgw(reader, MODELS_DIR)
    print(f"Reader initialized with fixed imgW={fixed_imgW}")
    return reader


def recognize_line(reader, line_img_bgr):
    """Recognize text from a single line crop image.

    Args:
        reader: EasyOCR Reader instance
        line_img_bgr: BGR image (numpy array) of a single line crop

    Returns:
        (text, confidence) tuple
    """
    # Convert to grayscale for recognize()
    if len(line_img_bgr.shape) == 3:
        gray = cv2.cvtColor(line_img_bgr, cv2.COLOR_BGR2GRAY)
    else:
        gray = line_img_bgr

    h, w = gray.shape
    if h == 0 or w == 0:
        return ('', 0.0)

    # Call recognize() with a single bbox covering the entire image
    results = reader.recognize(
        gray,
        horizontal_list=[[0, w, 0, h]],
        free_list=[],
        reformat=False,
        detail=1
    )

    if results:
        _, text, confidence = results[0]
        return (text, confidence)
    return ('', 0.0)


def test_image(reader, image_path, gt_path, verbose=True):
    """Test the v2 pipeline on a single image against ground truth.

    Returns:
        dict with results and metrics
    """
    basename = os.path.basename(image_path)
    gt_lines = load_ground_truth(gt_path)

    # Split image into lines
    splitter = TooltipLineSplitter(output_dir='/tmp/v2_test')
    img, gray, binary = splitter.preprocess_image(image_path)
    detected_lines = splitter.detect_text_lines(binary)

    if verbose:
        print(f"\n{'='*70}")
        print(f"  {basename}")
        print(f"  GT lines: {len(gt_lines)}, Detected lines: {len(detected_lines)}")
        print(f"{'='*70}")

    # Extract line crops from the original image
    results = []
    n_lines = min(len(detected_lines), len(gt_lines))

    for i, line_info in enumerate(detected_lines):
        x, y, w, h = line_info['x'], line_info['y'], line_info['width'], line_info['height']

        # Apply same proportional padding as extract_lines()
        pad_x = max(2, h // 3)
        pad_y = max(1, h // 5)
        x_pad = max(0, x - pad_x)
        y_pad = max(0, y - pad_y)
        w_pad = min(img.shape[1] - x_pad, w + 2 * pad_x)
        h_pad = min(img.shape[0] - y_pad, h + 2 * pad_y)

        line_crop = img[y_pad:y_pad+h_pad, x_pad:x_pad+w_pad]

        # Recognize
        text, confidence = recognize_line(reader, line_crop)

        gt_text = gt_lines[i] if i < len(gt_lines) else '???'

        # Character-level accuracy (using SequenceMatcher)
        matcher = difflib.SequenceMatcher(None, gt_text, text)
        char_accuracy = matcher.ratio()

        exact_match = (text.strip() == gt_text.strip())

        results.append({
            'line_num': i + 1,
            'gt': gt_text,
            'ocr': text,
            'confidence': confidence,
            'char_accuracy': char_accuracy,
            'exact_match': exact_match,
        })

        if verbose:
            status = 'OK' if exact_match else 'XX'
            print(f"  [{status}] Line {i+1:2d} (conf={confidence:.3f}, acc={char_accuracy:.1%})")
            if not exact_match:
                print(f"       GT:  {gt_text}")
                print(f"       OCR: {text}")

    # Handle line count mismatch
    if len(detected_lines) != len(gt_lines):
        if verbose:
            print(f"\n  WARNING: Line count mismatch (detected={len(detected_lines)}, gt={len(gt_lines)})")

    # Summary metrics
    if results:
        exact_matches = sum(1 for r in results if r['exact_match'])
        avg_char_accuracy = sum(r['char_accuracy'] for r in results) / len(results)
        avg_confidence = sum(r['confidence'] for r in results) / len(results)
    else:
        exact_matches = 0
        avg_char_accuracy = 0.0
        avg_confidence = 0.0

    summary = {
        'image': basename,
        'gt_lines': len(gt_lines),
        'detected_lines': len(detected_lines),
        'exact_matches': exact_matches,
        'total_compared': len(results),
        'exact_match_rate': exact_matches / len(results) if results else 0,
        'avg_char_accuracy': avg_char_accuracy,
        'avg_confidence': avg_confidence,
        'results': results,
    }

    if verbose:
        print(f"\n  Summary: {exact_matches}/{len(results)} exact matches "
              f"({summary['exact_match_rate']:.1%}), "
              f"avg char accuracy: {avg_char_accuracy:.1%}, "
              f"avg confidence: {avg_confidence:.3f}")

    return summary


def find_gt_pairs(sample_dir):
    """Find all image + ground truth .txt pairs in sample_dir."""
    pairs = []
    for f in sorted(os.listdir(sample_dir)):
        if f.endswith('.png') and 'processed' in f and not f.endswith('_original.png'):
            base = os.path.splitext(f)[0]
            txt = os.path.join(sample_dir, base + '.txt')
            if os.path.exists(txt):
                pairs.append((os.path.join(sample_dir, f), txt))
    return pairs


def main():
    parser = argparse.ArgumentParser(description='Test v2 OCR pipeline (LineSplitter + recognize)')
    parser.add_argument('image', nargs='?', help='Single image to test (optional)')
    parser.add_argument('--quiet', '-q', action='store_true', help='Only show summary')
    args = parser.parse_args()

    print("Initializing EasyOCR reader with custom model...")
    reader = init_reader()

    if args.image:
        # Single image mode
        image_path = args.image
        gt_path = os.path.splitext(image_path)[0] + '.txt'
        if not os.path.exists(gt_path):
            print(f"Error: Ground truth file not found: {gt_path}")
            sys.exit(1)
        test_image(reader, image_path, gt_path, verbose=not args.quiet)
    else:
        # Test all GT pairs
        pairs = find_gt_pairs(SAMPLE_DIR)
        if not pairs:
            print(f"No ground truth pairs found in {SAMPLE_DIR}")
            sys.exit(1)

        print(f"Found {len(pairs)} ground truth pairs\n")

        all_summaries = []
        for image_path, gt_path in pairs:
            summary = test_image(reader, image_path, gt_path, verbose=not args.quiet)
            all_summaries.append(summary)

        # Overall summary
        total_exact = sum(s['exact_matches'] for s in all_summaries)
        total_compared = sum(s['total_compared'] for s in all_summaries)
        total_char_acc = sum(s['avg_char_accuracy'] * s['total_compared'] for s in all_summaries)

        print(f"\n{'='*70}")
        print(f"  OVERALL RESULTS")
        print(f"{'='*70}")
        for s in all_summaries:
            print(f"  {s['image']:40s}  {s['exact_matches']:3d}/{s['total_compared']:<3d} exact  "
                  f"char_acc={s['avg_char_accuracy']:.1%}  conf={s['avg_confidence']:.3f}")
        print(f"  {'─'*66}")
        if total_compared > 0:
            print(f"  {'TOTAL':40s}  {total_exact:3d}/{total_compared:<3d} exact  "
                  f"char_acc={total_char_acc/total_compared:.1%}")
        print()


if __name__ == '__main__':
    main()
