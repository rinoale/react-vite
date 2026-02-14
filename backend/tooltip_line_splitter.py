#!/usr/bin/env python3
"""
Mabinogi Item Tooltip Line Splitter
Automatically splits item tooltip images into individual text lines for OCR training
"""

import os
import sys
import json
from datetime import datetime

# Check for required dependencies
DEPENDENCIES_AVAILABLE = False
try:
    import cv2
    import numpy as np
    from PIL import Image, ImageEnhance, ImageFilter
    DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install with: pip install opencv-python numpy Pillow")

class TooltipLineSplitter:
    def __init__(self, output_dir="split_output"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(os.path.join(output_dir, "images"), exist_ok=True)
        os.makedirs(os.path.join(output_dir, "labels"), exist_ok=True)
        
    def preprocess_image(self, image_path):
        """Preprocess image for better line detection"""
        if not DEPENDENCIES_AVAILABLE:
            raise RuntimeError("Required dependencies not available")
            
        # Read image
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Could not read image: {image_path}")
        
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Auto-detect background type and threshold accordingly
        mean_val = np.mean(gray)
        if mean_val >= 128:
            # Light background, dark text → invert so text becomes white (foreground)
            _, binary = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY_INV)
        else:
            # Dark background, bright text → text is already bright (foreground)
            _, binary = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY)
        
        return img, gray, binary
    
    def _remove_borders(self, binary_img):
        """Remove vertical border columns that interfere with line detection.

        Tooltip images have thin UI border lines (1-2px wide columns that span
        many rows). These contribute a few white pixels per row that prevent
        gap detection between text lines.

        Horizontal separators are NOT removed because they are single rows
        that don't bridge sections, and removing them can destroy section
        headers like "개조" and "세공" that sit adjacent to box borders.
        """
        h, w = binary_img.shape
        cleaned = binary_img.copy()

        # Mask out columns where >15% of rows are white (vertical borders)
        col_density = np.sum(binary_img > 0, axis=0) / h
        for col in range(w):
            if col_density[col] > 0.15:
                cleaned[:, col] = 0

        return cleaned

    def detect_text_lines(self, binary_img, min_height=6, max_height=25, min_width=10):
        """Detect individual text lines using horizontal projection profile"""
        if not DEPENDENCIES_AVAILABLE:
            return []

        h, w = binary_img.shape

        # Step 1: Remove UI border lines that bridge gaps between text lines
        cleaned = self._remove_borders(binary_img)

        # Step 2: Horizontal projection on cleaned image
        projection = np.sum(cleaned > 0, axis=1)

        # Step 3: Find rows with actual text content
        threshold = max(3, w * 0.015)
        has_text = projection > threshold

        # Step 4: Close tiny gaps in has_text (up to 2 rows)
        # Thin character strokes can cause 1-row dips below threshold,
        # but inter-line gaps are typically 4+ rows.
        gap_tolerance = 2
        i = 0
        while i < h:
            if not has_text[i] and i > 0 and has_text[i - 1]:
                # Found start of a gap — check if it's short enough to close
                gap_start = i
                while i < h and not has_text[i]:
                    i += 1
                gap_len = i - gap_start
                if gap_len <= gap_tolerance and i < h and has_text[i]:
                    # Close the gap
                    for g in range(gap_start, i):
                        has_text[g] = True
            else:
                i += 1

        # Step 5: Find contiguous runs of text rows
        lines = []
        in_line = False
        line_start = 0

        for y in range(h):
            if has_text[y] and not in_line:
                line_start = y
                in_line = True
            elif not has_text[y] and in_line:
                line_h = y - line_start
                if min_height <= line_h <= max_height:
                    self._add_line(binary_img, lines, line_start, y, min_width)
                elif line_h > max_height:
                    self._split_tall_block(binary_img, cleaned, lines,
                                           line_start, y, min_height, max_height, min_width)
                in_line = False

        # Handle last line if image ends with text
        if in_line:
            line_h = h - line_start
            if min_height <= line_h <= max_height:
                self._add_line(binary_img, lines, line_start, h, min_width)
            elif line_h > max_height:
                self._split_tall_block(binary_img, cleaned, lines,
                                       line_start, h, min_height, max_height, min_width)

        return lines

    def _add_line(self, binary_img, lines, y_start, y_end, min_width):
        """Add a detected line, computing its horizontal extent from the original binary image.

        Filters out UI border elements:
        1. Thin clusters (1-2px wide) far from text — vertical border lines
        2. Wide clusters with low column density — horizontal bar borders (ㅡㅡㅡ)
        Then trims to the actual text bounds.
        """
        line_h = y_end - y_start
        row_slice = binary_img[y_start:y_end, :]
        col_projection = np.sum(row_slice > 0, axis=0)

        # Find contiguous ink clusters
        ink_cols = col_projection > 0
        clusters = []
        in_cluster = False
        start = 0
        for c in range(len(ink_cols)):
            if ink_cols[c] and not in_cluster:
                start = c
                in_cluster = True
            elif not ink_cols[c] and in_cluster:
                clusters.append((start, c - 1))
                in_cluster = False
        if in_cluster:
            clusters.append((start, len(ink_cols) - 1))

        if not clusters:
            return

        # Filter out border artifacts
        if len(clusters) > 1:
            gap_threshold = line_h * 2
            # A cluster is "text" if it's wider than 2px AND has sufficient
            # column density (avg ink rows per column >= 2.0).
            # Wide clusters with density < 2.0 are horizontal bars (ㅡㅡㅡ).
            text_clusters = []
            for cs, ce in clusters:
                cw = ce - cs + 1
                if cw <= 2:
                    continue
                avg_density = float(np.mean(col_projection[cs:ce + 1]))
                # Wide + low density = horizontal bar border
                if cw > line_h * 3 and avg_density < 2.0:
                    continue
                text_clusters.append((cs, ce))

            if text_clusters:
                filtered = []
                for cs, ce in clusters:
                    cw = ce - cs + 1
                    avg_density = float(np.mean(col_projection[cs:ce + 1]))

                    # Skip horizontal bar borders
                    if cw > line_h * 3 and avg_density < 2.0:
                        continue

                    if cw > 2:
                        filtered.append((cs, ce))
                        continue

                    # Thin cluster: check distance to nearest text cluster
                    min_dist = min(
                        min(abs(cs - tce), abs(ce - tcs))
                        for tcs, tce in text_clusters
                    )
                    if min_dist <= gap_threshold:
                        filtered.append((cs, ce))
                clusters = filtered if filtered else clusters

        x_start = int(clusters[0][0])
        x_end = int(clusters[-1][1]) + 1
        line_w = x_end - x_start
        if line_w >= min_width:
            lines.append({
                'x': x_start,
                'y': int(y_start),
                'width': line_w,
                'height': int(y_end - y_start),
            })

    def _split_tall_block(self, binary_img, cleaned, lines,
                          y_start, y_end, min_height, max_height, min_width):
        """Split an oversized block into individual lines using local projection analysis."""
        block = cleaned[y_start:y_end, :]
        projection = np.sum(block > 0, axis=1)

        # Use a lower threshold to find gaps within the block
        threshold = max(1, np.median(projection[projection > 0]) * 0.1) if np.any(projection > 0) else 1
        has_text = projection > threshold

        in_line = False
        local_start = 0
        for y in range(len(has_text)):
            if has_text[y] and not in_line:
                local_start = y
                in_line = True
            elif not has_text[y] and in_line:
                line_h = y - local_start
                if min_height <= line_h <= max_height:
                    self._add_line(binary_img, lines, y_start + local_start, y_start + y, min_width)
                in_line = False

        if in_line:
            line_h = len(has_text) - local_start
            if min_height <= line_h <= max_height:
                self._add_line(binary_img, lines, y_start + local_start, y_start + len(has_text), min_width)
    
    def extract_lines(self, img, lines, base_filename):
        """Extract individual line images"""
        if not DEPENDENCIES_AVAILABLE:
            return []
            
        extracted_lines = []
        
        for i, line in enumerate(lines):
            # Extract region
            x, y, w, h = line['x'], line['y'], line['width'], line['height']
            
            # Add proportional padding (small enough not to bleed into adjacent lines)
            pad_x = max(2, line['height'] // 3)
            pad_y = max(1, line['height'] // 5)
            x = max(0, x - pad_x)
            y = max(0, y - pad_y)
            w = min(img.shape[1] - x, w + 2 * pad_x)
            h = min(img.shape[0] - y, h + 2 * pad_y)
            
            line_img = img[y:y+h, x:x+w]
            
            # Save line image
            line_filename = f"{base_filename}_line_{i+1:03d}.png"
            line_path = os.path.join(self.output_dir, "images", line_filename)
            cv2.imwrite(line_path, line_img)
            
            extracted_lines.append({
                'filename': line_filename,
                'path': line_path,
                'bounds': line,
                'text': ''  # To be filled manually
            })
        
        return extracted_lines
    
    def create_visualization(self, img, lines, output_path):
        """Create visualization of detected lines"""
        if not DEPENDENCIES_AVAILABLE:
            return
            
        vis_img = img.copy()
        
        for i, line in enumerate(lines):
            x, y, w, h = line['x'], line['y'], line['width'], line['height']
            
            # Draw bounding box
            color = (0, 255, 0) if i % 2 == 0 else (255, 0, 0)
            cv2.rectangle(vis_img, (x, y), (x + w, y + h), color, 2)
            
            # Add line number
            cv2.putText(vis_img, str(i+1), (x, y-5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        
        cv2.imwrite(output_path, vis_img)
    
    def create_training_manifest(self, lines, base_filename):
        """Create JSON manifest for training"""
        manifest = {
            'source_image': base_filename,
            'total_lines': len(lines),
            'lines': lines,
            'created_at': datetime.now().isoformat()
        }
        
        manifest_path = os.path.join(self.output_dir, f"{base_filename}_manifest.json")
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        
        return manifest_path
    
    def process_image(self, image_path, save_visualization=True):
        """Process a single image"""
        filename = os.path.basename(image_path)
        base_filename = os.path.splitext(filename)[0]
        
        try:
            # Preprocess
            img, gray, binary = self.preprocess_image(image_path)
            
            # Detect lines
            lines = self.detect_text_lines(binary)
            
            if not lines:
                print(f"Warning: No text lines detected in {filename}")
                return []
            
            # Extract lines
            extracted_lines = self.extract_lines(img, lines, base_filename)
            
            # Create visualization
            if save_visualization:
                vis_path = os.path.join(self.output_dir, f"{base_filename}_visualization.png")
                self.create_visualization(img, lines, vis_path)
            
            # Create manifest
            self.create_training_manifest(extracted_lines, base_filename)
            
            print(f"✓ Processed {filename}: {len(lines)} lines detected")
            return extracted_lines
            
        except Exception as e:
            print(f"✗ Error processing {filename}: {e}")
            return []
    
    def process_directory(self, input_dir, save_visualization=True):
        """Process all images in a directory"""
        if not os.path.exists(input_dir):
            print(f"Error: Directory {input_dir} does not exist")
            return
        
        image_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff'}
        image_files = [
            f for f in os.listdir(input_dir) 
            if os.path.splitext(f.lower())[1] in image_extensions
        ]
        
        if not image_files:
            print(f"No image files found in {input_dir}")
            return
        
        print(f"Processing {len(image_files)} images...")
        
        total_lines = 0
        for image_file in image_files:
            image_path = os.path.join(input_dir, image_file)
            lines = self.process_image(image_path, save_visualization)
            total_lines += len(lines)
        
        print(f"\n✓ Complete! Total lines extracted: {total_lines}")
        print(f"Output saved to: {self.output_dir}")
        
        # Create summary
        self.create_summary(total_lines, len(image_files))
    
    def create_summary(self, total_lines, total_images):
        """Create processing summary"""
        summary = {
            'total_images_processed': total_images,
            'total_lines_extracted': total_lines,
            'average_lines_per_image': total_lines / total_images if total_images > 0 else 0,
            'output_directory': self.output_dir
        }
        
        summary_path = os.path.join(self.output_dir, "processing_summary.json")
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        return summary

def main():
    try:
        import argparse
    except ImportError:
        print("Error: argparse module not available")
        sys.exit(1)
    
    parser = argparse.ArgumentParser(description='Split Mabinogi item tooltip images into text lines')
    parser.add_argument('input', help='Input image file or directory')
    parser.add_argument('-o', '--output', default='split_output', help='Output directory')
    parser.add_argument('--no-vis', action='store_true', help='Skip visualization creation')
    parser.add_argument('--min-height', type=int, default=8, help='Minimum line height')
    parser.add_argument('--max-height', type=int, default=50, help='Maximum line height')
    
    args = parser.parse_args()
    
    if not DEPENDENCIES_AVAILABLE:
        print("Please install required dependencies first:")
        print("pip install opencv-python numpy Pillow")
        sys.exit(1)
    
    # Initialize splitter
    splitter = TooltipLineSplitter(args.output)
    
    # Process input
    if os.path.isfile(args.input):
        splitter.process_image(args.input, not args.no_vis)
    elif os.path.isdir(args.input):
        splitter.process_directory(args.input, not args.no_vis)
    else:
        print(f"Error: {args.input} is not a valid file or directory")
        sys.exit(1)

if __name__ == "__main__":
    main()