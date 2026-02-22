"""V3 OCR pipeline: segment-first processing.

Shared by /upload-item-v3 endpoint and test scripts.
"""

import os

import easyocr

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

    content_reader = easyocr.Reader(
        ['ko'],
        model_storage_directory=MODELS_DIR,
        user_network_directory=MODELS_DIR,
        recog_network='custom_mabinogi',
    )
    patch_reader_imgw(content_reader, MODELS_DIR)

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
                    save_raw=False):
    """Run the full v3 pipeline on a color screenshot.

    Steps:
      1. segment_and_tag — header detection + section labeling
      2. parse_from_segments — content OCR per segment
      3. apply_fm — prefix stripping + section-aware fuzzy matching
      4. rebuild structured data for enchant/reforge sections

    Args:
        save_raw: if True, saves pre-FM text as line['raw_text'] (for test comparison)

    Returns:
        dict with 'sections', 'all_lines', 'tagged_segments'
    """
    # Step 1: segment with header OCR
    tagged = segment_and_tag(img_bgr, header_reader, section_patterns, config)

    # Step 2: content OCR per segment
    result = parser.parse_from_segments(
        tagged, content_reader, enchant_header_reader=enchant_header_reader)

    all_lines = result.get('all_lines', [])
    sections = result.get('sections', {})

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

    return {
        'sections': sections,
        'all_lines': all_lines,
        'tagged_segments': tagged,
    }
