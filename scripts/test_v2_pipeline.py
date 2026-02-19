#!/usr/bin/env python3
"""
Test the v2 OCR pipeline: MabinogiTooltipParser (section-aware)

Splits sample images into line crops, groups sub-lines, runs OCR,
categorizes into sections, and compares against ground truth .txt files.

Usage:
    python3 scripts/test_v2_pipeline.py                          # Test all GT pairs
    python3 scripts/test_v2_pipeline.py data/sample_images/captain_suit_processed.png  # Single image
    python3 scripts/test_v2_pipeline.py -q                       # Summary only
    python3 scripts/test_v2_pipeline.py --sections               # Show section breakdown
    python3 scripts/test_v2_pipeline.py --include-fuzzy           # Show FM: line (post-fuzzy result)
"""

import os
import sys
import re
import argparse
import difflib

import cv2
import numpy as np

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'backend'))

from mabinogi_tooltip_parser import MabinogiTooltipParser

MODELS_DIR = os.path.join(PROJECT_ROOT, 'backend', 'models')
SAMPLE_DIR = os.path.join(PROJECT_ROOT, 'data', 'sample_images')
CONFIG_PATH = os.path.join(PROJECT_ROOT, 'configs', 'mabinogi_tooltip.yaml')
DICT_DIR   = os.path.join(PROJECT_ROOT, 'data', 'dictionary')


def normalize_line(text):
    """Strip leading structural prefixes (-, ., ㄴ) and surrounding whitespace."""
    return re.sub(r'^[\s\-\.ㄴ]+', '', text).strip()


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


def init_corrector():
    """Load TextCorrector with both game dictionaries."""
    from text_corrector import TextCorrector
    corrector = TextCorrector()
    corrector.load_dictionary(os.path.join(DICT_DIR, 'reforging_options.txt'))
    corrector.load_dictionary(os.path.join(DICT_DIR, 'tooltip_general.txt'))
    return corrector


