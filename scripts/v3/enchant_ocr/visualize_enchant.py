#!/usr/bin/env python3
"""Visualize the enchant OCR pipeline step by step.

For a single original color screenshot, finds the enchant section and produces
8 numbered images showing each stage of the enchant processing pipeline:

  01_content_region.png   — Color enchant content crop from segmenter
  02_white_mask.png       — Binary mask: bright (>150) + balanced channels (<1.4 ratio)
  03_projection.png       — Sideways bar chart of white pixels per row
  04_bands_overlay.png    — Content region + detected bands as semi-transparent blue boxes
  05_binary.png           — BT.601 → threshold=80 binary
  06_lines_detected.png   — Binary with bounding boxes: red=overlaps band, green=effect
  07_lines_tagged.png     — Color content with tagged lines: blue=header, green=effect + labels
  08_ocr_results.png      — Color content (padded right 250px) with OCR text + confidence

Usage:
    python3 scripts/v3/enchant_ocr/visualize_enchant.py data/sample_images/titan_blade_original.png tmp/enchant_vis/
"""

import argparse
import os
import sys

import cv2
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'backend'))

from lib.pipeline.tooltip_parsers import MabinogiTooltipParser
from lib.image_processors.mabinogi_processor import (
    detect_enchant_slot_headers, classify_enchant_line,
)
from lib.pipeline.line_split import MabinogiTooltipSplitter, group_by_y
from lib.pipeline.section_handlers._ocr import ocr_grouped_lines
from lib.pipeline.segmenter import (
    init_header_reader,
    load_config,
    load_section_patterns,
    segment_and_tag,
)

MODELS_DIR  = os.path.join(PROJECT_ROOT, 'backend', 'ocr', 'models')
CONFIG_PATH = os.path.join(PROJECT_ROOT, 'configs', 'mabinogi_tooltip.yaml')
DICT_DIR    = os.path.join(PROJECT_ROOT, 'data', 'dictionary')

# Row threshold and gap tolerance — must match detect_enchant_slot_headers()
ROW_THRESHOLD = 10
GAP_TOLERANCE = 2
BAND_H_MIN, BAND_H_MAX = 8, 15
BAND_PX_MIN = 150


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

