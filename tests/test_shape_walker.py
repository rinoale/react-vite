"""Tests for backend/lib/shape_walker.py — uses synthetic numpy arrays."""

import numpy as np
import pytest

from lib.shape_walker import (
    Direction,
    Segment,
    ShapeDef,
    ShapeMatch,
    SHAPE_NIEUN,
    SHAPE_DOT,
    find_seeds,
    find_shape,
    find_all_shapes,
    classify_cluster,
)


def _make_nieun(h, w, v_start, v_len, h_len, stroke_w=1):
    """Draw a ㄴ shape: vertical stroke down, then horizontal stroke right.

    Args:
        h, w: mask dimensions.
        v_start: row where vertical stroke begins.
        v_len: length of vertical stroke (pixels).
        h_len: length of horizontal stroke (pixels).
        stroke_w: stroke thickness (pixels).

    Returns:
        uint8 mask with 255 = ink.
    """
    mask = np.zeros((h, w), dtype=np.uint8)
    # Vertical stroke (going down from v_start)
    v_end = v_start + v_len
    mask[v_start:v_end, 0:stroke_w] = 255
    # Horizontal stroke (going right from bottom of vertical)
    corner_row = v_end - stroke_w
    mask[corner_row:corner_row + stroke_w, 0:h_len] = 255
    return mask


def _make_dot(h, w, r, c, size):
    """Draw a small square dot."""
    mask = np.zeros((h, w), dtype=np.uint8)
    mask[r:r + size, c:c + size] = 255
    return mask


class TestSegment:
    def test_defaults(self):
        seg = Segment(Direction.DOWN)
        assert seg.min_px == 1
        assert seg.max_px is None

    def test_frozen(self):
        seg = Segment(Direction.DOWN, min_px=3)
        with pytest.raises(AttributeError):
            seg.min_px = 5

    def test_custom_values(self):
        seg = Segment(Direction.RIGHT, min_px=5, max_px=10)
        assert seg.direction == Direction.RIGHT
        assert seg.min_px == 5
        assert seg.max_px == 10


class TestShapeDef:
    def test_frozen(self):
        with pytest.raises(AttributeError):
            SHAPE_NIEUN.name = 'test'

    def test_nieun_segments(self):
        assert len(SHAPE_NIEUN.segments) == 2
        assert SHAPE_NIEUN.segments[0].direction == Direction.DOWN
        assert SHAPE_NIEUN.segments[1].direction == Direction.RIGHT

    def test_dot_segments(self):
        assert len(SHAPE_DOT.segments) == 1
        assert SHAPE_DOT.segments[0].direction == Direction.DOT


class TestFindSeeds:
    def test_empty_mask(self):
        mask = np.zeros((10, 10), dtype=np.uint8)
        assert find_seeds(mask) == []

    def test_single_pixel(self):
        mask = np.zeros((10, 10), dtype=np.uint8)
        mask[5, 3] = 255
        seeds = find_seeds(mask)
        assert seeds == [(5, 3)]

    def test_prefers_leftmost(self):
        mask = np.zeros((10, 20), dtype=np.uint8)
        mask[3, 8] = 255   # further right
        mask[5, 2] = 255   # leftmost
        seeds = find_seeds(mask)
        assert all(c == 2 for _, c in seeds)

    def test_multiple_runs(self):
        """Two separate vertical runs in leftmost column → two seeds."""
        mask = np.zeros((20, 10), dtype=np.uint8)
        mask[2:5, 0] = 255    # first run
        mask[10:14, 0] = 255  # second run
        seeds = find_seeds(mask)
        assert len(seeds) == 2
        assert seeds[0] == (2, 0)
        assert seeds[1] == (10, 0)

    def test_region_restriction(self):
        mask = np.zeros((20, 20), dtype=np.uint8)
        mask[2, 1] = 255   # outside region
        mask[12, 8] = 255  # inside region
        seeds = find_seeds(mask, region=(10, 5, 15, 15))
        assert len(seeds) == 1
        assert seeds[0] == (12, 8)


class TestShapeNieun:
    def test_basic_nieun(self):
        mask = _make_nieun(12, 12, v_start=0, v_len=6, h_len=6, stroke_w=1)
        match = classify_cluster(mask, [SHAPE_NIEUN, SHAPE_DOT])
        assert match is not None
        assert match.shape.name == 'ㄴ'
        assert len(match.seg_lengths) == 2

    def test_thick_stroke_nieun(self):
        mask = _make_nieun(14, 14, v_start=0, v_len=8, h_len=8, stroke_w=2)
        match = classify_cluster(mask, [SHAPE_NIEUN, SHAPE_DOT])
        assert match is not None
        assert match.shape.name == 'ㄴ'

    def test_too_short_vertical_fails(self):
        """Vertical segment shorter than min_px=3 → no match."""
        mask = _make_nieun(10, 10, v_start=0, v_len=2, h_len=6, stroke_w=1)
        match = classify_cluster(mask, [SHAPE_NIEUN])
        assert match is None

    def test_too_short_horizontal_fails(self):
        """Horizontal segment shorter than min_px=3 → no match."""
        mask = _make_nieun(10, 10, v_start=0, v_len=6, h_len=2, stroke_w=1)
        match = classify_cluster(mask, [SHAPE_NIEUN])
        assert match is None

    def test_not_confused_with_dot(self):
        """A clear ㄴ shape should match SHAPE_NIEUN, not SHAPE_DOT."""
        mask = _make_nieun(12, 12, v_start=0, v_len=6, h_len=6, stroke_w=1)
        # Try dot first — should fail because extent > 4
        match_dot = classify_cluster(mask, [SHAPE_DOT])
        assert match_dot is None
        # ㄴ should still match
        match_nieun = classify_cluster(mask, [SHAPE_NIEUN])
        assert match_nieun is not None


