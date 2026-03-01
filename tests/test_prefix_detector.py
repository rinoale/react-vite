"""Tests for backend/lib/prefix_detector.py — uses synthetic numpy arrays."""

import numpy as np

from lib.prefix_detector import detect_prefix


class TestDetectPrefix:
    def test_all_white_image_no_prefix(self):
        mask = np.zeros((16, 80), dtype=np.uint8)
        result = detect_prefix(mask)
        assert result['type'] is None

    def test_small_image_no_prefix(self):
        mask = np.zeros((2, 5), dtype=np.uint8)
        result = detect_prefix(mask)
        assert result['type'] is None

    def test_left_column_dot_bullet(self):
        """Simulate a bullet · : small ink cluster at left, gap, then main text."""
        h, w = 16, 80
        mask = np.zeros((h, w), dtype=np.uint8)
        # Small dot: 2px wide, 3px tall in top-left region
        mask[6:9, 2:4] = 255
        # Main text starting at column 12
        mask[3:13, 12:60] = 255
        result = detect_prefix(mask)
        assert result['type'] == 'bullet'
        assert result['x'] == 2
        assert result['gap'] > 0
        assert result['main_x'] == 12

    def test_wider_cluster_subbullet(self):
        """Simulate a subbullet ㄴ: wider prefix cluster."""
        h, w = 16, 80
        mask = np.zeros((h, w), dtype=np.uint8)
        # ㄴ shape: wider cluster (6px), partial height
        mask[8:14, 2:8] = 255
        # Main text starting at column 16
        mask[3:13, 16:60] = 255
        result = detect_prefix(mask)
        assert result['type'] == 'subbullet'

    def test_no_gap_no_prefix(self):
        """Continuous ink from left edge — not a prefix pattern."""
        h, w = 16, 80
        mask = np.zeros((h, w), dtype=np.uint8)
        # Continuous text from column 2 to 60, no gap
        mask[3:13, 2:60] = 255
        result = detect_prefix(mask)
        assert result['type'] is None

    def test_full_height_cluster_rejected(self):
        """A full-height first cluster should be rejected (plain text character)."""
        h, w = 16, 80
        mask = np.zeros((h, w), dtype=np.uint8)
        # Full-height cluster: spans all rows
        mask[0:16, 2:4] = 255
        # Gap then main text
        mask[3:13, 12:60] = 255
        result = detect_prefix(mask)
        assert result['type'] is None
