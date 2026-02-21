#!/usr/bin/env python3
"""Generate synthetic training images for the enchant slot header OCR model.

Images match real enchant header crops from the V3 segmentation pipeline:
- Font size 11 → text_h=11, total_h=15 with padding
- Binary (0/255), tight-cropped to ink bounds
- Padding: pad_y = max(1, h//5) = 2, pad_x = max(2, h//3) = 3

Reference characteristics (from tmp/enchant_header_samples/):
  Height: 15px (all), Width: 55-118px median 65
  Ink ratio: 0.258-0.331, mean 0.279

Run from project root:
    python3 scripts/generate_enchant_header_training.py
"""

import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# === Configuration ===
FONT_PATH = "data/fonts/mabinogi_classic.ttf"
DICT_PATH = "data/dictionary/enchant_slot_header.txt"
OUTPUT_DIR = "backend/ocr/enchant_header_train_data"
IMAGES_DIR = os.path.join(OUTPUT_DIR, "images")
LABELS_DIR = os.path.join(OUTPUT_DIR, "labels")

FONT_SIZE = 11
THRESHOLD = 80
VARIATIONS_PER_LABEL = 3

# Quality gates (reference: ink 0.258-0.331, w 55-118, h 15)
MIN_INK_RATIO = 0.10
MIN_WIDTH = 10
MIN_HEIGHT = 8


def render_line(text, font_size):
    """Render a single text line, tight-cropped to ink bounds + padding.

    Matches how the V3 pipeline crops enchant slot headers:
    pad_x = max(2, h//3), pad_y = max(1, h//5).

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

    img = Image.new('L', (img_w, img_h), color=255)
    draw = ImageDraw.Draw(img)
    draw.text((pad_x, pad_y - bbox[1]), text, font=font, fill=0)

    thresh = THRESHOLD + random.randint(-5, 20)
    img = img.point(lambda x: 0 if x < thresh else 255, 'L')

    return img, True


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


if __name__ == "__main__":
    generate_data()
