#!/usr/bin/env python3
"""Segment tooltip images into header+content sections using orange-anchored detection.

Uses segment_and_tag() for full pipeline: header detection → header OCR → section labeling.
Saves per-segment crops (named by section label) and a visualization overlay.

Supports single image or glob pattern for batch processing.

Usage:
    # Single image
    python3 scripts/v3/segmentation/test_segmentation.py data/sample_images/titan_blade_original.png tmp/seg_out/

    # Batch (glob pattern — quote to prevent shell expansion)
    python3 scripts/v3/segmentation/test_segmentation.py 'data/themes/*.png' tmp/segmented/

    # Without header OCR (faster, no model loading — segment geometry only)
    python3 scripts/v3/segmentation/test_segmentation.py --no-ocr 'data/themes/*.png' tmp/segmented/
"""

import argparse
import glob
import os
import sys

import cv2

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'backend'))

CONFIG_PATH = os.path.join(PROJECT_ROOT, 'configs', 'mabinogi_tooltip.yaml')
MODELS_DIR = os.path.join(PROJECT_ROOT, 'backend', 'ocr', 'models')


def segment_one(img_path, output_dir, header_reader, patterns, config, use_ocr=True):
    """Segment a single image and save crops."""
    img = cv2.imread(img_path)
    if img is None:
        print(f"  SKIP: could not read {img_path}")
        return

    base = os.path.splitext(os.path.basename(img_path))[0]

    if use_ocr:
        from lib.tooltip_segmenter import segment_and_tag
        tagged = segment_and_tag(img, header_reader, patterns, config)
    else:
        from lib.tooltip_segmenter import detect_headers, build_segments
        headers = detect_headers(img, config)
        segments = build_segments(img, headers)
        # Build minimal tagged list without OCR
        tagged = []
        for seg in segments:
            idx = seg['index']
            cnt = seg['content']
            content_crop = img[cnt['y']:cnt['y'] + cnt['h'], :]
            hdr = seg['header']
            header_crop = None
            if hdr:
                header_crop = img[hdr['y']:hdr['y'] + hdr['h'],
                                  hdr['x']:hdr['x'] + hdr['w']]
            tagged.append({
                'index': idx,
                'section': 'pre_header' if hdr is None else None,
                'header_crop': header_crop,
                'content_crop': content_crop,
                'header_ocr_text': '',
                'header_ocr_conf': 0.0,
            })

    os.makedirs(output_dir, exist_ok=True)

    # Save full image for reference
    cv2.imwrite(os.path.join(output_dir, '00_full.png'), img)

    vis = img.copy()
    w_img = img.shape[1]
    colors = [
        (0, 200, 0), (255, 200, 0), (200, 0, 255), (0, 255, 255),
        (255, 100, 100), (100, 255, 100), (100, 100, 255), (200, 200, 0),
    ]

    for seg in tagged:
        idx = seg['index']
        section = seg['section'] or f'seg{idx}'
        color = colors[idx % len(colors)]

        if seg['header_crop'] is not None:
            cv2.imwrite(os.path.join(output_dir, f'{idx:02d}_header_{section}.png'),
                        seg['header_crop'])
            h, w = seg['header_crop'].shape[:2]
            # Draw header box on visualization
            # (approximate position from crop size — exact coords not stored in tagged)

        if seg['content_crop'] is not None and seg['content_crop'].shape[0] > 0:
            cv2.imwrite(os.path.join(output_dir, f'{idx:02d}_content_{section}.png'),
                        seg['content_crop'])

    cv2.imwrite(os.path.join(output_dir, '00_vis.png'), vis)

    n_headers = sum(1 for s in tagged if s['header_crop'] is not None)
    sections = [s['section'] or '?' for s in tagged]
    print(f"  {base}: {len(tagged)} segments, {n_headers} headers  [{', '.join(sections)}]")


def main():
    parser = argparse.ArgumentParser(
        description='Segment tooltip images into header+content sections')
    parser.add_argument('image', help='Image path or glob pattern (quote globs)')
    parser.add_argument('output', help='Output directory')
    parser.add_argument('--no-ocr', action='store_true',
                        help='Skip header OCR (faster, no section labels)')
    args = parser.parse_args()

    # Expand glob
    images = sorted(glob.glob(args.image))
    if not images:
        print(f"No images found matching: {args.image}")
        sys.exit(1)

    # Load models (once)
    header_reader = patterns = None
    from lib.tooltip_segmenter import load_config
    config = load_config(CONFIG_PATH)

    if not args.no_ocr:
        from lib.tooltip_segmenter import init_header_reader, load_section_patterns
        header_reader = init_header_reader(models_dir=MODELS_DIR)
        patterns = load_section_patterns(CONFIG_PATH)

    print(f"Processing {len(images)} image(s) → {args.output}/\n")

    batch = len(images) > 1
    for img_path in images:
        name = os.path.splitext(os.path.basename(img_path))[0]
        out_dir = os.path.join(args.output, name) if batch else args.output
        segment_one(img_path, out_dir, header_reader, patterns, config,
                    use_ocr=not args.no_ocr)

    print(f"\nDone. Output: {args.output}")


if __name__ == '__main__':
    main()
