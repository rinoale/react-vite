"""V3 OCR pipeline: segment-first processing.

Shared by /upload-item-v3 endpoint and test scripts.
"""

import json
import os
import re
import uuid

import cv2
import easyocr
import numpy as np

from lib.dual_reader import DualReader
from lib.log import logger, timed, timed_block
from lib.mabinogi_tooltip_parser import MabinogiTooltipParser
from lib.ocr_utils import patch_reader_imgw
from lib.text_corrector import TextCorrector
from lib.tooltip_segmenter import (
    init_header_reader,
    init_enchant_header_reader,
    load_section_patterns,
    load_config,
    segment_and_tag,
)

# Known mabinogi_classic.ttf text colors in tooltips (RGB).
MABINOGI_CLASSIC_COLORS = [
    (255, 252, 157),  # yellow (item name, emphasis)
    (255, 255, 255),  # white (general text)
]


def mabinogi_classic_mask(img_bgr, tolerance=5):
    """Create a binary mask of pixels matching known mabinogi_classic font colors.

    Args:
        img_bgr: BGR image (numpy array)
        tolerance: per-channel tolerance for color matching

    Returns:
        Binary mask (numpy uint8, 255=match, 0=no match)
    """
    mask = np.zeros(img_bgr.shape[:2], dtype=np.uint8)
    for r, g, b in MABINOGI_CLASSIC_COLORS:
        bgr = np.array([b, g, r], dtype=np.int16)
        diff = np.abs(img_bgr.astype(np.int16) - bgr)
        match = np.all(diff <= tolerance, axis=2)
        mask[match] = 255
    return mask


BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR  = os.path.join(BASE_DIR, 'ocr', 'models')
CONFIG_PATH = os.path.join(BASE_DIR, '..', 'configs', 'mabinogi_tooltip.yaml')
DICT_DIR    = os.path.join(BASE_DIR, '..', 'data', 'dictionary')


@timed("v3 init_pipeline")
def init_pipeline():
    """Initialize all V3 pipeline components.

    Returns:
        dict with keys: header_reader, enchant_header_reader,
        content_reader, parser, section_patterns, config, corrector
    """
    header_reader = init_header_reader(models_dir=MODELS_DIR)
    enchant_header_reader = init_enchant_header_reader(models_dir=MODELS_DIR)

    # Dual-reader: two font-specific models, pick higher confidence per line.
    classic_reader = easyocr.Reader(
        ['ko'],
        model_storage_directory=MODELS_DIR,
        user_network_directory=MODELS_DIR,
        recog_network='custom_mabinogi_classic',
    )
    patch_reader_imgw(classic_reader, MODELS_DIR, recog_network='custom_mabinogi_classic')

    nanum_reader = easyocr.Reader(
        ['ko'],
        model_storage_directory=MODELS_DIR,
        user_network_directory=MODELS_DIR,
        recog_network='custom_nanum_gothic_bold',
    )
    patch_reader_imgw(nanum_reader, MODELS_DIR, recog_network='custom_nanum_gothic_bold')

    content_reader = DualReader(
        [classic_reader, nanum_reader],
        ['mabinogi_classic', 'nanum_gothic_bold'],
    )

    # Dedicated preheader reader for mabinogi_classic font
    preheader_mc_reader = easyocr.Reader(
        ['ko'],
        model_storage_directory=MODELS_DIR,
        user_network_directory=MODELS_DIR,
        recog_network='custom_preheader_mabinogi_classic',
    )
    patch_reader_imgw(preheader_mc_reader, MODELS_DIR,
                      recog_network='custom_preheader_mabinogi_classic')

    # Dedicated preheader reader for nanum_gothic font
    preheader_ng_reader = easyocr.Reader(
        ['ko'],
        model_storage_directory=MODELS_DIR,
        user_network_directory=MODELS_DIR,
        recog_network='custom_preheader_nanum_gothic',
    )
    patch_reader_imgw(preheader_ng_reader, MODELS_DIR,
                      recog_network='custom_preheader_nanum_gothic')

    parser = MabinogiTooltipParser(CONFIG_PATH)
    section_patterns = load_section_patterns(CONFIG_PATH)
    config = load_config(CONFIG_PATH)
    corrector = TextCorrector(dict_dir=DICT_DIR)

    return {
        'header_reader': header_reader,
        'enchant_header_reader': enchant_header_reader,
        'content_reader': content_reader,
        'content_mc_reader': classic_reader,
        'content_ng_reader': nanum_reader,
        'preheader_mc_reader': preheader_mc_reader,
        'preheader_ng_reader': preheader_ng_reader,
        'parser': parser,
        'section_patterns': section_patterns,
        'config': config,
        'corrector': corrector,
    }


