"""ErgHandler: extract erg grade and level from the grade line."""

import re

from ._base import BaseHandler
from ._helpers import (
    detect_prefix, plain_lines_only, ocr_lines, prepend_header,
)

# "등급 S (50/50 레벨)" — parentheses often missing in OCR
# Captures: grade (S/A/B), current level, max level
_ERG_GRADE_RE = re.compile(
    r'등급\s+([SAB])\s*[\(\[]?\s*(\d{1,2})\s*/\s*(\d{1,2})\s*레벨\s*[\)\]]?'
)


class ErgHandler(BaseHandler):
    """Erg section: extract grade/level from the grade line, FM the rest."""

    @detect_prefix('bullet', 'subbullet')
    @plain_lines_only
    def _process(self, seg, grouped_lines, *, pipeline, font_reader,
                 attach_crops=False, **ctx):
        corrector = pipeline['corrector']
        section = seg['section']

        ocr_results = ocr_lines(seg, grouped_lines, font_reader, section,
                                attach_crops=attach_crops)

        # Find the first line matching the grade pattern
        best_line = None
        best_m = None
        for l in ocr_results:
            m = _ERG_GRADE_RE.search(l['text'])
            if m:
                best_line = l
                best_m = m
                break

        section_data = {'lines': []}
        prepend_header(seg, section, section_data)

        if best_line:
            section_data['lines'].append({
                'text': best_line['text'],
                'confidence': best_line['confidence'],
                'bounds': best_line['bounds'],
                'section': best_line.get('section', section),
                'ocr_model': best_line.get('ocr_model', ''),
                '_prefix_type': best_line.get('_prefix_type'),
                '_crop': best_line.get('_crop'),
            })
            level = int(best_m.group(2))
            max_level = int(best_m.group(3))
            section_data['erg_grade'] = best_m.group(1)
            section_data['erg_level'] = level if 1 <= level <= 50 else None
            section_data['erg_max_level'] = max_level if 1 <= max_level <= 50 else None

        return section_data
