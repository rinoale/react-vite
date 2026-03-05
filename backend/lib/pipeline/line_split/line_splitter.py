#!/usr/bin/env python3
"""
Mabinogi Item Tooltip Line Splitter
Automatically splits item tooltip images into individual text lines for OCR training
"""

import os
from collections import OrderedDict

# Check for required dependencies
DEPENDENCIES_AVAILABLE = False
try:
    import cv2
    import numpy as np
    DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install with: pip install opencv-python numpy Pillow")

def group_by_y(lines):
    """Group horizontally-split sub-lines by shared y-position.

    Lines at the same y are sub-segments of one original line,
    produced by horizontal splitting in _add_line().

    Returns:
        list of lists, each inner list contains sub-lines sorted by x.
    """
    groups = OrderedDict()
    for line in lines:
        y = line['y']
        if y not in groups:
            groups[y] = []
        groups[y].append(line)

    result = []
    for y, sub_lines in groups.items():
        sub_lines.sort(key=lambda l: l['x'])
        result.append(sub_lines)
    return result


def _get_line_split_config(config=None):
    """Build full line-split config with defaults.

    Follows the same pattern as segmenter._get_header_detection_config().
    """
    config = config or {}
    det = config.get('detection', {})
    hz = config.get('horizontal', {})
    pad = config.get('padding', {})
    br = config.get('border_removal', {})
    cf = config.get('cluster_filter', {})
    out = config.get('outlier', {})
    st = config.get('stitch', {})
    return {
        'detection': {
            'binarization_threshold': det.get('binarization_threshold', 80),
            'background_polarity_cutoff': det.get('background_polarity_cutoff', 128),
            'row_density_ratio': det.get('row_density_ratio', 0.015),
            'row_density_minimum': det.get('row_density_minimum', 3),
            'minimum_height': det.get('minimum_height', 6),
            'minimum_width': det.get('minimum_width', 10),
        },
        'horizontal': {
            'split_factor': hz.get('split_factor', 3),
        },
        'padding': {
            'horizontal_divisor': pad.get('horizontal_divisor', 3),
            'horizontal_minimum': pad.get('horizontal_minimum', 2),
            'vertical_divisor': pad.get('vertical_divisor', 5),
            'vertical_minimum': pad.get('vertical_minimum', 1),
        },
        'border_removal': {
            'column_density': br.get('column_density', 0.6),
            'maximum_run_width': br.get('maximum_run_width', 3),
        },
        'cluster_filter': {
            'thin_width': cf.get('thin_width', 2),
            'bar_width_factor': cf.get('bar_width_factor', 3),
            'bar_maximum_density': cf.get('bar_maximum_density', 2.0),
            'bracket_maximum_density': cf.get('bracket_maximum_density', 2.0),
            'bracket_minimum_gap': cf.get('bracket_minimum_gap', 4),
            'border_stripe_density': cf.get('border_stripe_density', 0.85),
            'gap_factor': cf.get('gap_factor', 2),
        },
        'outlier': {
            'gap_multiplier': out.get('gap_multiplier', 2),
            'gap_offset': out.get('gap_offset', 4),
        },
        'stitch': {
            'baseline_offset': st.get('baseline_offset', 1),
        },
    }


