#!/usr/bin/env python3
"""
Test the v3 OCR pipeline: segment-first (header detection → section label → content OCR)

Accepts original color screenshots (not preprocessed). For each image:
  1. detect_headers() → segment_and_tag() using header OCR model
  2. parse_from_segments() → content OCR per segment
  3. FM (fuzzy matching) applied for sections that have a dictionary file
  4. Compare against GT if available, otherwise print detected output

Usage:
    python3 scripts/v3/test_v3_pipeline.py data/sample_images/titan_blade_original.png
    python3 scripts/v3/test_v3_pipeline.py data/sample_images/ -q
    python3 scripts/v3/test_v3_pipeline.py data/sample_images/ --sections
    python3 scripts/v3/test_v3_pipeline.py data/sample_images/ --normalize
"""

import os
import sys
import re
import argparse
import difflib

import cv2

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'backend'))

from lib.mabinogi_tooltip_parser import MabinogiTooltipParser
from lib.tooltip_segmenter import (
    init_header_reader,
    load_section_patterns,
    load_config,
    segment_and_tag,
)

MODELS_DIR  = os.path.join(PROJECT_ROOT, 'backend', 'ocr', 'models')
CONFIG_PATH = os.path.join(PROJECT_ROOT, 'configs', 'mabinogi_tooltip.yaml')
DICT_DIR    = os.path.join(PROJECT_ROOT, 'data', 'dictionary')


def normalize_line(text):
    """Strip leading structural prefixes (-, ., ㄴ) and surrounding whitespace."""
    return re.sub(r'^[\s\-\.ㄴ]+', '', text).strip()


def load_ground_truth(txt_path):
    with open(txt_path, 'r', encoding='utf-8') as f:
        lines = f.read().splitlines()
    return [line for line in lines if line.strip()]


def find_gt_file(image_path, gt_dir, gt_suffix):
    """Look for a GT file matching image_path in gt_dir (or same dir)."""
    basename = os.path.splitext(os.path.basename(image_path))[0]
    search_dir = gt_dir or os.path.dirname(image_path)

    candidates = [
        basename + gt_suffix,
        basename.replace('_processed', '') + gt_suffix,
        basename + '_processed' + gt_suffix,
    ]
    for name in candidates:
        path = os.path.join(search_dir, name)
        if os.path.exists(path):
            return path
    return None


def init_readers():
    import easyocr
    from lib.ocr_utils import patch_reader_imgw

    print("Initializing header OCR reader (custom_header)...")
    header_reader = init_header_reader(models_dir=MODELS_DIR)

    print("Initializing content OCR reader (custom_mabinogi)...")
    content_reader = easyocr.Reader(
        ['ko'],
        model_storage_directory=MODELS_DIR,
        user_network_directory=MODELS_DIR,
        recog_network='custom_mabinogi',
    )
    fixed_imgW = patch_reader_imgw(content_reader, MODELS_DIR)
    print(f"Content reader initialized with fixed imgW={fixed_imgW}")
    return header_reader, content_reader


def init_corrector():
    from lib.text_corrector import TextCorrector
    return TextCorrector(dict_dir=DICT_DIR)


