import os
import random
import glob
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np
import cv2

# Configuration - Assumes running from project root
FONT_PATH = "data/fonts/mabinogi_classic.ttf"
DICT_PATHS = [
    "data/dictionary/reforging_options.txt",
    "data/dictionary/tooltip_general.txt",
]
OUTPUT_DIR = "backend/train_data"
IMAGES_DIR = os.path.join(OUTPUT_DIR, "images")
LABELS_DIR = os.path.join(OUTPUT_DIR, "labels")

# Image Settings
IMAGE_HEIGHT = 32  # Standard height for OCR lines
FONT_SIZE = 18    # Approximate size of game text
MIN_PADDING = 5
MAX_PADDING = 15

# Colors (R, G, B) - Black text on white background for OCR
TEXT_COLORS = [
    (0, 0, 0),       # Black
    (20, 20, 20),    # Near Black
    (40, 40, 40),    # Dark Grey
    (10, 10, 10),    # Very Dark Grey
]

BG_COLORS = [
    (255, 255, 255), # White
    (245, 245, 245), # Off-White
    (240, 240, 240), # Light Grey
]

def ensure_dirs():
    os.makedirs(IMAGES_DIR, exist_ok=True)
    os.makedirs(LABELS_DIR, exist_ok=True)

def generate_data(num_samples=1000):
    ensure_dirs()
    
    # 1. Load Dictionaries
    words = []
    for dict_path in DICT_PATHS:
        if not os.path.exists(dict_path):
            print(f"Warning: Dictionary not found at {dict_path}, skipping.")
            continue
        with open(dict_path, 'r', encoding='utf-8') as f:
            entries = [line.strip() for line in f if line.strip()]
        print(f"Loaded {len(entries)} entries from {dict_path}")
        words.extend(entries)

    if not words:
        print("Error: No dictionary entries loaded.")
        return

    print(f"Total: {len(words)} dictionary entries.")
    
    # 2. Load Font
    try:
        font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    except Exception as e:
        print(f"Error loading font: {e}")
        # Fallback to default if custom font fails
        font = ImageFont.load_default()

    count = 0
    # Create multiple variations for each word
    for word in words:
        # Generate 2 variations per word
        for i in range(2): 
            # 1. Create canvas
            text_color = random.choice(TEXT_COLORS)
            bg_color = random.choice(BG_COLORS)
            
            # Measure text size
            # getbbox returns (left, top, right, bottom)
            bbox = font.getbbox(word)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            # Calculate image size with padding
            pad_left = random.randint(MIN_PADDING, MAX_PADDING)
            pad_top = random.randint(MIN_PADDING, MAX_PADDING)
            pad_right = random.randint(MIN_PADDING, MAX_PADDING)
            pad_bottom = random.randint(MIN_PADDING, MAX_PADDING)
            
            img_w = text_width + pad_left + pad_right
            img_h = max(IMAGE_HEIGHT, text_height + pad_top + pad_bottom)
            
            img = Image.new('RGB', (img_w, img_h), color=bg_color)
            draw = ImageDraw.Draw(img)
            
            # Draw text centered vertically
            draw.text((pad_left, (img_h - text_height) // 2 - bbox[1]), word, font=font, fill=text_color)
            
            # 2. Augmentations
            # Slight Blur
            if random.random() > 0.5:
                img = img.filter(ImageFilter.GaussianBlur(radius=0.5))
            
            # Noise (using numpy)
            if random.random() > 0.5:
                np_img = np.array(img)
                noise = np.random.randint(0, 20, np_img.shape, dtype='uint8')
                np_img = cv2.add(np_img, noise)
                img = Image.fromarray(np_img)

            # 3. Save
            filename = f"syn_{count:06d}"
            image_path = os.path.join(IMAGES_DIR, f"{filename}.png")
            label_path = os.path.join(LABELS_DIR, f"{filename}.txt")
            
            img.save(image_path)
            
            with open(label_path, 'w', encoding='utf-8') as lf:
                lf.write(word)
                
            count += 1
            if count % 500 == 0:
                print(f"Generated {count} images...")
                
    print(f"\nDone! Generated {count} synthetic training images in {OUTPUT_DIR}")

if __name__ == "__main__":
    generate_data()
