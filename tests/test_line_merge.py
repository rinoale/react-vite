"""Tests for backend/lib/line_merge.py — gap outlier detection."""

from lib.line_merge import detect_gap_outlier


class TestDetectGapOutlier:
    def test_empty_returns_none(self):
        assert detect_gap_outlier([]) is None

    def test_single_item_returns_none(self):
        items = [(0, {'y': 10, 'height': 14})]
        assert detect_gap_outlier(items) is None

    def test_uniform_gaps_returns_none(self):
        items = [
            (0, {'y': 10, 'height': 14}),
            (1, {'y': 28, 'height': 14}),  # gap = 4
            (2, {'y': 46, 'height': 14}),  # gap = 4
            (3, {'y': 64, 'height': 14}),  # gap = 4
        ]
        assert detect_gap_outlier(items) is None

    def test_clear_outlier_at_end(self):
        items = [
            (0, {'y': 10, 'height': 14}),
            (1, {'y': 28, 'height': 14}),   # gap = 4
            (2, {'y': 46, 'height': 14}),   # gap = 4
            (3, {'y': 200, 'height': 14}),  # gap = 140 -> outlier
        ]
        result = detect_gap_outlier(items)
        assert result == 3

    def test_outlier_in_middle(self):
        items = [
            (0, {'y': 10, 'height': 14}),
            (1, {'y': 28, 'height': 14}),   # gap = 4
            (2, {'y': 200, 'height': 14}),  # gap = 158 -> outlier
            (3, {'y': 218, 'height': 14}),  # gap = 4
        ]
        # Scans from bottom — finds the outlier at position 2
        result = detect_gap_outlier(items)
        assert result == 2
