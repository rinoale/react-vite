"""
Shape walker — general-purpose shape detection via directional walk rules.

A shape is a sequence of direction segments (e.g. DOWN → RIGHT for ㄴ).
The walker traces ink pixels in each direction, chaining segments together.

No domain-specific logic; consumers define shapes via ShapeDef constants.

Usage:
    from lib.image_processors.shape_walker import classify_cluster, SHAPE_NIEUN, SHAPE_DOT

    match = classify_cluster(cluster_mask, [SHAPE_NIEUN, SHAPE_DOT])
    if match:
        print(match.shape.name)  # 'ㄴ' or '·'
"""

from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np


class Direction(Enum):
    DOWN = 'down'
    RIGHT = 'right'
    UP = 'up'
    LEFT = 'left'
    DOT = 'dot'


# Direction → (row_delta, col_delta)
_DELTAS = {
    Direction.DOWN: (1, 0),
    Direction.RIGHT: (0, 1),
    Direction.UP: (-1, 0),
    Direction.LEFT: (0, -1),
}

# Direction → perpendicular axis for thick walk band
_PERP_DELTAS = {
    Direction.DOWN: (0, 1),    # band along columns
    Direction.RIGHT: (1, 0),   # band along rows
    Direction.UP: (0, 1),
    Direction.LEFT: (1, 0),
}


@dataclass(frozen=True)
class Segment:
    direction: Direction
    min_px: int = 1
    max_px: Optional[int] = None


@dataclass(frozen=True)
class ShapeDef:
    name: str
    segments: tuple


@dataclass
class ShapeMatch:
    shape: ShapeDef
    origin: tuple          # (row, col) of walk start
    extent: tuple          # (min_row, min_col, max_row, max_col)
    seg_lengths: tuple     # length per segment
    walked: frozenset      # set of (row, col) for debugging


# Built-in shape constants
SHAPE_NIEUN = ShapeDef('ㄴ', (Segment(Direction.DOWN, min_px=3), Segment(Direction.RIGHT, min_px=2)))
SHAPE_DOT = ShapeDef('·', (Segment(Direction.DOT, min_px=1, max_px=4),))

# Divisor for corner tolerance when transitioning between segments.
# tolerance = max(1, stroke_width // _CORNER_TOLERANCE_DIVISOR)
_CORNER_TOLERANCE_DIVISOR = 2


def find_seeds(mask, region=None):
    """Find seed pixels by scanning the leftmost ink column.

    Returns the topmost pixel of each vertical run in that column.

    Args:
        mask: 2D uint8 array (0 = ink, 255 = background).
        region: optional (r0, c0, r1, c1) sub-region.

    Returns:
        List of (row, col) seed coordinates.
    """
    if region is not None:
        r0, c0, r1, c1 = region
        sub = mask[r0:r1, c0:c1]
    else:
        r0, c0 = 0, 0
        sub = mask

    if sub.size == 0:
        return []

    # Find leftmost column with ink
    col_has_ink = np.any(sub == 0, axis=0)
    ink_cols = np.where(col_has_ink)[0]
    if len(ink_cols) == 0:
        return []

    left_col = ink_cols[0]
    col_data = sub[:, left_col] == 0

    # Extract topmost pixel of each vertical run
    seeds = []
    in_run = False
    for r in range(len(col_data)):
        if col_data[r] and not in_run:
            seeds.append((r + r0, left_col + c0))
            in_run = True
        elif not col_data[r]:
            in_run = False

    return seeds


def _measure_stroke_width(mask, row, col, direction):
    """Measure stroke width perpendicular to walk direction at seed point."""
    h, w = mask.shape
    pr, pc = _PERP_DELTAS[direction]

    width = 1  # the seed pixel itself
    # Scan in positive perpendicular direction
    for sign in (1, -1):
        step = 1
        while True:
            nr = row + pr * sign * step
            nc = col + pc * sign * step
            if 0 <= nr < h and 0 <= nc < w and mask[nr, nc] == 0:
                width += 1
                step += 1
            else:
                break

    return width


def _walk_segment(mask, row, col, direction, min_px, max_px):
    """Walk in one direction using thick walk (perpendicular band).

    At each step, checks a perpendicular band (width = stroke width at seed).
    Continues while any pixel in the band is ink.

    Returns:
        (end_row, end_col, length, walked_set) or None if min_px not met.
    """
    h, w = mask.shape
    dr, dc = _DELTAS[direction]
    pr, pc = _PERP_DELTAS[direction]

    stroke_w = _measure_stroke_width(mask, row, col, direction)
    half_w = stroke_w // 2

    walked = set()
    walked.add((row, col))
    length = 0
    cr, cc = row, col

    while True:
        nr, nc = cr + dr, cc + dc
        if not (0 <= nr < h and 0 <= nc < w):
            break

        # Check perpendicular band at the next position
        band_has_ink = False
        for offset in range(-half_w, half_w + 1):
            br = nr + pr * offset
            bc = nc + pc * offset
            if 0 <= br < h and 0 <= bc < w and mask[br, bc] == 0:
                band_has_ink = True
                walked.add((br, bc))

        if not band_has_ink:
            break

        cr, cc = nr, nc
        walked.add((cr, cc))
        length += 1

        if max_px is not None and length >= max_px:
            break

    if length < min_px:
        return None

    return (cr, cc, length, walked)