class TestShapeDot:
    def test_2x2_dot(self):
        mask = _make_dot(10, 10, 4, 0, 2)
        match = classify_cluster(mask, [SHAPE_DOT])
        assert match is not None
        assert match.shape.name == '·'

    def test_single_pixel_dot(self):
        mask = np.zeros((6, 6), dtype=np.uint8)
        mask[3, 0] = 255
        match = classify_cluster(mask, [SHAPE_DOT])
        assert match is not None
        assert match.shape.name == '·'

    def test_too_large_fails(self):
        """Dot with extent > max_px=4 → no match."""
        mask = _make_dot(10, 10, 0, 0, 5)
        match = classify_cluster(mask, [SHAPE_DOT])
        assert match is None

    def test_not_confused_with_nieun(self):
        """A small dot should not match SHAPE_NIEUN."""
        mask = _make_dot(10, 10, 4, 0, 2)
        match = classify_cluster(mask, [SHAPE_NIEUN])
        assert match is None


class TestFindShape:
    def test_region_restriction(self):
        mask = np.zeros((30, 30), dtype=np.uint8)
        mask[20:23, 10:12] = 255  # dot in lower region
        match = find_shape(mask, [SHAPE_DOT], region=(15, 5, 28, 25))
        assert match is not None
        assert match.shape.name == '·'

    def test_no_match(self):
        mask = np.zeros((10, 10), dtype=np.uint8)
        assert find_shape(mask, [SHAPE_NIEUN, SHAPE_DOT]) is None

    def test_priority_order(self):
        """When SHAPE_NIEUN is listed first and matches, it wins over DOT."""
        mask = _make_nieun(12, 12, v_start=0, v_len=6, h_len=6, stroke_w=1)
        match = find_shape(mask, [SHAPE_NIEUN, SHAPE_DOT])
        assert match is not None
        assert match.shape.name == 'ㄴ'

    def test_find_all_shapes(self):
        """Multiple seeds can produce multiple matches."""
        mask = np.zeros((30, 10), dtype=np.uint8)
        # Two dots at different vertical positions in leftmost column
        mask[3:5, 0:2] = 255
        mask[20:22, 0:2] = 255
        matches = find_all_shapes(mask, [SHAPE_DOT])
        assert len(matches) == 2
        assert all(m.shape.name == '·' for m in matches)


class TestCustomShapes:
    def test_horizontal_bar(self):
        """A shape defined as RIGHT-only should match a horizontal bar."""
        shape_bar = ShapeDef('bar', (Segment(Direction.RIGHT, min_px=5),))
        mask = np.zeros((5, 20), dtype=np.uint8)
        mask[2, 0:10] = 255
        match = classify_cluster(mask, [shape_bar])
        assert match is not None
        assert match.shape.name == 'bar'
        assert match.seg_lengths[0] >= 5

    def test_giyeok_right_down(self):
        """ㄱ shape: RIGHT → DOWN."""
        shape_giyeok = ShapeDef('ㄱ', (
            Segment(Direction.RIGHT, min_px=3),
            Segment(Direction.DOWN, min_px=3),
        ))
        mask = np.zeros((12, 12), dtype=np.uint8)
        # Horizontal bar across top
        mask[0, 0:6] = 255
        # Vertical bar from right end going down
        mask[0:7, 5] = 255
        match = classify_cluster(mask, [shape_giyeok])
        assert match is not None
        assert match.shape.name == 'ㄱ'

    def test_custom_shape_no_match(self):
        """Shape doesn't match when pattern is wrong."""
        shape_up = ShapeDef('up', (Segment(Direction.UP, min_px=5),))
        mask = np.zeros((10, 10), dtype=np.uint8)
        # Horizontal line — won't match UP direction
        mask[5, 0:8] = 255
        match = classify_cluster(mask, [shape_up])
        assert match is None


class TestEdgeCases:
    def test_empty_mask(self):
        mask = np.zeros((10, 10), dtype=np.uint8)
        assert classify_cluster(mask, [SHAPE_NIEUN, SHAPE_DOT]) is None

    def test_full_mask(self):
        """Fully inked mask — too large for DOT, ㄴ walks everywhere."""
        mask = np.full((10, 10), 255, dtype=np.uint8)
        match = classify_cluster(mask, [SHAPE_DOT])
        assert match is None  # extent > 4

    def test_scattered_noise(self):
        """Random sparse noise — unlikely to form a valid shape."""
        rng = np.random.RandomState(42)
        mask = np.zeros((20, 20), dtype=np.uint8)
        # Scatter 5 random pixels
        for _ in range(5):
            mask[rng.randint(0, 20), rng.randint(0, 20)] = 255
        # Shouldn't match ㄴ (needs connected down→right)
        match = classify_cluster(mask, [SHAPE_NIEUN])
        assert match is None

    def test_shape_match_has_walked_set(self):
        """ShapeMatch.walked should contain the pixels traversed."""
        mask = _make_dot(8, 8, 3, 0, 2)
        match = classify_cluster(mask, [SHAPE_DOT])
        assert match is not None
        assert len(match.walked) > 0
        # All walked pixels should be within the mask
        for r, c in match.walked:
            assert 0 <= r < 8 and 0 <= c < 8
