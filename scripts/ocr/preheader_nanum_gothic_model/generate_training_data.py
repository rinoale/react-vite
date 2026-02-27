#!/usr/bin/env python3
"""
Generate synthetic training images for the pre-header NanumGothicBold font OCR model.

Specialized for pre_header region content only:
  - Item names with optional enchant prefix/suffix and holywater prefix
    e.g. "축복받은 창백한 소울 리버레이트 원드 단검"

Uses zero-noise rendering (fixed threshold, no randomization) at font 11-13.

Run from project root:
    python3 scripts/ocr/preheader_nanum_gothic_model/generate_training_data.py
    python3 scripts/ocr/preheader_nanum_gothic_model/generate_training_data.py --version v1
"""

import argparse
import os
import random
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from scripts.ocr.lib.model_version import resolve_version, load_training_config
from scripts.ocr.lib.render_utils import (
    render_line_clean, split_all_labels,
    MIN_INK_RATIO, MIN_WIDTH, MIN_HEIGHT,
)

MODEL_TYPE = 'preheader_nanum_gothic'

# === Configuration ===
_parser = argparse.ArgumentParser(add_help=False)
_parser.add_argument('--version', default=None)
_args, _ = _parser.parse_known_args()
_VERSION = resolve_version(MODEL_TYPE, _args.version)
_config = load_training_config(MODEL_TYPE, _VERSION)
print(f"Version: {_VERSION}")

FONT_PATH = _config['font']['path']
OUTPUT_DIR = f"backend/ocr/preheader_nanum_gothic_model/{_VERSION}/train_data"
IMAGES_DIR = os.path.join(OUTPUT_DIR, "images")
LABELS_DIR = os.path.join(OUTPUT_DIR, "labels")

FONT_SIZES = [11, 11, 12, 12, 13, 13]
CANVAS_WIDTH = 400
VARIATIONS_PER_LABEL = 3

# Dictionary paths for pre_header content
ITEM_NAME_PATH = "data/dictionary/item_name.txt"
SPECIAL_ITEM_NAME_PATH = "data/dictionary/special_weight_item_name.txt"
ENCHANT_PREFIX_PATH = "data/dictionary/enchant_prefix.txt"
ENCHANT_SUFFIX_PATH = "data/dictionary/enchant_suffix.txt"

# Holywater prefixes (applied before enchant prefix in item name line)
HOLYWATER_PREFIXES = ['각인된', '축복받은']


def load_dict_file(path):
    """Load a dictionary file, returning list of non-empty lines."""
    if not os.path.exists(path):
        print(f"Warning: Dictionary not found at {path}, skipping.")
        return []
    with open(path, 'r', encoding='utf-8') as f:
        entries = [line.strip() for line in f if line.strip()]
    print(f"  Loaded {len(entries):5d} entries from {os.path.basename(path)}")
    return entries


def generate_item_name_lines(item_names, prefixes, suffixes):
    """Generate item name lines with random enchant prefix/suffix and holywater prefix.

    Format: [holywater] [prefix] [suffix] item_name
    Each component is independently random (present or absent).
    """
    lines = []
    for item_name in item_names:
        parts = []

        # Holywater prefix: 각인된 40%, 축복받은 20%, nothing 40%
        r = random.random()
        if r < 0.4:
            parts.append('각인된')
        elif r < 0.6:
            parts.append('축복받은')

        # Enchant prefix: random or nothing
        if prefixes and random.random() < 0.5:
            parts.append(random.choice(prefixes))

        # Enchant suffix: random or nothing
        if suffixes and random.random() < 0.5:
            parts.append(random.choice(suffixes))

        parts.append(item_name)

        lines.append(' '.join(parts))
    return lines


