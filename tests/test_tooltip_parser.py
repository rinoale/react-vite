"""Tests for build_enchant_structured / build_reforge_structured.

These functions take pre-tagged line dicts as input — no images needed.
A MabinogiTooltipParser instance is required (loads yaml config).
"""

import pytest
from pathlib import Path


@pytest.fixture
def parser():
    """MabinogiTooltipParser with real yaml config."""
    from lib.mabinogi_tooltip_parser import MabinogiTooltipParser
    config_path = Path(__file__).resolve().parents[1] / 'configs' / 'mabinogi_tooltip.yaml'
    return MabinogiTooltipParser(str(config_path))


class TestBuildEnchantStructured:
    def test_prefix_and_suffix_with_effects(self, parser):
        lines = [
            {'is_header': False, 'is_enchant_hdr': True,
             'text': '[접두] 충격을 (랭크 F)', 'enchant_slot': '접두'},
            {'is_header': False, 'text': '최대대미지 15 증가'},
            {'is_header': False, 'text': '밸런스 3 % 증가'},
            {'is_header': False, 'is_enchant_hdr': True,
             'text': '[접미] 관리자 (랭크 6)', 'enchant_slot': '접미'},
            {'is_header': False, 'text': '방어 5 증가'},
        ]
        result = parser.build_enchant_structured(lines)
        assert result['prefix'] is not None
        assert result['prefix']['name'] == '충격을'
        assert result['prefix']['rank'] == 'F'
        assert len(result['prefix']['effects']) == 2
        assert result['suffix'] is not None
        assert result['suffix']['name'] == '관리자'
        assert result['suffix']['rank'] == '6'
        assert len(result['suffix']['effects']) == 1

    def test_prefix_only(self, parser):
        lines = [
            {'is_header': False, 'is_enchant_hdr': True,
             'text': '[접두] 충격을 (랭크 F)', 'enchant_slot': '접두'},
            {'is_header': False, 'text': '최대대미지 15 증가'},
        ]
        result = parser.build_enchant_structured(lines)
        assert result['prefix'] is not None
        assert result['suffix'] is None

    def test_empty_lines(self, parser):
        result = parser.build_enchant_structured([])
        assert result['prefix'] is None
        assert result['suffix'] is None

    def test_effect_number_extraction(self, parser):
        lines = [
            {'is_header': False, 'is_enchant_hdr': True,
             'text': '[접두] 테스트 (랭크 A)', 'enchant_slot': '접두'},
            {'is_header': False, 'text': '최대대미지 53 증가'},
        ]
        result = parser.build_enchant_structured(lines)
        eff = result['prefix']['effects'][0]
        assert eff['option_name'] == '최대대미지'
        assert eff['option_level'] == 53


class TestBuildReforgeStructured:
    def test_single_option_with_sub_effect(self, parser):
        lines = [
            {'is_header': False, 'is_reforge_sub': False,
             'text': '- 스매시 대미지(15/20 레벨)',
             'reforge_name': '스매시 대미지', 'reforge_level': 15,
             'reforge_max_level': 20},
            {'is_header': False, 'is_reforge_sub': True,
             'text': 'ㄴ 대미지 150 % 증가'},
        ]
        result = parser.build_reforge_structured(lines)
        assert len(result['options']) == 1
        opt = result['options'][0]
        assert opt['name'] == '스매시 대미지'
        assert opt['level'] == 15
        assert opt['max_level'] == 20
        assert opt['effect'] == '대미지 150 % 증가'

    def test_multiple_options(self, parser):
        lines = [
            {'is_header': False, 'is_reforge_sub': False,
             'text': '- 스매시 대미지(15/20 레벨)',
             'reforge_name': '스매시 대미지', 'reforge_level': 15,
             'reforge_max_level': 20},
            {'is_header': False, 'is_reforge_sub': True,
             'text': 'ㄴ 대미지 150 % 증가'},
            {'is_header': False, 'is_reforge_sub': False,
             'text': '- 크리티컬 대미지(10/20 레벨)',
             'reforge_name': '크리티컬 대미지', 'reforge_level': 10,
             'reforge_max_level': 20},
            {'is_header': False, 'is_reforge_sub': True,
             'text': 'ㄴ 크리티컬 대미지 120 % 증가'},
        ]
        result = parser.build_reforge_structured(lines)
        assert len(result['options']) == 2
        assert result['options'][1]['name'] == '크리티컬 대미지'
        assert result['options'][1]['level'] == 10

    def test_header_lines_skipped(self, parser):
        lines = [
            {'is_header': True, 'text': '세공 옵션'},
            {'is_header': False, 'is_reforge_sub': False,
             'text': '- 윈드밀 대미지(5/20 레벨)',
             'reforge_name': '윈드밀 대미지', 'reforge_level': 5,
             'reforge_max_level': 20},
        ]
        result = parser.build_reforge_structured(lines)
        assert len(result['options']) == 1
