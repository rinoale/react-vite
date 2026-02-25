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
from pathlib import Path
import re
from collections import OrderedDict

import cv2
import numpy as np
import yaml

from lib.tooltip_line_splitter import TooltipLineSplitter

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

# Effect number extraction: 'stat_name NUMBER[%] direction'
# Group 1: stat name, Group 2: number, Group 3: optional %, Group 4: rest (증가/감소/etc.)
_EFFECT_NUM_RE = re.compile(r'^(.+?)\s+(\d+(?:\.\d+)?)\s*(%?)\s*(.*)$')


def classify_enchant_line(content_bgr, bounds, bands):
    """Classify an enchant line as 'header', 'effect', or 'grey'.

    Uses band overlap for headers, mean text-pixel saturation for grey vs effect.
    Grey lines (descriptions, "인챈트 추출 불가", empty-slot explanations) have
    desaturated text (sat < 0.15) while effect lines are colored (sat > 0.2).

    Args:
        content_bgr: BGR numpy array of the enchant content region
        bounds:      dict with 'x', 'y', 'width', 'height'
        bands:       list of (y_start, y_end) from detect_enchant_slot_headers()

    Returns:
        'header', 'effect', or 'grey'
    """
    y, h = bounds['y'], bounds['height']
    x, w = bounds['x'], bounds['width']

    # Band overlap → header
    if any(min(y + h, be) - max(y, bs) > 0 for bs, be in bands):
        return 'header'

    # Saturation of text pixels (foreground only, bg excluded)
    roi = content_bgr[y:y + h, x:x + w]
    roi_max = roi.max(axis=2)
    text_mask = roi_max > 40
    if text_mask.sum() == 0:
        return 'grey'

    text_px = roi[text_mask].astype(np.float32)
    max_ch = text_px.max(axis=1)
    min_ch = text_px.min(axis=1)
    mean_sat = ((max_ch - min_ch) / (max_ch + 1)).mean()

    return 'grey' if mean_sat < 0.15 else 'effect'


def _strip_border_cols(white_mask, edge_cols=3, density_threshold=0.5):
    """Mask out edge columns with high white pixel density (border artifacts).

    Checks the leftmost and rightmost `edge_cols` columns. If the fraction
    of white pixels exceeds `density_threshold`, that column is cleared.
    Border columns have near-continuous bright pixels (50-90% density),
    while text in edge columns has sparse, short bursts (~10-15px per line).
    """
    h, w = white_mask.shape
    cols_to_check = list(range(min(edge_cols, w))) + \
                    list(range(max(0, w - edge_cols), w))

    for c in cols_to_check:
        density = white_mask[:, c].sum() / h
        if density > density_threshold:
            white_mask[:, c] = False

    return white_mask


def _oreo_flip(content_bgr):
    """BGR → white mask (bright & balanced) → strip border cols → invert to black-on-white.
    # bright-on-dark → white mask (max_ch>150, ratio<1.4) → strip border cols → invert
    """
    r = content_bgr[:, :, 2].astype(np.float32)
    g = content_bgr[:, :, 1].astype(np.float32)
    b = content_bgr[:, :, 0].astype(np.float32)
    max_ch = np.maximum(np.maximum(r, g), b)
    min_ch = np.minimum(np.minimum(r, g), b)
    white_mask = (max_ch > 150) & ((max_ch / (min_ch + 1)) < 1.4)
    white_mask = _strip_border_cols(white_mask)
    ocr_input = cv2.bitwise_not(white_mask.astype(np.uint8) * 255)
    return white_mask, ocr_input


def detect_enchant_slot_headers(content_bgr):
    """Detect enchant slot header lines using white-text color mask.

    Slot headers (e.g., '[접두] 충격을 (랭크 F)') use balanced white text
    that is distinguishable from colored effect text on any background theme.

    Algorithm:
      1. oreo_flip: white-pixel mask (bright & balanced) → invert
      2. Horizontal projection → run detection → merge with gap tolerance 2
      3. Filter: 8 <= height <= 15 AND total_white_px >= 150

    Args:
        content_bgr: BGR numpy array of the enchant content region

    Returns:
        List of (y_start, y_end) tuples (y_end exclusive) for detected bands.
    """
    white_mask, _ = _oreo_flip(content_bgr)

    wpr = white_mask.sum(axis=1)

    ROW_THRESHOLD = 10
    GAP_TOLERANCE = 2

    # Find runs of rows with sufficient white pixels
    runs = []
    in_run = False
    run_start = 0
    for y in range(len(wpr)):
        if wpr[y] >= ROW_THRESHOLD:
            if not in_run:
                run_start = y
                in_run = True
        else:
            if in_run:
                runs.append((run_start, y))
                in_run = False
    if in_run:
        runs.append((run_start, len(wpr)))

    # Merge runs separated by small gaps
    merged = []
    for start, end in runs:
        if merged and start - merged[-1][1] <= GAP_TOLERANCE:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append([start, end])

    # Filter by height and total white pixel count
    bands = []
    for start, end in merged:
        h = end - start
        total_px = int(wpr[start:end].sum())
        if 8 <= h <= 15 and total_px >= 150:
            bands.append((start, end))

    return bands


