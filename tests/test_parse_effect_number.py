"""Tests for _parse_effect_number."""

from lib.pipeline.tooltip_parsers import _parse_effect_number


class TestParseEffectNumber:
    def test_integer_value(self):
        name, level = _parse_effect_number('최대대미지 53 증가')
        assert name == '최대대미지'
        assert level == 53

    def test_decimal_value(self):
        name, level = _parse_effect_number('아르카나 스킬 보너스 대미지 1.5% 증가')
        assert name == '아르카나 스킬 보너스 대미지'
        assert level == 1.5

    def test_no_number_returns_none(self):
        name, level = _parse_effect_number('활성화된 아르카나의 전용 옵션일 때 효과 발동')
        assert name is None
        assert level is None

    def test_negative_number_not_matched(self):
        """Regex expects positive numbers; negative sign is part of stat name."""
        name, level = _parse_effect_number('방어 -5 감소')
        # '-5' is not matched by \d+ — text won't match _EFFECT_NUM_RE
        assert name is None
        assert level is None

    def test_multiple_numbers_first_wins(self):
        name, level = _parse_effect_number('대미지 10 ~ 20 증가')
        assert name == '대미지'
        assert level == 10

    def test_whitespace_stripped(self):
        name, level = _parse_effect_number('  밸런스 3 % 증가  ')
        assert name == '밸런스'
        assert level == 3
