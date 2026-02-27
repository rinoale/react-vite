"""Excess effect line merging for enchant sections.

When the line splitter produces more OCR lines than the enchant entry has
effects, the extras are either leaked non-enchant content (gap outlier) or
wrapped fragments of long effect lines (narrow tail lines).

Two-pass algorithm:
  Pass 1 — Gap-based trim: detect outlier vertical gap → trim everything below.
  Pass 2 — Tail-window merge: find narrowest lines in tail → merge into neighbors.

All detection functions are pure (return indices, no mutation).
Mutation helpers are separate and explicit.
"""

import numpy as np


def detect_gap_outlier(active_items):
    """Find where a vertical gap outlier starts, scanning from the bottom.

    Args:
        active_items: [(orig_index, bounds_dict), ...] pre-filtered active items.
                      Each bounds_dict must have 'y' and 'height'.

    Returns:
        Position in active_items where the outlier starts, or None.
    """
    if len(active_items) < 2:
        return None

    gaps = []
    for k in range(1, len(active_items)):
        prev_b = active_items[k - 1][1]
        cur_b = active_items[k][1]
        gap = cur_b.get('y', 0) - (prev_b.get('y', 0) + prev_b.get('height', 0))
        gaps.append((k, gap))

    sorted_gaps = sorted(g for _, g in gaps)
    median_gap = sorted_gaps[len(sorted_gaps) // 2]
    threshold = max(median_gap * 2, median_gap + 4)

    for k, gap in reversed(gaps):
        if gap >= threshold:
            return k
    return None


def find_fragment_indices(active_items, excess):
    """Identify fragment lines to merge by width ranking in a tail window.

    Fragments cluster at the bottom (long effects wrap). Search the last
    ``excess * 2`` items for the narrowest ones.

    Args:
        active_items: [(orig_index, bounds_dict), ...] pre-filtered active items.
                      Each bounds_dict must have 'width'.
        excess: number of fragments to find.

    Returns:
        Set of original indices (from active_items[i][0]) to merge.
    """
    window_size = excess * 2
    search_pool = active_items[-window_size:]
    ranked = sorted(search_pool, key=lambda t: t[1].get('width', 9999))
    return {idx for idx, _ in ranked[:excess]}


def mark_trimmed(lines, active_items, trim_position):
    """Set text='' and _merged=True on all lines from trim_position onward.

    Args:
        lines: full list of line dicts (mutated in place).
        active_items: [(orig_index, bounds_dict), ...].
        trim_position: index into active_items from which to start trimming.
    """
    for k in range(trim_position, len(active_items)):
        orig_idx = active_items[k][0]
        lines[orig_idx]['text'] = ''
        lines[orig_idx]['_merged'] = True


def _stitch_crops(target, source, prepend=False):
    """Horizontally concatenate two crop images, padding to equal height.

    Args:
        target: line dict receiving the merged crop (mutated in place).
        source: line dict whose crop is being absorbed.
        prepend: if True, source goes left of target; else right.
    """
    t_crop = target.get('_crop')
    s_crop = source.get('_crop')
    if t_crop is None or s_crop is None:
        return

    h_t, h_s = t_crop.shape[0], s_crop.shape[0]
    max_h = max(h_t, h_s)
    # Pad shorter crop with white (255) at the bottom
    if h_t < max_h:
        pad = np.full((max_h - h_t, t_crop.shape[1]), 255, dtype=t_crop.dtype)
        t_crop = np.vstack([t_crop, pad])
    if h_s < max_h:
        pad = np.full((max_h - h_s, s_crop.shape[1]), 255, dtype=s_crop.dtype)
        s_crop = np.vstack([s_crop, pad])

    if prepend:
        target['_crop'] = np.hstack([s_crop, t_crop])
    else:
        target['_crop'] = np.hstack([t_crop, s_crop])


def merge_fragments(lines, fragment_indices):
    """Merge each fragment into its nearest active neighbor.

    For each fragment (sorted by index): find nearest preceding active line
    and append text. If no preceding neighbor exists, merge forward.
    Also stitches crop images side by side when ``_crop`` is present.

    Args:
        lines: full list of line dicts (mutated in place).
        fragment_indices: set of indices into ``lines`` to absorb.
    """
    for idx in sorted(fragment_indices):
        fragment_text = lines[idx].get('text', '')
        # Find preceding non-merged active line
        neighbor = None
        for j in range(idx - 1, -1, -1):
            if j not in fragment_indices and lines[j].get('text', '').strip():
                neighbor = j
                break
        if neighbor is None:
            # No preceding neighbor — merge forward
            for j in range(idx + 1, len(lines)):
                if j not in fragment_indices and lines[j].get('text', '').strip():
                    neighbor = j
                    break
        if neighbor is not None and neighbor != idx:
            prepend = idx < neighbor
            if prepend:
                lines[neighbor]['text'] = f"{fragment_text} {lines[neighbor]['text']}".strip()
            else:
                lines[neighbor]['text'] = f"{lines[neighbor]['text']} {fragment_text}".strip()
            _stitch_crops(lines[neighbor], lines[idx], prepend=prepend)
        # Clear absorbed fragment
        lines[idx]['text'] = ''
        lines[idx]['_merged'] = True


def merge_excess_lines(lines, expected_count):
    """Orchestrator: merge excess split lines in-place.

    When the line splitter produces more lines than the enchant entry has
    effects, the shortest lines are fragments that should be merged into
    their neighbors.

    Two-pass approach:
      1. Gap detection → trim outlier and everything below.
      2. Tail-window merge → absorb narrowest fragments into neighbors.

    Mutates ``lines`` in-place: absorbed/trimmed lines get empty text
    and ``_merged=True``.

    Args:
        lines: list of line dicts (must have 'text', 'bounds').
        expected_count: number of real effects from the enchant DB entry.
    """
    active = [(i, l['bounds']) for i, l in enumerate(lines)
              if l.get('text', '').strip() and not l.get('is_grey')]
    if len(active) <= expected_count:
        return

    # --- Pass 1: gap-based trim ---
    trim_pos = detect_gap_outlier(active)
    if trim_pos is not None:
        mark_trimmed(lines, active, trim_pos)
        active = active[:trim_pos]

    excess = len(active) - expected_count
    if excess <= 0:
        return

    # --- Pass 2: tail-window width-based merge ---
    fragment_ids = find_fragment_indices(active, excess)
    merge_fragments(lines, fragment_ids)
