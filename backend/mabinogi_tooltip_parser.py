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

# Lines that appear above the item name in the pre-header block.
# Extend this set if new top-level status lines are discovered.
_PRE_NAME_PATTERNS = {'전용 해제'}

# Reforge section patterns
# Header: '- 스매시 대미지(15/20 레벨)' — name before '(', level/max_level inside
_REFORGE_HEADER_RE = re.compile(r'^[-\s]*(.+?)\s*\((\d+)/(\d+)\s*레벨\)')
# Sub-bullet: 'ㄴ 대미지 150 % 증가' — describes effect at current level
_REFORGE_SUB_RE    = re.compile(r'^\s*ㄴ')

# Enchant section patterns
# Header: '[접두] 충격을 (랭크 F)' or '[접미] 관리자 (랭크 6)' — ranks: A-F or 1-9
_ENCHANT_HEADER_RE = re.compile(r'^\[?(접두|접미)\]?\s+(.+?)\s*\(랭크\s*([A-F0-9]+)\)')


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

    def parse_from_segments(self, tagged_segments, reader):
        """Build full structured result from segment_and_tag() output.

        Drop-in replacement for parse_tooltip() in the new segment-first pipeline.
        Section labels come from header OCR — no post-hoc pattern matching needed.

        Args:
            tagged_segments: list of dicts from tooltip_segmenter.segment_and_tag()
            reader:          content OCR EasyOCR reader (custom_mabinogi, imgW patched)

        Returns:
            dict with 'sections' (OrderedDict) and 'all_lines' — same format as
            parse_tooltip() so callers need no changes.
        """
        sections = OrderedDict()
        all_lines = []

        for seg in tagged_segments:
            section      = seg['section']
            content_crop = seg['content_crop']

            if content_crop is None or content_crop.shape[0] == 0:
                continue

            # Prepend header text as a line so line count matches GT
            header_line = None
            if seg['header_crop'] is not None and seg.get('header_ocr_text'):
                header_line = {
                    'text':       seg['header_ocr_text'],
                    'confidence': seg['header_ocr_conf'],
                    'bounds':     {},
                    'section':    section,
                    'is_header':  True,
                }

            section_data = self._parse_segment_from_array(content_crop, section, reader)

            if section == 'pre_header':
                sections.update(section_data)
                if 'lines' in section_data.get('pre_header', {}):
                    all_lines.extend(section_data['pre_header']['lines'])
            else:
                # Insert header text as first line of this segment
                if header_line is not None and 'lines' in section_data:
                    section_data['lines'].insert(0, header_line)

                if section and section not in sections:
                    sections[section] = section_data
                elif section:
                    # Merge duplicate sections (multiple headers with same label)
                    existing = sections[section]
                    if 'lines' in existing and 'lines' in section_data:
                        existing['lines'].extend(section_data['lines'])
                if 'lines' in section_data:
                    all_lines.extend(section_data['lines'])

        return {'sections': sections, 'all_lines': all_lines}

    def _parse_segment_from_array(self, content_bgr, section, reader):
        """Parse one content region (BGR numpy array) with a pre-known section label.

        Preprocessing: BT.601 grayscale → threshold=80 (mirrors frontend pipeline).
        Passes the binary image directly to line detection and OCR.

        Args:
            content_bgr: numpy BGR array (content_crop from segment_and_tag)
            section:     section label string (e.g. 'enchant', 'reforge', 'pre_header')
            reader:      content OCR reader (custom_mabinogi, imgW patched)

        Returns:
            section data dict — same per-section format as _categorize_sections produces.
            For 'pre_header' returns {'item_name': {...}, 'item_type': {...}}.
        """
        gray = cv2.cvtColor(content_bgr, cv2.COLOR_BGR2GRAY)
        # black text on white — correct polarity for OCR (matches training data)
        _, binary = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY_INV)
        # detect_text_lines counts pixels > 0 as foreground, so it needs
        # white text on black — invert the binary before line detection
        binary_detect = cv2.bitwise_not(binary)

        detected_lines = self.detect_text_lines(binary_detect)
        grouped        = self._group_by_y(detected_lines)
        ocr_results    = self._ocr_grouped_lines(binary, grouped, reader)

        for line in ocr_results:
            line['section'] = section

        if section == 'pre_header':
            return self._parse_pre_header(ocr_results)

        sec_config = self.sections_config.get(section, {})
        if sec_config.get('skip', False):
            return {'skipped': True, 'line_count': len(ocr_results)}

        parse_mode = sec_config.get('parse_mode')
        if parse_mode == 'color_parts':
            return self._parse_color_section(ocr_results)
        if parse_mode == 'reforge_options':
            return self._parse_reforge_section(ocr_results)
        if parse_mode == 'enchant_options':
            return self._parse_enchant_section(ocr_results)

        return {
            'lines': [
                {'text': l['text'], 'confidence': l['confidence'],
                 'bounds': l['bounds'], 'section': l.get('section', section)}
                for l in ocr_results
            ]
        }

    def _parse_pre_header(self, ocr_results):
        """Return all pre-header lines as a single 'pre_header' section.

        No special-case splitting — every line before the first orange header
        is simply tagged 'pre_header' and passed through.
        """
        for line in ocr_results:
            line['section'] = 'pre_header'
        return {'pre_header': {
            'lines': ocr_results,
            'text': ' '.join(l['text'] for l in ocr_results),
        }}

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

        A ratio guard rejects matches where the pattern is buried in a much
        longer line — real headers are short standalone words, so the pattern
        must occupy at least 50% of the cleaned text length.

        Returns:
            section key string or None
        """
        cleaned = text.strip().strip('-').strip()
        if not cleaned:
            return None
        for pattern, section_key in self._header_patterns.items():
            if pattern in cleaned:
                if len(pattern) / len(cleaned) >= 0.5:
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
            line['section'] = current_section   # tag each line with its section key
            section_lines.setdefault(current_section, [])
            section_lines[current_section].append(line)

        # Process pre-header lines (item_name, item_type, craftsman)
        pre_header = section_lines.pop('_pre_header', [])
        if pre_header:
            # Some items have a status line above the item name (e.g. '전용 해제').
            # Skip those and find the true item_name as the first non-status line.
            idx = 0
            if pre_header[0]['text'].strip() in _PRE_NAME_PATTERNS:
                pre_header[0]['section'] = 'item_flags'
                idx = 1

            if idx < len(pre_header):
                pre_header[idx]['section'] = 'item_name'
                sections['item_name'] = {
                    'lines': [pre_header[idx]],
                    'text': pre_header[idx]['text'],
                }

            # Remaining lines (item_type, craftsman, etc.)
            if idx + 1 < len(pre_header):
                for l in pre_header[idx + 1:]:
                    l['section'] = 'item_type'
                sections['item_type'] = {
                    'lines': pre_header[idx + 1:],
                    'text': ' '.join(l['text'] for l in pre_header[idx + 1:]),
                }

        # Process each detected section
        for section_key, lines in section_lines.items():
            sec_config = self.sections_config.get(section_key, {})

            # Skip sections marked as skip
            if sec_config.get('skip', False):
                sections[section_key] = {'skipped': True, 'line_count': len(lines)}
                continue

            # Structural parsing by parse_mode
            parse_mode = sec_config.get('parse_mode')
            if parse_mode == 'color_parts':
                sections[section_key] = self._parse_color_section(lines)
                continue
            if parse_mode == 'reforge_options':
                sections[section_key] = self._parse_reforge_section(lines)
                continue
            if parse_mode == 'enchant_options':
                sections[section_key] = self._parse_enchant_section(lines)
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

    def _parse_reforge_section(self, lines):
        """Parse reforge section into structured option records.

        Each reforge option is a header line 'NAME(current/max 레벨)' followed
        by one ㄴ sub-bullet describing the effect at the current level.

        Tags each line dict with metadata for FM and DB storage:
          header line: reforge_name, reforge_level, reforge_max_level, is_reforge_sub=False
          sub-bullet:  is_reforge_sub=True

        Returns:
            {'options': [{name, level, max_level, effect}], 'lines': lines}
        """
        options = []
        current = None

        for line in lines:
            text = line.get('text', '')
            m = _REFORGE_HEADER_RE.match(text)
            if m:
                name      = m.group(1).strip().lstrip('-').strip()
                level     = int(m.group(2))
                max_level = int(m.group(3))
                current = {
                    'name':      name,
                    'level':     level,
                    'max_level': max_level,
                    'effect':    None,
                }
                options.append(current)
                line['reforge_name']      = name
                line['reforge_level']     = level
                line['reforge_max_level'] = max_level
                line['is_reforge_sub']    = False
            elif _REFORGE_SUB_RE.match(text):
                line['is_reforge_sub'] = True
                if current is not None:
                    effect = _REFORGE_SUB_RE.sub('', text).strip()
                    current['effect'] = effect
            else:
                line['is_reforge_sub'] = False

        return {'options': options, 'lines': lines}

    def _parse_enchant_section(self, lines):
        """Parse enchant section into slot-grouped records.

        Each enchant is a header '[접두|접미] NAME (랭크 RANK)' followed by
        effect lines starting with '-'.

        Tags each line dict with metadata for FM and DB storage:
          header line: enchant_slot, enchant_name, enchant_rank, is_enchant_hdr=True
          effect line: is_enchant_hdr=False

        Returns:
            {'enchants': [{slot, name, rank, effects}], 'lines': lines}
        """
        enchants = []
        current = None

        for line in lines:
            text = line.get('text', '')
            m = _ENCHANT_HEADER_RE.match(text)
            if m:
                slot = m.group(1)
                name = m.group(2).strip()
                rank = m.group(3)
                current = {
                    'slot':    slot,
                    'name':    name,
                    'rank':    rank,
                    'effects': [],
                }
                enchants.append(current)
                line['enchant_slot']   = slot
                line['enchant_name']   = name
                line['enchant_rank']   = rank
                line['is_enchant_hdr'] = True
            else:
                line['is_enchant_hdr'] = False
                if current is not None:
                    effect = text.strip().lstrip('-').strip()
                    if effect:
                        current['effects'].append(effect)

        return {'enchants': enchants, 'lines': lines}

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