def draw_projection(wpr, img_width, bar_width=300):
    """Sideways bar chart of white-pixels-per-row.

    Green bars = above ROW_THRESHOLD, gray bars = below.
    Red vertical line marks the threshold.

    Returns BGR image (height=len(wpr), width=bar_width).
    """
    h = len(wpr)
    canvas = np.zeros((h, bar_width, 3), dtype=np.uint8)
    max_val = max(int(wpr.max()), 1)
    scale = (bar_width - 20) / max_val  # leave margin

    for y in range(h):
        bw = int(wpr[y] * scale)
        if bw > 0:
            color = (0, 200, 0) if wpr[y] >= ROW_THRESHOLD else (100, 100, 100)
            cv2.line(canvas, (0, y), (bw, y), color, 1)

    # Red vertical line at threshold
    thr_x = int(ROW_THRESHOLD * scale)
    cv2.line(canvas, (thr_x, 0), (thr_x, h - 1), (0, 0, 255), 1)
    cv2.putText(canvas, f"thr={ROW_THRESHOLD}", (thr_x + 3, 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)

    return canvas


def draw_bands_overlay(img, bands, alpha=0.3):
    """Semi-transparent blue rectangles over detected bands.

    Returns annotated BGR copy.
    """
    vis = img.copy()
    overlay = img.copy()
    for (ys, ye) in bands:
        cv2.rectangle(overlay, (0, ys), (vis.shape[1] - 1, ye - 1),
                       (255, 150, 0), -1)  # filled blue
    cv2.addWeighted(overlay, alpha, vis, 1 - alpha, 0, vis)
    # Draw borders and labels
    for i, (ys, ye) in enumerate(bands):
        cv2.rectangle(vis, (0, ys), (vis.shape[1] - 1, ye - 1),
                       (255, 150, 0), 1)
        cv2.putText(vis, f"band {i} y={ys}-{ye} h={ye - ys}",
                    (4, ys - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.35,
                    (255, 150, 0), 1)
    return vis


def draw_tagged_lines(img, lines):
    """Blue boxes for headers, green for effects, grey for skipped. With labels.

    Returns annotated BGR copy.
    """
    vis = img.copy()
    for i, line in enumerate(lines):
        b = line['bounds']
        x, y, w, h = b['x'], b['y'], b['width'], b['height']
        is_hdr = line.get('is_enchant_hdr', False)
        is_grey = line.get('is_grey', False)
        if is_hdr:
            color = (255, 150, 0)
            slot = line.get('enchant_slot', '')
            tag = f"[{slot}]"
        elif is_grey:
            color = (140, 140, 140)
            tag = "grey"
        else:
            color = (0, 200, 0)
            tag = "eff"
        cv2.rectangle(vis, (x, y), (x + w - 1, y + h - 1), color, 1)
        cv2.putText(vis, f"{i}:{tag}", (x + w + 2, y + h - 1),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.3, color, 1)
    return vis


def draw_ocr_results(img, lines):
    """Pad image right 250px, draw boxes + 'conf text' per line.

    Returns annotated BGR image (wider than input).
    """
    pad_w = 250
    h, w = img.shape[:2]
    canvas = np.zeros((h, w + pad_w, 3), dtype=np.uint8)
    canvas[:, :w] = img if len(img.shape) == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    for i, line in enumerate(lines):
        b = line['bounds']
        x, y, bw, bh = b['x'], b['y'], b['width'], b['height']
        is_hdr = line.get('is_enchant_hdr', False)
        is_grey = line.get('is_grey', False)
        if is_hdr:
            color = (255, 150, 0)
        elif is_grey:
            color = (140, 140, 140)
        else:
            color = (0, 200, 0)
        cv2.rectangle(canvas, (x, y), (x + bw - 1, y + bh - 1), color, 1)

        if is_grey:
            label = "(grey/skipped)"
        else:
            text = line.get('text', '')
            conf = line.get('confidence', 0.0)
            label = f"{conf:.2f} {text[:30]}"
        cv2.putText(canvas, label, (w + 4, y + bh - 1),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.32, color, 1)
    return canvas


# ---------------------------------------------------------------------------
# Reader / corrector init
# ---------------------------------------------------------------------------

def init_content_reader():
    import easyocr
    from lib.ocr_utils import patch_reader_imgw

    print("Initializing content OCR reader (custom_mabinogi)...")
    content_reader = easyocr.Reader(
        ['ko'],
        model_storage_directory=MODELS_DIR,
        user_network_directory=MODELS_DIR,
        recog_network='custom_mabinogi',
    )
    fixed_imgW = patch_reader_imgw(content_reader, MODELS_DIR)
    print(f"Content reader initialized with fixed imgW={fixed_imgW}")
    return content_reader


def init_corrector():
    from lib.text_processors import MabinogiTextCorrector
    return MabinogiTextCorrector(dict_dir=DICT_DIR)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Visualize the enchant OCR pipeline step by step')
    parser.add_argument('image', help='Path to original color screenshot or enchant crop')
    parser.add_argument('output', help='Output directory for visualization images')
    parser.add_argument('--crop', action='store_true',
                        help='Treat input as a pre-cropped enchant content image '
                             '(skip segmentation, no header reader needed)')
    args = parser.parse_args()

    if not os.path.isfile(args.image):
        print(f"ERROR: file not found: {args.image}")
        sys.exit(1)
    os.makedirs(args.output, exist_ok=True)

    # --- Init ---
    content_reader = init_content_reader()
    corrector = init_corrector()
    tooltip_parser = MabinogiTooltipParser(CONFIG_PATH)
    splitter = MabinogiTooltipSplitter()

    img_bgr = cv2.imread(args.image)
    if img_bgr is None:
        print(f"ERROR: cannot read image: {args.image}")
        sys.exit(1)

    print(f"\nImage: {args.image}  ({img_bgr.shape[1]}x{img_bgr.shape[0]})")

    if args.crop:
        # Input is already the enchant content region
        content_bgr = img_bgr
    else:
        # Full screenshot: segment and find enchant section
        print("Initializing header OCR reader (custom_header)...")
        header_reader = init_header_reader(models_dir=MODELS_DIR)
        config = load_config(CONFIG_PATH)
        section_patterns = load_section_patterns(CONFIG_PATH)

        tagged = segment_and_tag(img_bgr, header_reader, section_patterns, config)

        enchant_seg = None
        available = []
        for seg in tagged:
            sec = seg['section']
            available.append(sec or '(unknown)')
            if sec == 'enchant':
                enchant_seg = seg

        if enchant_seg is None:
            print(f"\nNo enchant section found.")
            print(f"Available sections: {', '.join(available)}")
            sys.exit(0)

        content_bgr = enchant_seg['content_crop']
    ch, cw = content_bgr.shape[:2]
    print(f"\nEnchant content region: {cw}x{ch}")

    # =====================================================================
    # Step 1: Save content region
    # =====================================================================
    print(f"\n--- Step 1: Content region ---")
    print(f"  Size: {cw}x{ch}")
    cv2.imwrite(os.path.join(args.output, '01_content_region.png'), content_bgr)

    # =====================================================================
    # Step 2: White mask (replicate inline to capture intermediates)
    # =====================================================================
    print(f"\n--- Step 2: White mask ---")
    r = content_bgr[:, :, 2].astype(np.float32)
    g = content_bgr[:, :, 1].astype(np.float32)
    b = content_bgr[:, :, 0].astype(np.float32)
    max_ch = np.maximum(np.maximum(r, g), b)
    min_ch = np.minimum(np.minimum(r, g), b)
    white_mask = (max_ch > 150) & ((max_ch / (min_ch + 1)) < 1.4)

    wpr = white_mask.sum(axis=1)  # white pixels per row
    total_white = int(white_mask.sum())
    print(f"  White pixels total: {total_white} ({100 * total_white / (ch * cw):.1f}%)")
    print(f"  White-px-per-row: min={int(wpr.min())}, max={int(wpr.max())}, "
          f"mean={wpr.mean():.1f}")

    mask_img = (white_mask.astype(np.uint8) * 255)
    cv2.imwrite(os.path.join(args.output, '02_white_mask.png'), mask_img)

    # =====================================================================
    # Step 3: Projection chart
    # =====================================================================
    print(f"\n--- Step 3: Projection ---")
    proj_img = draw_projection(wpr, cw)
    cv2.imwrite(os.path.join(args.output, '03_projection.png'), proj_img)
    rows_above = int((wpr >= ROW_THRESHOLD).sum())
    print(f"  Rows above threshold ({ROW_THRESHOLD}): {rows_above}/{ch}")

    # =====================================================================
    # Step 4: Run detection → bands → overlay
    # =====================================================================
    print(f"\n--- Step 4: Band detection ---")

    # Replicate run detection from detect_enchant_slot_headers
    runs = []
    in_run = False
    run_start = 0
    for y in range(len(wpr)):
        if wpr[y] >= ROW_THRESHOLD:
            if not in_run:
                run_start = y
                in_run = True
        else:
            if in_run:
                runs.append((run_start, y))
                in_run = False
    if in_run:
        runs.append((run_start, len(wpr)))
    print(f"  Raw runs: {len(runs)}")
    for i, (s, e) in enumerate(runs):
        print(f"    run {i}: y={s}-{e} h={e - s} px={int(wpr[s:e].sum())}")

    # Merge
    merged = []
    for start, end in runs:
        if merged and start - merged[-1][1] <= GAP_TOLERANCE:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    print(f"  After merge (gap_tol={GAP_TOLERANCE}): {len(merged)}")

    # Filter
    bands = []
    for start, end in merged:
        h = end - start
        total_px = int(wpr[start:end].sum())
        ok = BAND_H_MIN <= h <= BAND_H_MAX and total_px >= BAND_PX_MIN
        status = 'PASS' if ok else 'FAIL'
        print(f"    band y={start}-{end} h={h} px={total_px}  [{status}]")
        if ok:
            bands.append((start, end))

    # Validate against library function
    lib_bands = detect_enchant_slot_headers(content_bgr)
    if bands == lib_bands:
        print(f"  Validation: matches detect_enchant_slot_headers() [{len(bands)} bands]")
    else:
        print(f"  WARNING: mismatch with detect_enchant_slot_headers()!")
        print(f"    inline: {bands}")
        print(f"    lib:    {lib_bands}")

    bands_img = draw_bands_overlay(content_bgr, bands)
    cv2.imwrite(os.path.join(args.output, '04_bands_overlay.png'), bands_img)

    # =====================================================================
    # Step 5: Binary preprocessing
    # =====================================================================
    print(f"\n--- Step 5: Binary preprocessing ---")
    gray = cv2.cvtColor(content_bgr, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY_INV)
    cv2.imwrite(os.path.join(args.output, '05_binary.png'), binary)
    ink_px = int((binary > 0).sum())
    print(f"  Binary (threshold=80): ink pixels={ink_px} "
          f"({100 * ink_px / (ch * cw):.1f}%)")

    # =====================================================================
    # Step 6: Line detection + classification (header/effect/grey)
    # =====================================================================
    print(f"\n--- Step 6: Line detection + classification ---")
    binary_detect = cv2.bitwise_not(binary)
    detected = splitter.detect_centered_lines(binary_detect)
    grouped = group_by_y(detected)
    print(f"  Detected {len(detected)} raw lines → {len(grouped)} groups")

    # Classify each group
    COLOR_HDR  = (0, 0, 255)    # red
    COLOR_EFF  = (0, 200, 0)    # green
    COLOR_GREY = (140, 140, 140) # grey

    vis_lines = binary.copy()
    if len(vis_lines.shape) == 2:
        vis_lines = cv2.cvtColor(vis_lines, cv2.COLOR_GRAY2BGR)

    classifications = []  # (group, merged_bounds, line_type)
    for group in grouped:
        first, last = group[0], group[-1]
        bounds = {
            'x': first['x'], 'y': first['y'],
            'width': (last['x'] + last['width']) - first['x'],
            'height': first['height'],
        }
        lt = classify_enchant_line(content_bgr, bounds, bands)
        classifications.append((group, bounds, lt))

        x, y, w, lh = bounds['x'], bounds['y'], bounds['width'], bounds['height']
        color = COLOR_HDR if lt == 'header' else COLOR_GREY if lt == 'grey' else COLOR_EFF
        tag = 'HDR' if lt == 'header' else 'GREY' if lt == 'grey' else 'eff'
        cv2.rectangle(vis_lines, (x, y), (x + w - 1, y + lh - 1), color, 1)
        cv2.putText(vis_lines, f"{len(classifications)-1}:{tag}",
                    (x + w + 2, y + lh - 1),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.3, color, 1)

    n_hdr = sum(1 for _, _, lt in classifications if lt == 'header')
    n_eff = sum(1 for _, _, lt in classifications if lt == 'effect')
    n_grey = sum(1 for _, _, lt in classifications if lt == 'grey')
    print(f"  Classification: header={n_hdr}  effect={n_eff}  grey={n_grey}")
    for i, (_, bounds, lt) in enumerate(classifications):
        print(f"    group {i}: y={bounds['y']:3d} h={bounds['height']:2d} w={bounds['width']:3d}  [{lt}]")

    cv2.imwrite(os.path.join(args.output, '06_lines_classified.png'), vis_lines)

    # =====================================================================
    # Step 7: Selective OCR (effects only) + tagging
    # =====================================================================
    print(f"\n--- Step 7: Selective OCR + tagging ---")
    print(f"  OCR calls: {n_eff} (skipping {n_hdr} headers + {n_grey} grey)")

    # Batch OCR only effect groups
    effect_groups = [g for g, _, lt in classifications if lt == 'effect']
    effect_ocr = (ocr_grouped_lines(binary, effect_groups, content_reader)
                  if effect_groups else [])
    effect_iter = iter(effect_ocr)

    # Assemble results
    ocr_results = []
    slot_idx = 0
    for group, bounds, line_type in classifications:
        if line_type == 'header':
            slot_idx += 1
            ocr_results.append({
                'text': '', 'confidence': 0.0,
                'sub_count': len(group), 'bounds': bounds, 'sub_lines': [],
                'section': 'enchant', 'is_enchant_hdr': True,
                'enchant_slot': '접두' if slot_idx == 1 else '접미',
                'enchant_name': '', 'enchant_rank': '',
            })
        elif line_type == 'grey':
            ocr_results.append({
                'text': '', 'confidence': 0.0,
                'sub_count': len(group), 'bounds': bounds, 'sub_lines': [],
                'section': 'enchant', 'is_enchant_hdr': False, 'is_grey': True,
            })
        else:  # effect
            line = next(effect_iter)
            line['section'] = 'enchant'
            line['is_enchant_hdr'] = False
            ocr_results.append(line)

    for i, line in enumerate(ocr_results):
        if line.get('is_enchant_hdr'):
            tag = f"[{line.get('enchant_slot', '')}]"
        elif line.get('is_grey'):
            tag = "GREY/skip"
        else:
            tag = "effect"
        conf = line.get('confidence', 0.0)
        text = line.get('text', '')
        print(f"    line {i} ({tag}, conf={conf:.3f}): {text}")

    tagged_img = draw_tagged_lines(content_bgr, ocr_results)
    cv2.imwrite(os.path.join(args.output, '07_lines_tagged.png'), tagged_img)

    # =====================================================================
    # Step 8: OCR results with text annotations
    # =====================================================================
    print(f"\n--- Step 8: OCR results visualization ---")
    ocr_img = draw_ocr_results(content_bgr, ocr_results)
    cv2.imwrite(os.path.join(args.output, '08_ocr_results.png'), ocr_img)

    # =====================================================================
    # Step 9: Enchant identification via FM
    # =====================================================================
    print(f"\n--- Step 9: Enchant FM identification ---")

    # Group by slot
    slots = []
    current_hdr, current_effects = None, []
    for i, line in enumerate(ocr_results):
        if line.get('is_enchant_hdr'):
            if current_hdr is not None:
                slots.append((current_hdr, current_effects))
            current_hdr = (i, line)
            current_effects = []
        elif current_hdr is not None:
            current_effects.append((i, line))
    if current_hdr is not None:
        slots.append((current_hdr, current_effects))

    for (hdr_idx, hdr_line), effect_pairs in slots:
        slot_type = hdr_line.get('enchant_slot', '?')
        effect_texts = [l['text'] for _, l in effect_pairs if l.get('text', '').strip()]
        print(f"\n  Slot: {slot_type} (header line {hdr_idx})")
        print(f"  Effect texts ({len(effect_texts)}):")
        for t in effect_texts:
            print(f"    - {t}")

        entry, rank = corrector.identify_enchant_from_effects(effect_texts, slot_type)
        if entry:
            print(f"  Identified: {entry['header']}  (rank_score={rank:.1f})")
            print(f"  DB effects:")
            for eff in entry['effects']:
                print(f"    - {eff}")
        else:
            print(f"  No match (rank_score={rank:.1f})")

    # =====================================================================
    # Step 10: Build structured enchant tree
    # =====================================================================
    print(f"\n--- Step 10: Structured enchant tree ---")
    structured = tooltip_parser.build_enchant_structured(ocr_results)
    for slot_name in ('prefix', 'suffix'):
        slot = structured.get(slot_name)
        if slot is None:
            print(f"  {slot_name}: None")
        else:
            print(f"  {slot_name}:")
            print(f"    name: {slot.get('name', '')}")
            print(f"    rank: {slot.get('rank', '')}")
            print(f"    effects ({len(slot.get('effects', []))}):")
            for eff in slot.get('effects', []):
                opt = ''
                if eff.get('option_name'):
                    opt = f"  [opt: {eff['option_name']}={eff.get('option_level', '')}]"
                print(f"      - {eff['text']}{opt}")

    print(f"\nOutput saved to: {args.output}/")
    print(f"  {len([f for f in os.listdir(args.output) if f.endswith('.png')])} images written")


if __name__ == '__main__':
    main()