@timed("v3 segment")
def _step_segment(img_bgr, header_reader, section_patterns, config):
    """Step 1: Segment tooltip into sections via orange header detection + header OCR.

    Finds orange header bands in the color screenshot, expands to near-black
    boundaries, then OCR's each header to assign a canonical section name.
    The region above the first header becomes 'pre_header'.

    Returns:
        (pre_header_seg, content_segments, tagged)
    """
    tagged = segment_and_tag(img_bgr, header_reader, section_patterns, config)
    seg_labels = [s['section'] for s in tagged]
    logger.info("v3 segment  %d segments %s", len(tagged), seg_labels)

    pre_header_seg = None
    content_segments = []
    for seg in tagged:
        if seg['section'] == 'pre_header':
            pre_header_seg = seg
        else:
            content_segments.append(seg)

    return pre_header_seg, content_segments, tagged


def _preprocess_mabinogi_classic(content_bgr):
    """Color-mask preprocessing for mabinogi_classic font.

    Isolates white/yellow text pixels matching known mabinogi_classic font
    colors, then inverts to black-text-on-white for OCR.

    Returns:
        (detect_binary, ocr_binary) — detect has white text on black for
        line detection; ocr has black text on white for OCR.
    """
    mask = mabinogi_classic_mask(content_bgr)
    return mask, cv2.bitwise_not(mask)


def _preprocess_nanum_gothic(content_bgr):
    """HSV yellow-isolate + threshold 120 preprocessing for nanum_gothic text.

    Isolates yellow-hued pixels (H=15-45, OpenCV scale) while preserving
    white/gray text (low saturation → skipped). All other colored pixels
    (blue, purple, etc.) are set to black.

    Then threshold 120 BINARY_INV cleanly binarizes even AA'd text.

    Returns:
        (detect_binary, ocr_binary)
    """
    hsv = cv2.cvtColor(content_bgr, cv2.COLOR_BGR2HSV)
    h = hsv[:, :, 0]  # 0-180 in OpenCV
    s = hsv[:, :, 1]  # 0-255 in OpenCV

    # Isolate yellow hue (H=15-45), skip low-saturation pixels (white/black)
    sat_mask = s >= 38  # ~15% of 255
    not_yellow = ~((h >= 15) & (h <= 45))
    reject_mask = sat_mask & not_yellow

    masked = content_bgr.copy()
    masked[reject_mask] = 0

    gray = cv2.cvtColor(masked, cv2.COLOR_BGR2GRAY)
    _, ocr_binary = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY_INV)
    detect_binary = cv2.bitwise_not(ocr_binary)
    return detect_binary, ocr_binary


def _ocr_pre_header_image(detect_binary, ocr_binary, parser, reader,
                          save_label, save_crops_dir, attach_crops):
    """Run line detection + OCR on a preprocessed pre_header image.

    Returns:
        list of OCR result dicts with 'text', 'confidence', etc.
    """
    detected = parser.detect_text_lines(detect_binary)
    grouped = parser._group_by_y(detected)
    return parser._ocr_grouped_lines(
        ocr_binary, grouped, reader,
        save_crops_dir=save_crops_dir, save_label=save_label,
        attach_crops=attach_crops)


