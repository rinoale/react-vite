"""Shared OCR invocation for section handlers.

Extracted from MabinogiTooltipParser — these functions run OCR on
pre-cropped line groups and return structured result dicts.
"""

import os

import cv2
import numpy as np

from lib.pipeline.line_split import merge_group_bounds
from lib.image_processors.prefix_detector import detect_prefix_per_color
from lib.image_processors.mabinogi_processor import oreo_flip

# Pixels to back off from color-mask main_x when slicing bullet prefixes.
# Anti-aliased text edges pass brightness threshold but not color match,
# so main_x can overshoot actual text start by this many pixels.
_PREFIX_ANTIALIAS_MARGIN = 2

# Proportional padding — same formula as TooltipLineSplitter.extract_lines().
# pad_x = max(_PAD_HORIZONTAL_MINIMUM, h // _PAD_HORIZONTAL_DIVISOR)
# pad_y = max(_PAD_VERTICAL_MINIMUM, h // _PAD_VERTICAL_DIVISOR)
_PAD_HORIZONTAL_DIVISOR = 3
_PAD_HORIZONTAL_MINIMUM = 2
_PAD_VERTICAL_DIVISOR = 5
_PAD_VERTICAL_MINIMUM = 1

# Minimum white pixels per column in enchant header band to count as text.
# Filters stray border pixels when finding the x-extent of white text.
_ENCHANT_HEADER_MIN_COL_WHITE = 3


