#!/usr/bin/env python3
"""
Generate synthetic training images for the NanumGothicBold font OCR model.

Uses game-like rendering pipeline (bright-on-dark → BT.601 → threshold → downscale)
to close the ink ratio and height gaps between synthetic and real inference crops.

Run from project root:
    python3 scripts/ocr/general_nanum_gothic_bold_model/generate_training_data.py
    python3 scripts/ocr/general_nanum_gothic_bold_model/generate_training_data.py --version a19
"""

import argparse
import os
import random
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from scripts.ocr.lib.model_version import resolve_version, load_training_config
from scripts.ocr.lib.training_templates import (
    generate_template_lines, load_dictionaries, HEADER_BOOSTS,
)
from scripts.ocr.lib.render_utils import (
    render_line_gamelike, split_all_labels,
    MIN_INK_RATIO, MIN_WIDTH, MIN_HEIGHT,
)

MODEL_TYPE = 'general_nanum_gothic_bold'

# === Configuration ===
_parser = argparse.ArgumentParser(add_help=False)
_parser.add_argument('--version', default=None)
_args, _ = _parser.parse_known_args()
_VERSION = resolve_version(MODEL_TYPE, _args.version)
_config = load_training_config(MODEL_TYPE, _VERSION)
print(f"Version: {_VERSION}")

BULLET = _config['prefixes']['bullet']
SUBBULLET = _config['prefixes']['subbullet']

FONT_PATH = _config['font']['path']
OUTPUT_DIR = f"backend/ocr/general_nanum_gothic_bold_model/{_VERSION}/train_data"
IMAGES_DIR = os.path.join(OUTPUT_DIR, "images")
LABELS_DIR = os.path.join(OUTPUT_DIR, "labels")

FONT_SIZES = [16, 16, 17, 17, 18, 18]
CANVAS_WIDTH = 400
VARIATIONS_PER_LABEL = 3


def generate_data():
    os.makedirs(IMAGES_DIR, exist_ok=True)
    os.makedirs(LABELS_DIR, exist_ok=True)

    # 1. Template-generated lines
    template_lines = generate_template_lines(bullet=BULLET, subbullet=SUBBULLET)
    print(f"Template lines: {len(template_lines)}")

    # 2. Dictionary entries
    dict_words = load_dictionaries()
    print(f"Dictionary entries: {len(dict_words)}")

    # Combine (deduplicate)
    all_labels = list(set(template_lines + dict_words))

    # Split long labels at word boundaries
    max_font = max(FONT_SIZES)
    max_text_width = CANVAS_WIDTH - 2 * max(2, 11 // 3)
    all_labels = split_all_labels(all_labels, FONT_PATH, max_font, max_text_width)
    all_labels = list(set(all_labels))
    print(f"Unique labels (pre-boost): {len(all_labels)}")

    # Post-dedup boost for critical section headers
    boost_count = 0
    for header, extra in HEADER_BOOSTS:
        all_labels.extend([header] * extra)
        boost_count += extra
    print(f"Post-dedup boost: +{boost_count} header copies → {len(all_labels)} total labels")

    random.shuffle(all_labels)
    print(f"Total labels (with boost): {len(all_labels)}")

    count = 0
    skipped = 0

    for label in all_labels:
        for v in range(VARIATIONS_PER_LABEL):
            font_size = random.choice(FONT_SIZES)
            cw = CANVAS_WIDTH + random.randint(-10, 10)

            img, ok = render_line_gamelike(label, FONT_PATH, font_size, cw)
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
