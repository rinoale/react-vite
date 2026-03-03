"""PreHeaderHandler: dual-font preprocessing+OCR, item name parsing."""

import os

import cv2
import numpy as np

from lib.utils.log import logger
from lib.pipeline.line_split import group_by_y
from ._ocr import ocr_grouped_lines

# Known mabinogi_classic.ttf text colors in tooltips (RGB).
_MABINOGI_CLASSIC_COLORS = [
    (255, 252, 157),  # yellow (item name, emphasis)
    (255, 255, 255),  # white (general text)
]


def _mabinogi_classic_mask(img_bgr, tolerance=5):
    """Create a binary mask of pixels matching known mabinogi_classic font colors."""
    mask = np.zeros(img_bgr.shape[:2], dtype=np.uint8)
    for r, g, b in _MABINOGI_CLASSIC_COLORS:
        bgr = np.array([b, g, r], dtype=np.int16)
        diff = np.abs(img_bgr.astype(np.int16) - bgr)
        match = np.all(diff <= tolerance, axis=2)
        mask[match] = 255
    return mask


def _preprocess_mabinogi_classic(content_bgr):
    """Color-mask preprocessing for mabinogi_classic font.

    Isolates white/yellow text pixels, then inverts to black-text-on-white.
    Returns (detect_binary, ocr_binary).
    """
    mask = _mabinogi_classic_mask(content_bgr)
    return mask, cv2.bitwise_not(mask)


def _preprocess_nanum_gothic(content_bgr):
    """HSV yellow-isolate + threshold 120 preprocessing for nanum_gothic text.

    Isolates yellow-hued pixels while preserving white/gray text.
    Returns (detect_binary, ocr_binary).
    """
    hsv = cv2.cvtColor(content_bgr, cv2.COLOR_BGR2HSV)
    h = hsv[:, :, 0]
    s = hsv[:, :, 1]

    sat_mask = s >= 38
    not_yellow = ~((h >= 15) & (h <= 45))
    reject_mask = sat_mask & not_yellow

    masked = content_bgr.copy()
    masked[reject_mask] = 0

    gray = cv2.cvtColor(masked, cv2.COLOR_BGR2GRAY)
    _, ocr_binary = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY_INV)
    detect_binary = cv2.bitwise_not(ocr_binary)
    return detect_binary, ocr_binary


def _ocr_pre_header_image(detect_binary, ocr_binary, splitter, reader,
                          save_label, save_crops_dir, attach_crops):
    """Run line detection + OCR on a preprocessed pre_header image."""
    detected = splitter.detect_text_lines(detect_binary)
    grouped = group_by_y(detected)
    return ocr_grouped_lines(
        ocr_binary, grouped, reader,
        save_crops_dir=save_crops_dir, save_label=save_label,
        attach_crops=attach_crops)


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

        mc_detect, mc_ocr = _preprocess_mabinogi_classic(content_bgr)
        ng_detect, ng_ocr = _preprocess_nanum_gothic(content_bgr)

        mc_results = _ocr_pre_header_image(
            mc_detect, mc_ocr, splitter, pipeline['preheader_mc_reader'],
            'pre_header_mc', _save, attach)
        ng_results = _ocr_pre_header_image(
            ng_detect, ng_ocr, splitter, pipeline['preheader_ng_reader'],
            'pre_header_ng', _save, attach)

        ocr_results = _pick_best_per_line(mc_results, ng_results)
        for line in ocr_results:
            line['section'] = 'pre_header'

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

        # Parse item name from first line, apply FM from parsed components
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