class TooltipLineSplitter:
    def __init__(self, output_dir="split_output", config=None):
        self.output_dir = output_dir
        self.cfg = _get_line_split_config(config)
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

        # Auto-detect background type and threshold to ocr_binary (ink=0)
        det = self.cfg['detection']
        mean_val = np.mean(gray)
        if mean_val >= det['background_polarity_cutoff']:
            # Light background, dark text → already ink=0
            _, binary = cv2.threshold(gray, det['binarization_threshold'], 255, cv2.THRESH_BINARY)
        else:
            # Dark background, bright text → invert so ink becomes 0
            _, binary = cv2.threshold(gray, det['binarization_threshold'], 255, cv2.THRESH_BINARY_INV)

        return img, gray, binary
    
    def _remove_borders(self, binary_img):
        """Remove UI border columns before line detection.  No-op in base class."""
        return binary_img

    def detect_centered_lines(self, binary_img, min_height=13, min_width=None):
        """Detect lines using greedy group merging with centered windows.

        Algorithm (no gap_tolerance, no _has_internal_gap, no _split_tall_block):

        1. Find raw text groups — contiguous has_text=True rows with NO gap
           tolerance.  Each group is a pure ink cluster.
        2. Greedy merge (top → bottom): for each unassigned group, start a
           candidate line with 1-row head padding.  Absorb subsequent groups
           while total_span <= min_height.  When the next group would exceed
           min_height, reject it (starts a new line).
        3. Trim trailing zero-projection rows from accumulated content.
        4. Center a min_height window on the content extent.
        5. Conflict resolution: respect upper — trim overlap from top, keep
           original bottom (don't expand further down).
        """
        if not DEPENDENCIES_AVAILABLE:
            return []

        det = self.cfg['detection']
        if min_width is None:
            min_width = det['minimum_width']

        img_h, img_w = binary_img.shape

        # Step 1: Horizontal projection + text detection (NO gap closing)
        cleaned = self._remove_borders(binary_img)
        projection = np.sum(cleaned == 0, axis=1)
        threshold = max(det['row_density_minimum'], img_w * det['row_density_ratio'])
        has_text = projection > threshold

        # Step 2: Find raw text groups (contiguous has_text=True runs)
        groups = []  # list of (start, end) — end exclusive
        in_group = False
        group_start = 0
        for y in range(img_h):
            if has_text[y] and not in_group:
                group_start = y
                in_group = True
            elif not has_text[y] and in_group:
                groups.append((group_start, y))
                in_group = False
        if in_group:
            groups.append((group_start, img_h))

        # Step 3: Greedy group merging
        min_block_height = det['minimum_height']
        windows = []
        gi = 0  # group index
        while gi < len(groups):
            g_start, g_end = groups[gi]

            # 1-row head padding: start from 1 row before first text row
            line_start = max(0, g_start - 1)
            content_start = g_start  # actual text content starts here
            content_end = g_end      # last text row (exclusive)
            gi += 1

            # Absorb subsequent groups while they fit within min_height
            while gi < len(groups):
                next_start, next_end = groups[gi]
                # Total span from line_start to end of next group
                total_span = next_end - line_start
                if total_span <= min_height:
                    content_end = next_end
                    gi += 1
                else:
                    break  # next group starts a new line

            # Trim trailing zero-projection rows from content
            while content_end > content_start and projection[content_end - 1] == 0:
                content_end -= 1

            # Skip if content too small (noise/border artifacts)
            content_h = content_end - content_start
            if content_h < min_block_height:
                continue

            # Center min_height window on content extent
            center = content_start + (content_end - content_start - 1) // 2
            half_above = (min_height - 1) // 2
            win_start = center - half_above
            win_end = win_start + min_height

            # Clamp to image bounds
            if win_start < 0:
                win_start = 0
                win_end = min(min_height, img_h)
            if win_end > img_h:
                win_end = img_h
                win_start = max(0, win_end - min_height)

            # Conflict: respect upper — trim overlap from top, keep original bottom
            if windows:
                prev_end = windows[-1][1]
                if win_start < prev_end:
                    win_start = prev_end
                    # win_end stays — don't expand further down

            # Only add if enough room
            if win_end - win_start > 0:
                windows.append((win_start, win_end))

        # Step 4: Compute horizontal extents via _add_line
        lines = []
        for win_start, win_end in windows:
            self._add_line(binary_img, lines, win_start, win_end, min_width)

        return lines


    def _add_line(self, binary_img, lines, y_start, y_end, min_width):
        """Add a detected line, computing its horizontal extent from the original binary image."""
        line_h = y_end - y_start
        row_slice = binary_img[y_start:y_end, :]
        col_projection = np.sum(row_slice == 0, axis=0)

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

        clusters = self._filter_clusters(clusters, col_projection, line_h)
        if not clusters:
            return

        # Split horizontally if wide gaps exist between cluster groups.
        # Normal inter-character gaps are 1-6px; large gaps indicate
        # separate text segments (e.g. "파트 A    R:0    G:0    B:0").
        split_threshold = line_h * self.cfg['horizontal']['split_factor']
        segments = []  # list of cluster sub-lists
        seg_start = 0
        for i in range(1, len(clusters)):
            gap = clusters[i][0] - clusters[i - 1][1] - 1
            if gap > split_threshold:
                segments.append(clusters[seg_start:i])
                seg_start = i
        segments.append(clusters[seg_start:])

        for seg in segments:
            x_start = int(seg[0][0])
            x_end = int(seg[-1][1]) + 1
            line_w = x_end - x_start
            if line_w >= min_width:
                lines.append({
                    'x': x_start,
                    'y': int(y_start),
                    'width': line_w,
                    'height': int(y_end - y_start),
                })

    def _filter_clusters(self, clusters, col_projection, line_h):
        """Filter ink clusters before horizontal splitting.  No-op in base class."""
        return clusters