@timed("v3 pre_header")
def _step_pre_header(pre_header_seg, parser, preheader_mc_reader,
                     preheader_ng_reader, crop_session_dir):
    """Step 2a: Process the pre_header region (above first orange header).

    Produces two preprocessed images and OCR's both with dedicated readers:
      - mabinogi_classic: color-mask → dedicated preheader_mc model (fitted)
      - nanum_gothic: HSV yellow-isolate + threshold 120 → dedicated preheader_ng model (fitted)
    Picks the higher-confidence result per line to determine the best font/model.

    Returns:
        (lines, sections)
    """
    if not pre_header_seg:
        return [], {}

    content_bgr = pre_header_seg['content_crop']
    _save = os.environ.get('SAVE_OCR_CROPS')
    attach = crop_session_dir is not None

    # Preprocess: two approaches
    mc_detect, mc_ocr = _preprocess_mabinogi_classic(content_bgr)
    ng_detect, ng_ocr = _preprocess_nanum_gothic(content_bgr)

    # OCR: dedicated preheader models for both font paths
    mc_results = _ocr_pre_header_image(
        mc_detect, mc_ocr, parser, preheader_mc_reader,
        'pre_header_mc', _save, attach)
    ng_results = _ocr_pre_header_image(
        ng_detect, ng_ocr, parser, preheader_ng_reader,
        'pre_header_ng', _save, attach)

    # Pick best per line by confidence
    ocr_results = _pick_best_per_line(mc_results, ng_results)

    for line in ocr_results:
        line['section'] = 'pre_header'
    sections = parser._parse_pre_header(ocr_results)
    lines = sections.get('pre_header', {}).get('lines', [])

    # Determine dominant font from pre_header results
    mc_count = sum(1 for l in ocr_results if l.get('preprocess') == 'mabinogi_classic')
    ng_count = sum(1 for l in ocr_results if l.get('preprocess') == 'nanum_gothic')
    detected_font = 'nanum_gothic' if ng_count > mc_count else 'mabinogi_classic'

    logger.info("v3 pre_header  %d lines  font=%s", len(lines), detected_font)
    return lines, sections, detected_font


def _pick_best_per_line(mc_results, ng_results):
    """Pick the higher-confidence OCR result per line from two preprocessing paths.

    Lines are matched by vertical position (bounds['y']). If line counts differ,
    the longer list is used as the base and unmatched lines keep their original result.

    Tie-breaking: mabinogi_classic is the default (more common font in tooltips).
    NG must have strictly higher confidence to win.

    Each result gets a 'preprocess' tag: 'mabinogi_classic' or 'nanum_gothic'.
    """
    def _y_key(line):
        return line.get('bounds', {}).get('y', 0)

    mc_by_y = {_y_key(line): line for line in mc_results}
    ng_by_y = {_y_key(line): line for line in ng_results}

    all_ys = sorted(set(mc_by_y) | set(ng_by_y))

    merged = []
    for y in all_ys:
        mc_line = mc_by_y.get(y)
        ng_line = ng_by_y.get(y)

        if mc_line and ng_line:
            # NG must strictly beat MC to win; tie goes to MC
            if ng_line.get('confidence', 0) > mc_line.get('confidence', 0):
                ng_line['preprocess'] = 'nanum_gothic'
                merged.append(ng_line)
            else:
                mc_line['preprocess'] = 'mabinogi_classic'
                merged.append(mc_line)
        elif mc_line:
            mc_line['preprocess'] = 'mabinogi_classic'
            merged.append(mc_line)
        else:
            ng_line['preprocess'] = 'nanum_gothic'
            merged.append(ng_line)

    return merged


@timed("v3 content_ocr")
def _step_content_ocr(content_segments, parser, content_reader,
                      enchant_header_reader, crop_session_dir):
    """Step 2b: Content OCR for each tagged segment (excluding pre_header).

    Each segment's content crop is preprocessed (BT.601 grayscale + threshold),
    split into lines via TooltipLineSplitter, then OCR'd with DualReader
    (mabinogi_classic + nanum_gothic_bold, highest confidence wins).
    Enchant segments use a dedicated enchant_header_reader for slot headers.

    Returns:
        (all_lines, sections)
    """
    result = parser.parse_from_segments(
        content_segments, content_reader,
        enchant_header_reader=enchant_header_reader,
        crop_session_dir=crop_session_dir)
    return result.get('all_lines', []), result.get('sections', {})


