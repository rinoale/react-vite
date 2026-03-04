"""SetItemHandler: extract set_name and set_level from the enhancement line."""

import os
import re

from rapidfuzz import fuzz, process

from ._base import BaseHandler
from ._helpers import (
    detect_prefix, filter_prefix, ocr_lines, prepend_header,
)

_SET_ENHANCE_RE = re.compile(r'(.+(?:강화|증가))\s*\+\s*(\d+)')
_FM_CUTOFF = 90

_DICT_PATH = os.path.join(
    os.path.dirname(__file__), '..', '..', '..', '..',
    'data', 'dictionary', 'set_name.txt',
)
_set_names = None


def _load_set_names():
    global _set_names
    if _set_names is None:
        with open(_DICT_PATH, encoding='utf-8') as f:
            _set_names = [line.strip() for line in f if line.strip()]
    return _set_names


class SetItemHandler(BaseHandler):
    """Set item section: extract set_name + set_level from enhancement line."""

    @detect_prefix('bullet')
    @filter_prefix('bullet')
    def _process(self, seg, grouped_lines, *, pipeline, font_reader,
                 attach_crops=False, **ctx):
        section = seg['section']

        ocr_results = ocr_lines(seg, grouped_lines, font_reader, section,
                                attach_crops=attach_crops)

        # Find all "{set_name} 강화 +{level}" lines
        names = _load_set_names()
        set_effects = []

        for l in ocr_results:
            m = _SET_ENHANCE_RE.search(l['text'])
            if not m:
                continue
            raw_name = m.group(1).strip()
            match = process.extractOne(raw_name, names, scorer=fuzz.ratio)
            if match and match[1] >= _FM_CUTOFF:
                set_effects.append({
                    'line': l,
                    'set_name': match[0],
                    'set_level': int(m.group(2)),
                })

        section_data = {'lines': []}
        prepend_header(seg, section, section_data)

        if set_effects:
            section_data['set_effects'] = []
            for eff in set_effects:
                l = eff['line']
                section_data['lines'].append({
                    'text': l['text'],
                    'confidence': l['confidence'],
                    'bounds': l['bounds'],
                    'section': l.get('section', section),
                    'ocr_model': l.get('ocr_model', ''),
                    '_prefix_type': l.get('_prefix_type'),
                    '_crop': l.get('_crop'),
                })
                section_data['set_effects'].append({
                    'set_name': eff['set_name'],
                    'set_level': eff['set_level'],
                })

        return section_data
