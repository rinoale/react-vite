"""V3 OCR pipeline: segment-first processing.

Shared by /upload-item-v3 endpoint and test scripts.
"""

import json
import os
import re
import uuid

import cv2
import easyocr
import yaml

from lib.utils.log import logger, timed, timed_block
from lib.pipeline.tooltip_parsers import MabinogiTooltipParser
from lib.pipeline.line_split import MabinogiTooltipSplitter
from lib.patches import patch_reader_imgw
from lib.pipeline.section_handlers import PreHeaderHandler, get_handler
from lib.pipeline.segmenter import (
    init_header_reader,
    init_enchant_header_reader,
    load_section_patterns,
    load_config,
    segment_and_tag,
)
from lib.text_processors import MabinogiTextCorrector

BASE_DIR    = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODELS_DIR  = os.path.join(BASE_DIR, 'ocr', 'models')
CONFIG_PATH = os.path.join(BASE_DIR, '..', 'configs', 'mabinogi_tooltip.yaml')
LINE_SPLIT_CONFIG_PATH = os.path.join(BASE_DIR, '..', 'configs', 'line_split.yaml')
DICT_DIR    = os.path.join(BASE_DIR, '..', 'data', 'dictionary')


_pipeline = None


def get_pipeline():
    """Return the initialized pipeline singleton."""
    return _pipeline


@timed("v3 init_pipeline")
def init_pipeline():
    """Initialize all V3 pipeline components (module singleton).

    Call once at startup.  After this, get_pipeline() and
    run_v3_pipeline() use the singleton directly.
    """
    global _pipeline

    header_reader = init_header_reader(models_dir=MODELS_DIR)
    enchant_header_reader = init_enchant_header_reader(models_dir=MODELS_DIR)

    # Font-specific content readers (pre_header determines which one to use)
    classic_reader = easyocr.Reader(
        ['ko'],
        model_storage_directory=MODELS_DIR,
        user_network_directory=MODELS_DIR,
        recog_network='custom_mabinogi_classic',
    )
    patch_reader_imgw(classic_reader, MODELS_DIR, recog_network='custom_mabinogi_classic')
    classic_reader.font_name = 'mabinogi_classic'

    nanum_reader = easyocr.Reader(
        ['ko'],
        model_storage_directory=MODELS_DIR,
        user_network_directory=MODELS_DIR,
        recog_network='custom_nanum_gothic_bold',
    )
    patch_reader_imgw(nanum_reader, MODELS_DIR, recog_network='custom_nanum_gothic_bold')
    nanum_reader.font_name = 'nanum_gothic'

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

    # Load line-split config and apply game-specific horizontal split override
    with open(LINE_SPLIT_CONFIG_PATH, 'r') as f:
        line_split_cfg = yaml.safe_load(f) or {}
    game_split = parser.config.get('horizontal_split_factor')
    if game_split is not None:
        line_split_cfg.setdefault('horizontal', {})['split_factor'] = game_split
    splitter = MabinogiTooltipSplitter(config=line_split_cfg)

    section_patterns = load_section_patterns(CONFIG_PATH)
    config = load_config(CONFIG_PATH)
    corrector = MabinogiTextCorrector(dict_dir=DICT_DIR)

    _pipeline = {
        'header_reader': header_reader,
        'enchant_header_reader': enchant_header_reader,
        'content_mc_reader': classic_reader,
        'content_ng_reader': nanum_reader,
        'preheader_mc_reader': preheader_mc_reader,
        'preheader_ng_reader': preheader_ng_reader,
        'parser': parser,
        'splitter': splitter,
        'section_patterns': section_patterns,
        'config': config,
        'corrector': corrector,
    }
    return _pipeline


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

    pre_header = sections.get('pre_header', {})
    parsed = {
        'enchant_prefix': pre_header.get('enchant_prefix'),
        'enchant_suffix': pre_header.get('enchant_suffix'),
    }
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

            orig = {
                'section': sec_key,
                'line_index': li,
                'text': line.get('text', ''),
                'raw_text': line.get('raw_text', line.get('text', '')),
                'confidence': float(line.get('confidence', 0)),
                'ocr_model': line.get('ocr_model', ''),
                'fm_applied': bool(line.get('fm_applied', False)),
            }
            if line.get('_is_stitched'):  # continuation stitch: propagate to ocr_results.json
                orig['_is_stitched'] = True
            originals.append(orig)

    with open(os.path.join(crop_session_dir, 'ocr_results.json'), 'w',
              encoding='utf-8') as f:
        json.dump(originals, f, ensure_ascii=False, indent=2)

    n_crops = sum(1 for o in originals
                  if os.path.isfile(os.path.join(
                      crop_session_dir, o['section'], f"{o['line_index']:03d}.png")))
    logger.info("v3 crops  session=%s  %d/%d saved", session_id, n_crops, len(originals))


@timed("v3 pipeline total")
def run_v3_pipeline(img_bgr, *, save_crops=False, save_crops_dir=None):
    """Run the full v3 pipeline on a color screenshot.

    Uses the module-level pipeline singleton (initialized by init_pipeline()).

    Args:
        img_bgr: Original color screenshot (BGR numpy array).
        save_crops: Whether to persist per-line crop images.
        save_crops_dir: Base directory for crop sessions.

    Returns:
        dict with 'sections', 'tagged_segments', 'abbreviated',
        and optionally 'session_id'
    """
    parser = _pipeline['parser']
    corrector = _pipeline['corrector']

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
        img_bgr, _pipeline['header_reader'], _pipeline['section_patterns'],
        _pipeline['config'])

    sections = {}
    attach = crop_session_dir is not None

    # Step 2: Pre-header — must run first (produces parsed_item_name for enchant)
    ph_handler = PreHeaderHandler()
    section_data, detected_font = ph_handler.process(
        pre_header_seg, crop_session_dir=crop_session_dir)
    sections['pre_header'] = section_data
    parsed_item_name = {
        'enchant_prefix': section_data.get('enchant_prefix'),
        'enchant_suffix': section_data.get('enchant_suffix'),
    }

    # Choose font-matched reader for content sections (per-request)
    font_reader = (
        _pipeline['content_ng_reader'] if detected_font == 'nanum_gothic'
        else _pipeline['content_mc_reader'])

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
            seg,
            font_reader=font_reader,
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