def _parse_effect_number(text):
    """Extract option_name and option_level from an effect text.

    Examples:
        '최대대미지 53 증가'                       → ('최대대미지', 53)
        '아르카나 스킬 보너스 대미지 1% 증가'      → ('아르카나 스킬 보너스 대미지', 1)
        '활성화된 아르카나의 전용 옵션일 때 효과 발동' → (None, None)

    Returns:
        (option_name, option_level) or (None, None) if no number found.
    """
    m = _EFFECT_NUM_RE.match(text.strip())
    if not m:
        return None, None
    name = m.group(1).strip()
    num_str = m.group(2)
    level = float(num_str) if '.' in num_str else int(num_str)
    return name, level


class MabinogiTooltipParser(TooltipLineSplitter):

    def __init__(self, config_path, output_dir="split_output"):
        super().__init__(output_dir)
        self.config = yaml.safe_load(Path(config_path).read_text())
        self.sections_config = self.config.get('sections', {})
        self.horizontal_split_factor = self.config.get('horizontal_split_factor', 3)
        # Build header pattern lookup: pattern_text → section_key
        self._header_patterns = {}
        for key, sec in self.sections_config.items():
            for pattern in sec.get('header_patterns', []):
                self._header_patterns[pattern] = key

    def parse_from_segments(self, tagged_segments, reader,
                            enchant_header_reader=None, crop_session_dir=None):
        """Build full structured result from segment_and_tag() output.

        Drop-in replacement for parse_tooltip() in the new segment-first pipeline.
        Section labels come from header OCR — no post-hoc pattern matching needed.

        Args:
            tagged_segments:       list of dicts from tooltip_segmenter.segment_and_tag()
            reader:                content OCR EasyOCR reader (custom_mabinogi, imgW patched)
            enchant_header_reader: optional dedicated enchant slot header OCR reader
                                   (custom_enchant_header). If None, falls back to content reader.
            crop_session_dir:      if set, each line dict will carry a '_crop' key
                                   (grayscale numpy array) for the caller to persist.

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

            section_data = self._parse_segment_from_array(
                content_crop, section, reader,
                enchant_header_reader=enchant_header_reader,
                attach_crops=crop_session_dir is not None)

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

    def _parse_segment_from_array(self, content_bgr, section, reader,
                                    enchant_header_reader=None,
                                    attach_crops=False):
        """Parse one content region (BGR numpy array) with a pre-known section label.

        Preprocessing: BT.601 grayscale → threshold=80 (mirrors frontend pipeline).
        Passes the binary image directly to line detection and OCR.

        Args:
            content_bgr:           numpy BGR array (content_crop from segment_and_tag)
            section:               section label string (e.g. 'enchant', 'reforge', 'pre_header')
            reader:                content OCR reader (custom_mabinogi, imgW patched)
            enchant_header_reader: optional dedicated enchant slot header reader

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

        # Enchant with white-mask bands: classify lines before OCR
        # to skip grey/description lines and save inference cost.
        sec_config = self.sections_config.get(section, {})
        parse_mode = sec_config.get('parse_mode')
        if parse_mode == 'enchant_options':
            slot_bands = detect_enchant_slot_headers(content_bgr)
            if slot_bands:
                return self._parse_enchant_with_bands(
                    content_bgr, binary, grouped, slot_bands, section, reader,
                    enchant_header_reader=enchant_header_reader,
                    attach_crops=attach_crops)

        # All other sections: OCR every line
        _save = os.environ.get('SAVE_OCR_CROPS')
        ocr_results    = self._ocr_grouped_lines(binary, grouped, reader,
                                                  save_crops_dir=_save,
                                                  save_label=f'content_{section}',
                                                  attach_crops=attach_crops)

        for line in ocr_results:
            line['section'] = section

        if section == 'pre_header':
            return self._parse_pre_header(ocr_results)

        if sec_config.get('skip', False):
            return {'skipped': True, 'line_count': len(ocr_results)}

        if parse_mode == 'color_parts':
            return self._parse_color_section(ocr_results)
        if parse_mode == 'reforge_options':
            return self._parse_reforge_section(ocr_results)
        if parse_mode == 'enchant_options':
            # Fallback: no bands detected, regex-based header detection
            return self._parse_enchant_section(ocr_results)

        return {
            'lines': [
                {'text': l['text'], 'confidence': l['confidence'],
                 'bounds': l['bounds'], 'section': l.get('section', section),
                 'ocr_model': l.get('ocr_model', '')}
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
        _save = os.environ.get('SAVE_OCR_CROPS')
        ocr_results = self._ocr_grouped_lines(img, grouped, reader,
                                               save_crops_dir=_save,
                                               save_label='content_v2')

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

    def _ocr_grouped_lines(self, img, grouped_lines, reader,
                           save_crops_dir=None, save_label='content',
                           attach_crops=False):
        """Run OCR on each grouped line, merging sub-line results.

        Args:
            img: Original BGR image
            grouped_lines: list of sub-line groups from _group_by_y()
            reader: EasyOCR Reader instance
            save_crops_dir: if set, save each crop to this directory before OCR
            save_label: label embedded in saved filenames (e.g. 'content_reforge')
            attach_crops: if True, attach grayscale crop as '_crop' on each result

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

                if save_crops_dir:
                    os.makedirs(save_crops_dir, exist_ok=True)
                    _n = len([f for f in os.listdir(save_crops_dir) if f.endswith('.png')])
                    cv2.imwrite(os.path.join(save_crops_dir, f'{_n:03d}_{save_label}.png'), gray)

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

                # Track which model won (DualReader sets last_model_names)
                model_name = ''
                if hasattr(reader, 'last_model_names') and reader.last_model_names:
                    model_name = reader.last_model_names[0]

                sub_texts.append(text)
                sub_confs.append(confidence)
                sub_details.append({
                    'text': text,
                    'confidence': float(confidence),
                    'bounds': line_info,
                    'ocr_model': model_name,
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

            # Use the model from the first sub-line (or most common if multiple)
            ocr_model = sub_details[0].get('ocr_model', '') if sub_details else ''

            entry = {
                'text': merged_text,
                'confidence': float(avg_conf),
                'sub_count': len(group),
                'bounds': merged_bounds,
                'sub_lines': sub_details,
                'ocr_model': ocr_model,
            }

            # Attach full-width line crop for correction training
            if attach_crops:
                mb = merged_bounds
                pad_y = max(1, mb['height'] // 5)
                pad_x = max(2, mb['height'] // 3)
                y0 = max(0, mb['y'] - pad_y)
                y1 = min(img.shape[0], mb['y'] + mb['height'] + pad_y)
                x0 = max(0, mb['x'] - pad_x)
                x1 = min(img.shape[1], mb['x'] + mb['width'] + pad_x)
                crop_region = img[y0:y1, x0:x1]
                if len(crop_region.shape) == 3:
                    crop_region = cv2.cvtColor(crop_region, cv2.COLOR_BGR2GRAY)
                entry['_crop'] = crop_region

            results.append(entry)

        return results

    def _ocr_enchant_headers(self, content_bgr, binary,
                             header_classifications, bands, reader,
                             save_crops_dir=None):
        """OCR enchant slot headers using white-mask band bounds.

        Instead of using line-splitter bounds (which include UI borders and
        pink rank text), crops are derived from the white-mask bands that
        originally detected the headers.  This produces tight crops matching
        only the white text visible in the slot header.

        Args:
            content_bgr:  BGR enchant content region (for building white mask)
            binary:       preprocessed binary (black text on white)
            header_classifications: list of (group, bounds, 'header') tuples
            bands:        list of (y_start, y_end) from detect_enchant_slot_headers()
            reader:       EasyOCR reader for enchant headers
            save_crops_dir: if set, save each crop before OCR

        Returns:
            list of dicts matching _ocr_grouped_lines output format
        """
        white_mask, ocr_source = _oreo_flip(content_bgr)

        img_h, img_w = ocr_source.shape[:2]
        results = []

        for group, bounds, _ in header_classifications:
            y_line = bounds['y']
            h_line = bounds['height']

            # Find overlapping band
            matched_band = None
            for bs, be in bands:
                if min(y_line + h_line, be) - max(y_line, bs) > 0:
                    matched_band = (bs, be)
                    break

            if matched_band is None:
                # Fallback: use line-splitter bounds (shouldn't happen)
                batch = self._ocr_grouped_lines(binary, [group], reader,
                                                save_crops_dir=save_crops_dir)
                results.extend(batch)
                continue

            bs, be = matched_band

            # Find x extent of white pixels within the band rows.
            # Require >= 3 white pixels per column to filter stray border pixels.
            band_mask = white_mask[bs:be, :]
            col_counts = band_mask.sum(axis=0)
            white_cols = np.where(col_counts >= 3)[0]
            if len(white_cols) == 0:
                # No white pixels found — fallback
                batch = self._ocr_grouped_lines(binary, [group], reader,
                                                save_crops_dir=save_crops_dir)
                results.extend(batch)
                continue

            x_start = int(white_cols[0])
            x_end = int(white_cols[-1]) + 1

            # Apply proportional padding (matching _ocr_grouped_lines formula)
            text_h = be - bs
            pad_x = max(2, text_h // 3)
            pad_y = max(1, text_h // 5)
            x_pad = max(0, x_start - pad_x)
            y_pad = max(0, bs - pad_y)
            w_pad = min(img_w - x_pad, (x_end - x_start) + 2 * pad_x)
            h_pad = min(img_h - y_pad, text_h + 2 * pad_y)

            # Crop from inverted white mask
            crop = ocr_source[y_pad:y_pad + h_pad, x_pad:x_pad + w_pad]
            gray = crop

            ch, cw = gray.shape
            if ch == 0 or cw == 0:
                results.append({
                    'text': '', 'confidence': 0.0,
                    'sub_count': len(group), 'bounds': bounds, 'sub_lines': [],
                })
                continue

            if save_crops_dir:
                os.makedirs(save_crops_dir, exist_ok=True)
                _n = len([f for f in os.listdir(save_crops_dir) if f.endswith('.png')])
                cv2.imwrite(os.path.join(save_crops_dir, f'{_n:03d}_enchant_hdr.png'), gray)

            ocr_results = reader.recognize(
                gray,
                horizontal_list=[[0, cw, 0, ch]],
                free_list=[],
                reformat=False,
                detail=1,
            )

            if ocr_results:
                _, text, confidence = ocr_results[0]
            else:
                text, confidence = '', 0.0

            results.append({
                'text': text,
                'confidence': float(confidence),
                'sub_count': len(group),
                'bounds': bounds,
                'sub_lines': [],
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

    @staticmethod
    def _detect_sub_lines_by_indent(lines):
        """Tag lines as sub-lines based on x-offset from section baseline.

        Lines indented significantly from the minimum x position are tagged
        is_reforge_sub=True. Falls back to ㄴ prefix detection.

        Resolution-independent: uses relative threshold (offset > min_x).
        """
        content_lines = [l for l in lines if not l.get('is_header')]
        if content_lines:
            min_x = min(l.get('bounds', {}).get('x', 0) for l in content_lines)
        else:
            min_x = 0

        for line in lines:
            if line.get('is_header'):
                continue
            # Skip lines already tagged as reforge option headers
            if 'reforge_name' in line:
                continue
            line_x = line.get('bounds', {}).get('x', 0)
            is_indented = (line_x - min_x) > min_x and min_x > 0
            line['is_reforge_sub'] = is_indented or bool(_REFORGE_SUB_RE.match(line.get('text', '')))

    def _parse_reforge_section(self, lines):
        """Parse reforge section into structured option records.

        Each reforge option is a main line (at baseline x), optionally followed
        by an indented sub-bullet describing the effect. Some options have a
        '(current/max 레벨)' level suffix, others don't.

        Tags each line dict with metadata for FM and DB storage:
          main line with levels:    reforge_name, reforge_level, reforge_max_level, is_reforge_sub=False
          main line without levels: reforge_name (text as-is), is_reforge_sub=False
          sub-bullet:               is_reforge_sub=True

        Returns:
            {'options': [{name, level, max_level, option_name, option_level, effect}], 'lines': lines}
        """
        # First pass: detect level-suffixed options via regex
        for line in lines:
            text = line.get('text', '')
            m = _REFORGE_HEADER_RE.match(text)
            if m:
                line['reforge_name']      = m.group(1).strip().lstrip('-').strip()
                line['reforge_level']     = int(m.group(2))
                line['reforge_max_level'] = int(m.group(3))
                line['is_reforge_sub']    = False

        # Second pass: detect sub-lines by indent
        self._detect_sub_lines_by_indent(lines)

        # Third pass: non-indented lines without reforge_name are level-less options
        for line in lines:
            if line.get('is_header'):
                continue
            if 'reforge_name' in line:
                continue
            if line.get('is_reforge_sub'):
                continue
            text = line.get('text', '').strip().lstrip('-').strip()
            if text:
                line['reforge_name']      = text
                line['reforge_level']     = None
                line['reforge_max_level'] = None
                line['is_reforge_sub']    = False

        result = self.build_reforge_structured(lines)
        result['lines'] = lines
        return result

    def build_reforge_structured(self, lines):
        """Build reforge options array from tagged lines.

        Call after FM correction to get option_name from corrected text.
        Lines must already be tagged by _parse_reforge_section.

        Returns:
            {'options': [{name, level, max_level, option_name, option_level, effect}]}
        """
        options = []
        current = None

        for line in lines:
            if line.get('is_header'):
                continue

            text = line.get('text', '')

            if not line.get('is_reforge_sub', True) and 'reforge_name' in line:
                m = _REFORGE_HEADER_RE.match(text)
                if m:
                    name      = m.group(1).strip().lstrip('-').strip()
                    level     = int(m.group(2))
                    max_level = int(m.group(3))
                else:
                    name      = text.strip().lstrip('-').strip() or line['reforge_name']
                    level     = line.get('reforge_level')
                    max_level = line.get('reforge_max_level')

                current = {
                    'name':         name,
                    'level':        level,
                    'max_level':    max_level,
                    'option_name':  name,
                    'option_level': level,
                    'effect':       None,
                }
                options.append(current)

            elif line.get('is_reforge_sub') and current is not None:
                effect = _REFORGE_SUB_RE.sub('', text).strip()
                current['effect'] = effect

        return {'options': options}

    def _parse_enchant_with_bands(self, content_bgr, binary, grouped,
                                    bands, section, reader,
                                    enchant_header_reader=None,
                                    attach_crops=False):
        """Parse enchant section with white-mask bands.

        Classifies each line group as header/effect/grey BEFORE OCR.
        Grey lines are skipped entirely. Headers and effects are OCR'd.
        Slot headers use the dedicated enchant_header_reader if available,
        falling back to the general content reader.

        Args:
            content_bgr:           BGR numpy array of the enchant content region
            binary:                preprocessed binary (black text on white)
            grouped:               line groups from _group_by_y()
            bands:                 slot header bands from detect_enchant_slot_headers()
            section:               section label ('enchant')
            reader:                content OCR reader
            enchant_header_reader: optional dedicated enchant slot header reader

        Returns:
            section data dict with prefix/suffix + lines
        """
        # 1. Classify each group
        classifications = []  # (group, merged_bounds, line_type)
        for group in grouped:
            first = group[0]
            last = group[-1]
            merged_bounds = {
                'x': first['x'],
                'y': first['y'],
                'width': (last['x'] + last['width']) - first['x'],
                'height': first['height'],
            }
            line_type = classify_enchant_line(content_bgr, merged_bounds, bands)
            classifications.append((group, merged_bounds, line_type))

        # 2. Batch OCR: headers and effects separately (may use different readers)
        #    Headers use white-mask band bounds for cropping (no border artifacts,
        #    no pink rank text). Effects use line-splitter bounds from binary.
        header_classifications = [(g, b, lt) for g, b, lt in classifications if lt == 'header']
        effect_groups = [g for g, _, lt in classifications if lt == 'effect']

        hdr_reader = enchant_header_reader if enchant_header_reader is not None else reader
        _save = os.environ.get('SAVE_OCR_CROPS')
        header_batch = (self._ocr_enchant_headers(
                            content_bgr, binary, header_classifications, bands,
                            hdr_reader, save_crops_dir=_save)
                        if header_classifications else [])
        effect_batch = (self._ocr_grouped_lines(binary, effect_groups, reader,
                                                save_crops_dir=_save,
                                                save_label='content_enchant',
                                                attach_crops=attach_crops)
                        if effect_groups else [])

        header_iter = iter(header_batch)
        effect_iter = iter(effect_batch)

        # 3. Assemble results — determine slot from position, not OCR text.
        #    Mabinogi tooltip: prefix always first, suffix second.
        #    Grey lines above first header → prefix slot is empty → header is suffix.
        hdr_model_name = ('enchant_header' if enchant_header_reader is not None
                          else 'general')
        n_headers = sum(1 for _, _, lt in classifications if lt == 'header')
        if n_headers == 2:
            slot_queue = ['접두', '접미']
        elif n_headers == 1:
            # Check if grey lines appear before the first header
            first_hdr_y = next(b['y'] for _, b, lt in classifications if lt == 'header')
            grey_above = any(lt == 'grey' and b['y'] < first_hdr_y
                             for _, b, lt in classifications)
            slot_queue = ['접미'] if grey_above else ['접두']
        else:
            slot_queue = []

        slot_iter = iter(slot_queue)
        ocr_results = []
        for group, bounds, line_type in classifications:
            if line_type == 'grey':
                ocr_results.append({
                    'text': '',
                    'confidence': 0.0,
                    'sub_count': len(group),
                    'bounds': bounds,
                    'sub_lines': [],
                    'section': section,
                    'is_enchant_hdr': False,
                    'is_grey': True,
                    'ocr_model': '',
                })
            elif line_type == 'header':
                line = next(header_iter)
                line['section'] = section
                line['is_enchant_hdr'] = True
                line['ocr_model'] = hdr_model_name
                line['enchant_slot'] = next(slot_iter, '')
                line['enchant_name'] = ''
                line['enchant_rank'] = ''
                ocr_results.append(line)
            else:  # effect
                line = next(effect_iter)
                line['section'] = section
                line['is_enchant_hdr'] = False
                line['ocr_model'] = 'general'
                ocr_results.append(line)

        result = self.build_enchant_structured(ocr_results)
        result['lines'] = ocr_results
        return result

    def _parse_enchant_section(self, lines):
        """Parse enchant section into prefix/suffix slot records.

        Each enchant is a header '[접두|접미] NAME (랭크 RANK)' followed by
        effect lines starting with '-'.

        Tags each line dict with metadata for FM and DB storage:
          header line: enchant_slot, enchant_name, enchant_rank, is_enchant_hdr=True
          effect line: is_enchant_hdr=False

        Returns:
            {'prefix': {text, name, rank, effects} | None,
             'suffix': {text, name, rank, effects} | None,
             'lines': lines}
        """
        for line in lines:
            text = line.get('text', '')
            m = _ENCHANT_HEADER_RE.match(text)
            if m:
                line['enchant_slot']   = m.group(1)
                line['enchant_name']   = m.group(2).strip()
                line['enchant_rank']   = m.group(3)
                line['is_enchant_hdr'] = True
            else:
                line['is_enchant_hdr'] = False

        result = self.build_enchant_structured(lines)
        result['lines'] = lines
        return result

    def build_enchant_structured(self, lines):
        """Build enchant prefix/suffix dicts from tagged lines.

        Call after FM correction to get names/effects from corrected text.
        Lines must already be tagged by _parse_enchant_section.

        Each effect is a dict with 'text' and optional 'option_name'/'option_level'
        extracted by _parse_effect_number().

        Returns:
            {'prefix': {text, name, rank, effects} | None,
             'suffix': {text, name, rank, effects} | None}
        """
        prefix = None
        suffix = None
        current = None

        for line in lines:
            if line.get('is_header'):
                continue

            if line.get('is_enchant_hdr'):
                text = line['text']
                m = _ENCHANT_HEADER_RE.match(text)
                if m:
                    name = m.group(2).strip()
                    rank = m.group(3)
                else:
                    name = line.get('enchant_name', '')
                    rank = line.get('enchant_rank', '')

                # Enrich text with rank from DB if available but not in OCR output
                display_text = text
                if name and rank and '랭크' not in text:
                    display_text = f"[{line.get('enchant_slot', '접두')}] {name} (랭크 {rank})"

                current = {'text': display_text, 'name': name, 'rank': rank, 'effects': []}
                slot = line.get('enchant_slot', '')
                if slot == '접두':
                    prefix = current
                elif slot == '접미':
                    suffix = current

            elif current is not None:
                eff_text = line['text'].strip().lstrip('-').strip()
                if eff_text:
                    entry = {'text': eff_text}
                    opt_name, opt_level = _parse_effect_number(eff_text)
                    if opt_name is not None:
                        entry['option_name']  = opt_name
                        entry['option_level'] = opt_level
                    current['effects'].append(entry)

        return {'prefix': prefix, 'suffix': suffix}

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
