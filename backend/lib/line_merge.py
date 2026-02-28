"""Gap outlier detection for line processing.

Provides detect_gap_outlier() used by line_processing.trim_outlier_tail()
to remove spatially leaked lines at segment boundaries.

Legacy note: This module previously contained excess effect line merging
(merge_excess_lines, find_fragment_indices, mark_trimmed, merge_fragments,
_stitch_crops) — a count-based algorithm that compared OCR line count against
DB expected_count to detect and merge wrapped fragments. That approach was
replaced by prefix-based merge_continuations() in line_processing.py, which
uses bullet prefix detection instead of effect counting.
"""


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
