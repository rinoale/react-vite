"""Mabinogi-specific tooltip parser.

Extends TooltipLineSplitter with section detection and categorization.
Produces structured item data from tooltip images by:
1. Splitting into lines (base class)
2. Grouping horizontally-split sub-lines
3. Running OCR on each group
4. Matching OCR text against section header patterns
5. Categorizing lines into sections
6. Structurally parsing known patterns (e.g. color parts)
"""

import os
import re
from collections import OrderedDict

import cv2
import numpy as np
import yaml

from tooltip_line_splitter import TooltipLineSplitter


class MabinogiTooltipParser(TooltipLineSplitter):

    def __init__(self, config_path, output_dir="split_output"):
        super().__init__(output_dir)
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.load(f, Loader=yaml.FullLoader)
        self.sections_config = self.config.get('sections', {})
        self.horizontal_split_factor = self.config.get('horizontal_split_factor', 3)
        # Build header pattern lookup: pattern_text → section_key
        self._header_patterns = {}
        for key, sec in self.sections_config.items():
            for pattern in sec.get('header_patterns', []):
                self._header_patterns[pattern] = key

    def parse_tooltip(self, image_path, reader):
        """Full pipeline: split → group → OCR → categorize → structure.

        Args:
            image_path: Path to preprocessed tooltip image
            reader: EasyOCR Reader instance (with imgW patch applied)

        Returns:
            dict with 'sections' (categorized data) and 'all_lines' (raw OCR)
        """
        img, gray, binary = self.preprocess_image(image_path)
        detected_lines = self.detect_text_lines(binary)

        # Group sub-lines by y-position (from horizontal splitting)
        grouped = self._group_by_y(detected_lines)

        # OCR each group
        ocr_results = self._ocr_grouped_lines(img, grouped, reader)

        # Categorize into sections
        sections = self._categorize_sections(ocr_results)

        return {
            'sections': sections,
            'all_lines': ocr_results,
        }

    def _group_by_y(self, lines):
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

    def _ocr_grouped_lines(self, img, grouped_lines, reader):
        """Run OCR on each grouped line, merging sub-line results.

        Args:
            img: Original BGR image
            grouped_lines: list of sub-line groups from _group_by_y()
            reader: EasyOCR Reader instance

        Returns:
            list of dicts with 'text', 'confidence', 'sub_count', 'bounds', 'sub_lines'
        """
        results = []
        for group in grouped_lines:
            sub_texts = []
            sub_confs = []
            sub_details = []

            for line_info in group:
                x, y, w, h = line_info['x'], line_info['y'], line_info['width'], line_info['height']

                # Apply proportional padding
                pad_x = max(2, h // 3)
                pad_y = max(1, h // 5)
                x_pad = max(0, x - pad_x)
                y_pad = max(0, y - pad_y)
                w_pad = min(img.shape[1] - x_pad, w + 2 * pad_x)
                h_pad = min(img.shape[0] - y_pad, h + 2 * pad_y)

                line_crop = img[y_pad:y_pad + h_pad, x_pad:x_pad + w_pad]

                # Convert to grayscale
                if len(line_crop.shape) == 3:
                    gray = cv2.cvtColor(line_crop, cv2.COLOR_BGR2GRAY)
                else:
                    gray = line_crop

                ch, cw = gray.shape
                if ch == 0 or cw == 0:
                    sub_texts.append('')
                    sub_confs.append(0.0)
                    sub_details.append({'text': '', 'confidence': 0.0, 'bounds': line_info})
                    continue

                ocr_results = reader.recognize(
                    gray,
                    horizontal_list=[[0, cw, 0, ch]],
                    free_list=[],
                    reformat=False,
                    detail=1
                )

                if ocr_results:
                    _, text, confidence = ocr_results[0]
                else:
                    text, confidence = '', 0.0

                sub_texts.append(text)
                sub_confs.append(confidence)
                sub_details.append({
                    'text': text,
                    'confidence': float(confidence),
                    'bounds': line_info,
                })

            # Merge sub-line results
            merged_text = ' '.join(t.strip() for t in sub_texts if t.strip())
            avg_conf = sum(sub_confs) / len(sub_confs) if sub_confs else 0.0

            # Use first sub-line's y/height, span full x range
            first = group[0]
            last = group[-1]
            merged_bounds = {
                'x': first['x'],
                'y': first['y'],
                'width': (last['x'] + last['width']) - first['x'],
                'height': first['height'],
            }

            results.append({
                'text': merged_text,
                'confidence': float(avg_conf),
                'sub_count': len(group),
                'bounds': merged_bounds,
                'sub_lines': sub_details,
            })

        return results

    def _match_section_header(self, text):
        """Check if text matches any section header pattern.

        Uses contains-check since OCR may add/drop characters
        (e.g. "바이템 속성" should still match "아이템 속성").

        Returns:
            section key string or None
        """
        cleaned = text.strip().strip('-').strip()
        for pattern, section_key in self._header_patterns.items():
            if pattern in cleaned:
                return section_key
        return None

    def _categorize_sections(self, ocr_results):
        """Categorize OCR results into sections based on header detection.

        Strategy:
        - Scan lines for section header matches
        - Lines before the first header are pre-header (item_name, item_type, etc.)
        - Lines after a header belong to that section until the next header
        - After 'item_color', remaining non-header lines are flavor_text

        Returns:
            OrderedDict of section_key → section_data
        """
        sections = OrderedDict()

        # First pass: find all header line indices
        header_indices = {}  # line_index → section_key
        for i, line in enumerate(ocr_results):
            section_key = self._match_section_header(line['text'])
            if section_key:
                header_indices[i] = section_key

        # Second pass: assign lines to sections
        current_section = '_pre_header'
        section_lines = OrderedDict()
        section_lines['_pre_header'] = []

        for i, line in enumerate(ocr_results):
            if i in header_indices:
                current_section = header_indices[i]
                if current_section not in section_lines:
                    section_lines[current_section] = []
                # Don't add the header line itself to content
                continue
            section_lines.setdefault(current_section, [])
            section_lines[current_section].append(line)

        # Process pre-header lines (item_name, item_type, craftsman)
        pre_header = section_lines.pop('_pre_header', [])
        if pre_header:
            # First line is always item_name
            sections['item_name'] = {
                'lines': [pre_header[0]],
                'text': pre_header[0]['text'],
            }
            # Remaining pre-header lines (item_type, craftsman, etc.)
            if len(pre_header) > 1:
                sections['item_type'] = {
                    'lines': pre_header[1:],
                    'text': ' '.join(l['text'] for l in pre_header[1:]),
                }

        # Process each detected section
        for section_key, lines in section_lines.items():
            sec_config = self.sections_config.get(section_key, {})

            # Skip sections marked as skip
            if sec_config.get('skip', False):
                sections[section_key] = {'skipped': True, 'line_count': len(lines)}
                continue

            # Structural parsing for color parts
            if sec_config.get('parse_mode') == 'color_parts':
                sections[section_key] = self._parse_color_section(lines)
                continue

            # Standard OCR section
            sections[section_key] = {
                'lines': [
                    {
                        'text': l['text'],
                        'confidence': l['confidence'],
                        'bounds': l['bounds'],
                    }
                    for l in lines
                ],
            }

        # Detect flavor_text: lines after item_color that aren't a known section
        # This is handled naturally by the section flow — any lines after the last
        # known section header that don't match a header are part of that section.
        # We post-process to separate flavor_text from the last real section.
        self._extract_trailing_sections(sections, ocr_results, header_indices)

        return sections

    def _extract_trailing_sections(self, sections, ocr_results, header_indices):
        """Identify flavor_text and shop_price from trailing lines.

        Lines after the last categorized section that don't belong to any
        header-detected section are flavor text or shop price.
        """
        if not ocr_results:
            return

        # Find the last header index
        if not header_indices:
            return

        last_header_idx = max(header_indices.keys())
        last_section_key = header_indices[last_header_idx]

        # Check if the last section has lines that look like flavor_text or shop_price
        if last_section_key in sections and 'lines' in sections[last_section_key]:
            lines = sections[last_section_key]['lines']
            # Look for 상점판매가 in the last section's lines
            for i, line in enumerate(lines):
                if '상점판매가' in line.get('text', ''):
                    # Split: everything from here is shop_price
                    sections['shop_price'] = {'skipped': True, 'line_count': len(lines) - i}
                    sections[last_section_key]['lines'] = lines[:i]
                    break

    def _parse_color_section(self, lines):
        """Parse color part lines structurally.

        Color part lines are horizontally split into sub-segments:
        "파트 A", "R:0", "G:0", "B:12"

        Instead of relying on OCR for the full sparse line, we parse
        each sub-segment individually.

        Returns:
            dict with 'parts' list of {part, r, g, b} dicts
        """
        parts = []
        for line in lines:
            sub_lines = line.get('sub_lines', [])
            if not sub_lines:
                # Single line, try to parse from full text
                part_data = self._parse_color_text(line.get('text', ''))
                if part_data:
                    parts.append(part_data)
                continue

            # Parse from sub-line texts
            part_name = None
            r, g, b = None, None, None
            for sub in sub_lines:
                text = sub.get('text', '').strip()
                if not text:
                    continue

                # Check for part name (파트 A, 파트 B, etc.)
                part_match = re.search(r'파트\s*([A-F])', text)
                if part_match:
                    part_name = part_match.group(1)
                    continue

                # Check for R:N, G:N, B:N
                rgb_match = re.search(r'([RGB])\s*[:\s]\s*(\d+)', text)
                if rgb_match:
                    channel = rgb_match.group(1)
                    value = int(rgb_match.group(2))
                    if channel == 'R':
                        r = value
                    elif channel == 'G':
                        g = value
                    elif channel == 'B':
                        b = value

            if part_name is not None:
                parts.append({
                    'part': part_name,
                    'r': r,
                    'g': g,
                    'b': b,
                })

        return {'parts': parts}

    def _parse_color_text(self, text):
        """Parse a color part from a single text string.

        Handles: "파트 A R:0 G:0 B:12", "- 파트 A R:0 G:0 B:0"
        """
        part_match = re.search(r'파트\s*([A-F])', text)
        if not part_match:
            return None

        part_name = part_match.group(1)
        r_match = re.search(r'R\s*[:\s]\s*(\d+)', text)
        g_match = re.search(r'G\s*[:\s]\s*(\d+)', text)
        b_match = re.search(r'B\s*[:\s]\s*(\d+)', text)

        return {
            'part': part_name,
            'r': int(r_match.group(1)) if r_match else None,
            'g': int(g_match.group(1)) if g_match else None,
            'b': int(b_match.group(1)) if b_match else None,
        }
