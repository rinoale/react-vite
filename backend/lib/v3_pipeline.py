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
from lib.section_handlers import PreHeaderHandler, get_handler
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


def _step_resolve_enchant(sections, corrector):
    """Three-strategy enchant resolution (P1/P2/P3).

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
            # Collect OCR effect lines for this slot
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


def _save_crops_by_section(sections, crop_session_dir, session_id):
    """Persist per-line crop images and OCR results JSON.

    Crop filenames: {section}/{line_index:03d}.png
    """
    originals = []
    for sec_key, sec_data in sections.items():
        lines = sec_data.get('lines') or []
        sec_dir = os.path.join(crop_session_dir, sec_key)
        for line in lines:
            li = line.get('line_index')
            if li is None:
                continue
            crop = line.pop('_crop', None)
            if crop is not None:
                os.makedirs(sec_dir, exist_ok=True)
                cv2.imwrite(os.path.join(sec_dir, f"{li:03d}.png"), crop)

            originals.append({
                'section': sec_key,
                'line_index': li,
                'text': line.get('text', ''),
                'raw_text': line.get('raw_text', line.get('text', '')),
                'confidence': float(line.get('confidence', 0)),
                'ocr_model': line.get('ocr_model', ''),
                'fm_applied': bool(line.get('fm_applied', False)),
            })

    with open(os.path.join(crop_session_dir, 'ocr_results.json'), 'w',
              encoding='utf-8') as f:
        json.dump(originals, f, ensure_ascii=False, indent=2)

    n_crops = sum(1 for o in originals
                  if os.path.isfile(os.path.join(
                      crop_session_dir, o['section'], f"{o['line_index']:03d}.png")))
    logger.info("v3 crops  session=%s  %d/%d saved", session_id, n_crops, len(originals))


@timed("v3 pipeline total")
def run_v3_pipeline(img_bgr, pipeline, *, save_crops=False, save_crops_dir=None):
    """Run the full v3 pipeline on a color screenshot.

    Args:
        img_bgr: Original color screenshot (BGR numpy array).
        pipeline: Dict from init_pipeline() with all shared resources.
        save_crops: Whether to persist per-line crop images.
        save_crops_dir: Base directory for crop sessions.

    Each section is processed end-to-end by its handler.
    No flat all_lines list — sections dict is the sole output.

    Returns:
        dict with 'sections', 'tagged_segments', 'abbreviated',
        and optionally 'session_id'
    """
    parser = pipeline['parser']
    corrector = pipeline['corrector']

    session_id = None
    crop_session_dir = None
    if save_crops:
        session_id = str(uuid.uuid4())
        if save_crops_dir:
            crop_session_dir = os.path.join(save_crops_dir, session_id)
        else:
            crop_session_dir = os.path.join(
                BASE_DIR, '..', 'tmp', 'ocr_crops', session_id)
        os.makedirs(crop_session_dir, exist_ok=True)

    # Step 1: Detect orange headers → segment into pre_header + tagged sections
    pre_header_seg, content_segments, tagged = _step_segment(
        img_bgr, pipeline['header_reader'], pipeline['section_patterns'],
        pipeline['config'])

    sections = {}
    attach = crop_session_dir is not None

    # Step 2: Pre-header — must run first (produces parsed_item_name for enchant)
    ph_handler = PreHeaderHandler()
    section_data, detected_font = ph_handler.process(
        pre_header_seg, pipeline, crop_session_dir=crop_session_dir)
    sections['pre_header'] = section_data
    parsed_item_name = section_data.get('parsed_item_name')

    # Set font_reader on pipeline for content handlers to use
    pipeline['font_reader'] = (
        pipeline['content_ng_reader'] if detected_font == 'nanum_gothic'
        else pipeline['content_mc_reader'])

    # Step 3: Content sections — each handler processes its section end-to-end
    for seg in content_segments:
        section_key = seg['section']
        content_crop = seg['content_crop']
        if content_crop is None or content_crop.shape[0] == 0:
            continue

        sec_config = parser.sections_config.get(section_key, {})
        if sec_config.get('skip', False):
            sections[section_key] = {'skipped': True, 'line_count': 0}
            continue

        handler = get_handler(section_key)
        section_data = handler.process(
            seg, pipeline,
            attach_crops=attach,
            parsed_item_name=parsed_item_name)

        if section_key not in sections:
            sections[section_key] = section_data
        else:
            # Merge duplicate sections (multiple headers with same label)
            existing = sections[section_key]
            if 'lines' in existing and 'lines' in section_data:
                existing['lines'].extend(section_data['lines'])

    # Step 4: Assign line_index per section (0-based within each section)
    for sec_data in sections.values():
        for idx, line in enumerate(sec_data.get('lines') or []):
            line['line_index'] = idx

    # Step 5: Save crop images (iterate sections, not flat list)
    if crop_session_dir:
        cv2.imwrite(os.path.join(crop_session_dir, 'original.png'), img_bgr)
        _save_crops_by_section(sections, crop_session_dir, session_id)

    # Step 6: Final enchant header competition (P1/P2/P3)
    _step_resolve_enchant(sections, corrector)

    # Log FM stats
    all_fm = sum(
        sum(1 for l in (sd.get('lines') or []) if l.get('fm_applied'))
        for sd in sections.values())
    all_total = sum(len(sd.get('lines') or []) for sd in sections.values())
    logger.info("v3 fm  %d/%d lines corrected", all_fm, all_total)

    # Detect abbreviated vs detail tooltip mode from item_grade content lines
    item_grade = sections.get('item_grade', {})
    grade_lines = [l for l in (item_grade.get('lines') or []) if not l.get('is_header')]
    abbreviated = len(grade_lines) <= 1

    result_dict = {
        'sections': sections,
        'tagged_segments': tagged,
        'abbreviated': abbreviated,
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
            sec_copy['header_index'] = h.get('line_index')
        sec_copy['lines'] = [l for l in lines if not l.get('is_header')]
        out[key] = sec_copy
    return out
