"""Reusable line processing functions for tooltip segment pipelines.

Extracted from _parse_enchant_with_bands to enable composition across
enchant, reforge, set_item, and other segment types.

Each function has a single responsibility and can be imported independently.
"""

import numpy as np

from lib.pipeline.line_split.line_merge import detect_gap_outlier
from lib.image_processors.prefix_detector import detect_prefix_per_color, BULLET_DETECTOR

# Vertical pixel offset applied to the right (continuation) crop when stitching.
# Compensates for sub-pixel baseline misalignment between split line crops.
_STITCH_BASELINE_OFFSET = 1


def merge_group_bounds(group):
    """Merge sub-line dicts into a single bounding box covering the group.

    Args:
        group: list of line dicts, each with 'x', 'y', 'width', 'height'.

    Returns:
        dict with merged 'x', 'y', 'width', 'height'.
    """
    first, last = group[0], group[-1]
    return {
        'x': first['x'],
        'y': first['y'],
        'width': (last['x'] + last['width']) - first['x'],
        'height': first['height'],
    }


def trim_outlier_tail(items, header_test):
    """Remove spatially distant lines leaked from below the section.

    Finds the last header, runs gap outlier detection on lines after it,
    and trims everything from the outlier boundary onward.

    Args:
        items:       list of (group, bounds, line_type) classification tuples.
        header_test: callable(line_type) -> bool identifying header lines.

    Returns:
        Trimmed list (may be the same object if no outlier found).
    """
    last_hdr_idx = -1
    for i, (_, _, lt) in enumerate(items):
        if header_test(lt):
            last_hdr_idx = i
    if last_hdr_idx < 0:
        return items

    tail = items[last_hdr_idx + 1:]
    tail_items = [(i, b) for i, (_, b, _) in enumerate(tail)]
    trim_pos = detect_gap_outlier(tail_items)
    if trim_pos is not None:
        abs_trim = last_hdr_idx + 1 + trim_pos
        return items[:abs_trim]
    return items


