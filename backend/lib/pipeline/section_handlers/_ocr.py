"""Shared OCR invocation for section handlers.

Extracted from MabinogiTooltipParser — these functions run OCR on
pre-cropped line groups and return structured result dicts.
"""

import os

import cv2
import numpy as np

from lib.pipeline.line_split import merge_group_bounds
from lib.image_processors.mabinogi_processor import oreo_flip

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
                      attach_crops=False):
    """Run OCR on each grouped line, merging sub-line results.

    Prefix detection is done externally by @detect_prefix decorator, which
    annotates each line_info with '_prefix_info'.  This function only handles
    prefix slicing (removing prefix pixels before OCR) based on those annotations.

    Args:
        img: Binary or BGR image
        grouped_lines: list of sub-line groups from group_by_y()
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
        sub_crops = []  # actual gray crops fed to OCR (for attach_crops)

        for line_info in group:
            x, y, w, h = line_info['x'], line_info['y'], line_info['width'], line_info['height']

            # Horizontal padding only — the centered line window already
            # provides vertical margin around the text.
            pad_x = max(_PAD_HORIZONTAL_MINIMUM, h // _PAD_HORIZONTAL_DIVISOR)
            x_pad = max(0, x - pad_x)
            w_pad = min(img.shape[1] - x_pad, w + 2 * pad_x)

            line_crop = img[y:y + h, x_pad:x_pad + w_pad]

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

            # Prefix slicing: use pre-computed offsets from @detect_prefix decorator
            prefix_info = line_info.get('_prefix_info') or {}
            cut_x = prefix_info.get('cut_x')
            if cut_x is not None and cut_x < cw:
                gray = gray[:, cut_x:]
                cw = gray.shape[1]

            sub_crops.append(gray)

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
            })

        # Merge sub-line results
        merged_text = ' '.join(t.strip() for t in sub_texts if t.strip())
        avg_conf = sum(sub_confs) / len(sub_confs) if sub_confs else 0.0

        merged_bounds = merge_group_bounds(group)

        # Use the model from the first sub-line (or most common if multiple)
        ocr_model = sub_details[0].get('ocr_model', '') if sub_details else ''

        # Prefix type from first sub-line (set by @detect_prefix decorator)
        first_prefix_info = group[0].get('_prefix_info') or {}
        first_prefix = first_prefix_info.get('type')

        entry = {
            'text': merged_text,
            'confidence': float(avg_conf),
            'sub_count': len(group),
            'bounds': merged_bounds,
            'sub_lines': sub_details,
            'ocr_model': ocr_model,
            '_prefix_type': first_prefix,
        }

        # Attach the actual crop that was OCR'd (post-prefix-slicing).
        if attach_crops and sub_crops:
            if len(sub_crops) == 1:
                entry['_crop'] = sub_crops[0]
            else:
                # Multiple sub-lines: hstack with height normalization
                max_h = max(c.shape[0] for c in sub_crops)
                padded = []
                for c in sub_crops:
                    if c.shape[0] < max_h:
                        pad = np.full((max_h - c.shape[0], c.shape[1]), 255, dtype=c.dtype)
                        padded.append(np.vstack([c, pad]))
                    else:
                        padded.append(c)
                entry['_crop'] = np.hstack(padded)

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
