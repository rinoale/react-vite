"""
Standalone CLI tool that replicates the frontend's image preprocessing
(grayscale → contrast → threshold → black text on white background).

Useful for manually preprocessing raw screenshots outside the browser,
e.g. to prepare test images or debug OCR issues.

Not used by the backend pipeline — the frontend (sell.jsx) handles
preprocessing in the browser before uploading.

Usage:
    python3 scripts/preprocess_v2.py input.png output.png
    python3 scripts/preprocess_v2.py input.png output.png --threshold 80
"""
import cv2
import numpy as np
import os
import argparse

def preprocess_image(image_path, contrast=1.0, brightness=1.0, threshold=80):
    """
    Python implementation of the frontend canvas preprocessing logic.
    Goal: Black text on White background.
    """
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not read image: {image_path}")

    # 1. Grayscale (using same weights as JS)
    # OpenCV's cvtColor uses slightly different weights, so let's do it manually for perfect match
    # R, G, B order in OpenCV is B, G, R
    b, g, r = cv2.split(img)
    gray = (0.299 * r + 0.587 * g + 0.114 * b).astype(np.uint8)

    # 2. Contrast & Brightness
    # JS: contrast * (data[i] - 128) + 128 + (brightness - 1) * 128
    # We use a float matrix for intermediate calculation to avoid clipping too early
    processed = contrast * (gray.astype(np.float32) - 128) + 128 + (brightness - 1) * 128
    processed = np.clip(processed, 0, 255).astype(np.uint8)

    # 3. Thresholding (Invert logic for Black on White)
    # JS: avg > threshold ? 0 : 255
    _, binary = cv2.threshold(processed, threshold, 255, cv2.THRESH_BINARY_INV)
    # THRESH_BINARY_INV turns bright (text) into 0 (black) and dark (bg) into 255 (white)
    # which is exactly what the user wants.

    return binary

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Preprocess image matching frontend logic')
    parser.add_argument('input', help='Input image path')
    parser.add_argument('output', help='Output image path')
    parser.add_argument('--contrast', type=float, default=1.0)
    parser.add_argument('--brightness', type=float, default=1.0)
    parser.add_argument('--threshold', type=int, default=80)
    
    args = parser.parse_args()
    
    result = preprocess_image(args.input, args.contrast, args.brightness, args.threshold)
    cv2.imwrite(args.output, result)
    print(f"Processed image saved to {args.output}")
