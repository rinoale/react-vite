"""V3 OCR pipeline: segment-first processing.

Shared by /upload-item-v3 endpoint and test scripts.
"""

import json
import os
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


@timed("v3 pre_header")
def _step_pre_header(pre_header_seg, parser, content_reader, crop_session_dir):
    """Step 2a: Process the pre_header region (above first orange header).

    Contains item name, enchant prefix/suffix names, and holywater effects —
    all rendered in mabinogi_classic.ttf with white/yellow colors.
    Extracts these by color-masking known mabinogi_classic font colors,
    then line-splitting and OCR'ing the resulting binary mask.

    Returns:
        (lines, sections)
    """
    if not pre_header_seg:
        return [], {}

    mask = mabinogi_classic_mask(pre_header_seg['content_crop'])
    detected = parser.detect_text_lines(mask)
    grouped = parser._group_by_y(detected)
    ocr_binary = cv2.bitwise_not(mask)
    _save = os.environ.get('SAVE_OCR_CROPS')
    ocr_results = parser._ocr_grouped_lines(
        ocr_binary, grouped, content_reader,
        save_crops_dir=_save, save_label='pre_header',
        attach_crops=crop_session_dir is not None)
    for line in ocr_results:
        line['section'] = 'pre_header'
    sections = parser._parse_pre_header(ocr_results)
    lines = sections.get('pre_header', {}).get('lines', [])

    logger.info("v3 pre_header  %d lines", len(lines))
    return lines, sections


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


def _save_crops(all_lines, crop_session_dir, session_id):
    """Persist OCR results JSON for correction training.

    Crop images are already saved before FM in run_v3_pipeline.
    """
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
        json.dump(originals, f, ensure_ascii=False, indent=2)
    n_crops = sum(1 for o in originals
                  if os.path.isfile(os.path.join(crop_session_dir, f"{o['global_index']:03d}.png")))
    logger.info("v3 crops  session=%s  %d/%d saved", session_id, n_crops, len(originals))


@timed("v3 pipeline total")
def run_v3_pipeline(img_bgr, header_reader, section_patterns, config,
                    content_reader, enchant_header_reader, parser, corrector,
                    save_raw=False, save_crops=False):
    """Run the full v3 pipeline on a color screenshot.

    Steps:
      1. segment    — header detection + section labeling
      2a. pre_header — color mask + OCR for item name region
      2b. content    — content OCR per segment
      3. fm          — prefix stripping + section-aware fuzzy matching
      4. rebuild     — structured data for enchant/reforge sections

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

    # Step 2a: Pre-header — color-mask mabinogi_classic text → line split → OCR
    pre_header_lines, pre_header_sections = _step_pre_header(
        pre_header_seg, parser, content_reader, crop_session_dir)

    # Step 2b: Content — per-segment grayscale preprocess → line split → DualReader OCR
    content_lines, content_sections = _step_content_ocr(
        content_segments, parser, content_reader,
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

    # Snapshot raw OCR text before FM overwrites it (for test comparison)
    if save_raw:
        for line in all_lines:
            line['raw_text'] = line.get('text', '')

    # Step 3: Fuzzy match OCR text against per-section dictionaries
    _step_fm(all_lines, sections, corrector)

    # Step 4: Rebuild enchant prefix/suffix slots and reforge options from corrected text
    _step_rebuild_structured(sections, parser)

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
