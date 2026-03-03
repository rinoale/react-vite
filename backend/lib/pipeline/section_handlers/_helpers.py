"""Shared helpers for section handlers."""

import os
from functools import wraps

import cv2

from lib.pipeline.line_split import group_by_y
from lib.image_processors.prefix_detector import BULLET_DETECTOR, SUBBULLET_DETECTOR
from ._ocr import ocr_grouped_lines


def bt601_binary(content_bgr, threshold=80):
    """BT.601 grayscale + threshold → (detect_binary, ocr_binary)."""
    gray = cv2.cvtColor(content_bgr, cv2.COLOR_BGR2GRAY)
    _, ocr_binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY_INV)
    detect_binary = cv2.bitwise_not(ocr_binary)
    return detect_binary, ocr_binary


def bt601_preprocessed(fn):
    """Decorator: run BT.601 binarization on seg['content_crop'] before handler.

    Enriches seg with 'detect_binary' and 'ocr_binary'.
    Original 'content_crop' (BGR) is preserved.
    """
    @wraps(fn)
    def wrapper(self, seg, **kw):
        seg['detect_binary'], seg['ocr_binary'] = bt601_binary(seg['content_crop'])
        return fn(self, seg, **kw)
    return wrapper


def ocr_lines(parser, splitter, detect_binary, ocr_binary, reader, section,
              content_bgr=None, attach_crops=False):
    """Line detect → group → prefix detect → OCR.  Returns list of line dicts."""
    detected = splitter.detect_text_lines(detect_binary)
    grouped = group_by_y(detected)

    _save = os.environ.get('SAVE_OCR_CROPS')
    sec_config = parser.sections_config.get(section, {})
    prefix_kw = {}
    if not sec_config.get('skip', False) and content_bgr is not None:
        prefix_kw = {'prefix_bgr': content_bgr,
                     'prefix_configs': [BULLET_DETECTOR, SUBBULLET_DETECTOR]}
    ocr_results = ocr_grouped_lines(
        ocr_binary, grouped, reader,
        save_crops_dir=_save,
        save_label=f'content_{section}',
        attach_crops=attach_crops,
        **prefix_kw)

    for line in ocr_results:
        line['section'] = section
    return ocr_results


def apply_line_fm(line, corrector, section, cutoff=80):
    """Apply FM to a single non-enchant content line.  Mutates line in place."""
    raw_text = line.get('text', '')
    if not raw_text.strip() or line.get('is_header'):
        line['fm_applied'] = False
        return

    # FM only for bullet-prefixed lines (skip sub-bullets and unprefixed)
    if line.get('_prefix_type') != 'bullet':
        line['fm_applied'] = False
        return

    if section not in corrector._section_norm_cache:
        line['fm_applied'] = False
        return

    fm_text, fm_score, paren_range = corrector.correct_normalized(
        raw_text, section=section, cutoff_score=cutoff)

    if fm_score > 0:
        line['text'] = fm_text
        line['fm_applied'] = True
        if paren_range:
            line['detail_range'] = paren_range
    elif fm_score < 0 and fm_score not in (-2, -3):
        line['fm_applied'] = False
        line['fm_rejected'] = fm_text
        line['fm_rejected_score'] = -fm_score
    else:
        line['fm_applied'] = False


def prepend_header(seg, section, section_data):
    """Insert the orange header OCR text as line 0 if present."""
    if seg['header_crop'] is not None and seg.get('header_ocr_text'):
        header_line = {
            'text':       seg['header_ocr_text'],
            'confidence': seg['header_ocr_conf'],
            'bounds':     {},
            'section':    section,
            'is_header':  True,
        }
        section_data.setdefault('lines', []).insert(0, header_line)


def snapshot_and_strip(lines, corrector):
    """Snapshot raw_text and strip structural prefixes on all lines."""
    for line in lines:
        line['raw_text'] = line.get('text', '')
        corrector.strip_text_prefix(line)