def test_image(reader, parser, image_path, gt_path, verbose=True, show_sections=False,
               normalize=False, corrector=None):
    """Test the section-aware pipeline on a single image against ground truth.

    Returns:
        dict with results and metrics
    """
    basename = os.path.basename(image_path)
    gt_lines = load_ground_truth(gt_path)

    # Run section-aware parsing pipeline
    result = parser.parse_tooltip(image_path, reader)
    ocr_lines = result['all_lines']
    sections = result['sections']

    # Compare only up to GT line count — extra OCR lines beyond GT are ignored
    compare_count = min(len(ocr_lines), len(gt_lines))

    if verbose:
        print(f"\n{'='*70}")
        print(f"  {basename}")
        print(f"  GT lines: {len(gt_lines)}, OCR lines: {len(ocr_lines)}, comparing: {compare_count}")
        print(f"{'='*70}")

    results = []
    for i in range(compare_count):
        line = ocr_lines[i]
        text = line.get('text', '')
        gt_text = gt_lines[i]

        cmp_gt  = normalize_line(gt_text) if normalize else gt_text
        cmp_ocr = normalize_line(text)    if normalize else text

        matcher      = difflib.SequenceMatcher(None, cmp_gt, cmp_ocr)
        char_accuracy = matcher.ratio()
        exact_match  = (cmp_ocr.strip() == cmp_gt.strip())

        # Fuzzy matching (only when corrector provided)
        fm_text          = None
        fm_score         = 0
        fm_exact         = False
        fm_char_accuracy = char_accuracy  # default to OCR accuracy if no FM

        if corrector is not None:
            fm_text, fm_score = corrector.correct_normalized(text)
            cmp_fm           = normalize_line(fm_text) if normalize else fm_text
            fm_exact         = (cmp_fm.strip() == cmp_gt.strip())
            fm_matcher       = difflib.SequenceMatcher(None, cmp_gt, cmp_fm)
            fm_char_accuracy = fm_matcher.ratio()

        results.append({
            'line_num':        i + 1,
            'gt':              gt_text,
            'ocr':             text,
            'confidence':      line.get('confidence', 0.0),
            'char_accuracy':   char_accuracy,
            'exact_match':     exact_match,
            'sub_count':       line.get('sub_count', 1),
            'fm_text':         fm_text,
            'fm_score':        fm_score,
            'fm_exact':        fm_exact,
            'fm_char_accuracy': fm_char_accuracy,
        })

        if verbose:
            # Status tag: FM replaces XX when fuzzy matching fixed the line
            if corrector is not None and not exact_match:
                status = 'FM' if fm_exact else 'XX'
            else:
                status = 'OK' if exact_match else 'XX'

            sub_tag = f' [{line.get("sub_count", 1)} segs]' if line.get('sub_count', 1) > 1 else ''
            print(f"  [{status}] Line {i+1:2d} (conf={line.get('confidence', 0):.3f}, acc={char_accuracy:.1%}){sub_tag}")

            if not exact_match:
                print(f"       GT:  {gt_text}")
                print(f"       OCR: {text}")
                if corrector is not None:
                    if fm_score > 0:
                        print(f"       FM:  {fm_text}  (score={fm_score})")
                    else:
                        print(f"       FM:  (no match)")

    # Show skipped OCR lines beyond GT
    if len(ocr_lines) > len(gt_lines) and verbose:
        skipped = len(ocr_lines) - len(gt_lines)
        print(f"\n  ({skipped} extra OCR lines beyond GT — not scored)")

    # Section breakdown
    if show_sections and sections:
        print(f"\n  {'─'*66}")
        print(f"  SECTIONS DETECTED:")
        for section_key, section_data in sections.items():
            if section_data.get('skipped'):
                print(f"    [{section_key}] (skipped, {section_data.get('line_count', 0)} lines)")
            elif 'parts' in section_data:
                parts = section_data['parts']
                print(f"    [{section_key}] {len(parts)} color parts")
                for p in parts:
                    print(f"      Part {p['part']}: R={p.get('r')}, G={p.get('g')}, B={p.get('b')}")
            elif 'lines' in section_data:
                n = len(section_data['lines'])
                print(f"    [{section_key}] {n} lines")
                for line in section_data['lines'][:3]:
                    print(f"      \"{line.get('text', '')[:60]}\"")
                if n > 3:
                    print(f"      ... ({n - 3} more)")
            elif 'text' in section_data:
                print(f"    [{section_key}] \"{section_data['text'][:60]}\"")

    # Summary metrics
    if results:
        exact_matches    = sum(1 for r in results if r['exact_match'])
        avg_char_accuracy = sum(r['char_accuracy'] for r in results) / len(results)
        avg_confidence   = sum(r['confidence'] for r in results) / len(results)
        fm_exact_matches    = sum(1 for r in results if r['fm_exact'])    if corrector else None
        fm_avg_char_accuracy = sum(r['fm_char_accuracy'] for r in results) / len(results) if corrector else None
    else:
        exact_matches = fm_exact_matches = 0
        avg_char_accuracy = fm_avg_char_accuracy = 0.0
        avg_confidence = 0.0

    summary = {
        'image':             basename,
        'gt_lines':          len(gt_lines),
        'detected_lines':    len(ocr_lines),
        'exact_matches':     exact_matches,
        'total_compared':    len(results),
        'exact_match_rate':  exact_matches / len(results) if results else 0,
        'avg_char_accuracy': avg_char_accuracy,
        'avg_confidence':    avg_confidence,
        'sections_detected': len(sections),
        'fm_exact_matches':     fm_exact_matches,
        'fm_avg_char_accuracy': fm_avg_char_accuracy,
        'results':           results,
    }

    if verbose:
        fm_part = ''
        if corrector is not None:
            recovered = fm_exact_matches - exact_matches
            fm_part = (f", FM: {fm_exact_matches}/{len(results)} exact "
                       f"(+{recovered} recovered, char_acc={fm_avg_char_accuracy:.1%})")
        print(f"\n  Summary: {exact_matches}/{len(results)} exact matches "
              f"({summary['exact_match_rate']:.1%}), "
              f"avg char accuracy: {avg_char_accuracy:.1%}, "
              f"avg confidence: {avg_confidence:.3f}, "
              f"sections: {len(sections)}{fm_part}")

    return summary


