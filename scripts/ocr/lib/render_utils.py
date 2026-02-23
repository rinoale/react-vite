"""Game-like rendering pipeline for synthetic OCR training images.

Closes two domain gaps between synthetic training data and real inference crops:
1. **Ink ratio**: bright-on-dark rendering + threshold produces thicker strokes (~0.20)
   matching real crops (was 0.144 with direct white-bg rendering)
2. **Height**: Renders at font 16-18, downscales to ~14-15px matching real splitter output

Pipeline:
  1. Dark background (20,20,20) + bright text (220,220,220) at font 16-18
  2. BT.601 grayscale: Y = 0.299R + 0.587G + 0.114B
  3. Threshold with BINARY_INV (bright text → black ink)
  4. Tight-crop to ink bounds + splitter padding
  5. Downscale to target height via cv2.INTER_AREA
  6. Re-threshold to strict binary (0/255)
  7. Quality gates
"""

import random

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Quality gates (same as existing pipeline)
MIN_INK_RATIO = 0.02
MIN_WIDTH = 10
MIN_HEIGHT = 8

# Target output height range matching real inference crops
TARGET_HEIGHT_MIN = 13
TARGET_HEIGHT_MAX = 16

# Rendering constants
BG_COLOR = (20, 20, 20)
TEXT_COLOR = (220, 220, 220)
FRONTEND_THRESHOLD = 80


def render_line_gamelike(text, font_path, font_size, canvas_width=400):
    """Render a text line using game-like bright-on-dark pipeline.

    Returns:
        (PIL Image mode 'L', bool success)
        Image is binary (0/255), height ~14-15px, tight-cropped with padding.
    """
    try:
        font = ImageFont.truetype(font_path, font_size)
    except Exception:
        return None, False

    bbox = font.getbbox(text)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    if text_w <= 0 or text_h <= 0:
        return None, False

    # Step 1: Render bright text on dark background (RGB)
    # Use generous canvas to avoid clipping
    pad_render = max(4, text_h // 2)
    img_w = text_w + 2 * pad_render
    img_h = text_h + 2 * pad_render

    img = Image.new('RGB', (img_w, img_h), color=BG_COLOR)
    draw = ImageDraw.Draw(img)
    draw.text((pad_render - bbox[0], pad_render - bbox[1]), text, font=font, fill=TEXT_COLOR)

    # Step 2: BT.601 grayscale
    arr = np.array(img, dtype=np.float32)
    gray = (0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]).astype(np.uint8)

    # Step 3: Threshold with BINARY_INV (bright text → black ink on white bg)
    thresh = FRONTEND_THRESHOLD + random.randint(-10, 40)
    _, binary = cv2.threshold(gray, thresh, 255, cv2.THRESH_BINARY_INV)

    # Step 4: Tight-crop to ink bounds
    ink_rows = np.where(binary.min(axis=1) < 255)[0]
    ink_cols = np.where(binary.min(axis=0) < 255)[0]

    if len(ink_rows) == 0 or len(ink_cols) == 0:
        return None, False

    y0, y1 = ink_rows[0], ink_rows[-1]
    x0, x1 = ink_cols[0], ink_cols[-1]
    cropped = binary[y0:y1 + 1, x0:x1 + 1]

    crop_h, crop_w = cropped.shape

    # Splitter-matching padding
    pad_y = max(1, crop_h // 5)
    pad_x = max(2, crop_h // 3)

    padded = np.full((crop_h + 2 * pad_y, crop_w + 2 * pad_x), 255, dtype=np.uint8)
    padded[pad_y:pad_y + crop_h, pad_x:pad_x + crop_w] = cropped

    # Step 5: Downscale to target height (~14-15px)
    h_padded = padded.shape[0]
    target_h = random.randint(TARGET_HEIGHT_MIN, TARGET_HEIGHT_MAX)

    if h_padded > target_h:
        scale = target_h / h_padded
        new_w = max(1, int(padded.shape[1] * scale))
        resized = cv2.resize(padded, (new_w, target_h), interpolation=cv2.INTER_AREA)
    else:
        resized = padded

    # Step 6: Re-threshold to strict binary (resize introduces gray values)
    _, final = cv2.threshold(resized, 127, 255, cv2.THRESH_BINARY)

    # Step 7: Quality gates
    h_final, w_final = final.shape
    if w_final < MIN_WIDTH or h_final < MIN_HEIGHT:
        return None, False

    ink_ratio = (final == 0).sum() / final.size if final.size > 0 else 0
    if ink_ratio < MIN_INK_RATIO:
        return None, False

    if len(np.unique(final)) < 2:
        return None, False

    return Image.fromarray(final, mode='L'), True


def split_long_label(text, font, max_width):
    """Split a label at word boundaries if it exceeds max_width pixels.

    Returns a list of sub-labels. If the text fits, returns [text].
    """
    bbox = font.getbbox(text)
    if bbox[2] - bbox[0] <= max_width:
        return [text]

    words = text.split(' ')
    parts = []
    current = words[0]
    for word in words[1:]:
        candidate = current + ' ' + word
        bbox = font.getbbox(candidate)
        if bbox[2] - bbox[0] <= max_width:
            current = candidate
        else:
            parts.append(current)
            current = word
    parts.append(current)
    return parts


def split_all_labels(labels, font_path, max_font_size, max_width):
    """Split all labels that would overflow at the largest font size."""
    font = ImageFont.truetype(font_path, max_font_size)
    result = []
    split_count = 0
    for label in labels:
        parts = split_long_label(label, font, max_width)
        if len(parts) > 1:
            split_count += 1
        result.extend(parts)
    if split_count > 0:
        print(f"  Split {split_count} long labels into {len(result) - len(labels) + split_count} sub-labels")
    return result