def promote_grey_by_prefix(classifications, content_bgr, padding_config=None):
    """Promote grey-classified lines to 'effect' if bullet prefix detected.

    Args:
        classifications: list of (group, bounds, line_type) tuples.
        content_bgr:     BGR color image of the content region.
        padding_config:  padding sub-config dict (horizontal_divisor, etc.).
                         Uses defaults matching extract_lines if None.

    Returns:
        Updated classifications list (mutated in place and returned).
    """
    if padding_config is None:
        padding_config = {
            'horizontal_divisor': 3, 'horizontal_minimum': 2,
            'vertical_divisor': 5, 'vertical_minimum': 1,
        }
    for i, (group, bounds, line_type) in enumerate(classifications):
        if line_type != 'grey':
            continue
        pad_y = max(padding_config['vertical_minimum'],
                    bounds['height'] // padding_config['vertical_divisor'])
        pad_x = max(padding_config['horizontal_minimum'],
                    bounds['height'] // padding_config['horizontal_divisor'])
        y0 = max(0, bounds['y'] - pad_y)
        y1 = min(content_bgr.shape[0], bounds['y'] + bounds['height'] + pad_y)
        x0 = max(0, bounds['x'] - pad_x)
        x1 = min(content_bgr.shape[1], bounds['x'] + bounds['width'] + pad_x)
        if detect_prefix_per_color(content_bgr[y0:y1, x0:x1], config=BULLET_DETECTOR)['type'] == 'bullet':
            classifications[i] = (group, bounds, 'effect')
    return classifications


def determine_enchant_slots(classifications):
    """Determine enchant slot order from classification structure.

    Rules:
      - 2 headers -> ['접두', '접미']
      - 1 header with grey lines above -> ['접미'] (prefix slot empty)
      - 1 header without grey above -> ['접두']
      - 0 headers -> []

    Args:
        classifications: list of (group, bounds, line_type) tuples.

    Returns:
        list of slot labels in order.
    """
    n_headers = sum(1 for _, _, lt in classifications if lt == 'header')
    if n_headers == 2:
        return ['접두', '접미']
    elif n_headers == 1:
        first_hdr_y = next(b['y'] for _, b, lt in classifications if lt == 'header')
        grey_above = any(lt == 'grey' and b['y'] < first_hdr_y
                         for _, b, lt in classifications)
        return ['접미'] if grey_above else ['접두']
    else:
        return []


def _stitch_crop(target, source, baseline_offset=_STITCH_BASELINE_OFFSET):
    """Append source's _crop image to the right of target's _crop.

    Continuation lines are the same logical line, so crops are aligned
    at the top. The shorter crop is bottom-padded with white (255).
    No-op if either side lacks a _crop.

    Args:
        baseline_offset: Vertical pixel offset for the right (continuation) crop.
    """
    t_crop = target.get('_crop')
    s_crop = source.get('_crop')
    if t_crop is None or s_crop is None:
        return

    white = np.uint8(255)
    if baseline_offset > 0:
        s_crop = np.vstack([np.full((baseline_offset, s_crop.shape[1]), white, dtype=s_crop.dtype), s_crop])

    h_t, h_s = t_crop.shape[0], s_crop.shape[0]
    max_h = max(h_t, h_s)
    if h_t < max_h:
        t_crop = np.vstack([t_crop, np.full((max_h - h_t, t_crop.shape[1]), white, dtype=t_crop.dtype)])
    if h_s < max_h:
        s_crop = np.vstack([s_crop, np.full((max_h - h_s, s_crop.shape[1]), white, dtype=s_crop.dtype)])
    target['_crop'] = np.hstack([t_crop, s_crop])


def merge_continuations(lines, header_field='is_enchant_hdr',
                        baseline_offset=_STITCH_BASELINE_OFFSET):
    """Merge continuation lines into preceding bullet-prefixed effects.

    Runs on assembled ocr_results (not raw effect_batch) so that headers
    provide slot boundaries and grey bullet lines serve as valid anchors.

    Rules:
      - header (by header_field) or is_header -> reset anchor (slot boundary)
      - _prefix_type == 'bullet'              -> new anchor
      - is_grey without bullet                -> standalone, don't merge or anchor
      - _prefix_type == 'subbullet'           -> sub-detail, don't merge
      - _prefix_type is None                  -> continuation, merge into anchor

    Absorbed lines get text='' and _cont_merged=True.
    Uses _cont_merged (not _merged) to avoid collision with legacy _merged flag
    which is filtered in v3_pipeline.py.

    Args:
        lines:           list of line dicts (mutated in place).
        header_field:    key to check for header lines (default 'is_enchant_hdr').
        baseline_offset: vertical pixel offset for crop stitching.
    """
    anchor_idx = None
    for i, line in enumerate(lines):
        if line.get(header_field) or line.get('is_header'):
            anchor_idx = None
            continue
        pt = line.get('_prefix_type')
        if pt == 'bullet':
            anchor_idx = i
        elif line.get('is_grey'):
            pass  # grey without bullet — standalone, don't merge or anchor
        elif pt is None and anchor_idx is not None:
            anchor = lines[anchor_idx]
            anchor['text'] = f"{anchor['text']} {line['text']}".strip()
            if 'raw_text' in anchor and 'raw_text' in line:
                anchor['raw_text'] = f"{anchor['raw_text']} {line['raw_text']}".strip()
            _stitch_crop(anchor, line, baseline_offset)  # continuation stitch: merge crop + mark
            anchor['_is_stitched'] = True
            line['text'] = ''
            line['_cont_merged'] = True
        # subbullet or orphan continuation: leave as-is


def count_effects_per_header(lines, header_field='is_enchant_hdr'):
    """Count non-grey, non-merged lines between consecutive headers.

    Args:
        lines:        list of line dicts.
        header_field: key to check for header lines (default 'is_enchant_hdr').

    Returns:
        List of (header_text, count) tuples.
    """
    current_hdr = None
    count = 0
    effect_counts = []
    for line in lines:
        if line.get(header_field):
            if current_hdr is not None:
                effect_counts.append((current_hdr, count))
            current_hdr = line.get('text', '?')
            count = 0
        elif current_hdr is not None and not line.get('_cont_merged') and not line.get('is_grey'):
            count += 1
    if current_hdr is not None:
        effect_counts.append((current_hdr, count))
    return effect_counts


