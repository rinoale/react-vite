#!/usr/bin/env python3
"""
Test the v3 OCR pipeline: segment-first (header detection → section label → content OCR)

Runs the same logic as the /upload-item-v3 endpoint:
  1. detect_headers() → segment_and_tag() using header OCR model
  2. parse_from_segments() → content OCR per segment (3 models)
  3. FM applied exactly as business logic does (mutates line['text'])
  4. Compare final text against GT if available

Usage:
    python3 scripts/v3/test_v3_pipeline.py data/sample_images/titan_blade_original.png
    python3 scripts/v3/test_v3_pipeline.py 'data/sample_images/*_original.png'
    python3 scripts/v3/test_v3_pipeline.py 'data/sample_images/*_original.png' -q
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

from lib.v3_pipeline import init_pipeline, run_v3_pipeline


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


_LINE_PREFIX_RE = re.compile(r'^[-ㄴ]\s*')


def test_image(pipeline, image_path, gt_path=None, verbose=True):
    """Run v3 pipeline on a single image and optionally compare against GT."""
    basename = os.path.basename(image_path)

    img_bgr = cv2.imread(image_path)
    if img_bgr is None:
        print(f"  ERROR: cannot read {image_path}")
        return None

    result = run_v3_pipeline(img_bgr, **pipeline, save_raw=True)
    ocr_lines = result['all_lines']
    sections  = result['sections']
    tagged    = result['tagged_segments']

    gt_lines_raw = load_ground_truth(gt_path) if gt_path else None
    # Strip structural prefixes from GT too (- or ㄴ) — output no longer has them
    if gt_lines_raw is not None:
        gt_lines = []
        for g in gt_lines_raw:
            m = _LINE_PREFIX_RE.match(g)
            gt_lines.append(g[m.end():] if m else g)
    else:
        gt_lines = None
    has_gt = gt_lines is not None
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

    for i in range(compare_count):
        line     = ocr_lines[i]
        text     = line.get('text', '')         # final text (after FM)
        raw_text = line.get('raw_text', text)   # raw OCR (before FM)
        section  = line.get('section', '')
        skipped  = line.get('is_grey', False)
        fm_applied = line.get('fm_applied', False)

        if has_gt:
            gt_text = gt_lines[i]
            if skipped:
                char_accuracy = None
                exact_match   = None
            else:
                matcher       = difflib.SequenceMatcher(None, gt_text.strip(), text.strip())
                char_accuracy = matcher.ratio()
                exact_match   = (text.strip() == gt_text.strip())
        else:
            gt_text = char_accuracy = exact_match = None

        results.append({
            'line_num':      i + 1,
            'gt':            gt_text,
            'text':          text,
            'raw_text':      raw_text,
            'confidence':    line.get('confidence', 0.0),
            'char_accuracy': char_accuracy,
            'exact_match':   exact_match,
            'section':       section,
            'skipped':       skipped,
            'fm_applied':    fm_applied,
        })

        if verbose:
            is_header_line = line.get('is_header', False)
            is_grey = line.get('is_grey', False)

            if is_header_line:
                label = section if section else '(undetected)'
                print(f"\n  {'─'*12} header '{label}' detected {'─'*12}")
            elif section != prev_section:
                label = section if section else '(undetected)'
                print(f"\n  {'─'*22} {label} {'─'*22}")

            if not is_header_line:
                prev_section = section

            # Grey lines: skip
            if is_grey:
                print(f"  [--] Line {i+1:2d}  <grey/skipped>")
                if has_gt:
                    print(f"       GT:  {gt_text}")
                continue

            # Model tag
            ocr_model = line.get('ocr_model', '')
            model_tag = f' [{ocr_model}]' if ocr_model and ocr_model != 'general' else ''

            sub_tag = f' [{line.get("sub_count", 1)} segs]' if line.get('sub_count', 1) > 1 else ''

            if has_gt:
                status = 'OK' if exact_match else 'XX'

                print(f"  [{status}] Line {i+1:2d} (conf={line.get('confidence', 0):.3f}, "
                      f"acc={char_accuracy:.1%}){sub_tag}{model_tag}")
                print(f"       GT:  {gt_text}")
                if fm_applied:
                    print(f"       OCR: {raw_text}")
                    print(f"       FM:  {text}")
                else:
                    print(f"       OCR: {text}")
            else:
                if fm_applied:
                    print(f"  Line {i+1:2d} (conf={line.get('confidence', 0):.3f})"
                          f"{sub_tag}{model_tag}")
                    print(f"       OCR: {raw_text}")
                    print(f"       FM:  {text}")
                else:
                    print(f"  Line {i+1:2d} (conf={line.get('confidence', 0):.3f})"
                          f"{sub_tag}{model_tag}  {text}")

    if has_gt and len(ocr_lines) > len(gt_lines) and verbose:
        print(f"\n  ({len(ocr_lines) - len(gt_lines)} extra OCR lines beyond GT — not scored)")

    # Summary metrics — exclude skipped (grey) lines
    counted = [r for r in results if not r.get('skipped')]
    n_skipped = len(results) - len(counted)
    n_fm = sum(1 for r in counted if r['fm_applied'])

    if has_gt and counted:
        exact_matches     = sum(1 for r in counted if r['exact_match'])
        avg_char_accuracy = sum(r['char_accuracy'] for r in counted) / len(counted)
        avg_confidence    = sum(r['confidence']    for r in counted) / len(counted)
    else:
        exact_matches = avg_char_accuracy = None
        avg_confidence = sum(r['confidence'] for r in results) / len(results) if results else 0.0

    summary = {
        'image':             basename,
        'gt_lines':          len(gt_lines) if has_gt else None,
        'detected_lines':    len(ocr_lines),
        'segments':          len(tagged),
        'headers_found':     sum(1 for s in tagged if s['header_crop'] is not None),
        'sections_detected': len(sections),
        'total_compared':    len(counted),
        'exact_matches':     exact_matches,
        'avg_char_accuracy': avg_char_accuracy,
        'avg_confidence':    avg_confidence,
        'fm_applied':        n_fm,
    }

    if verbose:
        if has_gt and counted:
            rate = exact_matches / len(counted) if counted else 0
            skip_part = f", {n_skipped} skipped" if n_skipped else ""
            fm_part   = f", FM applied: {n_fm}" if n_fm else ""
            print(f"\n  Summary: {exact_matches}/{len(counted)} exact matches "
                  f"({rate:.1%}), "
                  f"avg char accuracy: {avg_char_accuracy:.1%}, "
                  f"avg confidence: {avg_confidence:.3f}, "
                  f"sections: {len(sections)}{skip_part}{fm_part}")
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
    argp.add_argument('path', help='Image file, folder, or glob pattern')
    argp.add_argument('--gt-dir', default=None,
                      help='Directory to search for GT files (default: same dir as images)')
    argp.add_argument('--gt-suffix', default='.txt',
                      help='GT file suffix (default: .txt)')
    argp.add_argument('--quiet', '-q', action='store_true', help='Summary only')
    args = argp.parse_args()

    pipeline = init_pipeline()
    print(f"Loaded {len(pipeline['section_patterns'])} section patterns")

    images = collect_images(args.path)
    if not images:
        print(f"No .png images found in: {args.path}")
        sys.exit(1)

    print(f"\nProcessing {len(images)} image(s)...\n")

    all_summaries = []
    for image_path in images:
        gt_path = find_gt_file(image_path, args.gt_dir, args.gt_suffix)
        summary = test_image(
            pipeline, image_path, gt_path=gt_path,
            verbose=not args.quiet,
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
            fm_col = f"  FM={s['fm_applied']}" if s['fm_applied'] else ""
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
        total_fm       = sum(s['fm_applied']       for s in gt_sums)
        fm_col = f"  FM={total_fm}" if total_fm else ""
        print(f"  {'─'*66}")
        if total_compared > 0:
            print(f"  {'TOTAL':40s}  {total_exact:3d}/{total_compared:<3d} exact  "
                  f"char_acc={total_char_acc/total_compared:.1%}{fm_col}")
    print()


if __name__ == '__main__':
    main()
