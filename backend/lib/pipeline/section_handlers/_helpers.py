"""Shared helpers for section handlers."""

import os
from functools import wraps

import cv2

from lib.image_processors.prefix_detector import (
    BULLET_DETECTOR, SUBBULLET_DETECTOR, detect_prefix_per_color,
)
from ._ocr import (
    ocr_grouped_lines,
    _PAD_HORIZONTAL_DIVISOR, _PAD_HORIZONTAL_MINIMUM,
    _PAD_VERTICAL_DIVISOR, _PAD_VERTICAL_MINIMUM,
)


def bt601_binary(content_bgr, threshold=80):
    """BT.601 grayscale + threshold → ocr_binary (ink=0, background=255)."""
    gray = cv2.cvtColor(content_bgr, cv2.COLOR_BGR2GRAY)
    _, ocr_binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY_INV)
    return ocr_binary


# Pixels to back off from color-mask main_x when slicing bullet prefixes.
# Anti-aliased text edges pass brightness threshold but not color match,
# so main_x can overshoot actual text start by this many pixels.
_PREFIX_ANTIALIAS_MARGIN = 2


def detect_prefix(*prefix_types):
    """Decorator: detect bullet/subbullet prefixes and compute slice offsets.

    Annotates each line_info with '_prefix_info' dict containing:
      type: 'bullet' | 'subbullet' | None
      x, w, main_x: detection geometry
      cut_x: column offset to slice prefix from padded crop (if prefix found)
    ocr_grouped_lines() reads '_prefix_info' for prefix slicing before OCR.
    """
    _TYPE_MAP = {'bullet': BULLET_DETECTOR, 'subbullet': SUBBULLET_DETECTOR}
    configs = [_TYPE_MAP[t] for t in prefix_types if t in _TYPE_MAP]

    def decorator(fn):
        @wraps(fn)
        def wrapper(self, seg, grouped_lines, *args, **kw):
            content_bgr = seg['content_crop']
            img_h, img_w = content_bgr.shape[:2]
            for group in grouped_lines:
                for line_info in group:
                    x = line_info['x']
                    y = line_info['y']
                    w = line_info['width']
                    h = line_info['height']
                    pad_x = max(_PAD_HORIZONTAL_MINIMUM, h // _PAD_HORIZONTAL_DIVISOR)
                    x_pad = max(0, x - pad_x)
                    w_pad = min(img_w - x_pad, w + 2 * pad_x)
                    # No vertical padding for prefix detection — the line
                    # height IS the threshold reference.  Padding inflates
                    # h, which inflates ratio-based thresholds (min_gap etc.)
                    # and rejects real prefixes.
                    bgr_crop = content_bgr[y:y + h, x_pad:x_pad + w_pad]
                    prefix_info = {'type': None}
                    for cfg in configs:
                        prefix_info = detect_prefix_per_color(bgr_crop, config=cfg)
                        if prefix_info['type'] is not None:
                            break
                    # Pre-compute slice offset
                    if (prefix_info['type'] in ('bullet', 'subbullet')
                            and prefix_info.get('main_x', w_pad) < w_pad):
                        prefix_end = prefix_info['x'] + prefix_info['w']
                        cut_x = max(prefix_end,
                                    prefix_info['main_x'] - _PREFIX_ANTIALIAS_MARGIN)
                        prefix_info['cut_x'] = cut_x
                    line_info['_prefix_info'] = prefix_info
            return fn(self, seg, grouped_lines, *args, **kw)
        return wrapper
    return decorator


def filter_prefix(*allowed_types):
    """Decorator: keep only grouped lines whose first sub-line has a matching prefix.

    Filters grouped_lines before _process runs, so lines without matching
    prefix are never OCR'd.  Must be applied after @detect_prefix (which
    annotates '_prefix_info' on each line_info).
    """
    allowed = set(allowed_types)

    def decorator(fn):
        @wraps(fn)
        def wrapper(self, seg, grouped_lines, *args, **kw):
            filtered = [
                group for group in grouped_lines
                if (group[0].get('_prefix_info') or {}).get('type') in allowed
            ]
            return fn(self, seg, filtered, *args, **kw)
        return wrapper
    return decorator


def reject_prefix(*rejected_types):
    """Decorator: remove grouped lines whose first sub-line has a rejected prefix.

    Filters grouped_lines before _process runs.  Must be applied after
    @detect_prefix (which annotates '_prefix_info' on each line_info).
    """
    rejected = set(rejected_types)

    def decorator(fn):
        @wraps(fn)
        def wrapper(self, seg, grouped_lines, *args, **kw):
            breakpoint()
            filtered = [
                group for group in grouped_lines
                if (group[0].get('_prefix_info') or {}).get('type') not in rejected
            ]
            return fn(self, seg, filtered, *args, **kw)
        return wrapper
    return decorator


def plain_lines_only(fn):
    """Decorator: keep only unprefixed lines (no bullet, no subbullet).

    Must be applied after @detect_prefix.
    """
    @wraps(fn)
    def wrapper(self, seg, grouped_lines, *args, **kw):
        filtered = [
            group for group in grouped_lines
            if (group[0].get('_prefix_info') or {}).get('type') is None
        ]
        return fn(self, seg, filtered, *args, **kw)
    return wrapper


def ocr_lines(seg, grouped_lines, reader, section, attach_crops=False):
    """OCR on pre-grouped lines.  Returns list of line dicts.

    Prefix detection should be done beforehand via @detect_prefix decorator,
    which annotates line_info dicts with '_prefix_info'.  ocr_grouped_lines()
    reads those annotations for prefix slicing.
    """
    _save = os.environ.get('SAVE_OCR_CROPS')
    ocr_results = ocr_grouped_lines(
        seg['ocr_binary'], grouped_lines, reader,
        save_crops_dir=_save,
        save_label=f'content_{section}',
        attach_crops=attach_crops)

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