def ocr_grouped_lines(img, grouped_lines, reader,
                      save_crops_dir=None, save_label='content',
                      attach_crops=False, prefix_bgr=None,
                      prefix_config=None, prefix_configs=None):
    """Run OCR on each grouped line, merging sub-line results.

    Args:
        img: Original BGR image
        grouped_lines: list of sub-line groups from _group_by_y()
        reader: EasyOCR Reader instance
        save_crops_dir: if set, save each crop to this directory before OCR
        save_label: label embedded in saved filenames (e.g. 'content_reforge')
        attach_crops: if True, attach grayscale crop as '_crop' on each result

    Returns:
        list of dicts with 'text', 'confidence', 'sub_count', 'bounds', 'sub_lines'
    """
    results = []
    for group in grouped_lines:
        sub_texts = []
        sub_confs = []
        sub_details = []

        for line_info in group:
            x, y, w, h = line_info['x'], line_info['y'], line_info['width'], line_info['height']

            # Apply proportional padding
            pad_x = max(_PAD_HORIZONTAL_MINIMUM, h // _PAD_HORIZONTAL_DIVISOR)
            pad_y = max(_PAD_VERTICAL_MINIMUM, h // _PAD_VERTICAL_DIVISOR)
            x_pad = max(0, x - pad_x)
            y_pad = max(0, y - pad_y)
            w_pad = min(img.shape[1] - x_pad, w + 2 * pad_x)
            h_pad = min(img.shape[0] - y_pad, h + 2 * pad_y)

            line_crop = img[y_pad:y_pad + h_pad, x_pad:x_pad + w_pad]

            # Convert to grayscale
            if len(line_crop.shape) == 3:
                gray = cv2.cvtColor(line_crop, cv2.COLOR_BGR2GRAY)
            else:
                gray = line_crop

            ch, cw = gray.shape
            if ch == 0 or cw == 0:
                sub_texts.append('')
                sub_confs.append(0.0)
                sub_details.append({'text': '', 'confidence': 0.0, 'bounds': line_info})
                continue

            # Prefix detection: slice off bullet prefix before OCR
            prefix_info = {'type': None}
            prefix_abs_cut = None  # absolute x where prefix was trimmed
            _configs = prefix_configs or ([prefix_config] if prefix_config else [])
            if prefix_bgr is not None and _configs:
                bgr_crop = prefix_bgr[y_pad:y_pad + h_pad, x_pad:x_pad + w_pad]
                for _cfg in _configs:
                    prefix_info = detect_prefix_per_color(bgr_crop, config=_cfg)
                    if prefix_info['type'] is not None:
                        break
                if prefix_info['type'] in ('bullet', 'subbullet') and prefix_info['main_x'] < cw:
                    # main_x from color mask can be 1-2px beyond actual text
                    # start on grayscale (anti-aliased edge pixels pass brightness
                    # threshold but not color match). Back off by margin, clamped
                    # to prefix_end so we always remove the prefix glyph.
                    prefix_end = prefix_info['x'] + prefix_info['w']
                    cut_x = max(prefix_end, prefix_info['main_x'] - _PREFIX_ANTIALIAS_MARGIN)
                    prefix_abs_cut = x_pad + cut_x
                    gray = gray[:, cut_x:]
                    cw = gray.shape[1]

            if save_crops_dir:
                os.makedirs(save_crops_dir, exist_ok=True)
                _n = len([f for f in os.listdir(save_crops_dir) if f.endswith('.png')])
                cv2.imwrite(os.path.join(save_crops_dir, f'{_n:03d}_{save_label}.png'), gray)

            ocr_results = reader.recognize(
                gray,
                horizontal_list=[[0, cw, 0, ch]],
                free_list=[],
                reformat=False,
                detail=1
            )

            if ocr_results:
                _, text, confidence = ocr_results[0]
            else:
                text, confidence = '', 0.0

            # Track which model won (DualReader sets last_model_names)
            model_name = ''
            if hasattr(reader, 'last_model_names') and reader.last_model_names:
                model_name = reader.last_model_names[0]

            sub_texts.append(text)
            sub_confs.append(confidence)
            sub_details.append({
                'text': text,
                'confidence': float(confidence),
                'bounds': line_info,
                'ocr_model': model_name,
                'prefix_type': prefix_info['type'],
                'prefix_abs_cut': prefix_abs_cut,
            })

        # Merge sub-line results
        merged_text = ' '.join(t.strip() for t in sub_texts if t.strip())
        avg_conf = sum(sub_confs) / len(sub_confs) if sub_confs else 0.0

        merged_bounds = merge_group_bounds(group)

        # Use the model from the first sub-line (or most common if multiple)
        ocr_model = sub_details[0].get('ocr_model', '') if sub_details else ''

        # Check if first sub-line had a prefix that was sliced
        first_prefix = sub_details[0].get('prefix_type') if sub_details else None
        has_prefix = first_prefix in ('bullet', 'subbullet')

        entry = {
            'text': merged_text,
            'confidence': float(avg_conf),
            'sub_count': len(group),
            'bounds': merged_bounds,
            'sub_lines': sub_details,
            'ocr_model': ocr_model,
            '_has_bullet': has_prefix,
            '_prefix_type': first_prefix,
        }

        # Attach line crop for correction training.
        if attach_crops:
            mb = merged_bounds
            pad_y = max(_PAD_VERTICAL_MINIMUM, mb['height'] // _PAD_VERTICAL_DIVISOR)
            pad_x = max(_PAD_HORIZONTAL_MINIMUM, mb['height'] // _PAD_HORIZONTAL_DIVISOR)
            y0 = max(0, mb['y'] - pad_y)
            y1 = min(img.shape[0], mb['y'] + mb['height'] + pad_y)
            x0 = max(0, mb['x'] - pad_x)
            x1 = min(img.shape[1], mb['x'] + mb['width'] + pad_x)
            # Use prefix cut position from first sub-line to trim prefix
            if has_prefix and sub_details:
                abs_cut = sub_details[0].get('prefix_abs_cut')
                if abs_cut is not None and abs_cut > x0:
                    x0 = abs_cut
            crop_region = img[y0:y1, x0:x1]
            if len(crop_region.shape) == 3:
                crop_region = cv2.cvtColor(crop_region, cv2.COLOR_BGR2GRAY)
            entry['_crop'] = crop_region

        results.append(entry)

    return results


def ocr_enchant_headers(content_bgr, binary,
                        header_classifications, bands, reader,
                        save_crops_dir=None, attach_crops=False):
    """OCR enchant slot headers using white-mask band bounds.

    Instead of using line-splitter bounds (which include UI borders and
    pink rank text), crops are derived from the white-mask bands that
    originally detected the headers.  This produces tight crops matching
    only the white text visible in the slot header.

    Args:
        content_bgr:  BGR enchant content region (for building white mask)
        binary:       preprocessed binary (black text on white)
        header_classifications: list of (group, bounds, 'header') tuples
        bands:        list of (y_start, y_end) from detect_enchant_slot_headers()
        reader:       EasyOCR reader for enchant headers
        save_crops_dir: if set, save each crop before OCR
        attach_crops: if True, attach grayscale crop as '_crop' on each result

    Returns:
        list of dicts matching ocr_grouped_lines output format
    """
    white_mask, ocr_source = oreo_flip(content_bgr)

    img_h, img_w = ocr_source.shape[:2]
    results = []

    for group, bounds, _ in header_classifications:
        y_line = bounds['y']
        h_line = bounds['height']

        # Find overlapping band
        matched_band = None
        for bs, be in bands:
            if min(y_line + h_line, be) - max(y_line, bs) > 0:
                matched_band = (bs, be)
                break

        if matched_band is None:
            # Fallback: use line-splitter bounds (shouldn't happen)
            batch = ocr_grouped_lines(binary, [group], reader,
                                      save_crops_dir=save_crops_dir)
            results.extend(batch)
            continue

        bs, be = matched_band

        # Find x extent of white pixels within the band rows.
        # Require >= 3 white pixels per column to filter stray border pixels.
        band_mask = white_mask[bs:be, :]
        col_counts = band_mask.sum(axis=0)
        white_cols = np.where(col_counts >= _ENCHANT_HEADER_MIN_COL_WHITE)[0]
        if len(white_cols) == 0:
            # No white pixels found — fallback
            batch = ocr_grouped_lines(binary, [group], reader,
                                      save_crops_dir=save_crops_dir)
            results.extend(batch)
            continue

        x_start = int(white_cols[0])
        x_end = int(white_cols[-1]) + 1

        # Apply proportional padding (matching ocr_grouped_lines formula)
        text_h = be - bs
        pad_x = max(_PAD_HORIZONTAL_MINIMUM, text_h // _PAD_HORIZONTAL_DIVISOR)
        pad_y = max(_PAD_VERTICAL_MINIMUM, text_h // _PAD_VERTICAL_DIVISOR)
        x_pad = max(0, x_start - pad_x)
        y_pad = max(0, bs - pad_y)
        w_pad = min(img_w - x_pad, (x_end - x_start) + 2 * pad_x)
        h_pad = min(img_h - y_pad, text_h + 2 * pad_y)

        # Crop from inverted white mask
        crop = ocr_source[y_pad:y_pad + h_pad, x_pad:x_pad + w_pad]
        gray = crop

        ch, cw = gray.shape
        if ch == 0 or cw == 0:
            results.append({
                'text': '', 'confidence': 0.0,
                'sub_count': len(group), 'bounds': bounds, 'sub_lines': [],
            })
            continue

        if save_crops_dir:
            os.makedirs(save_crops_dir, exist_ok=True)
            _n = len([f for f in os.listdir(save_crops_dir) if f.endswith('.png')])
            cv2.imwrite(os.path.join(save_crops_dir, f'{_n:03d}_enchant_hdr.png'), gray)

        ocr_results = reader.recognize(
            gray,
            horizontal_list=[[0, cw, 0, ch]],
            free_list=[],
            reformat=False,
            detail=1,
        )

        if ocr_results:
            _, text, confidence = ocr_results[0]
        else:
            text, confidence = '', 0.0

        entry = {
            'text': text,
            'confidence': float(confidence),
            'sub_count': len(group),
            'bounds': bounds,
            'sub_lines': [],
        }
        if attach_crops:
            entry['_crop'] = gray
        results.append(entry)

    return results
