"""Shared test fixtures for Mabinogi OCR backend tests."""

import pytest


@pytest.fixture
def make_line_dict():
    """Factory for line dicts used by line_processing / tooltip_parser."""
    def _make(text='', **overrides):
        d = {
            'text': text,
            'confidence': 0.9,
            'x': 0,
            'y': 0,
            'width': 100,
            'height': 14,
        }
        d.update(overrides)
        return d
    return _make


@pytest.fixture
def make_bounds():
    """Factory for bounds dicts (x, y, width, height)."""
    def _make(y, height, x=0, width=100):
        return {'x': x, 'y': y, 'width': width, 'height': height}
    return _make


@pytest.fixture
def make_classification(make_bounds):
    """Factory for (group, bounds, line_type) classification tuples."""
    def _make(y, height, line_type, **overrides):
        bounds = make_bounds(y, height, **overrides)
        group = [bounds]
        return (group, bounds, line_type)
    return _make


@pytest.fixture
def mini_text_corrector():
    """TextCorrector with small inline dictionaries — no file I/O.

    Sections:
        reforge:  5 entries (option names)
        enchant:  5 entries (slot headers + effects)
        item_name: 3 entries

    Also sets up _enchant_prefixes, _enchant_suffixes, and a minimal
    _enchant_db for match_enchant_effect tests.
    """
    from lib.text_corrector import TextCorrector, _normalize_nums

    tc = TextCorrector.__new__(TextCorrector)
    tc.dictionary = []
    tc._norm_cache = []
    tc._section_dicts = {}
    tc._section_norm_cache = {}
    tc._enchant_db = []
    tc._enchant_headers_norm = []
    tc._enchant_prefixes = []
    tc._enchant_suffixes = []

    # Reforge entries
    reforge = [
        '스매시 대미지 N % 증가',
        '크리티컬 대미지 N % 증가',
        '매직 실드 방어 N % 증가',
        '윈드밀 대미지 N % 증가',
        '파이어볼트 대미지 N % 증가',
    ]

    # Enchant entries (slot header + effects)
    enchant = [
        '[접두] 충격을 (랭크 F)',
        '최대대미지 N 증가',
        '밸런스 N % 증가',
        '[접미] 관리자 (랭크 6)',
        '방어 N 증가',
    ]

    # Item names
    item_name = [
        '다이아몬드 롱소드',
        '페넌스 체인블레이드',
        '가시 니들',
    ]

    # Prefix / suffix names for item name parsing
    tc._enchant_prefixes = ['충격의', '명예의', '방랑자의']
    tc._enchant_suffixes = ['관리자', '기사의', '오솔길']

    def _load_section(name, entries):
        tc._section_dicts[name] = entries
        tc._section_norm_cache[name] = [(_normalize_nums(e), e) for e in entries]
        tc.dictionary.extend(entries)

    _load_section('reforge', reforge)
    _load_section('enchant', enchant)
    _load_section('item_name', item_name)

    tc._norm_cache = [(_normalize_nums(e), e) for e in tc.dictionary]

    # Minimal enchant DB for match_enchant_effect tests
    entry = {
        'header': '[접두] 충격을 (랭크 F)',
        'header_norm': _normalize_nums('[접두] 충격을 (랭크 F)'),
        'slot': '접두',
        'name': '충격을',
        'rank': 'F',
        'effects': ['최대대미지 15 증가', '밸런스 3 % 증가'],
        'effects_norm': [
            (_normalize_nums('최대대미지 15 증가'), '최대대미지 15 증가'),
            (_normalize_nums('밸런스 3 % 증가'), '밸런스 3 % 증가'),
        ],
        'effects_full': ['최대대미지 15 증가', '밸런스 3 % 증가'],
        'effects_full_norm': [
            (_normalize_nums('최대대미지 15 증가'), '최대대미지 15 증가'),
            (_normalize_nums('밸런스 3 % 증가'), '밸런스 3 % 증가'),
        ],
    }
    tc._enchant_db = [entry]
    tc._enchant_headers_norm = [(entry['header_norm'], entry)]

    return tc
