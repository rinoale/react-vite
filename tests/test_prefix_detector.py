"""Tests for backend/lib/prefix_detector.py — uses synthetic numpy arrays."""

import numpy as np

from lib.prefix_detector import (
    detect_prefix, PrefixDetectorConfig, BULLET_DETECTOR, SUBBULLET_DETECTOR,
    EFFECT_BLUE_RGB, EFFECT_RED_RGB,
)
from lib.shape_walker import SHAPE_DOT, SHAPE_NIEUN


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


def _make_dot_mask():
    """Create a mask with a small dot cluster + gap + main text."""
    h, w = 16, 80
    mask = np.zeros((h, w), dtype=np.uint8)
    mask[6:9, 2:4] = 255      # small dot
    mask[3:13, 12:60] = 255   # main text
    return mask


def _make_nieun_mask():
    """Create a mask with a ㄴ-shaped cluster + gap + main text.

    ㄴ shape: vertical stroke down, then horizontal stroke right.
    """
    h, w = 16, 80
    mask = np.zeros((h, w), dtype=np.uint8)
    # Vertical stroke: 2px wide, 5px tall
    mask[4:9, 2:4] = 255
    # Horizontal stroke: 5px wide, 2px tall at bottom of vertical
    mask[8:10, 2:7] = 255
    # Gap then main text
    mask[3:13, 16:60] = 255
    return mask


class TestPrefixDetectorConfig:
    def test_bullet_config_detects_dot(self):
        """BULLET_DETECTOR finds · shape."""
        mask = _make_dot_mask()
        result = detect_prefix(mask, config=BULLET_DETECTOR)
        assert result['type'] == 'bullet'

    def test_bullet_config_rejects_nieun(self):
        """BULLET_DETECTOR ignores ㄴ-shaped cluster (only looks for DOT)."""
        mask = _make_nieun_mask()
        result = detect_prefix(mask, config=BULLET_DETECTOR)
        assert result['type'] is None

    def test_subbullet_config_detects_nieun(self):
        """SUBBULLET_DETECTOR finds ㄴ shape."""
        mask = _make_nieun_mask()
        result = detect_prefix(mask, config=SUBBULLET_DETECTOR)
        assert result['type'] == 'subbullet'

    def test_subbullet_config_rejects_dot(self):
        """SUBBULLET_DETECTOR ignores dot-shaped cluster (only looks for NIEUN)."""
        mask = _make_dot_mask()
        result = detect_prefix(mask, config=SUBBULLET_DETECTOR)
        assert result['type'] is None

    def test_default_backward_compat(self):
        """detect_prefix(mask) without config still works — finds both shapes."""
        dot_mask = _make_dot_mask()
        assert detect_prefix(dot_mask)['type'] == 'bullet'
        nieun_mask = _make_nieun_mask()
        assert detect_prefix(nieun_mask)['type'] == 'subbullet'

    def test_build_mask(self):
        """PrefixDetectorConfig.build_mask() produces correct color mask."""
        # Create a small BGR image with one blue pixel and one red pixel
        img = np.zeros((4, 4, 3), dtype=np.uint8)
        # Blue pixel at (1, 1): BGR = (238, 149, 74)
        img[1, 1] = [238, 149, 74]
        # Red pixel at (2, 2): BGR = (103, 103, 255)
        img[2, 2] = [103, 103, 255]

        mask = BULLET_DETECTOR.build_mask(img)
        assert mask[1, 1] == 255  # blue matched
        assert mask[2, 2] == 255  # red matched
        assert mask[0, 0] == 0    # black not matched
