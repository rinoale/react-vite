import os
import random
import glob
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
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
TARGET_HEIGHT = 32  
MIN_FONT_SIZE = 12
MAX_FONT_SIZE = 26
MIN_PADDING = 0  
MAX_PADDING = 15 

# Colors (R, G, B) - Before thresholding, slight variation helps augmentation
TEXT_COLORS = [(0, 0, 0), (15, 15, 15), (40, 40, 40)]
BG_COLORS = [(255, 255, 255), (250, 250, 250)]

# Frontend threshold value (from sell.jsx preprocessing)
FRONTEND_THRESHOLD = 80

def ensure_dirs():
    os.makedirs(IMAGES_DIR, exist_ok=True)
    os.makedirs(LABELS_DIR, exist_ok=True)

def generate_data():
    ensure_dirs()
    
    # 1. Load Dictionaries
    words = []
    for dict_path in DICT_PATHS:
        if not os.path.exists(dict_path):
            print(f"Warning: Dictionary not found at {dict_path}, skipping.")
            continue
        with open(dict_path, 'r', encoding='utf-8') as f:
            entries = [line.strip() for line in f if line.strip()]
        words.extend(entries)

    print(f"Total entries: {len(words)}")
    
    count = 0
    # Generate more variations to handle domain gap
    variations_per_word = 5

    for word in words:
        for i in range(variations_per_word):
            # A. Randomize parameters
            font_size = random.randint(MIN_FONT_SIZE, MAX_FONT_SIZE)
            text_color = random.choice(TEXT_COLORS)
            bg_color = random.choice(BG_COLORS)
            
            try:
                font = ImageFont.truetype(FONT_PATH, font_size)
            except:
                font = ImageFont.load_default()

            # B. Measure text
            bbox = font.getbbox(word)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            
            # C. Create initial canvas
            pad = 4
            temp_img = Image.new('RGB', (w + pad*2, h + pad*2), color=bg_color)
            draw = ImageDraw.Draw(temp_img)
            draw.text((pad, pad - bbox[1]), word, font=font, fill=text_color)
            
            # --- AUGMENTATION STRATEGY ---
            # Goal: produce BINARY (0/255) images matching frontend-preprocessed screenshots

            # 1. Random Blur (to simulate varying focus/resolution)
            if random.random() > 0.5:
                blur_radius = random.uniform(0.1, 1.0)
                temp_img = temp_img.filter(ImageFilter.GaussianBlur(radius=blur_radius))

            # 2. Convert to Grayscale
            gray = temp_img.convert('L')

            # 3. Binary Thresholding (ALWAYS applied - real images are 100% binary)
            # Use threshold near frontend value (80) with small variation
            thresh = FRONTEND_THRESHOLD + random.randint(-10, 40)
            gray = gray.point(lambda x: 0 if x < thresh else 255, 'L')

            # 4. Dilate/Erode (to simulate font thickness variations)
            if random.random() > 0.7:
                kernel = np.ones((random.randint(1,2), random.randint(1,2)), np.uint8)
                np_img = np.array(gray)
                if random.random() > 0.5:
                    np_img = cv2.erode(np_img, kernel, iterations=1)
                else:
                    np_img = cv2.dilate(np_img, kernel, iterations=1)
                gray = Image.fromarray(np_img)

            # 5. Resize to Target Height (32px)
            aspect_ratio = gray.width / gray.height
            new_h = TARGET_HEIGHT
            new_w = int(TARGET_HEIGHT * aspect_ratio)

            # Use any interpolation — we re-threshold after resize
            interp = random.choice([Image.NEAREST, Image.BILINEAR, Image.BICUBIC])
            final_text_img = gray.resize((new_w, new_h), interp)

            # 6. Re-threshold after resize to guarantee binary output
            # BILINEAR/BICUBIC interpolation introduces gray pixels from binary input
            final_text_img = final_text_img.point(lambda x: 0 if x < 128 else 255, 'L')

            # 7. Add Final Random Padding
            final_pad_left = random.randint(MIN_PADDING, MAX_PADDING)
            final_pad_right = random.randint(MIN_PADDING, MAX_PADDING)

            canvas_w = final_text_img.width + final_pad_left + final_pad_right
            canvas = Image.new('L', (canvas_w, TARGET_HEIGHT), color=255)
            canvas.paste(final_text_img, (final_pad_left, 0))

            # 8. Convert back to RGB (EasyOCR expects 3 channels)
            canvas = canvas.convert('RGB')

            # 8. Save
            filename = f"syn_{count:06d}"
            image_path = os.path.join(IMAGES_DIR, f"{filename}.png")
            label_path = os.path.join(LABELS_DIR, f"{filename}.txt")
            
            canvas.save(image_path)
            with open(label_path, 'w', encoding='utf-8') as lf:
                lf.write(word)
                
            count += 1
            if count % 1000 == 0:
                print(f"Generated {count} images...")
                
    print(f"\nDone! Generated {count} synthetic images in {OUTPUT_DIR}")

if __name__ == "__main__":
    generate_data()
