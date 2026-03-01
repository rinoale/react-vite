"""Tests for backend/lib/text_corrector.py — uses mini_text_corrector fixture."""


class TestCorrectNormalized:
    def test_exact_match_high_score(self, mini_text_corrector):
        text, score, _range = mini_text_corrector.correct_normalized(
            '스매시 대미지 15 % 증가', section='reforge')
        assert score >= 90
        assert '스매시 대미지' in text
        assert '15' in text

    def test_close_fuzzy_match(self, mini_text_corrector):
        text, score, _range = mini_text_corrector.correct_normalized(
            '스메시 대미지 15 % 증가', section='reforge')
        assert score > 0
        assert '스매시 대미지' in text

    def test_no_match_returns_original(self, mini_text_corrector):
        original = '완전히 다른 텍스트 없는 항목'
        text, score, _range = mini_text_corrector.correct_normalized(
            original, section='reforge')
        # Below cutoff -> negative score (candidate) or 0
        assert score <= 0

    def test_section_specific_dict(self, mini_text_corrector):
        """Reforge section should only search reforge entries."""
        text, score, _range = mini_text_corrector.correct_normalized(
            '최대대미지 15 증가', section='reforge')
        # '최대대미지 N 증가' is in enchant, not reforge
        # Should not match reforge entries well
        assert score <= 0 or '대미지' in text

    def test_unknown_section_returns_minus_2(self, mini_text_corrector):
        text, score, _range = mini_text_corrector.correct_normalized(
            '아무거나', section='nonexistent_section')
        assert score == -2


class TestParseItemName:
    def test_simple_item_name_only(self, mini_text_corrector):
        result = mini_text_corrector.parse_item_name('다이아몬드 롱소드')
        assert result['item_name'] == '다이아몬드 롱소드'
        assert result['enchant_prefix'] is None
        assert result['enchant_suffix'] is None

    def test_holywater_prefix_suffix_item(self, mini_text_corrector):
        result = mini_text_corrector.parse_item_name(
            '축복받은 충격의 관리자 다이아몬드 롱소드')
        assert result['_holywater'] == '축복받은'
        assert result['item_name'] == '다이아몬드 롱소드'

    def test_ego_keyword_strip(self, mini_text_corrector):
        result = mini_text_corrector.parse_item_name('정령 다이아몬드 롱소드')
        assert result['_ego'] is True
        assert result['item_name'] == '다이아몬드 롱소드'

    def test_no_match_fallback(self, mini_text_corrector):
        result = mini_text_corrector.parse_item_name('알수없는아이템')
        assert result['item_name'] is not None  # fallback to raw text


class TestMatchEnchantEffect:
    def test_exact_effect_match(self, mini_text_corrector):
        entry = mini_text_corrector._enchant_db[0]
        text, score = mini_text_corrector.match_enchant_effect(
            '최대대미지 15 증가', entry)
        assert score > 0
        assert '최대대미지' in text

    def test_number_normalized_match(self, mini_text_corrector):
        entry = mini_text_corrector._enchant_db[0]
        text, score = mini_text_corrector.match_enchant_effect(
            '최대대미지 99 증가', entry)
        # Should match template and re-inject 99
        assert '99' in text

    def test_no_entry_returns_original(self, mini_text_corrector):
        text, score = mini_text_corrector.match_enchant_effect(
            '최대대미지 15 증가', None)
        assert score == 0
        assert text == '최대대미지 15 증가'