def generate_data():
    os.makedirs(IMAGES_DIR, exist_ok=True)
    os.makedirs(LABELS_DIR, exist_ok=True)

    # Load dictionaries
    print("Loading dictionaries...")
    item_names = load_dict_file(ITEM_NAME_PATH)
    special_item_names = load_dict_file(SPECIAL_ITEM_NAME_PATH)
    prefixes = load_dict_file(ENCHANT_PREFIX_PATH)
    suffixes = load_dict_file(ENCHANT_SUFFIX_PATH)

    # Generate composite item name lines (with random prefix/suffix/holywater)
    print("Generating item name lines...")
    name_lines = generate_item_name_lines(item_names, prefixes, suffixes)
    special_name_lines = generate_item_name_lines(special_item_names, prefixes, suffixes)
    print(f"  Item name lines: {len(name_lines)}")
    print(f"  Special item name lines: {len(special_name_lines)}")

    all_labels = []
    all_labels.extend(name_lines)
    # Boost special item names ~10x
    for _ in range(10):
        all_labels.extend(generate_item_name_lines(special_item_names, prefixes, suffixes))

    # Also include bare enchant names (prefix/suffix appear solo in some lines)
    all_labels.extend(prefixes)
    all_labels.extend(suffixes)

    # Deduplicate
    all_labels = list(set(all_labels))

    # Split long labels at word boundaries
    max_font = max(FONT_SIZES)
    max_text_width = CANVAS_WIDTH - 2 * max(2, 11 // 3)
    all_labels = split_all_labels(all_labels, FONT_PATH, max_font, max_text_width)
    all_labels = list(set(all_labels))
    print(f"Unique labels (after split+dedup): {len(all_labels)}")

    random.shuffle(all_labels)
    print(f"Total labels: {len(all_labels)}")

    # Auto-generate unique_chars.txt from all labels
    all_chars = set()
    for label in all_labels:
        all_chars.update(label)
    chars_sorted = sorted(all_chars)
    chars_path = os.path.join(
        f"backend/ocr/preheader_nanum_gothic_model/{_VERSION}",
        "unique_chars.txt"
    )
    with open(chars_path, 'w', encoding='utf-8') as f:
        f.write(''.join(chars_sorted))
    print(f"Generated {chars_path}: {len(chars_sorted)} unique chars")

    count = 0
    skipped = 0

    for label in all_labels:
        for v in range(VARIATIONS_PER_LABEL):
            font_size = random.choice(FONT_SIZES)
            cw = CANVAS_WIDTH + random.randint(-10, 10)

            img, ok = render_line_clean(label, FONT_PATH, font_size, cw)
            if not ok:
                skipped += 1
                continue

            # Convert to RGB (EasyOCR expects 3 channels)
            img_rgb = img.convert('RGB')

            filename = f"syn_{count:06d}"
            img_rgb.save(os.path.join(IMAGES_DIR, f"{filename}.png"))
            with open(os.path.join(LABELS_DIR, f"{filename}.txt"), 'w', encoding='utf-8') as f:
                f.write(label)

            count += 1
            if count % 5000 == 0:
                print(f"  Generated {count} images...")

    print(f"\nDone! Generated {count} images ({skipped} skipped)")
    print(f"Output: {OUTPUT_DIR}")

    # Full verification
    print("\nVerifying ALL images...")
    all_files = [f for f in os.listdir(IMAGES_DIR) if f.endswith('.png')]
    failures = {'non_binary': 0, 'low_ink': 0, 'too_small': 0}
    for f in all_files:
        img = Image.open(os.path.join(IMAGES_DIR, f))
        arr = np.array(img)
        if len(arr.shape) == 3:
            arr = arr[:, :, 0]

        unique = set(np.unique(arr))
        if unique - {0, 255}:
            failures['non_binary'] += 1

        ink_ratio = (arr == 0).sum() / arr.size if arr.size > 0 else 0
        if ink_ratio < MIN_INK_RATIO:
            failures['low_ink'] += 1

        w, h = img.size
        if w < MIN_WIDTH or h < MIN_HEIGHT:
            failures['too_small'] += 1

    total_failures = sum(failures.values())
    if total_failures == 0:
        print(f"  ALL {len(all_files)} images PASSED (binary, ink>{MIN_INK_RATIO:.0%}, w>={MIN_WIDTH}, h>={MIN_HEIGHT})")
    else:
        print(f"  FAILURES in {len(all_files)} images: {failures}")


if __name__ == "__main__":
    generate_data()
