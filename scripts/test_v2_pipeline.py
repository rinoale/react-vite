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
    python3 scripts/test_v2_pipeline.py --include-fuzzy --fm-threshold 0.85  # FM only when conf < 0.85
    python3 scripts/test_v2_pipeline.py --include-fuzzy --use-gt-sections    # use GT text for section detection (verify FM quality)
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

MODELS_DIR = os.path.join(PROJECT_ROOT, 'backend', 'ocr', 'models')
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
    """Load TextCorrector from dictionary directory (one file per section)."""
    from text_corrector import TextCorrector
    return TextCorrector(dict_dir=DICT_DIR)


def test_image(reader, parser, image_path, gt_path, verbose=True, show_sections=False,
               normalize=False, corrector=None, fm_conf_threshold=None,
               use_gt_sections=False):
    """Test the section-aware pipeline on a single image against ground truth.

    Args:
        use_gt_sections: If True, re-run section detection using GT text instead of OCR text.
                         This isolates FM quality from section detection errors.

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

    # Optional: re-categorize sections using GT text for perfect section assignment.
    # Isolates FM dictionary quality from OCR section detection errors.
    if use_gt_sections and compare_count > 0:
        orig_texts = [l['text'] for l in ocr_lines]
        for i in range(compare_count):
            ocr_lines[i]['text'] = gt_lines[i]
        sections = parser._categorize_sections(ocr_lines)   # re-tags line['section'] in-place
        for i, t in enumerate(orig_texts):
            ocr_lines[i]['text'] = t                        # restore OCR text, keep section tags

    if verbose:
        print(f"\n{'='*70}")
        print(f"  {basename}")
        print(f"  GT lines: {len(gt_lines)}, OCR lines: {len(ocr_lines)}, comparing: {compare_count}")
        if use_gt_sections:
            print(f"  [GT-SECTIONS MODE: section detection uses GT text]")
        print(f"{'='*70}")

    results = []
    prev_section = None
    current_enchant_entry = None   # tracks matched enchant entry for phase-2 effect matching
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
        fm_gated         = False          # True when skipped due to confidence gate
        skip_accuracy    = False          # True for reforge sub-bullets (ㄴ lines)

        if corrector is not None:
            conf    = line.get('confidence', 0.0)
            section = line.get('section', '')
            fm_gated = fm_conf_threshold is not None and conf >= fm_conf_threshold

            if not fm_gated:
                is_enchant_hdr = line.get('is_enchant_hdr')
                enchant_db_ready = bool(getattr(corrector, '_enchant_db', []))

                if section == 'enchant' and enchant_db_ready and is_enchant_hdr is not None:
                    if is_enchant_hdr:
                        # Phase 1: match header → get enchant entry for this slot
                        fm_text, fm_score, current_enchant_entry = corrector.match_enchant_header(text)
                    else:
                        # Phase 2: match effect against only this enchant's ~4-8 effects
                        fm_text, fm_score = corrector.match_enchant_effect(text, current_enchant_entry)
                else:
                    fm_text, fm_score = corrector.correct_normalized(text, section=section)
            else:
                fm_text, fm_score = text, -1  # skipped: high-confidence OCR trusted

            # Reforge ㄴ sub-bullets: skip from accuracy counting
            if fm_score == -3:
                skip_accuracy = True

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
            'fm_gated':        fm_gated,
            'skip_accuracy':   skip_accuracy,
        })

        if verbose:
            # Print category boundary when section changes
            cur_section = line.get('section', '')
            if cur_section != prev_section:
                label = cur_section if cur_section else '(undetected)'
                print(f"\n  {'─'*20} {label} {'─'*20}")
                prev_section = cur_section

            # Status tag
            # FM: OCR wrong → FM correct  | XX: wrong, not fixed
            # OK: OCR correct, FM neutral | RF: OCR correct → FM regressed
            if corrector is not None:
                if exact_match and not fm_exact and fm_score > 0:
                    status = 'RF'   # FM regression: correct OCR → wrong FM
                elif not exact_match:
                    status = 'FM' if fm_exact else 'XX'
                else:
                    status = 'OK'
            else:
                status = 'OK' if exact_match else 'XX'

            sub_tag = f' [{line.get("sub_count", 1)} segs]' if line.get('sub_count', 1) > 1 else ''
            print(f"  [{status}] Line {i+1:2d} (conf={line.get('confidence', 0):.3f}, acc={char_accuracy:.1%}){sub_tag}")

            section     = line.get('section', '')
            section_tag = f'  [section: {section}]' if section else ''
            print(f"       GT:  {gt_text}")
            print(f"       OCR: {text}{section_tag}")
            if corrector is not None:
                is_enchant_hdr = line.get('is_enchant_hdr')
                enchant_db_ready = bool(getattr(corrector, '_enchant_db', []))
                if section == 'enchant' and enchant_db_ready and is_enchant_hdr is not None:
                    dict_tag = 'enchant[hdr]' if is_enchant_hdr else 'enchant[eff]'
                else:
                    dict_tag = (f'{section}.txt'
                                if section and section in corrector._section_norm_cache
                                else 'combined')
                show_fm = not exact_match or (exact_match and not fm_exact and fm_score > 0)
                if show_fm:
                    if fm_gated:
                        print(f"       FM:  (skipped — conf={line.get('confidence', 0):.3f} >= {fm_conf_threshold})")
                    elif fm_score == -3:
                        print(f"       FM:  (sub-bullet skipped)")
                    elif fm_score == -2:
                        print(f"       FM:  (no dictionary for '{section}', skipped)")
                    elif fm_score > 0:
                        print(f"       FM:  {fm_text}  (score={fm_score:.1f}, searched: {dict_tag})")
                    else:
                        print(f"       FM:  (no match, searched: {dict_tag})")

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

    # Summary metrics — exclude reforge sub-bullets (skip_accuracy=True) from counts
    counted = [r for r in results if not r.get('skip_accuracy')]
    skipped_count = len(results) - len(counted)

    if counted:
        exact_matches     = sum(1 for r in counted if r['exact_match'])
        avg_char_accuracy = sum(r['char_accuracy'] for r in counted) / len(counted)
        avg_confidence    = sum(r['confidence'] for r in counted) / len(counted)
        fm_exact_matches     = sum(1 for r in counted if r['fm_exact'])     if corrector else None
        fm_avg_char_accuracy = sum(r['fm_char_accuracy'] for r in counted) / len(counted) if corrector else None
        fm_gated_count       = sum(1 for r in counted if r.get('fm_gated')) if corrector else 0
    else:
        exact_matches = fm_exact_matches = 0
        avg_char_accuracy = fm_avg_char_accuracy = 0.0
        avg_confidence = 0.0
        fm_gated_count = 0

    summary = {
        'image':             basename,
        'gt_lines':          len(gt_lines),
        'detected_lines':    len(ocr_lines),
        'exact_matches':     exact_matches,
        'total_compared':    len(counted),
        'skipped_count':     skipped_count,
        'exact_match_rate':  exact_matches / len(counted) if counted else 0,
        'avg_char_accuracy': avg_char_accuracy,
        'avg_confidence':    avg_confidence,
        'sections_detected': len(sections),
        'fm_exact_matches':     fm_exact_matches,
        'fm_avg_char_accuracy': fm_avg_char_accuracy,
        'results':           results,
    }

    if verbose:
        skip_note = f', skipped={skipped_count}' if skipped_count else ''
        fm_part = ''
        if corrector is not None:
            recovered = fm_exact_matches - exact_matches
            gate_note = f', gated={fm_gated_count}' if fm_conf_threshold is not None else ''
            fm_part = (f", FM: {fm_exact_matches}/{len(counted)} exact "
                       f"(+{recovered} recovered, char_acc={fm_avg_char_accuracy:.1%}{gate_note})")
        print(f"\n  Summary: {exact_matches}/{len(counted)} exact matches "
              f"({summary['exact_match_rate']:.1%}){skip_note}, "
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
    argp.add_argument('--fm-threshold', type=float, default=None, metavar='CONF',
                       help='Confidence gate: apply FM only when OCR conf < CONF (e.g. 0.85). '
                            'Only effective with --include-fuzzy.')
    argp.add_argument('--use-gt-sections', '-g', action='store_true',
                       help='Use GT text for section detection (perfect categorization). '
                            'Isolates FM dictionary quality from OCR recognition errors.')
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
                   normalize=args.normalize, corrector=corrector,
                   fm_conf_threshold=args.fm_threshold,
                   use_gt_sections=args.use_gt_sections)
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
                                 normalize=args.normalize, corrector=corrector,
                                 fm_conf_threshold=args.fm_threshold,
                                 use_gt_sections=args.use_gt_sections)
            all_summaries.append(summary)

        # Overall summary
        total_exact    = sum(s['exact_matches'] for s in all_summaries)
        total_compared = sum(s['total_compared'] for s in all_summaries)
        total_skipped  = sum(s.get('skipped_count', 0) for s in all_summaries)
        total_char_acc = sum(s['avg_char_accuracy'] * s['total_compared'] for s in all_summaries)
        total_fm_exact    = sum(s['fm_exact_matches'] for s in all_summaries if s['fm_exact_matches'] is not None) if corrector else None
        total_fm_char_acc = sum(s['fm_avg_char_accuracy'] * s['total_compared'] for s in all_summaries if s['fm_avg_char_accuracy'] is not None) if corrector else None

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
            skip_col = f"  skipped={total_skipped}" if total_skipped else ''
            fm_total_col = ''
            if corrector is not None:
                recovered = total_fm_exact - total_exact
                fm_total_col = (f"  FM={total_fm_exact:3d}/{total_compared} "
                                f"(+{recovered} recovered, char_acc={total_fm_char_acc/total_compared:.1%})")
            print(f"  {'TOTAL':40s}  {total_exact:3d}/{total_compared:<3d} exact  "
                  f"char_acc={total_char_acc/total_compared:.1%}{skip_col}{fm_total_col}")
        print()


if __name__ == '__main__':
    main()
