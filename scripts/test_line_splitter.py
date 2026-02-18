#!/usr/bin/env python3
"""Test the TooltipLineSplitter by splitting an image and saving results."""

import argparse
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

import cv2
from mabinogi_tooltip_parser import MabinogiTooltipParser

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(PROJECT_ROOT, 'configs', 'mabinogi_tooltip.yaml')


def main():
    parser = argparse.ArgumentParser(description='Split a tooltip image into lines')
    parser.add_argument('image', help='Path to the target image')
    parser.add_argument('output', help='Directory to save split line images')
    args = parser.parse_args()

    if not os.path.isfile(args.image):
        print(f"Error: {args.image} not found")
        sys.exit(1)

    os.makedirs(args.output, exist_ok=True)

    splitter = MabinogiTooltipParser(CONFIG_PATH, output_dir=args.output)

    # Preprocess and detect
    img, gray, binary = splitter.preprocess_image(args.image)
    lines = splitter.detect_text_lines(binary)

    if not lines:
        print("No lines detected.")
        sys.exit(0)

    # Save each line image directly into the output directory
    base = os.path.splitext(os.path.basename(args.image))[0]
    for i, line in enumerate(lines):
        x, y, w, h = line['x'], line['y'], line['width'], line['height']

        # Add padding
        pad = 4
        x0 = max(0, x - pad)
        y0 = max(0, y - pad)
        x1 = min(img.shape[1], x + w + pad)
        y1 = min(img.shape[0], y + h + pad)

        line_img = img[y0:y1, x0:x1]
        out_path = os.path.join(args.output, f"{base}_line_{i + 1:03d}.png")
        cv2.imwrite(out_path, line_img)

    # Save visualization with bounding boxes
    vis_path = os.path.join(args.output, f"{base}_visualization.png")
    splitter.create_visualization(img, lines, vis_path)

    print(f"Detected {len(lines)} lines. Saved to {args.output}/")


if __name__ == '__main__':
    main()
