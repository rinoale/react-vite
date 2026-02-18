#!/usr/bin/env python3
"""
Regenerate ground truth files from the current pipeline output.

For each GT image, runs MabinogiTooltipParser to detect lines,
OCRs each line, and writes a candidate GT file for manual review.

Output format per line:
  [LINE_NUM] OCR_TEXT            ← edit this to correct text
  # conf=0.XXX section=XXXXX    ← metadata comment (ignored by loader)

Usage:
    python3 scripts/regenerate_gt.py                    # All GT images → _gt_candidate.txt
    python3 scripts/regenerate_gt.py --image <path>     # Single image
    python3 scripts/regenerate_gt.py --apply             # Copy verified candidates over .txt files
"""

import os
import sys
import argparse

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'backend'))

from mabinogi_tooltip_parser import MabinogiTooltipParser

MODELS_DIR = os.path.join(PROJECT_ROOT, 'backend', 'models')
SAMPLE_DIR = os.path.join(PROJECT_ROOT, 'data', 'sample_images')
CONFIG_PATH = os.path.join(PROJECT_ROOT, 'configs', 'mabinogi_tooltip.yaml')


def init_reader():
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


def find_gt_images(sample_dir):
    """Find all processable images in sample_dir."""
    images = []
    for f in sorted(os.listdir(sample_dir)):
        if f.endswith('.png') and 'processed' in f and not f.endswith('_original.png'):
            images.append(os.path.join(sample_dir, f))
    return images


def find_section_for_line(sections, line_idx):
    """Find which section a line belongs to based on index matching."""
    # Build a flat index → section_key map from section data
    for section_key, section_data in sections.items():
        if section_data.get('skipped'):
            continue
        if 'parts' in section_data:
            # Color section — mark as color
            return section_key
        if 'lines' in section_data:
            for sline in section_data['lines']:
                bounds = sline.get('bounds', {})
                if bounds.get('y') == line_idx:
                    return section_key
    return '?'


def generate_candidate(reader, parser, image_path):
    """Run pipeline and write candidate GT file."""
    basename = os.path.splitext(os.path.basename(image_path))[0]
    candidate_path = os.path.join(os.path.dirname(image_path), basename + '_gt_candidate.txt')

    result = parser.parse_tooltip(image_path, reader)
    ocr_lines = result['all_lines']
    sections = result['sections']

    # Build line_index → section_key mapping
    # We match by checking which section contains lines with matching bounds
    line_section_map = {}
    for section_key, section_data in sections.items():
        if 'lines' in section_data:
            for sline in section_data['lines']:
                sb = sline.get('bounds', {})
                for i, ol in enumerate(ocr_lines):
                    ob = ol.get('bounds', {})
                    if ob.get('y') == sb.get('y') and ob.get('x') == sb.get('x'):
                        line_section_map[i] = section_key
        elif 'text' in section_data:
            # item_name style — single text field
            for i, ol in enumerate(ocr_lines):
                if ol.get('text') == section_data['text']:
                    line_section_map[i] = section_key
        elif 'parts' in section_data:
            # Color parts — match by section_key name in header patterns
            line_section_map[section_key] = section_key

    # Also detect header lines (they're not in any section's 'lines')
    header_lines = set()
    for i, ol in enumerate(ocr_lines):
        if i not in line_section_map:
            # Check if this line matched a section header
            text = ol.get('text', '')
            matched = parser._match_section_header(text)
            if matched:
                line_section_map[i] = f"{matched} (header)"
                header_lines.add(i)

    # Write candidate file
    with open(candidate_path, 'w', encoding='utf-8') as f:
        old_gt_path = os.path.splitext(image_path)[0] + '.txt'
        old_gt_lines = []
        if os.path.exists(old_gt_path):
            with open(old_gt_path, 'r', encoding='utf-8') as og:
                old_gt_lines = [l for l in og.read().splitlines() if l.strip()]

        f.write(f"# GT candidate for {basename}\n")
        f.write(f"# Lines detected: {len(ocr_lines)}, Old GT lines: {len(old_gt_lines)}\n")
        f.write(f"# Sections: {list(sections.keys())}\n")
        f.write(f"#\n")
        f.write(f"# INSTRUCTIONS:\n")
        f.write(f"#   1. Compare each line against the actual image\n")
        f.write(f"#   2. Fix OCR errors in the text after the line number\n")
        f.write(f"#   3. Delete lines that should be skipped (flavor text, etc.)\n")
        f.write(f"#   4. When done, run: python3 scripts/regenerate_gt.py --apply\n")
        f.write(f"#\n")

        for i, line in enumerate(ocr_lines):
            text = line.get('text', '')
            conf = line.get('confidence', 0.0)
            sub_count = line.get('sub_count', 1)
            section = line_section_map.get(i, '?')

            # Show old GT for reference if available
            old_ref = ''
            if i < len(old_gt_lines):
                old_ref = f'  old_gt="{old_gt_lines[i]}"'

            sub_tag = f' subs={sub_count}' if sub_count > 1 else ''
            f.write(f"{text}\n")
            f.write(f"# [{i+1:3d}] conf={conf:.3f} section={section}{sub_tag}{old_ref}\n")

    print(f"  Written: {candidate_path} ({len(ocr_lines)} lines)")
    return candidate_path


def apply_candidates(sample_dir):
    """Copy verified candidate files over the original .txt GT files.

    Strips comment lines (starting with #) and writes clean GT.
    """
    applied = 0
    for f in sorted(os.listdir(sample_dir)):
        if not f.endswith('_gt_candidate.txt'):
            continue

        candidate_path = os.path.join(sample_dir, f)
        # Derive original GT path: remove _gt_candidate suffix
        base = f.replace('_gt_candidate.txt', '.txt')
        gt_path = os.path.join(sample_dir, base)

        # Read candidate, strip comments
        with open(candidate_path, 'r', encoding='utf-8') as cf:
            lines = cf.read().splitlines()

        clean_lines = [l for l in lines if not l.startswith('#')]
        # Remove trailing empty lines
        while clean_lines and not clean_lines[-1].strip():
            clean_lines.pop()

        with open(gt_path, 'w', encoding='utf-8') as gf:
            gf.write('\n'.join(clean_lines) + '\n')

        print(f"  Applied: {candidate_path} → {gt_path} ({len(clean_lines)} lines)")
        applied += 1

    if applied == 0:
        print("No candidate files found. Run without --apply first.")
    else:
        print(f"\n{applied} GT files updated. You can delete _gt_candidate.txt files now.")


def main():
    argp = argparse.ArgumentParser(description='Regenerate GT files from current pipeline')
    argp.add_argument('--image', help='Single image path (optional)')
    argp.add_argument('--apply', action='store_true',
                      help='Apply verified candidates over .txt GT files')
    args = argp.parse_args()

    if args.apply:
        apply_candidates(SAMPLE_DIR)
        return

    print("Initializing EasyOCR reader...")
    reader = init_reader()
    parser = MabinogiTooltipParser(CONFIG_PATH)

    if args.image:
        generate_candidate(reader, parser, args.image)
    else:
        images = find_gt_images(SAMPLE_DIR)
        if not images:
            print(f"No images found in {SAMPLE_DIR}")
            sys.exit(1)

        print(f"Found {len(images)} images\n")
        for image_path in images:
            generate_candidate(reader, parser, image_path)

    print(f"\nDone. Review the _gt_candidate.txt files, fix OCR errors, then run:")
    print(f"  python3 scripts/regenerate_gt.py --apply")


if __name__ == '__main__':
    main()
