"""ItemModHandler: pink-line detection for special upgrade extraction."""

import re

import numpy as np
from rapidfuzz import fuzz

from ._base import BaseHandler
from ._helpers import (
    detect_prefix, plain_lines_only, ocr_lines, prepend_header,
)
from lib.image_processors.prefix_detector import _color_mask

SPECIAL_UPGRADE_RGB = (231, 71, 146)
_SPECIAL_UPGRADE_RE = re.compile(r'([RS])\s*[\(\[]?\s*(\d+)\s*단계')
_SPECIAL_UPGRADE_PREFIX = '특별 개조'
_SPECIAL_UPGRADE_FM_CUTOFF = 60
_MIN_PINK_INK = 50


class ItemModHandler(BaseHandler):
    """Finds the pink special-upgrade line, OCRs only it, extracts structured data."""

    @detect_prefix('bullet', 'subbullet')
    @plain_lines_only
    def _process(self, seg, grouped_lines, *, pipeline, font_reader,
                 attach_crops=False, **ctx):
        content_bgr = seg['content_crop']
        section = seg['section']
        img_h, img_w = content_bgr.shape[:2]

        section_data = {'lines': []}
        prepend_header(seg, section, section_data)

        # Find the pink special-upgrade line
        target_group = None
        for group in grouped_lines:
            line_info = group[0]
            x, y = line_info['x'], line_info['y']
            w, h = line_info['width'], line_info['height']
            y2 = min(y + h, img_h)
            x2 = min(x + w, img_w)
            crop = content_bgr[y:y2, x:x2]
            if crop.size == 0:
                continue
            mask = _color_mask(crop, SPECIAL_UPGRADE_RGB, 15)
            if np.count_nonzero(mask == 0) >= _MIN_PINK_INK:
                target_group = group
                break

        if target_group is None:
            return section_data

        # OCR the pink line — always nanum gothic font (same as enchant/category headers)
        ng_reader = pipeline['content_ng_reader']
        ocr_results = ocr_lines(seg, [target_group], ng_reader, section,
                                attach_crops=attach_crops)

        for line in ocr_results:
            section_data['lines'].append({
                'text': line['text'],
                'confidence': line['confidence'],
                'bounds': line['bounds'],
                'section': section,
                'ocr_model': line.get('ocr_model', ''),
                '_prefix_type': line.get('_prefix_type'),
                '_crop': line.get('_crop'),
            })

        # Pink line found — always emit flag + fields (null if extraction fails)
        section_data['has_special_upgrade'] = True
        section_data['special_upgrade_type'] = None
        section_data['special_upgrade_level'] = None

        if ocr_results:
            text = ocr_results[0].get('text', '')
            m = _SPECIAL_UPGRADE_RE.search(text)
            if m:
                prefix = text[:m.start()].strip()
                if fuzz.ratio(prefix, _SPECIAL_UPGRADE_PREFIX) >= _SPECIAL_UPGRADE_FM_CUTOFF:
                    section_data['special_upgrade_type'] = m.group(1)
                    level = int(m.group(2))
                    section_data['special_upgrade_level'] = level if 1 <= level <= 8 else None

        return section_data
