"""Tests for backend/lib/line_processing.py — pure functions, no I/O."""

from lib.pipeline.line_split.line_processing import (
    merge_group_bounds,
    trim_outlier_tail,
    determine_enchant_slots,
    merge_continuations,
    count_effects_per_header,
)


# ---------------------------------------------------------------------------
# merge_group_bounds
# ---------------------------------------------------------------------------

class TestMergeGroupBounds:
    def test_single_item(self, make_bounds):
        group = [make_bounds(y=10, height=14, x=5, width=80)]
        result = merge_group_bounds(group)
        assert result == {'x': 5, 'y': 10, 'width': 80, 'height': 14}

    def test_two_items(self, make_bounds):
        group = [
            make_bounds(y=10, height=14, x=5, width=40),
            make_bounds(y=10, height=14, x=60, width=30),
        ]
        result = merge_group_bounds(group)
        assert result['x'] == 5
        assert result['y'] == 10
        assert result['width'] == (60 + 30) - 5  # 85
        assert result['height'] == 14

    def test_three_items_spanning_wide(self, make_bounds):
        group = [
            make_bounds(y=10, height=14, x=0, width=20),
            make_bounds(y=10, height=14, x=50, width=20),
            make_bounds(y=10, height=14, x=100, width=30),
        ]
        result = merge_group_bounds(group)
        assert result['x'] == 0
        assert result['width'] == (100 + 30) - 0  # 130


# ---------------------------------------------------------------------------
# trim_outlier_tail
# ---------------------------------------------------------------------------

class TestTrimOutlierTail:
    def test_no_outlier(self, make_classification):
        items = [
            make_classification(10, 14, 'header'),
            make_classification(30, 14, 'effect'),
            make_classification(50, 14, 'effect'),
        ]
        result = trim_outlier_tail(items, header_test=lambda lt: lt == 'header')
        assert len(result) == 3

    def test_clear_gap_outlier_at_end(self, make_classification):
        # Need enough uniform-gap items so the median stays small,
        # then one outlier at the end exceeds max(median*2, median+4).
        items = [
            make_classification(10, 14, 'header'),
            make_classification(30, 14, 'effect'),   # gap 6
            make_classification(50, 14, 'effect'),   # gap 6
            make_classification(70, 14, 'effect'),   # gap 6
            make_classification(200, 14, 'effect'),  # gap 116 -> outlier
        ]
        result = trim_outlier_tail(items, header_test=lambda lt: lt == 'header')
        assert len(result) == 4

    def test_all_headers_no_trim(self, make_classification):
        """No header found -> return as-is."""
        items = [
            make_classification(10, 14, 'effect'),
            make_classification(30, 14, 'effect'),
        ]
        result = trim_outlier_tail(items, header_test=lambda lt: lt == 'header')
        assert len(result) == 2


# ---------------------------------------------------------------------------
# determine_enchant_slots
# ---------------------------------------------------------------------------

class TestDetermineEnchantSlots:
    def test_two_headers(self, make_classification):
        items = [
            make_classification(10, 14, 'header'),
            make_classification(30, 14, 'effect'),
            make_classification(50, 14, 'header'),
            make_classification(70, 14, 'effect'),
        ]
        assert determine_enchant_slots(items) == ['접두', '접미']

    def test_one_header_no_grey_prefix(self, make_classification):
        items = [
            make_classification(10, 14, 'header'),
            make_classification(30, 14, 'effect'),
        ]
        assert determine_enchant_slots(items) == ['접두']

    def test_one_header_with_grey_above_suffix(self, make_classification):
        items = [
            make_classification(10, 14, 'grey'),
            make_classification(50, 14, 'header'),
            make_classification(70, 14, 'effect'),
        ]
        assert determine_enchant_slots(items) == ['접미']

    def test_zero_headers(self, make_classification):
        items = [
            make_classification(10, 14, 'effect'),
            make_classification(30, 14, 'grey'),
        ]
        assert determine_enchant_slots(items) == []


# ---------------------------------------------------------------------------
# merge_continuations
# ---------------------------------------------------------------------------

class TestMergeContinuations:
    def test_bullet_plus_continuation_merge(self, make_line_dict):
        lines = [
            make_line_dict('헤더', is_enchant_hdr=True),
            make_line_dict('최대대미지 53 증가', _prefix_type='bullet'),
            make_line_dict('적용)', _prefix_type=None),  # continuation
        ]
        merge_continuations(lines)
        assert lines[1]['text'] == '최대대미지 53 증가 적용)'
        assert lines[2]['text'] == ''
        assert lines[2].get('_cont_merged') is True

    def test_header_resets_anchor(self, make_line_dict):
        lines = [
            make_line_dict('헤더1', is_enchant_hdr=True),
            make_line_dict('효과1', _prefix_type='bullet'),
            make_line_dict('헤더2', is_enchant_hdr=True),
            make_line_dict('orphan', _prefix_type=None),  # no anchor after header
        ]
        merge_continuations(lines)
        # orphan should NOT be merged (anchor was reset by header)
        assert lines[3]['text'] == 'orphan'
        assert lines[3].get('_cont_merged') is None

    def test_subbullet_standalone(self, make_line_dict):
        lines = [
            make_line_dict('헤더', is_enchant_hdr=True),
            make_line_dict('효과1', _prefix_type='bullet'),
            make_line_dict('ㄴ 세부사항', _prefix_type='subbullet'),
        ]
        merge_continuations(lines)
        assert lines[2]['text'] == 'ㄴ 세부사항'  # not merged

    def test_grey_standalone(self, make_line_dict):
        lines = [
            make_line_dict('헤더', is_enchant_hdr=True),
            make_line_dict('효과1', _prefix_type='bullet'),
            make_line_dict('설명 텍스트', is_grey=True),
        ]
        merge_continuations(lines)
        assert lines[2]['text'] == '설명 텍스트'  # not merged

    def test_no_anchor_orphan(self, make_line_dict):
        lines = [
            make_line_dict('orphan', _prefix_type=None),
        ]
        merge_continuations(lines)
        assert lines[0]['text'] == 'orphan'  # no anchor, no merge


# ---------------------------------------------------------------------------
# count_effects_per_header
# ---------------------------------------------------------------------------

class TestCountEffectsPerHeader:
    def test_basic_counting(self, make_line_dict):
        lines = [
            make_line_dict('헤더1', is_enchant_hdr=True),
            make_line_dict('효과1'),
            make_line_dict('효과2'),
            make_line_dict('헤더2', is_enchant_hdr=True),
            make_line_dict('효과3'),
        ]
        result = count_effects_per_header(lines)
        assert result == [('헤더1', 2), ('헤더2', 1)]

    def test_skips_merged_and_grey(self, make_line_dict):
        lines = [
            make_line_dict('헤더', is_enchant_hdr=True),
            make_line_dict('효과1'),
            make_line_dict('', _cont_merged=True),
            make_line_dict('설명', is_grey=True),
            make_line_dict('효과2'),
        ]
        result = count_effects_per_header(lines)
        assert result == [('헤더', 2)]

    def test_multiple_headers(self, make_line_dict):
        lines = [
            make_line_dict('A', is_enchant_hdr=True),
            make_line_dict('B', is_enchant_hdr=True),
            make_line_dict('효과'),
        ]
        result = count_effects_per_header(lines)
        assert result == [('A', 0), ('B', 1)]
