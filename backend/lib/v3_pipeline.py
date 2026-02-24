"""V3 OCR pipeline: segment-first processing.

Shared by /upload-item-v3 endpoint and test scripts.
"""

import json
import os
import uuid

import cv2
import easyocr

from lib.dual_reader import DualReader
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

BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR  = os.path.join(BASE_DIR, 'ocr', 'models')
CONFIG_PATH = os.path.join(BASE_DIR, '..', 'configs', 'mabinogi_tooltip.yaml')
DICT_DIR    = os.path.join(BASE_DIR, '..', 'data', 'dictionary')


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

    parser = MabinogiTooltipParser(CONFIG_PATH)
    section_patterns = load_section_patterns(CONFIG_PATH)
    config = load_config(CONFIG_PATH)
    corrector = TextCorrector(dict_dir=DICT_DIR)

    return {
        'header_reader': header_reader,
        'enchant_header_reader': enchant_header_reader,
        'content_reader': content_reader,
        'parser': parser,
        'section_patterns': section_patterns,
        'config': config,
        'corrector': corrector,
    }


def run_v3_pipeline(img_bgr, header_reader, section_patterns, config,
                    content_reader, enchant_header_reader, parser, corrector,
                    save_raw=False, save_crops=False):
    """Run the full v3 pipeline on a color screenshot.

    Steps:
      1. segment_and_tag — header detection + section labeling
      2. parse_from_segments — content OCR per segment
      3. apply_fm — prefix stripping + section-aware fuzzy matching
      4. rebuild structured data for enchant/reforge sections

    Args:
        save_raw: if True, saves pre-FM text as line['raw_text'] (for test comparison)
        save_crops: if True, saves per-line crop PNGs keyed by session_id

    Returns:
        dict with 'sections', 'all_lines', 'tagged_segments', and optionally 'session_id'
    """
    # Generate session for crop persistence
    session_id = None
    crop_session_dir = None
    if save_crops:
        session_id = str(uuid.uuid4())
        crop_session_dir = os.path.join(
            BASE_DIR, '..', 'tmp', 'ocr_crops', session_id)
        os.makedirs(crop_session_dir, exist_ok=True)

    # Step 1: segment with header OCR
    tagged = segment_and_tag(img_bgr, header_reader, section_patterns, config)

    # Step 2: content OCR per segment
    result = parser.parse_from_segments(
        tagged, content_reader, enchant_header_reader=enchant_header_reader,
        crop_session_dir=crop_session_dir)

    all_lines = result.get('all_lines', [])
    sections = result.get('sections', {})

    # Tag every line with a global index (needed for frontend diff mapping)
    for idx, line in enumerate(all_lines):
        line['global_index'] = idx

    # Persist per-line crop images for correction training
    if crop_session_dir:
        for line in all_lines:
            crop = line.pop('_crop', None)
            if crop is not None:
                fname = f"{line['global_index']:03d}.png"
                cv2.imwrite(os.path.join(crop_session_dir, fname), crop)

    if save_raw:
        for line in all_lines:
            line['raw_text'] = line.get('text', '')

    # Step 3: FM (includes prefix stripping)
    corrector.apply_fm(all_lines, sections)

    # Step 4: rebuild structured data from FM-corrected lines
    if 'enchant' in sections and sections['enchant'].get('lines'):
        enchant_updated = parser.build_enchant_structured(sections['enchant']['lines'])
        sections['enchant'].update(enchant_updated)

    if 'reforge' in sections and sections['reforge'].get('lines'):
        reforge_updated = parser.build_reforge_structured(sections['reforge']['lines'])
        sections['reforge'].update(reforge_updated)

    # Persist original OCR results for server-side diffing at registration time
    if crop_session_dir:
        originals = []
        for line in all_lines:
            originals.append({
                'global_index': line['global_index'],
                'text': line.get('text', ''),
                'confidence': float(line.get('confidence', 0)),
                'section': line.get('section', ''),
                'ocr_model': line.get('ocr_model', ''),
                'fm_applied': bool(line.get('fm_applied', False)),
            })
        with open(os.path.join(crop_session_dir, 'ocr_results.json'), 'w',
                  encoding='utf-8') as f:
            json.dump(originals, f, ensure_ascii=False)

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
