#!/usr/bin/env python3
"""Measure line heights across all sample/theme images and cluster by distribution.

Runs the V3 line split pipeline on each image, collects all line heights,
clusters them into groups using gaps in the sorted distribution, and reports
statistics per cluster plus per-image extremes.

Usage:
    python3 scripts/v3/line_split/measure_line_heights.py
    python3 scripts/v3/line_split/measure_line_heights.py --dirs data/sample_images
    python3 scripts/v3/line_split/measure_line_heights.py --dirs data/sample_images data/themes
"""

import argparse
import os
import sys
from collections import defaultdict

import cv2
import numpy as np
import yaml

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'backend'))

CONFIG_PATH = os.path.join(PROJECT_ROOT, 'configs', 'mabinogi_tooltip.yaml')
LINE_SPLIT_CONFIG_PATH = os.path.join(PROJECT_ROOT, 'configs', 'line_split.yaml')
MODELS_DIR = os.path.join(PROJECT_ROOT, 'backend', 'ocr', 'models')

from lib.pipeline.segmenter import (
    load_config, load_section_patterns, init_header_reader,
    segment_and_tag,
)
from lib.pipeline.section_handlers._helpers import bt601_binary
from lib.pipeline.line_split import MabinogiTooltipSplitter, group_by_y


def collect_images(dirs):
    """Collect image paths from directories."""
    images = []
    for d in dirs:
        if not os.path.isdir(d):
            print(f"  WARNING: {d} not found, skipping")
            continue
        for f in sorted(os.listdir(d)):
            if f.endswith('_original.png') or (not f.startswith('.') and f.endswith('.png')):
                images.append(os.path.join(d, f))
    return images


def cluster_heights(heights, gap_threshold=2):
    """Cluster sorted heights into groups separated by gaps > gap_threshold."""
    if not heights:
        return []
    sorted_h = sorted(heights)
    clusters = [[sorted_h[0]]]
    for h in sorted_h[1:]:
        if h - clusters[-1][-1] > gap_threshold:
            clusters.append([h])
        else:
            clusters[-1].append(h)
    return clusters


def main():
    parser = argparse.ArgumentParser(description='Measure line heights across images')
    parser.add_argument('--dirs', nargs='+',
                        default=[
                            os.path.join(PROJECT_ROOT, 'data', 'sample_images'),
                            os.path.join(PROJECT_ROOT, 'data', 'themes'),
                        ],
                        help='Directories to scan')
    parser.add_argument('--gap', type=int, default=2,
                        help='Gap threshold for clustering (default: 2)')
    args = parser.parse_args()

    config = load_config(CONFIG_PATH)
    patterns = load_section_patterns(CONFIG_PATH)
    header_reader = init_header_reader(models_dir=MODELS_DIR)

    with open(LINE_SPLIT_CONFIG_PATH, 'r') as f:
        line_split_cfg = yaml.safe_load(f) or {}
    game_split = config.get('horizontal_split_factor')
    if game_split is not None:
        line_split_cfg.setdefault('horizontal', {})['split_factor'] = game_split
    splitter = MabinogiTooltipSplitter(config=line_split_cfg)

    images = collect_images(args.dirs)
    if not images:
        print("No images found.")
        return

    print(f"Scanning {len(images)} images...\n")

    all_heights = []                       # (height, image_name, section, line_idx)
    per_image_heights = defaultdict(list)   # image_name -> [heights]

    for image_path in images:
        img = cv2.imread(image_path)
        if img is None:
            continue
        base = os.path.basename(image_path)

        try:
            tagged = segment_and_tag(img, header_reader, patterns, config)
        except Exception as e:
            print(f"  ERROR: {base}: {e}")
            continue

        for seg in tagged:
            section = seg['section'] or 'unknown'
            content_crop = seg['content_crop']
            if content_crop is None or content_crop.shape[0] == 0:
                continue
            ocr_binary = bt601_binary(content_crop)
            detected = splitter.detect_text_lines(ocr_binary)
            for i, line in enumerate(detected):
                h = line['height']
                all_heights.append((h, base, section, i))
                per_image_heights[base].append(h)

    if not all_heights:
        print("No lines detected.")
        return

    # Cluster
    height_values = [h for h, _, _, _ in all_heights]
    clusters = cluster_heights(height_values, gap_threshold=args.gap)

    print(f"{'='*70}")
    print(f"  TOTAL: {len(all_heights)} lines across {len(per_image_heights)} images")
    print(f"  Height range: {min(height_values)} - {max(height_values)}")
    print(f"  {len(clusters)} cluster(s) (gap threshold={args.gap})")
    print(f"{'='*70}")

    for ci, cluster in enumerate(clusters):
        arr = np.array(cluster)
        print(f"\n  Cluster {ci}: heights {min(cluster)}-{max(cluster)}  "
              f"({len(cluster)} lines, {len(cluster)/len(all_heights)*100:.1f}%)")
        print(f"    mean={arr.mean():.1f}  median={np.median(arr):.0f}  "
              f"std={arr.std():.2f}")

        # Distribution within cluster
        from collections import Counter
        dist = Counter(cluster)
        for h in sorted(dist.keys()):
            bar = '#' * dist[h]
            print(f"    h={h:2d}: {dist[h]:4d} {bar}")

    # Per-image: find images with min/max heights
    print(f"\n{'='*70}")
    print(f"  PER-IMAGE EXTREMES")
    print(f"{'='*70}")

    # Find entries with global min/max height
    min_h = min(height_values)
    max_h = max(height_values)

    min_entries = [(h, img, sec, li) for h, img, sec, li in all_heights if h == min_h]
    max_entries = [(h, img, sec, li) for h, img, sec, li in all_heights if h == max_h]

    print(f"\n  Lowest (h={min_h}): {len(min_entries)} lines")
    for h, img, sec, li in min_entries[:10]:
        print(f"    {img}  [{sec}]  line {li}")
    if len(min_entries) > 10:
        print(f"    ... and {len(min_entries) - 10} more")

    print(f"\n  Highest (h={max_h}): {len(max_entries)} lines")
    for h, img, sec, li in max_entries[:10]:
        print(f"    {img}  [{sec}]  line {li}")
    if len(max_entries) > 10:
        print(f"    ... and {len(max_entries) - 10} more")

    # Per-cluster extremes
    for ci, cluster in enumerate(clusters):
        c_min, c_max = min(cluster), max(cluster)
        c_min_entries = [(h, img, sec, li) for h, img, sec, li in all_heights if h == c_min]
        c_max_entries = [(h, img, sec, li) for h, img, sec, li in all_heights if h == c_max]
        print(f"\n  Cluster {ci} ({c_min}-{c_max}):")
        print(f"    Lowest (h={c_min}):  {c_min_entries[0][1]} [{c_min_entries[0][2]}]")
        print(f"    Highest (h={c_max}): {c_max_entries[0][1]} [{c_max_entries[0][2]}]")


if __name__ == '__main__':
    main()
