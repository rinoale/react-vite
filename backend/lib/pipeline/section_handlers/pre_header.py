"""PreHeaderHandler: dual-font preprocessing+OCR, item name parsing."""

import os

import cv2
import numpy as np

from lib.utils.log import logger
from lib.image_processors.mabinogi_processor import (
    _HSV_SATURATION_THRESHOLD,
    _YELLOW_BINARY_THRESHOLD,
)

# Pre-header uses a wider yellow hue range than mabinogi_processor (25-40)
# to capture the full range of nanum_gothic tooltip text colors.
_PREHEADER_YELLOW_HUE_MIN = 15
_PREHEADER_YELLOW_HUE_MAX = 45
from lib.pipeline.line_split import group_by_y
from ._ocr import (
    ocr_grouped_lines,
    _PAD_HORIZONTAL_DIVISOR, _PAD_HORIZONTAL_MINIMUM,
)

# Maximum content width before horizontal splitting (matches model imgW).
_MAX_CONTENT_WIDTH = 200

# Minimum word-space gap width (pixels) to consider as a split point.
_MIN_SPACE_GAP = 3

# Maximum vertical gap between consecutive lines to merge as one block.
_MAX_NEXTLINE_GAP = 1

# Known mabinogi_classic.ttf text colors in tooltips (RGB).
_MABINOGI_CLASSIC_COLORS = [
    (255, 252, 157),  # yellow (item name, emphasis)
    (255, 255, 255),  # white (general text)
]


def _preprocess_mabinogi_classic(content_bgr, tolerance=5):
    """Color-mask preprocessing for mabinogi_classic font.

    Isolates white/yellow text pixels as black ink on white background.
    Returns ocr_binary (ink=0, background=255).
    """
    ocr_binary = np.full(content_bgr.shape[:2], 255, dtype=np.uint8)
    img16 = content_bgr.astype(np.int16)
    for r, g, b in _MABINOGI_CLASSIC_COLORS:
        target = np.array([b, g, r], dtype=np.int16)
        match = np.all(np.abs(img16 - target) <= tolerance, axis=2)
        ocr_binary[match] = 0
    return ocr_binary


def _preprocess_nanum_gothic(content_bgr):
    """HSV yellow-isolate + threshold 120 preprocessing for nanum_gothic text.

    Isolates yellow-hued pixels while preserving white/gray text.
    Returns ocr_binary (ink=0, background=255).
    """
    hsv = cv2.cvtColor(content_bgr, cv2.COLOR_BGR2HSV)
    h = hsv[:, :, 0]
    s = hsv[:, :, 1]

    sat_mask = s >= _HSV_SATURATION_THRESHOLD
    not_yellow = ~((h >= _PREHEADER_YELLOW_HUE_MIN) & (h <= _PREHEADER_YELLOW_HUE_MAX))
    reject_mask = sat_mask & not_yellow

    masked = content_bgr.copy()
    masked[reject_mask] = 0

    gray = cv2.cvtColor(masked, cv2.COLOR_BGR2GRAY)
    _, ocr_binary = cv2.threshold(gray, _YELLOW_BINARY_THRESHOLD, 255, cv2.THRESH_BINARY_INV)
    return ocr_binary


def _find_word_spaces(gray_crop):
    """Find word-space gaps in a line crop (columns with zero ink).

    Returns list of (gap_start, gap_end) for gaps >= _MIN_SPACE_GAP.
    """
    col_ink = (gray_crop < 128).astype(np.uint8).sum(axis=0)
    in_gap = False
    spaces = []
    start = 0
    for i, v in enumerate(col_ink):
        if v == 0 and not in_gap:
            start = i
            in_gap = True
        elif v > 0 and in_gap:
            if i - start >= _MIN_SPACE_GAP:
                spaces.append((start, i))
            in_gap = False
    return spaces


