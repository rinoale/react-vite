#!/usr/bin/env python3
"""Generate training images for the enchant slot header OCR model.

Generates synthetic images from dictionary labels, then mixes in real crops
from data/sample_enchant_headers/ (oversampled to target ratio).

Rendering matches the real V3 inference pipeline:
  Game: white text on dark bg → white mask (bright & balanced RGB) → invert
  Synthetic: white text on dark bg → grayscale → white mask threshold → invert

Reference characteristics (from tmp/ocr_crops/ with white mask preprocessing):
  Height: 15px (all), Width: 55-118px median 75
  Ink ratio: 0.198-0.217, mean 0.209

Run from project root:
    python3 scripts/ocr/enchant_header_model/generate_training_data.py              # uses active version
    python3 scripts/ocr/enchant_header_model/generate_training_data.py --version v3 # explicit version
"""

import argparse
import glob
import os
import random
import shutil
import sys

import numpy as np
import yaml
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from scripts.ocr.lib.model_version import resolve_version, version_dir
from scripts.ocr.lib.render_utils import render_enchant_header

# === Configuration ===
_parser = argparse.ArgumentParser(add_help=False)
_parser.add_argument('--version', default=None)
_args, _ = _parser.parse_known_args()
_VERSION = resolve_version('enchant_header', _args.version)
print(f"Version: {_VERSION}")

FONT_PATH = "data/fonts/NanumGothicBold.ttf"
DICT_PATH = "data/train_words/enchant_slot_header.txt"
OUTPUT_DIR = f"backend/ocr/enchant_header_model/{_VERSION}/enchant_header_train_data"
IMAGES_DIR = os.path.join(OUTPUT_DIR, "images")
LABELS_DIR = os.path.join(OUTPUT_DIR, "labels")

# Multiple font sizes for variation (v2: was single FONT_SIZE=11 in v1)
FONT_SIZES = [10, 10, 11, 11, 12, 12]
VARIATIONS_PER_LABEL = 10  # v2: was 3 in v1

# Quality gates (reference: ink 0.198-0.217, w 55-118, h 15)
MIN_INK_RATIO = 0.10
MIN_WIDTH = 10
MIN_HEIGHT = 8


def load_labels():
    """Load enchant slot header labels from dictionary file."""
    with open(DICT_PATH, 'r', encoding='utf-8') as f:
        labels = [line.strip() for line in f if line.strip()]
    return labels


def load_real_samples_config():
    """Load real_samples config from training_config.yaml if present."""
    ver_dir = version_dir('enchant_header', _VERSION)
    config_path = os.path.join(ver_dir, 'training_config.yaml')
    if not os.path.exists(config_path):
        return None
    with open(config_path, 'r') as f:
        cfg = yaml.safe_load(f)
    return cfg.get('real_samples')


def collect_real_samples(real_cfg):
    """Collect real sample image/GT pairs from the configured directory.

    Returns list of (image_path, label) tuples.
    """
    sample_dir = real_cfg['dir']
    if not os.path.isdir(sample_dir):
        print(f"Warning: real samples dir not found: {sample_dir}")
        return []

    pairs = []
    for png_path in sorted(glob.glob(os.path.join(sample_dir, '*.png'))):
        gt_path = png_path.replace('.png', '.txt')
        if not os.path.exists(gt_path):
            continue
        label = open(gt_path, 'r', encoding='utf-8').read().strip()
        if not label:
            continue
        pairs.append((png_path, label))

    return pairs


