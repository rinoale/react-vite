#!/usr/bin/env python3
"""
Test the v3 OCR pipeline: segment-first (header detection → section label → content OCR)

Accepts a folder of original color screenshots (not preprocessed). For each image:
  1. detect_headers() → segment_and_tag() using header OCR model
  2. parse_from_segments() → content OCR per segment
  3. Compare against GT if available, otherwise print detected output

Usage:
    python3 scripts/test_v3_pipeline.py data/sample_images/titan_blade_original.png
    python3 scripts/test_v3_pipeline.py data/themes/
    python3 scripts/test_v3_pipeline.py data/themes/ --gt-dir data/sample_images/
    python3 scripts/test_v3_pipeline.py data/themes/ -q
    python3 scripts/test_v3_pipeline.py data/themes/ --sections
    python3 scripts/test_v3_pipeline.py data/sample_images/titan_blade_original.png -f
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

from mabinogi_tooltip_parser import MabinogiTooltipParser
from tooltip_segmenter import init_header_reader, load_section_patterns, segment_and_tag

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
    from ocr_utils import patch_reader_imgw

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
    from text_corrector import TextCorrector
    return TextCorrector(dict_dir=DICT_DIR)


def test_image(header_reader, content_reader, parser, section_patterns,
               image_path, gt_path=None, verbose=True, show_sections=False,
               normalize=False, corrector=None, fm_conf_threshold=None):
    """Run v3 pipeline on a single image and optionally compare against GT."""
    basename = os.path.basename(image_path)

    img_bgr = cv2.imread(image_path)
    if img_bgr is None:
        print(f"  ERROR: cannot read {image_path}")
        return None

    # Step 1: segment with header OCR
    tagged = segment_and_tag(img_bgr, header_reader, section_patterns)

    # Step 2: content OCR per segment
    result  = parser.parse_from_segments(tagged, content_reader)
    ocr_lines = result['all_lines']
    sections  = result['sections']

    seg_by_section = {seg['section']: seg for seg in tagged if seg['header_crop'] is not None}

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

        # Fuzzy matching
        fm_text = fm_score = fm_exact = fm_char_accuracy = None
        fm_gated = False

        if corrector is not None and has_gt:
            conf     = line.get('confidence', 0.0)
            fm_gated = fm_conf_threshold is not None and conf >= fm_conf_threshold

            if not fm_gated:
                is_enchant_hdr   = line.get('is_enchant_hdr')
                enchant_db_ready = bool(getattr(corrector, '_enchant_db', []))

                if section == 'enchant' and enchant_db_ready and is_enchant_hdr is not None:
                    if is_enchant_hdr:
                        fm_text, fm_score, current_enchant_entry = corrector.match_enchant_header(text)
                    else:
                        fm_text, fm_score = corrector.match_enchant_effect(text, current_enchant_entry)
                else:
                    fm_text, fm_score = corrector.correct_normalized(text, section=section)
            else:
                fm_text, fm_score = text, -1

            cmp_fm           = normalize_line(fm_text) if normalize else fm_text
            fm_exact         = (cmp_fm.strip() == cmp_gt.strip()) if has_gt else None
            fm_matcher       = difflib.SequenceMatcher(None, cmp_gt, cmp_fm) if has_gt else None
            fm_char_accuracy = fm_matcher.ratio() if fm_matcher else None

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
            'fm_gated':        fm_gated,
        })

        if verbose:
            if section != prev_section:
                label = section if section else '(undetected)'
                seg_info = ''
                if section in seg_by_section:
                    s = seg_by_section[section]
                    seg_info = (f"  [header ocr='{s['header_ocr_text']}'  "
                                f"conf={s['header_ocr_conf']:.2f}  "
                                f"score={s['header_match_score']}]")
                print(f"\n  {'─'*20} {label} {'─'*20}{seg_info}")
                prev_section = section

            if has_gt:
                if corrector is not None:
                    if exact_match and not fm_exact and fm_score and fm_score > 0:
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

                if corrector is not None:
                    is_enchant_hdr   = line.get('is_enchant_hdr')
                    enchant_db_ready = bool(getattr(corrector, '_enchant_db', []))
                    if section == 'enchant' and enchant_db_ready and is_enchant_hdr is not None:
                        dict_tag = 'enchant[hdr]' if is_enchant_hdr else 'enchant[eff]'
                    else:
                        dict_tag = (f'{section}.txt'
                                    if section and section in corrector._section_norm_cache
                                    else 'combined')
                    show_fm = not exact_match or (exact_match and not fm_exact and fm_score and fm_score > 0)
                    if show_fm:
                        if fm_gated:
                            print(f"       FM:  (skipped — conf={line.get('confidence', 0):.3f} >= {fm_conf_threshold})")
                        elif fm_score == -3:
                            print(f"       FM:  (sub-bullet skipped)")
                        elif fm_score == -2:
                            print(f"       FM:  (no dictionary for '{section}', skipped)")
                        elif fm_score and fm_score > 0:
                            print(f"       FM:  {fm_text}  (score={fm_score:.1f}, searched: {dict_tag})")
                        else:
                            print(f"       FM:  (no match, searched: {dict_tag})")
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

    # Summary metrics — exclude reforge sub-bullets (skip_accuracy=True) from counts
    for r in results:
        r.setdefault('skip_accuracy', r.get('fm_score') == -3)
    counted       = [r for r in results if not r.get('skip_accuracy')]
    skipped_count = len(results) - len(counted)

    if has_gt and counted:
        exact_matches     = sum(1 for r in counted if r['exact_match'])
        avg_char_accuracy = sum(r['char_accuracy'] for r in counted) / len(counted)
        avg_confidence    = sum(r['confidence']    for r in counted) / len(counted)
        fm_exact_matches     = sum(1 for r in counted if r['fm_exact'])     if corrector else None
        fm_avg_char_accuracy = (sum(r['fm_char_accuracy'] for r in counted if r['fm_char_accuracy'] is not None)
                                / len(counted)) if corrector else None
        fm_gated_count = sum(1 for r in counted if r.get('fm_gated')) if corrector else 0
    else:
        exact_matches = avg_char_accuracy = fm_exact_matches = fm_avg_char_accuracy = None
        fm_gated_count = 0
        avg_confidence = sum(r['confidence'] for r in results) / len(results) if results else 0.0

    summary = {
        'image':              basename,
        'gt_lines':           len(gt_lines) if has_gt else None,
        'detected_lines':     len(ocr_lines),
        'segments':           len(tagged),
        'headers_found':      sum(1 for s in tagged if s['header_crop'] is not None),
        'sections_detected':  len(sections),
        'total_compared':     len(counted),
        'skipped_count':      skipped_count,
        'exact_matches':      exact_matches,
        'avg_char_accuracy':  avg_char_accuracy,
        'avg_confidence':     avg_confidence,
        'fm_exact_matches':   fm_exact_matches,
        'fm_avg_char_accuracy': fm_avg_char_accuracy,
        'results':            results,
    }

    if verbose:
        if has_gt and counted:
            rate      = exact_matches / len(counted) if counted else 0
            skip_note = f', skipped={skipped_count}' if skipped_count else ''
            fm_part   = ''
            if corrector is not None:
                recovered = fm_exact_matches - exact_matches
                gate_note = f', gated={fm_gated_count}' if fm_conf_threshold is not None else ''
                fm_part   = (f", FM: {fm_exact_matches}/{len(counted)} exact "
                             f"(+{recovered} recovered, char_acc={fm_avg_char_accuracy:.1%}{gate_note})")
            print(f"\n  Summary: {exact_matches}/{len(counted)} exact matches "
                  f"({rate:.1%}){skip_note}, "
                  f"avg char accuracy: {avg_char_accuracy:.1%}, "
                  f"avg confidence: {avg_confidence:.3f}, "
                  f"sections: {len(sections)}{fm_part}")
        else:
            print(f"\n  Summary: {len(ocr_lines)} lines detected, "
                  f"avg confidence: {avg_confidence:.3f}, "
                  f"sections: {len(sections)}")

    return summary


def collect_images(path):
    if os.path.isfile(path):
        return [path]
    return sorted(
        os.path.join(path, f)
        for f in os.listdir(path)
        if f.lower().endswith('.png')
    )


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
    argp.add_argument('--include-fuzzy', '-f', action='store_true',
                      help='Show FM: line with fuzzy matching result')
    argp.add_argument('--fm-threshold', type=float, default=None, metavar='CONF',
                      help='Apply FM only when OCR conf < CONF (e.g. 0.85). Only with -f.')
    args = argp.parse_args()

    header_reader, content_reader = init_readers()
    parser           = MabinogiTooltipParser(CONFIG_PATH)
    section_patterns = load_section_patterns(CONFIG_PATH)
    print(f"Loaded {len(section_patterns)} section patterns")

    corrector = None
    if args.include_fuzzy:
        print("Loading dictionaries for fuzzy matching...")
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
            image_path, gt_path=gt_path,
            verbose=not args.quiet,
            show_sections=args.sections,
            normalize=args.normalize,
            corrector=corrector,
            fm_conf_threshold=args.fm_threshold,
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
            if corrector is not None:
                recovered = s['fm_exact_matches'] - s['exact_matches']
                fm_col = f"  FM={s['fm_exact_matches']:3d} (+{recovered})"
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
        total_skipped  = sum(s.get('skipped_count', 0) for s in gt_sums)
        total_char_acc = sum(s['avg_char_accuracy'] * s['total_compared'] for s in gt_sums)
        fm_total_col   = ''
        if corrector is not None:
            total_fm_exact    = sum(s['fm_exact_matches']                           for s in gt_sums)
            total_fm_char_acc = sum(s['fm_avg_char_accuracy'] * s['total_compared'] for s in gt_sums)
            recovered = total_fm_exact - total_exact
            fm_total_col = (f"  FM={total_fm_exact:3d}/{total_compared} "
                            f"(+{recovered} recovered, char_acc={total_fm_char_acc/total_compared:.1%})")
        print(f"  {'─'*66}")
        if total_compared > 0:
            skip_col = f"  skipped={total_skipped}" if total_skipped else ''
            print(f"  {'TOTAL':40s}  {total_exact:3d}/{total_compared:<3d} exact  "
                  f"char_acc={total_char_acc/total_compared:.1%}{skip_col}{fm_total_col}")
    print()


if __name__ == '__main__':
    main()