@timed("v3 fm")
def _step_fm(all_lines, sections, corrector):
    """Step 3: Section-aware fuzzy matching against per-section dictionaries.

    Strips bullet prefixes (., ㄴ), then matches OCR text against known
    dictionary entries using RapidFuzz. If fm_score > 0, replaces text
    with the matched dictionary entry (fm_applied=true). Enchant effects
    use condition-stripped matching to avoid short-entry inflation.

    Mutates all_lines and sections in place.
    """
    corrector.apply_fm(all_lines, sections)
    fm_count = sum(1 for l in all_lines if l.get('fm_applied'))
    logger.info("v3 fm  %d/%d lines corrected", fm_count, len(all_lines))


@timed("v3 rebuild_structured")
def _step_rebuild_structured(sections, parser):
    """Step 4: Rebuild structured data for enchant and reforge sections.

    After FM correction, re-parses enchant lines into prefix/suffix slot dicts
    (name, rank, effects[]) and reforge lines into option_name/option_level pairs.
    Must run after FM so corrected text propagates into structured data.

    Mutates sections in place.
    """
    if 'enchant' in sections and sections['enchant'].get('lines'):
        enchant_updated = parser.build_enchant_structured(sections['enchant']['lines'])
        sections['enchant'].update(enchant_updated)

    if 'reforge' in sections and sections['reforge'].get('lines'):
        reforge_updated = parser.build_reforge_structured(sections['reforge']['lines'])
        sections['reforge'].update(reforge_updated)


def _step_parse_item_name(sections, corrector):
    """Step 5: Parse the first pre_header line into structured item name components.

    Extracts holywater, enchant_prefix, enchant_suffix, ego, and item_name
    from the OCR text. Stores result in sections['pre_header']['parsed_item_name'].
    """
    ph = sections.get('pre_header', {})
    ph_lines = ph.get('lines', [])
    if not ph_lines:
        return

    first_text = ph_lines[0].get('text', '')
    if not first_text:
        return

    parsed = corrector.parse_item_name(first_text)
    ph['parsed_item_name'] = parsed