def mix_real_samples(real_cfg, synthetic_count, counter_start):
    """Copy real samples into training data dir, oversampled to target ratio.

    Args:
        real_cfg: dict with 'dir' and 'oversample_target_ratio'
        synthetic_count: number of synthetic images already generated
        counter_start: starting filename counter

    Returns:
        number of real images added
    """
    pairs = collect_real_samples(real_cfg)
    if not pairs:
        print("No real samples found — skipping mix.")
        return 0

    target_ratio = real_cfg.get('oversample_target_ratio', 0.10)
    # target_ratio = real / (synthetic + real)
    # real = synthetic * target_ratio / (1 - target_ratio)
    target_real = int(synthetic_count * target_ratio / (1 - target_ratio))
    copies_per_sample = max(1, target_real // len(pairs))

    count = 0
    idx = counter_start
    for copy_i in range(copies_per_sample):
        for img_path, label in pairs:
            img = Image.open(img_path)
            # Ensure RGB for consistency with synthetic images
            img_rgb = img.convert('RGB')

            filename = f"enchant_hdr_{idx:05d}"
            img_rgb.save(os.path.join(IMAGES_DIR, f"{filename}.png"))
            with open(os.path.join(LABELS_DIR, f"{filename}.txt"), 'w', encoding='utf-8') as f:
                f.write(label)
            idx += 1
            count += 1

    print(f"Mixed {count} real images ({len(pairs)} unique × {copies_per_sample} copies)")
    print(f"  Target ratio: {target_ratio:.0%}, actual: {count}/{synthetic_count + count} = {count/(synthetic_count + count):.1%}")
    return count


def generate_data():
    os.makedirs(IMAGES_DIR, exist_ok=True)
    os.makedirs(LABELS_DIR, exist_ok=True)

    labels = load_labels()
    print(f"Loaded {len(labels)} labels from {DICT_PATH}")

    random.shuffle(labels)

    count = 0
    skipped = 0

    for label in labels:
        for v in range(VARIATIONS_PER_LABEL):
            font_size = random.choice(FONT_SIZES)
            img, ok = render_enchant_header(label, FONT_PATH, font_size)
            if not ok:
                skipped += 1
                continue

            arr = np.array(img)
            ink_ratio = (arr == 0).sum() / arr.size if arr.size > 0 else 0
            img_w, img_h = img.size

            if len(np.unique(arr)) < 2:
                skipped += 1
                continue
            if ink_ratio < MIN_INK_RATIO:
                skipped += 1
                continue
            if img_w < MIN_WIDTH or img_h < MIN_HEIGHT:
                skipped += 1
                continue

            img_rgb = img.convert('RGB')

            filename = f"enchant_hdr_{count:05d}"
            img_rgb.save(os.path.join(IMAGES_DIR, f"{filename}.png"))
            with open(os.path.join(LABELS_DIR, f"{filename}.txt"), 'w', encoding='utf-8') as f:
                f.write(label)

            count += 1

    synthetic_count = count
    print(f"Generated {synthetic_count} synthetic images ({skipped} skipped)")

    # Mix real samples if configured
    real_cfg = load_real_samples_config()
    real_count = 0
    if real_cfg:
        real_count = mix_real_samples(real_cfg, synthetic_count, counter_start=count)
        count += real_count
    else:
        print("No real_samples config — synthetic only.")

    print(f"\nTotal: {count} images (synthetic={synthetic_count}, real={real_count})")
    print(f"Output: {OUTPUT_DIR}")

    # Verify
    all_files = [f for f in os.listdir(IMAGES_DIR) if f.endswith('.png')]
    heights, widths, inks = [], [], []
    for f in all_files:
        img = Image.open(os.path.join(IMAGES_DIR, f))
        arr = np.array(img)
        if len(arr.shape) == 3:
            arr = arr[:, :, 0]
        w, h = img.size
        heights.append(h)
        widths.append(w)
        inks.append((arr == 0).sum() / arr.size)

    heights = np.array(heights)
    widths = np.array(widths)
    inks = np.array(inks)
    print(f"\nVerification ({len(all_files)} images):")
    print(f"  Height: {heights.min()}-{heights.max()} (unique: {sorted(set(heights))})")
    print(f"  Width:  {widths.min()}-{widths.max()} (median: {int(np.median(widths))})")
    print(f"  Ink:    {inks.min():.3f}-{inks.max():.3f} (mean: {inks.mean():.3f})")
    print(f"  Target: 0.198-0.217, mean 0.209")


if __name__ == "__main__":
    generate_data()