def _split_and_ocr(gray_crop, reader, max_content):
    """Right-long horizontal split: split words off the left until right fits.

    Finds the earliest word-space where the right portion fits under
    max_content. If the left portion also exceeds, recurse.
    Returns merged OCR text and average confidence.
    """
    h, w = gray_crop.shape
    if w <= max_content:
        pad_x = max(_PAD_HORIZONTAL_MINIMUM, h // _PAD_HORIZONTAL_DIVISOR)
        padded = np.full((h, w + 2 * pad_x), 255, dtype=np.uint8)
        padded[:, pad_x:pad_x + w] = gray_crop
        ch, cw = padded.shape
        results = reader.recognize(
            padded, horizontal_list=[[0, cw, 0, ch]],
            free_list=[], reformat=False, detail=1)
        if results:
            _, text, conf = results[0]
            return text, conf
        return '', 0.0

    spaces = _find_word_spaces(gray_crop)
    if not spaces:
        # No word spaces — can't split, OCR as-is
        pad_x = max(_PAD_HORIZONTAL_MINIMUM, h // _PAD_HORIZONTAL_DIVISOR)
        padded = np.full((h, w + 2 * pad_x), 255, dtype=np.uint8)
        padded[:, pad_x:pad_x + w] = gray_crop
        ch, cw = padded.shape
        results = reader.recognize(
            padded, horizontal_list=[[0, cw, 0, ch]],
            free_list=[], reformat=False, detail=1)
        if results:
            _, text, conf = results[0]
            return text, conf
        return '', 0.0

    # Right-long: find earliest split where right chunk fits
    split_space = None
    for gap_start, gap_end in spaces:
        right_w = w - gap_end
        if right_w <= max_content:
            split_space = (gap_start, gap_end)
            break

    if split_space is None:
        # No single split makes the right fit — take last space
        split_space = spaces[-1]

    gap_start, gap_end = split_space
    left_crop = gray_crop[:, :gap_start]
    right_crop = gray_crop[:, gap_end:]

    # Recurse on each chunk
    left_text, left_conf = _split_and_ocr(left_crop, reader, max_content)
    right_text, right_conf = _split_and_ocr(right_crop, reader, max_content)

    merged_text = f"{left_text} {right_text}".strip()
    avg_conf = (left_conf + right_conf) / 2 if (left_text and right_text) else max(left_conf, right_conf)
    return merged_text, avg_conf


def _ocr_pre_header_image(ocr_binary, splitter, reader,
                          save_label, save_crops_dir, attach_crops):
    """Run line detection + OCR on a preprocessed pre_header image.

    Lines wider than _MAX_CONTENT_WIDTH are horizontally split (right-long)
    so each chunk fits within the model's imgW.
    """
    detected = splitter.detect_centered_lines(ocr_binary)
    grouped = group_by_y(detected)

    h_img = ocr_binary.shape[0]
    pad_x = max(_PAD_HORIZONTAL_MINIMUM, 13 // _PAD_HORIZONTAL_DIVISOR)
    max_content = _MAX_CONTENT_WIDTH - 2 * pad_x

    # Check if any line needs splitting
    needs_split = False
    for group in grouped:
        w = group[0]['width']
        if w + 2 * pad_x > _MAX_CONTENT_WIDTH:
            needs_split = True
            break

    if not needs_split:
        return ocr_grouped_lines(
            ocr_binary, grouped, reader,
            save_crops_dir=save_crops_dir, save_label=save_label,
            attach_crops=attach_crops)

    # Split-and-OCR path for wide lines
    from lib.pipeline.line_split import merge_group_bounds
    results = []
    for group in grouped:
        bounds = merge_group_bounds(group)
        x, y, w, h = bounds['x'], bounds['y'], bounds['width'], bounds['height']

        line_crop = ocr_binary[y:y + h, x:x + w]
        # Convert to grayscale if needed
        if len(line_crop.shape) == 3:
            gray = cv2.cvtColor(line_crop, cv2.COLOR_BGR2GRAY)
        else:
            gray = line_crop

        if w + 2 * pad_x > _MAX_CONTENT_WIDTH:
            text, conf = _split_and_ocr(gray, reader, max_content)
        else:
            # Normal OCR with padding
            padded = np.full((h, w + 2 * pad_x), 255, dtype=np.uint8)
            padded[:, pad_x:pad_x + w] = gray
            ch, cw = padded.shape
            ocr_out = reader.recognize(
                padded, horizontal_list=[[0, cw, 0, ch]],
                free_list=[], reformat=False, detail=1)
            if ocr_out:
                _, text, conf = ocr_out[0]
            else:
                text, conf = '', 0.0

        results.append({
            'text': text,
            'confidence': float(conf),
            'sub_count': len(group),
            'bounds': bounds,
            'sub_lines': [],
            'ocr_model': '',
            '_prefix_type': None,
        })

    return results


def _pick_best_per_line(mc_results, ng_results):
    """Pick the higher-confidence OCR result per line from two preprocessing paths.

    Lines are matched by vertical position (bounds['y']).
    Tie-breaking: mabinogi_classic wins (more common font in tooltips).
    """
    def _y_key(line):
        return line.get('bounds', {}).get('y', 0)

    mc_by_y = {_y_key(line): line for line in mc_results}
    ng_by_y = {_y_key(line): line for line in ng_results}

    merged = []
    for y in sorted(set(mc_by_y) | set(ng_by_y)):
        mc_line = mc_by_y.get(y)
        ng_line = ng_by_y.get(y)

        if mc_line and ng_line:
            if ng_line.get('confidence', 0) > mc_line.get('confidence', 0):
                ng_line['preprocess'] = 'nanum_gothic'
                merged.append(ng_line)
            else:
                mc_line['preprocess'] = 'mabinogi_classic'
                merged.append(mc_line)
        elif mc_line:
            mc_line['preprocess'] = 'mabinogi_classic'
            merged.append(mc_line)
        else:
            ng_line['preprocess'] = 'nanum_gothic'
            merged.append(ng_line)

    return merged


def _merge_nextlines(ocr_results):
    """Merge consecutive lines with vertical gap <= _MAX_NEXTLINE_GAP.

    The game wraps long item names across multiple lines with gap=0.
    This merges them into a single line before parse_item_name().
    """
    if len(ocr_results) <= 1:
        return ocr_results

    merged = [ocr_results[0]]
    for line in ocr_results[1:]:
        prev = merged[-1]
        prev_bottom = prev['bounds']['y'] + prev['bounds']['height']
        gap = line['bounds']['y'] - prev_bottom

        if gap <= _MAX_NEXTLINE_GAP:
            prev['text'] = f"{prev['text']} {line['text']}".strip()
            prev['confidence'] = (prev['confidence'] + line['confidence']) / 2
            prev['bounds'] = {
                'x': min(prev['bounds']['x'], line['bounds']['x']),
                'y': prev['bounds']['y'],
                'width': max(
                    prev['bounds']['x'] + prev['bounds']['width'],
                    line['bounds']['x'] + line['bounds']['width'],
                ) - min(prev['bounds']['x'], line['bounds']['x']),
                'height': line['bounds']['y'] + line['bounds']['height'] - prev['bounds']['y'],
            }
            prev['sub_count'] = prev.get('sub_count', 1) + line.get('sub_count', 1)
        else:
            merged.append(line)

    return merged


class PreHeaderHandler:
    """Dual-font preprocessing+OCR, no prefix detection, parse_item_name."""

    def process(self, seg, *, crop_session_dir=None):
        """Full pre_header lifecycle: preprocess → OCR → item name parse.

        Returns (section_data, detected_font).
        """
        from lib.pipeline.v3 import get_pipeline

        pipeline = get_pipeline()
        parser = pipeline['parser']
        splitter = pipeline['splitter']
        corrector = pipeline['corrector']

        if not seg:
            return {'lines': []}, 'mabinogi_classic'

        content_bgr = seg['content_crop']
        _save = os.environ.get('SAVE_OCR_CROPS')
        attach = crop_session_dir is not None

        mc_ocr = _preprocess_mabinogi_classic(content_bgr)
        ng_ocr = _preprocess_nanum_gothic(content_bgr)

        mc_results = _ocr_pre_header_image(
            mc_ocr, splitter, pipeline['preheader_mc_reader'],
            'pre_header_mc', _save, attach)
        ng_results = _ocr_pre_header_image(
            ng_ocr, splitter, pipeline['preheader_ng_reader'],
            'pre_header_ng', _save, attach)

        ocr_results = _pick_best_per_line(mc_results, ng_results)
        for line in ocr_results:
            line['section'] = 'pre_header'

        # Merge nextlined item name: consecutive lines with gap <= 1
        ocr_results = _merge_nextlines(ocr_results)

        sections = parser._parse_pre_header(ocr_results)
        section_data = sections.get('pre_header', {'lines': []})
        lines = section_data.get('lines', [])

        mc_count = sum(1 for l in ocr_results if l.get('preprocess') == 'mabinogi_classic')
        ng_count = sum(1 for l in ocr_results if l.get('preprocess') == 'nanum_gothic')
        detected_font = 'nanum_gothic' if ng_count > mc_count else 'mabinogi_classic'

        # Snapshot raw text
        for line in lines:
            line['raw_text'] = line.get('text', '')
            line['fm_applied'] = False

        # Parse item name from merged first line, apply FM from parsed components
        if lines:
            first_text = lines[0].get('text', '')
            if first_text:
                parsed = corrector.parse_item_name(first_text)

                # Promote structured fields to section-level metadata
                section_data['item_name'] = parsed.get('item_name')
                section_data['enchant_prefix'] = parsed.get('enchant_prefix')
                section_data['enchant_suffix'] = parsed.get('enchant_suffix')

                # Reconstruct corrected text from fuzzy-matched components
                parts = []
                if parsed.get('_holywater'):
                    parts.append(parsed['_holywater'])
                if parsed.get('enchant_prefix'):
                    parts.append(parsed['enchant_prefix'])
                if parsed.get('enchant_suffix'):
                    parts.append(parsed['enchant_suffix'])
                if parsed.get('_ego'):
                    parts.append('정령')
                parts.append(parsed['item_name'])
                fm_text = ' '.join(parts)

                if fm_text != first_text:
                    lines[0]['text'] = fm_text
                    lines[0]['fm_applied'] = True

        logger.info("v3 pre_header  %d lines  font=%s", len(lines), detected_font)
        return section_data, detected_font