def test_image(header_reader, content_reader, parser, section_patterns,
               image_path, corrector, gt_path=None, verbose=True,
               show_sections=False, normalize=False):
    """Run v3 pipeline on a single image and optionally compare against GT."""
    basename = os.path.basename(image_path)

    img_bgr = cv2.imread(image_path)
    if img_bgr is None:
        print(f"  ERROR: cannot read {image_path}")
        return None

    # Step 1: segment with header OCR
    config = load_config(CONFIG_PATH)
    tagged = segment_and_tag(img_bgr, header_reader, section_patterns, config)

    # Step 2: content OCR per segment
    result  = parser.parse_from_segments(tagged, content_reader)
    ocr_lines = result['all_lines']
    sections  = result['sections']

    # Which sections have a dictionary?
    fm_sections = set(corrector._section_norm_cache.keys())

    gt_lines = load_ground_truth(gt_path) if gt_path else None
    has_gt   = gt_lines is not None

    compare_count = min(len(ocr_lines), len(gt_lines)) if has_gt else len(ocr_lines)

    if verbose:
        print(f"\n{'='*70}")
        print(f"  {basename}")
        n_headers = sum(1 for s in tagged if s['header_crop'] is not None)
        print(f"  Segments: {len(tagged)} ({n_headers} headers detected)")
        for seg in tagged:
            if seg['header_crop'] is None:
                print(f"    [pre_header]")
            else:
                status = '✓' if seg['section'] else '✗'
                print(f"    {status} [{seg['section'] or 'UNKNOWN':20s}]  "
                      f"ocr='{seg['header_ocr_text']}'  "
                      f"conf={seg['header_ocr_conf']:.2f}  "
                      f"score={seg['header_match_score']}")
        if has_gt:
            print(f"  GT lines: {len(gt_lines)}, OCR lines: {len(ocr_lines)}, comparing: {compare_count}")
        else:
            print(f"  OCR lines: {len(ocr_lines)}  (no GT — output only)")
        print(f"{'='*70}")

    results = []
    prev_section = None
    current_enchant_entry = None

    for i in range(compare_count):
        line    = ocr_lines[i]
        text    = line.get('text', '')
        section = line.get('section', '')

        if has_gt:
            gt_text = gt_lines[i]
            cmp_gt  = normalize_line(gt_text) if normalize else gt_text
            cmp_ocr = normalize_line(text)    if normalize else text
            matcher       = difflib.SequenceMatcher(None, cmp_gt, cmp_ocr)
            char_accuracy = matcher.ratio()
            exact_match   = (cmp_ocr.strip() == cmp_gt.strip())
        else:
            gt_text = char_accuracy = exact_match = None

        # Fuzzy matching — applied for sections that have a dictionary
        fm_text = fm_score = fm_exact = fm_char_accuracy = None

        if section in fm_sections:
            enchant_db_ready = bool(corrector._enchant_db)

            if section == 'enchant' and enchant_db_ready:
                # Try header FM on every line — let the score decide,
                # don't rely on regex tag (OCR garbles headers beyond regex recognition)
                hdr_text, hdr_score, hdr_entry = corrector.match_enchant_header(text)
                if hdr_score > 0:
                    fm_text, fm_score = hdr_text, hdr_score
                    current_enchant_entry = hdr_entry
                else:
                    fm_text, fm_score = corrector.match_enchant_effect(text, current_enchant_entry)
            else:
                fm_text, fm_score = corrector.correct_normalized(text, section=section)

            if has_gt and fm_text is not None:
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
            'section':         section,
            'fm_text':         fm_text,
            'fm_score':        fm_score,
            'fm_exact':        fm_exact,
            'fm_char_accuracy':fm_char_accuracy,
        })

        if verbose:
            is_header_line = line.get('is_header', False)

            if is_header_line:
                label = section if section else '(undetected)'
                print(f"\n  {'─'*12} header '{label}' detected {'─'*12}")
            elif section != prev_section:
                label = section if section else '(undetected)'
                print(f"\n  {'─'*22} {label} {'─'*22}")

            if not is_header_line:
                prev_section = section

            if has_gt:
                has_fm = fm_text is not None and fm_score is not None
                if has_fm:
                    if exact_match and not fm_exact and fm_score > 0:
                        status = 'RF'
                    elif not exact_match:
                        status = 'FM' if fm_exact else 'XX'
                    else:
                        status = 'OK'
                else:
                    status = 'OK' if exact_match else 'XX'

                sub_tag = f' [{line.get("sub_count", 1)} segs]' if line.get('sub_count', 1) > 1 else ''
                print(f"  [{status}] Line {i+1:2d} (conf={line.get('confidence', 0):.3f}, acc={char_accuracy:.1%}){sub_tag}")
                print(f"       GT:  {gt_text}")
                print(f"       OCR: {text}")

                if has_fm:
                    if fm_score == -3:
                        print(f"       FM:  (sub-bullet skipped)")
                    elif fm_score > 0:
                        fm_acc = f', acc={fm_char_accuracy:.1%}' if fm_char_accuracy is not None else ''
                        print(f"       FM:  {fm_text}  (score={fm_score:.1f}{fm_acc})")
                    else:
                        print(f"       FM:  (no match)")
            else:
                sub_tag = f' [{line.get("sub_count", 1)} segs]' if line.get('sub_count', 1) > 1 else ''
                print(f"  Line {i+1:2d} (conf={line.get('confidence', 0):.3f}){sub_tag}  {text}")

    if has_gt and len(ocr_lines) > len(gt_lines) and verbose:
        print(f"\n  ({len(ocr_lines) - len(gt_lines)} extra OCR lines beyond GT — not scored)")

    if show_sections and sections:
        print(f"\n  {'─'*66}")
        print(f"  SECTIONS:")
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
                for ln in section_data['lines'][:3]:
                    print(f"      \"{ln.get('text', '')[:60]}\"")
                if n > 3:
                    print(f"      ... ({n - 3} more)")
            elif 'text' in section_data:
                print(f"    [{section_key}] \"{section_data['text'][:60]}\"")

    # Summary metrics
    counted = results
    fm_counted = [r for r in results if r['fm_text'] is not None]

    if has_gt and counted:
        exact_matches     = sum(1 for r in counted if r['exact_match'])
        avg_char_accuracy = sum(r['char_accuracy'] for r in counted) / len(counted)
        avg_confidence    = sum(r['confidence']    for r in counted) / len(counted)
        fm_exact_matches     = sum(1 for r in fm_counted if r['fm_exact'])
        fm_avg_char_accuracy = (sum(r['fm_char_accuracy'] for r in fm_counted if r['fm_char_accuracy'] is not None)
                                / len(fm_counted)) if fm_counted else None
    else:
        exact_matches = avg_char_accuracy = fm_exact_matches = fm_avg_char_accuracy = None
        avg_confidence = sum(r['confidence'] for r in results) / len(results) if results else 0.0

    summary = {
        'image':              basename,
        'gt_lines':           len(gt_lines) if has_gt else None,
        'detected_lines':     len(ocr_lines),
        'segments':           len(tagged),
        'headers_found':      sum(1 for s in tagged if s['header_crop'] is not None),
        'sections_detected':  len(sections),
        'total_compared':     len(counted),
        'fm_compared':        len(fm_counted),
        'exact_matches':      exact_matches,
        'avg_char_accuracy':  avg_char_accuracy,
        'avg_confidence':     avg_confidence,
        'fm_exact_matches':   fm_exact_matches,
        'fm_avg_char_accuracy': fm_avg_char_accuracy,
        'results':            results,
    }

    if verbose:
        if has_gt and counted:
            rate = exact_matches / len(counted) if counted else 0
            fm_part = ''
            if fm_counted:
                recovered = fm_exact_matches - sum(1 for r in fm_counted if r['exact_match'])
                fm_part = (f", FM: {fm_exact_matches}/{len(fm_counted)} exact "
                           f"(+{recovered} recovered"
                           f", char_acc={fm_avg_char_accuracy:.1%}" if fm_avg_char_accuracy else "")
                fm_part += ")"
            print(f"\n  Summary: {exact_matches}/{len(counted)} exact matches "
                  f"({rate:.1%}), "
                  f"avg char accuracy: {avg_char_accuracy:.1%}, "
                  f"avg confidence: {avg_confidence:.3f}, "
                  f"sections: {len(sections)}{fm_part}")
        else:
            print(f"\n  Summary: {len(ocr_lines)} lines detected, "
                  f"avg confidence: {avg_confidence:.3f}, "
                  f"sections: {len(sections)}")

    return summary