def _check_dot(mask, row, col, min_px, max_px):
    """4-connected flood fill bounded by max_px extent.

    Returns:
        (extent_tuple, walked_set) or None if bounding box exceeds constraints.
    """
    h, w = mask.shape
    if mask[row, col] != 0:
        return None

    visited = set()
    queue = deque()
    queue.append((row, col))
    visited.add((row, col))

    min_r, min_c = row, col
    max_r, max_c = row, col

    while queue:
        r, c = queue.popleft()
        min_r = min(min_r, r)
        min_c = min(min_c, c)
        max_r = max(max_r, r)
        max_c = max(max_c, c)

        for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0),
                       (1, 1), (1, -1), (-1, 1), (-1, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < h and 0 <= nc < w and (nr, nc) not in visited and mask[nr, nc] == 0:
                visited.add((nr, nc))
                queue.append((nr, nc))

    extent_h = max_r - min_r + 1
    extent_w = max_c - min_c + 1
    extent_max = max(extent_h, extent_w)

    if extent_max < min_px:
        return None
    if max_px is not None and extent_max > max_px:
        return None

    return ((min_r, min_c, max_r, max_c), frozenset(visited))


def _try_shape(mask, seed, shape_def):
    """Try to match a shape starting from seed.

    Chains segments: end of segment N → start of segment N+1.
    Corner tolerance: search within max(1, stroke_width // 2) radius.

    Returns:
        ShapeMatch or None.
    """
    row, col = seed
    h, w = mask.shape

    if mask[row, col] != 0:
        return None

    all_walked = set()
    seg_lengths = []

    for i, seg in enumerate(shape_def.segments):
        if seg.direction == Direction.DOT:
            result = _check_dot(mask, row, col, seg.min_px, seg.max_px)
            if result is None:
                return None
            extent, walked = result
            all_walked |= walked
            seg_lengths.append(max(extent[2] - extent[0] + 1, extent[3] - extent[1] + 1))
            # DOT is always the terminal segment
            return ShapeMatch(
                shape=shape_def,
                origin=seed,
                extent=extent,
                seg_lengths=tuple(seg_lengths),
                walked=frozenset(all_walked),
            )

        result = _walk_segment(mask, row, col, seg.direction, seg.min_px, seg.max_px)
        if result is None:
            return None

        end_row, end_col, length, walked = result
        all_walked |= walked
        seg_lengths.append(length)

        # Transition to next segment with corner tolerance
        if i < len(shape_def.segments) - 1:
            next_dir = shape_def.segments[i + 1].direction
            if next_dir == Direction.DOT:
                row, col = end_row, end_col
                continue

            next_dr, next_dc = _DELTAS[next_dir]
            stroke_w = _measure_stroke_width(mask, seed[0], seed[1], seg.direction)
            tolerance = max(1, stroke_w // _CORNER_TOLERANCE_DIVISOR)

            # Search within tolerance radius for the next segment's start
            best = None
            for offset in range(-tolerance, tolerance + 1):
                pr, pc = _PERP_DELTAS[next_dir]
                sr = end_row + next_dr + pr * offset
                sc = end_col + next_dc + pc * offset
                if 0 <= sr < h and 0 <= sc < w and mask[sr, sc] == 0:
                    if best is None:
                        best = (sr, sc)
                    break

            if best is None:
                # Try the direct next position
                sr = end_row + next_dr
                sc = end_col + next_dc
                if 0 <= sr < h and 0 <= sc < w and mask[sr, sc] == 0:
                    best = (sr, sc)

            if best is None:
                return None

            row, col = best

    # Compute extent from walked pixels
    if all_walked:
        rows = [p[0] for p in all_walked]
        cols = [p[1] for p in all_walked]
        extent = (min(rows), min(cols), max(rows), max(cols))
    else:
        extent = (seed[0], seed[1], seed[0], seed[1])

    return ShapeMatch(
        shape=shape_def,
        origin=seed,
        extent=extent,
        seg_lengths=tuple(seg_lengths),
        walked=frozenset(all_walked),
    )


def find_shape(mask, shapes, region=None):
    """Find the first matching shape in the mask.

    Args:
        mask: 2D uint8 array (0 = ink, 255 = background).
        shapes: list of ShapeDef to try (priority order).
        region: optional (r0, c0, r1, c1) sub-region.

    Returns:
        ShapeMatch or None.
    """
    seeds = find_seeds(mask, region)
    for seed in seeds:
        for shape_def in shapes:
            match = _try_shape(mask, seed, shape_def)
            if match is not None:
                return match
    return None


def find_all_shapes(mask, shapes, region=None):
    """Find all matching shapes in the mask.

    Args:
        mask: 2D uint8 array (0 = ink, 255 = background).
        shapes: list of ShapeDef to try.
        region: optional (r0, c0, r1, c1) sub-region.

    Returns:
        List of ShapeMatch.
    """
    seeds = find_seeds(mask, region)
    matches = []
    for seed in seeds:
        for shape_def in shapes:
            match = _try_shape(mask, seed, shape_def)
            if match is not None:
                matches.append(match)
                break  # one match per seed
    return matches


def classify_cluster(mask, shapes):
    """Classify an isolated cluster sub-region by shape.

    Convenience entry point for prefix_detector — takes an already-extracted
    cluster mask and tries each shape definition.

    Args:
        mask: 2D uint8 array of the cluster region (0 = ink, 255 = background).
        shapes: list of ShapeDef to try (priority order).

    Returns:
        ShapeMatch or None.
    """
    seeds = find_seeds(mask)
    for seed in seeds:
        for shape_def in shapes:
            match = _try_shape(mask, seed, shape_def)
            if match is not None:
                return match
    return None