def _step_resolve_enchant(sections, corrector):
    """Step 6: Three-strategy enchant resolution (P1/P2/P3).

    Collects enchant name candidates from three sources:
      P1: Item name parsing (pre_header OCR → FM against enchant dicts)
      P2: Raw enchant header OCR (pre-Dullahan snapshot)
      P3: Dullahan result (header + effect body matching)

    P1 is prioritized. When the winner is found in the DB, its effects
    serve as templates with OCR numbers injected as rolled values.

    Mutates sections['enchant'] in place.
    """
    enchant = sections.get('enchant')
    if not enchant:
        return

    parsed = sections.get('pre_header', {}).get('parsed_item_name')
    enchant_lines = enchant.get('lines', [])

    resolution = {}

    for slot_key, slot_type, p1_field in [
        ('prefix', '접두', 'enchant_prefix'),
        ('suffix', '접미', 'enchant_suffix'),
    ]:
        p1_name, p1_entry, p1_score = None, None, 0
        p2_name, p2_raw = None, None
        p3_name, p3_score = None, 0

        # Collect P1: from parsed item name
        if parsed and parsed.get(p1_field):
            p1_name = parsed[p1_field]
            p1_entry = corrector.lookup_enchant_by_name(p1_name, slot_type=slot_type)
            if p1_entry:
                p1_score = 100  # exact name match from item_name parser

        # Collect P2 and P3 from enchant header lines
        for line in enchant_lines:
            if not line.get('is_enchant_hdr'):
                continue
            line_slot = line.get('enchant_slot', '')
            if line_slot != slot_type:
                continue

            # P2: raw header OCR (before Dullahan)
            raw_hdr = line.get('_raw_enchant_header', '')
            if raw_hdr:
                p2_raw = raw_hdr
                # Extract name from raw header: '[접두] name' or '[접두] name (랭크 X)'
                m = re.match(r'\[?(접두|접미)\]?\s+(.+?)(?:\s*\(랭크\s*[A-F0-9]+\))?\s*$', raw_hdr)
                if m:
                    p2_name = m.group(2).strip()

            # P3: Dullahan result
            if line.get('enchant_name'):
                p3_name = line['enchant_name']
                p3_score = line.get('_dullahan_score', 0)

        # Priority: P1 > P2 > P3
        winner = None
        winner_entry = None
        winner_source = None

        if p1_entry:
            winner = p1_name
            winner_entry = p1_entry
            winner_source = 'P1_item_name'
        elif p2_name:
            winner = p2_name
            winner_entry = corrector.lookup_enchant_by_name(p2_name, slot_type=slot_type)
            winner_source = 'P2_header_ocr'
        elif p3_name:
            winner = p3_name
            winner_entry = corrector.lookup_enchant_by_name(p3_name, slot_type=slot_type)
            winner_source = 'P3_dullahan'

        slot_resolution = {
            'winner': winner_source,
            'p1': {'name': p1_name, 'score': p1_score} if p1_name else None,
            'p2': {'name': p2_name, 'raw_text': p2_raw} if p2_name else None,
            'p3': {'name': p3_name, 'score': p3_score} if p3_name else None,
        }
        resolution[slot_key] = slot_resolution

        # Enrich enchant slot with DB-templated effects for any winner with a DB entry
        if winner_entry:
            # Collect OCR effect lines (dicts with text + global_index) for this slot
            ocr_effect_lines = []
            in_slot = False
            for line in enchant_lines:
                if line.get('is_enchant_hdr'):
                    in_slot = (line.get('enchant_slot', '') == slot_type)
                    continue
                if in_slot and not line.get('is_grey'):
                    if line.get('text', '').strip():
                        ocr_effect_lines.append(line)

            templated = corrector.build_templated_effects(winner_entry, ocr_effect_lines)
            enchant[slot_key] = {
                'text': f"[{slot_type}] {winner_entry['name']} (랭크 {winner_entry['rank']})",
                'name': winner_entry['name'],
                'rank': winner_entry['rank'],
                'effects': templated,
                'source': winner_source,
            }

    enchant['resolution'] = resolution
    logger.info("v3 resolve_enchant  %s", {k: v.get('winner') for k, v in resolution.items()})


def _save_crops(all_lines, crop_session_dir, session_id):
    """Persist OCR results JSON for correction training.

    Crop images are already saved before FM in run_v3_pipeline.
    """
    originals = []
    for line in all_lines:
        originals.append({
            'global_index': line['global_index'],
            'text': line.get('text', ''),
            'raw_text': line.get('raw_text', line.get('text', '')),
            'confidence': float(line.get('confidence', 0)),
            'section': line.get('section', ''),
            'ocr_model': line.get('ocr_model', ''),
            'fm_applied': bool(line.get('fm_applied', False)),
        })
    with open(os.path.join(crop_session_dir, 'ocr_results.json'), 'w',
              encoding='utf-8') as f:
        json.dump(originals, f, ensure_ascii=False, indent=2)
    n_crops = sum(1 for o in originals
                  if os.path.isfile(os.path.join(crop_session_dir, f"{o['global_index']:03d}.png")))
    logger.info("v3 crops  session=%s  %d/%d saved", session_id, n_crops, len(originals))