def find_gt_pairs(sample_dir, gt_suffix='.txt'):
    """Find all image + ground truth pairs in sample_dir."""
    pairs = []
    for f in sorted(os.listdir(sample_dir)):
        if f.endswith('.png') and 'processed' in f and not f.endswith('_original.png'):
            base = os.path.splitext(f)[0]
            txt = os.path.join(sample_dir, base + gt_suffix)
            if os.path.exists(txt):
                pairs.append((os.path.join(sample_dir, f), txt))
    return pairs


def main():
    argp = argparse.ArgumentParser(description='Test v2 OCR pipeline (section-aware)')
    argp.add_argument('image', nargs='?', help='Single image to test (optional)')
    argp.add_argument('--quiet', '-q', action='store_true', help='Only show summary')
    argp.add_argument('--sections', '-s', action='store_true', help='Show section breakdown')
    argp.add_argument('--gt-suffix', default='.txt',
                       help='GT file suffix (default: .txt, use _expected.txt for expected-only)')
    argp.add_argument('--normalize', '-n', action='store_true',
                       help='Strip leading structural prefixes (-, ., ㄴ) before comparison')
    argp.add_argument('--include-fuzzy', '-f', action='store_true',
                       help='Show FM: line with number-normalized fuzzy matching result')
    args = argp.parse_args()

    print("Initializing EasyOCR reader with custom model...")
    reader = init_reader()
    parser = MabinogiTooltipParser(CONFIG_PATH)

    corrector = None
    if args.include_fuzzy:
        print("Loading dictionaries for fuzzy matching...")
        corrector = init_corrector()

    gt_suffix = args.gt_suffix

    if args.image:
        image_path = args.image
        base = os.path.splitext(image_path)[0]
        gt_path = base + gt_suffix
        if not os.path.exists(gt_path):
            print(f"Error: Ground truth file not found: {gt_path}")
            sys.exit(1)
        test_image(reader, parser, image_path, gt_path,
                   verbose=not args.quiet, show_sections=args.sections,
                   normalize=args.normalize, corrector=corrector)
    else:
        pairs = find_gt_pairs(SAMPLE_DIR, gt_suffix)
        if not pairs:
            print(f"No ground truth pairs found in {SAMPLE_DIR} with suffix '{gt_suffix}'")
            sys.exit(1)

        print(f"Found {len(pairs)} ground truth pairs\n")

        all_summaries = []
        for image_path, gt_path in pairs:
            summary = test_image(reader, parser, image_path, gt_path,
                                 verbose=not args.quiet, show_sections=args.sections,
                                 normalize=args.normalize, corrector=corrector)
            all_summaries.append(summary)

        # Overall summary
        total_exact    = sum(s['exact_matches'] for s in all_summaries)
        total_compared = sum(s['total_compared'] for s in all_summaries)
        total_char_acc = sum(s['avg_char_accuracy'] * s['total_compared'] for s in all_summaries)
        total_fm_exact    = sum(s['fm_exact_matches'] for s in all_summaries) if corrector else None
        total_fm_char_acc = sum(s['fm_avg_char_accuracy'] * s['total_compared'] for s in all_summaries) if corrector else None

        print(f"\n{'='*70}")
        print(f"  OVERALL RESULTS")
        print(f"{'='*70}")
        for s in all_summaries:
            fm_col = ''
            if corrector is not None:
                recovered = s['fm_exact_matches'] - s['exact_matches']
                fm_col = f"  FM={s['fm_exact_matches']:3d} (+{recovered})"
            print(f"  {s['image']:40s}  {s['exact_matches']:3d}/{s['total_compared']:<3d} exact  "
                  f"char_acc={s['avg_char_accuracy']:.1%}  conf={s['avg_confidence']:.3f}  "
                  f"sections={s['sections_detected']}{fm_col}")
        print(f"  {'─'*66}")
        if total_compared > 0:
            fm_total_col = ''
            if corrector is not None:
                recovered = total_fm_exact - total_exact
                fm_total_col = (f"  FM={total_fm_exact:3d}/{total_compared} "
                                f"(+{recovered} recovered, char_acc={total_fm_char_acc/total_compared:.1%})")
            print(f"  {'TOTAL':40s}  {total_exact:3d}/{total_compared:<3d} exact  "
                  f"char_acc={total_char_acc/total_compared:.1%}{fm_total_col}")
        print()


if __name__ == '__main__':
    main()
