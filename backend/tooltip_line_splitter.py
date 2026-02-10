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
        
        # Simple global threshold for bright text on dark background
        # Adjust 80 based on testing (mean is 26, so 80 is safe)
        _, binary = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY)
        
        # Dilate slightly to connect broken characters
        kernel = np.ones((1, 3), np.uint8)
        cleaned = cv2.dilate(binary, kernel, iterations=1)
        
        return img, gray, cleaned
    
    def detect_text_lines(self, binary_img, min_height=8, max_height=50, min_width=30):
        """Detect individual text lines using connected components"""
        if not DEPENDENCIES_AVAILABLE:
            return []
            
        # Find connected components
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary_img, connectivity=8)
        
        lines = []
        
        for i in range(1, num_labels):  # Skip background (0)
            x, y, w, h, area = stats[i]
            
            # Filter based on text line characteristics
            if (min_height <= h <= max_height and 
                w >= min_width and 
                area > min_height * min_width * 0.3):  # Minimum density
                
                lines.append({
                    'x': int(x),
                    'y': int(y),
                    'width': int(w),
                    'height': int(h),
                    'area': int(area),
                    'label': int(i)
                })
        
        # Sort lines by vertical position (top to bottom)
        lines.sort(key=lambda l: l['y'])
        
        return self.merge_overlapping_lines(lines)
    
    def merge_overlapping_lines(self, lines, vertical_threshold=5):
        """Merge lines that are vertically close to each other"""
        if not lines:
            return []
        
        merged = []
        current_group = [lines[0]]
        
        for i in range(1, len(lines)):
            current_line = lines[i]
            last_line = current_group[-1]
            
            # Check if lines should be merged
            if (current_line['y'] - (last_line['y'] + last_line['height']) < vertical_threshold and
                abs(current_line['x'] - last_line['x']) < 50):  # Similar horizontal position
                
                # Merge with current group
                current_group.append(current_line)
            else:
                # Save current group and start new one
                merged.append(self.merge_group(current_group))
                current_group = [current_line]
        
        # Don't forget the last group
        merged.append(self.merge_group(current_group))
        
        return merged
    
    def merge_group(self, group):
        """Merge a group of lines into a single line bounding box"""
        if not group:
            return None
        
        min_x = min(l['x'] for l in group)
        min_y = min(l['y'] for l in group)
        max_x = max(l['x'] + l['width'] for l in group)
        max_y = max(l['y'] + l['height'] for l in group)
        
        return {
            'x': int(min_x),
            'y': int(min_y),
            'width': int(max_x - min_x),
            'height': int(max_y - min_y),
            'components': int(len(group))
        }
    
    def extract_lines(self, img, lines, base_filename):
        """Extract individual line images"""
        if not DEPENDENCIES_AVAILABLE:
            return []
            
        extracted_lines = []
        
        for i, line in enumerate(lines):
            # Extract region
            x, y, w, h = line['x'], line['y'], line['width'], line['height']
            
            # Add some padding
            padding = 10
            x = max(0, x - padding)
            y = max(0, y - padding)
            w = min(img.shape[1] - x, w + 2 * padding)
            h = min(img.shape[0] - y, h + 2 * padding)
            
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