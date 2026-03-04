"""ItemAttrsHandler: item attributes OCR with dictionary-prefix FM."""

import re

from rapidfuzz import fuzz

# Attribute values are purely numeric: digits, ~, /, %, +, ., spaces.
# Korean in the value means it's a description line, not an attribute.
_KOREAN_PAT = re.compile(r'[가-힣]')

from ._base import BaseHandler
from ._helpers import (
    detect_prefix, ocr_lines,
    prepend_header, snapshot_and_strip,
)

# Map dictionary labels → structured metadata keys.
_ATTR_KEY_MAP = {
    '공격': 'damage',
    '마법 공격력': 'magic_damage',
    '전투 점성술 재능 스킬 대미지': 'additional_damage',
    '밸런스': 'balance',
    '방어력': 'defense',
    '보호': 'protection',
    '마법 방어력': 'magic_defense',
    '마법 보호': 'magic_protection',
    '내구력': 'durability',
}

_FM_CUTOFF = 70


class ItemAttrsHandler(BaseHandler):
    """Item attributes section handler with dictionary-prefix FM."""

    @detect_prefix('bullet', 'subbullet')
    def _process(self, seg, grouped_lines, *, pipeline, font_reader,
                 attach_crops=False, **ctx):
        """OCR → dictionary-prefix match → extract value."""
        parser = pipeline['parser']
        corrector = pipeline['corrector']
        section = seg['section']

        ocr_results = ocr_lines(seg, grouped_lines, font_reader, section,
                                attach_crops=attach_crops)

        section_data = {
            'lines': [
                {'text': l['text'], 'confidence': l['confidence'],
                 'bounds': l['bounds'], 'section': l.get('section', section),
                 'ocr_model': l.get('ocr_model', ''),
                 '_prefix_type': l.get('_prefix_type'),
                 '_crop': l.get('_crop')}
                for l in ocr_results
            ]
        }
        prepend_header(seg, section, section_data)

        # ── FM phase: dictionary-prefix matching ──
        lines = section_data.get('lines', [])
        snapshot_and_strip(lines, corrector)

        attr_dict = corrector._section_dicts.get('item_attrs', [])
        attrs = {}
        for line in lines:
            if line.get('is_header'):
                line['fm_applied'] = False
                continue
            key, value = _match_attr_prefix(line, attr_dict)
            if key:
                attrs[key] = value

        section_data['attrs'] = attrs
        return section_data


def _match_attr_prefix(line, attr_dict, cutoff=_FM_CUTOFF):
    """Match dictionary entry as a prefix of the OCR text, extract value from remainder.

    For each dictionary entry, fuzzy-match it against the same-length prefix of the
    OCR text. If matched, the remainder (after the prefix) is the value.

    e.g. "마법 방어력 5"  → dict "마법 방어력" matches prefix → value "5"
         "마법 방어 50, 마법 보호 90 차감" → no dict entry matches as prefix → skip

    Returns (attr_key, value) on match, (None, None) otherwise.
    """
    text = line.get('text', '')
    if not text.strip():
        line['fm_applied'] = False
        return None, None

    best_entry = None
    best_score = 0
    best_remainder = ''

    for entry in attr_dict:
        entry_len = len(entry)
        # The OCR text must be longer than the entry (need space + value after)
        if len(text) <= entry_len:
            continue
        prefix = text[:entry_len]
        score = fuzz.ratio(prefix, entry)
        if score > best_score:
            best_score = score
            best_entry = entry
            best_remainder = text[entry_len:].strip()

    if best_score >= cutoff and best_entry and best_remainder:
        # Reject if value contains Korean (description line, not attribute)
        if _KOREAN_PAT.search(best_remainder):
            line['fm_applied'] = False
            return None, None
        line['text'] = f'{best_entry} {best_remainder}'
        line['fm_applied'] = True
        attr_key = _ATTR_KEY_MAP.get(best_entry)
        return attr_key, best_remainder

    line['fm_applied'] = False
    return None, None
