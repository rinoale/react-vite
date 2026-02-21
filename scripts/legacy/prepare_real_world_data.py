import cv2
import numpy as np
import os
import argparse
import sys

# Add backend to path for TooltipLineSplitter
sys.path.append(os.path.join(os.getcwd(), 'backend'))
from lib.tooltip_line_splitter import TooltipLineSplitter

def preprocess_image(img, contrast=1.0, brightness=1.0, threshold=80):
    """Matches frontend logic: Black text on White background."""
    # Manual Grayscale (weighted)
    b, g, r = cv2.split(img)
    gray = (0.299 * r + 0.587 * g + 0.114 * b).astype(np.float32)

    # Contrast & Brightness
    processed = contrast * (gray - 128) + 128 + (brightness - 1) * 128
    processed = np.clip(processed, 0, 255).astype(np.uint8)

    # Thresholding (Invert logic for Black on White)
    _, binary = cv2.threshold(processed, threshold, 255, cv2.THRESH_BINARY_INV)
    return binary

def run_pipeline(input_image, output_dir="real_world_data"):
    """
    Preprocesses and splits a real-world image into lines for ground truth generation.
    """
    if not os.path.exists(input_image):
        print(f"Error: {input_image} not found")
        return

    # Prepare directories
    image_name = os.path.splitext(os.path.basename(input_image))[0]
    task_dir = os.path.join(output_dir, image_name)
    os.makedirs(os.path.join(task_dir, "images"), exist_ok=True)
    os.makedirs(os.path.join(task_dir, "labels"), exist_ok=True)

    # 1. Load and Preprocess matching frontend logic
    img = cv2.imread(input_image)
    processed_img = preprocess_image(img)
    
    # Save the processed image (Black on White)
    processed_path = os.path.join(task_dir, f"{image_name}_processed.png")
    cv2.imwrite(processed_path, processed_img)

    # 2. Use TooltipLineSplitter on the SAVED processed image
    # This allows the splitter to use its internal 'preprocess_image' logic
    # which correctly handles the Black-on-White inversion.
    splitter = TooltipLineSplitter(output_dir=task_dir)
    
    # process_image returns the extracted line info
    extracted_lines = splitter.process_image(processed_path, save_visualization=True)

    print(f"Success: Extracted {len(extracted_lines)} lines to {task_dir}/images/")
    print(f"Full processed image saved at {processed_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Prepare real world images for GT generation')
    parser.add_argument('input', help='Input image path')
    parser.add_argument('--output', default='real_world_data', help='Output base directory')
    args = parser.parse_args()
    
    run_pipeline(args.input, args.output)
