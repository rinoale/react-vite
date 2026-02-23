#!/usr/bin/env python3
"""Generate synthetic training images for the enchant slot header OCR model.

Rendering matches the real V3 inference pipeline:
  Game: white text on dark bg → white mask (bright & balanced RGB) → invert
  Synthetic: white text on dark bg → grayscale → white mask threshold → invert

Reference characteristics (from tmp/ocr_crops/ with white mask preprocessing):
  Height: 15px (all), Width: 55-118px median 75
  Ink ratio: 0.198-0.217, mean 0.209

Run from project root:
    python3 scripts/ocr/enchant_header_model/generate_training_data.py              # uses active version
    python3 scripts/ocr/enchant_header_model/generate_training_data.py --version v2 # explicit version
"""

import argparse
import os
import random
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from scripts.ocr.lib.model_version import resolve_version
from scripts.ocr.lib.render_utils import render_enchant_header

# === Configuration ===
_parser = argparse.ArgumentParser(add_help=False)
_parser.add_argument('--version', default=None)
_args, _ = _parser.parse_known_args()
_VERSION = resolve_version('enchant_header', _args.version)
print(f"Version: {_VERSION}")

FONT_PATH = "data/fonts/NanumGothicBold.ttf"
DICT_PATH = "data/dictionary/enchant_slot_header.txt"
OUTPUT_DIR = f"backend/ocr/enchant_header_model/{_VERSION}/enchant_header_train_data"
IMAGES_DIR = os.path.join(OUTPUT_DIR, "images")
LABELS_DIR = os.path.join(OUTPUT_DIR, "labels")

FONT_SIZE = 11
VARIATIONS_PER_LABEL = 3

# White mask threshold for training data rendering.
# Real pipeline uses max_ch > 150, but PIL's anti-aliasing spread differs.
# Threshold=132 on NanumGothicBold matches real crop ink ratio (~0.209).
WHITE_MASK_THRESHOLD = 132

# Dark background brightness range (game tooltip backgrounds)
BG_BRIGHTNESS_RANGE = (20, 45)
# Text brightness range (game white text)
TEXT_BRIGHTNESS_RANGE = (220, 255)

# Quality gates (reference: ink 0.198-0.217, w 55-118, h 15)
MIN_INK_RATIO = 0.10
MIN_WIDTH = 10
MIN_HEIGHT = 8


def render_line(text, font_size):
    """Render white text on dark bg, apply white mask, invert.

    Mimics the real inference pipeline:
    1. Bright text on dark background (like the game)
    2. White mask: pixels > 150 → white, else black
    3. Invert: black text on white background

    Returns (PIL Image in mode 'L', bool success).
    """
    try:
        font = ImageFont.truetype(FONT_PATH, font_size)
    except Exception:
        return None, False

    bbox = font.getbbox(text)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    if text_w <= 0 or text_h <= 0:
        return None, False

    pad_y = max(1, text_h // 5)
    pad_x = max(2, text_h // 3)
    img_h = text_h + 2 * pad_y
    img_w = text_w + 2 * pad_x

    # Step 1: Render bright text on dark background
    bg = random.randint(*BG_BRIGHTNESS_RANGE)
    fg = random.randint(*TEXT_BRIGHTNESS_RANGE)
    img = Image.new('L', (img_w, img_h), color=bg)
    draw = ImageDraw.Draw(img)
    draw.text((pad_x, pad_y - bbox[1]), text, font=font, fill=fg)

    # Step 2: White mask — pixel > 150 → 255, else 0
    arr = np.array(img)
    white_on_black = np.where(arr > WHITE_MASK_THRESHOLD, 255, 0).astype(np.uint8)

    # Step 3: Invert — black text on white background
    black_on_white = 255 - white_on_black

    return Image.fromarray(black_on_white, mode='L'), True


def load_labels():
    """Load enchant slot header labels from dictionary file."""
    with open(DICT_PATH, 'r', encoding='utf-8') as f:
        labels = [line.strip() for line in f if line.strip()]
    return labels


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
            img, ok = render_line(label, FONT_SIZE)
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

    print(f"Generated {count} images ({skipped} skipped)")
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