@timed("v3 pipeline total")
def run_v3_pipeline(img_bgr, header_reader, section_patterns, config,
                    content_reader, content_mc_reader, content_ng_reader,
                    enchant_header_reader,
                    preheader_mc_reader, preheader_ng_reader,
                    parser, corrector,
                    save_crops=False):
    """Run the full v3 pipeline on a color screenshot.

    Steps:
      1. segment    — header detection + section labeling
      2a. pre_header — color mask + OCR for item name region
      2b. content    — content OCR per segment
      3. fm          — prefix stripping + section-aware fuzzy matching
      4. rebuild     — structured data for enchant/reforge sections
      5. parse_item_name — extract enchant prefix/suffix from item name
      6. resolve_enchant — three-strategy resolution (P1/P2/P3)

    Returns:
        dict with 'sections', 'all_lines', 'tagged_segments', and optionally 'session_id'
    """
    session_id = None
    crop_session_dir = None
    if save_crops:
        session_id = str(uuid.uuid4())
        crop_session_dir = os.path.join(
            BASE_DIR, '..', 'tmp', 'ocr_crops', session_id)
        os.makedirs(crop_session_dir, exist_ok=True)

    # Step 1: Detect orange headers → segment into pre_header + tagged sections
    pre_header_seg, content_segments, tagged = _step_segment(
        img_bgr, header_reader, section_patterns, config)

    # Step 2a: Pre-header — dedicated preheader models for both fonts, pick best
    pre_header_lines, pre_header_sections, detected_font = _step_pre_header(
        pre_header_seg, parser, preheader_mc_reader,
        preheader_ng_reader, crop_session_dir)

    # Step 2b: Content — font-matched single reader + BT.601 grayscale
    font_reader = content_ng_reader if detected_font == 'nanum_gothic' else content_mc_reader
    content_lines, content_sections = _step_content_ocr(
        content_segments, parser, font_reader,
        enchant_header_reader, crop_session_dir)

    # Merge pre_header and content results
    all_lines = pre_header_lines + content_lines
    sections = {**pre_header_sections, **content_sections}

    # Assign global indices for frontend line mapping
    for idx, line in enumerate(all_lines):
        line['global_index'] = idx

    # Save crop images before FM (FM mutates text, crops should reflect raw OCR)
    if crop_session_dir:
        for line in all_lines:
            crop = line.pop('_crop', None)
            if crop is not None:
                fname = f"{line['global_index']:03d}.png"
                cv2.imwrite(os.path.join(crop_session_dir, fname), crop)

    # Snapshot raw OCR text before FM overwrites it
    for line in all_lines:
        line['raw_text'] = line.get('text', '')

    # Step 3: Fuzzy match OCR text against per-section dictionaries
    _step_fm(all_lines, sections, corrector)

    # Remove merged fragment lines so line counts match expected effects
    if 'enchant' in sections and sections['enchant'].get('lines'):
        sections['enchant']['lines'] = [
            l for l in sections['enchant']['lines'] if not l.get('_merged')]
    all_lines = [l for l in all_lines if not l.get('_merged')]
    # Re-index after filtering so frontend gets consecutive indices
    for idx, line in enumerate(all_lines):
        line['global_index'] = idx

    # Step 4: Rebuild enchant prefix/suffix slots and reforge options from corrected text
    _step_rebuild_structured(sections, parser)

    # Step 5: Parse item name from pre_header first line
    _step_parse_item_name(sections, corrector)

    # Step 6: Three-strategy enchant resolution (P1/P2/P3)
    _step_resolve_enchant(sections, corrector)

    # Persist OCR results JSON for correction training
    if crop_session_dir:
        _save_crops(all_lines, crop_session_dir, session_id)

    result_dict = {
        'sections': sections,
        'all_lines': all_lines,
        'tagged_segments': tagged,
    }
    if session_id:
        result_dict['session_id'] = session_id
    return result_dict


def prepare_sections_for_response(sections):
    """Transform raw sections for HTTP response.

    Promotes is_header lines to section-level metadata
    (header_text, header_confidence, header_index) and removes
    them from lines[].  Returns a new dict — does not mutate input.
    """
    out = {}
    for key, sec in sections.items():
        sec_copy = dict(sec)
        lines = sec_copy.get('lines') or []
        header_lines = [l for l in lines if l.get('is_header')]
        if header_lines:
            h = header_lines[0]
            sec_copy['header_text'] = h.get('text', '')
            sec_copy['header_confidence'] = h.get('confidence', 0.0)
            sec_copy['header_index'] = h.get('global_index')
        sec_copy['lines'] = [l for l in lines if not l.get('is_header')]
        out[key] = sec_copy
    return out