def collect_images(path):
    import glob
    expanded = sorted(glob.glob(path))
    if expanded:
        return [f for f in expanded if os.path.isfile(f)]
    if os.path.isdir(path):
        return sorted(
            os.path.join(path, f)
            for f in os.listdir(path)
            if f.lower().endswith('.png')
        )
    return [path] if os.path.isfile(path) else []


def main():
    argp = argparse.ArgumentParser(description='Test v3 OCR pipeline (segment-first)')
    argp.add_argument('path', help='Image file or folder of color screenshots to process')
    argp.add_argument('--gt-dir', default=None,
                      help='Directory to search for GT files (default: same dir as images)')
    argp.add_argument('--gt-suffix', default='.txt',
                      help='GT file suffix (default: .txt)')
    argp.add_argument('--quiet', '-q', action='store_true', help='Summary only')
    argp.add_argument('--sections', '-s', action='store_true', help='Show section breakdown')
    argp.add_argument('--normalize', '-n', action='store_true',
                      help='Strip leading structural prefixes before GT comparison')
    args = argp.parse_args()

    header_reader, content_reader = init_readers()
    parser           = MabinogiTooltipParser(CONFIG_PATH)
    section_patterns = load_section_patterns(CONFIG_PATH)
    print(f"Loaded {len(section_patterns)} section patterns")

    corrector = init_corrector()

    images = collect_images(args.path)
    if not images:
        print(f"No .png images found in: {args.path}")
        sys.exit(1)

    print(f"\nProcessing {len(images)} image(s)...\n")

    all_summaries = []
    for image_path in images:
        gt_path = find_gt_file(image_path, args.gt_dir, args.gt_suffix)
        summary = test_image(
            header_reader, content_reader, parser, section_patterns,
            image_path, corrector, gt_path=gt_path,
            verbose=not args.quiet,
            show_sections=args.sections,
            normalize=args.normalize,
        )
        if summary:
            all_summaries.append(summary)

    if not all_summaries:
        return

    has_gt = any(s['gt_lines'] is not None for s in all_summaries)

    print(f"\n{'='*70}")
    print(f"  OVERALL RESULTS  (v3 segment-first pipeline)")
    print(f"{'='*70}")

    for s in all_summaries:
        if s['gt_lines'] is not None:
            fm_col = ''
            if s['fm_compared'] > 0:
                fm_col = f"  FM={s['fm_exact_matches']}/{s['fm_compared']}"
            print(f"  {s['image']:40s}  {s['exact_matches']:3d}/{s['total_compared']:<3d} exact  "
                  f"char_acc={s['avg_char_accuracy']:.1%}  conf={s['avg_confidence']:.3f}  "
                  f"hdrs={s['headers_found']}  sections={s['sections_detected']}{fm_col}")
        else:
            print(f"  {s['image']:40s}  {s['detected_lines']:3d} lines (no GT)  "
                  f"conf={s['avg_confidence']:.3f}  hdrs={s['headers_found']}  sections={s['sections_detected']}")

    if has_gt:
        gt_sums        = [s for s in all_summaries if s['gt_lines'] is not None]
        total_exact    = sum(s['exact_matches']    for s in gt_sums)
        total_compared = sum(s['total_compared']   for s in gt_sums)
        total_char_acc = sum(s['avg_char_accuracy'] * s['total_compared'] for s in gt_sums)
        total_fm_compared = sum(s['fm_compared']   for s in gt_sums)
        total_fm_exact    = sum(s['fm_exact_matches'] or 0 for s in gt_sums)
        fm_total_col = ''
        if total_fm_compared > 0:
            fm_total_col = f"  FM={total_fm_exact}/{total_fm_compared}"
        print(f"  {'─'*66}")
        if total_compared > 0:
            print(f"  {'TOTAL':40s}  {total_exact:3d}/{total_compared:<3d} exact  "
                  f"char_acc={total_char_acc/total_compared:.1%}{fm_total_col}")
    print()


if __name__ == '__main__':
    main()
