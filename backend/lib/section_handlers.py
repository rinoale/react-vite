"""Section handlers for V3 OCR pipeline.

Each handler owns a section's full lifecycle via a uniform interface:
  process(seg, pipeline) → section_data dict

The pipeline dict (from init_pipeline()) carries all shared resources:
  parser, corrector, readers, config, etc.

No all_lines flat list. Each section is processed end-to-end by its handler.
"""

import os

import cv2

from lib.line_processing import (
    merge_group_bounds, trim_outlier_tail, promote_grey_by_prefix,
    determine_enchant_slots, merge_continuations, count_effects_per_header,
)
from lib.log import logger
from lib.prefix_detector import detect_prefix_per_color, BULLET_DETECTOR, SUBBULLET_DETECTOR


# ── helpers ──────────────────────────────────────────────────────────────────

def _bt601_binary(content_bgr, threshold=80):
    """BT.601 grayscale + threshold → (detect_binary, ocr_binary)."""
    gray = cv2.cvtColor(content_bgr, cv2.COLOR_BGR2GRAY)
    _, ocr_binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY_INV)
    detect_binary = cv2.bitwise_not(ocr_binary)
    return detect_binary, ocr_binary


def _ocr_lines(parser, detect_binary, ocr_binary, reader, section,
               content_bgr=None, attach_crops=False):
    """Line detect → group → prefix detect → OCR.  Returns list of line dicts."""
    detected = parser.detect_text_lines(detect_binary)
    grouped = parser._group_by_y(detected)

    _save = os.environ.get('SAVE_OCR_CROPS')
    sec_config = parser.sections_config.get(section, {})
    prefix_kw = {}
    if not sec_config.get('skip', False) and content_bgr is not None:
        prefix_kw = {'prefix_bgr': content_bgr,
                     'prefix_configs': [BULLET_DETECTOR, SUBBULLET_DETECTOR]}
    ocr_results = parser._ocr_grouped_lines(
        ocr_binary, grouped, reader,
        save_crops_dir=_save,
        save_label=f'content_{section}',
        attach_crops=attach_crops,
        **prefix_kw)

    for line in ocr_results:
        line['section'] = section
    return ocr_results


def _apply_line_fm(line, corrector, section, cutoff=80):
    """Apply FM to a single non-enchant content line.  Mutates line in place."""
    raw_text = line.get('text', '')
    if not raw_text.strip() or line.get('is_header'):
        line['fm_applied'] = False
        return

    # FM only for bullet-prefixed lines (skip sub-bullets and unprefixed)
    if line.get('_prefix_type') != 'bullet':
        line['fm_applied'] = False
        return

    if section not in corrector._section_norm_cache:
        line['fm_applied'] = False
        return

    fm_text, fm_score, paren_range = corrector.correct_normalized(
        raw_text, section=section, cutoff_score=cutoff)

    if fm_score > 0:
        line['text'] = fm_text
        line['fm_applied'] = True
        if paren_range:
            line['detail_range'] = paren_range
    elif fm_score < 0 and fm_score not in (-2, -3):
        line['fm_applied'] = False
        line['fm_rejected'] = fm_text
        line['fm_rejected_score'] = -fm_score
    else:
        line['fm_applied'] = False


def _prepend_header(seg, section, section_data):
    """Insert the orange header OCR text as line 0 if present."""
    if seg['header_crop'] is not None and seg.get('header_ocr_text'):
        header_line = {
            'text':       seg['header_ocr_text'],
            'confidence': seg['header_ocr_conf'],
            'bounds':     {},
            'section':    section,
            'is_header':  True,
        }
        section_data.setdefault('lines', []).insert(0, header_line)


def _snapshot_and_strip(lines, corrector):
    """Snapshot raw_text and strip structural prefixes on all lines."""
    for line in lines:
        line['raw_text'] = line.get('text', '')
        corrector.strip_text_prefix(line)


# ── PreHeaderHandler ─────────────────────────────────────────────────────────

class PreHeaderHandler:
    """Dual-font preprocessing+OCR, no prefix detection, parse_item_name."""

    def process(self, seg, pipeline, *, crop_session_dir=None):
        """Full pre_header lifecycle: preprocess → OCR → item name parse.

        Returns (section_data, detected_font).
        """
        from lib.v3_pipeline import (
            _preprocess_mabinogi_classic, _preprocess_nanum_gothic,
            _ocr_pre_header_image, _pick_best_per_line,
        )
        parser = pipeline['parser']
        corrector = pipeline['corrector']

        if not seg:
            return {'lines': []}, 'mabinogi_classic'

        content_bgr = seg['content_crop']
        _save = os.environ.get('SAVE_OCR_CROPS')
        attach = crop_session_dir is not None

        mc_detect, mc_ocr = _preprocess_mabinogi_classic(content_bgr)
        ng_detect, ng_ocr = _preprocess_nanum_gothic(content_bgr)

        mc_results = _ocr_pre_header_image(
            mc_detect, mc_ocr, parser, pipeline['preheader_mc_reader'],
            'pre_header_mc', _save, attach)
        ng_results = _ocr_pre_header_image(
            ng_detect, ng_ocr, parser, pipeline['preheader_ng_reader'],
            'pre_header_ng', _save, attach)

        ocr_results = _pick_best_per_line(mc_results, ng_results)
        for line in ocr_results:
            line['section'] = 'pre_header'

        sections = parser._parse_pre_header(ocr_results)
        section_data = sections.get('pre_header', {'lines': []})
        lines = section_data.get('lines', [])

        mc_count = sum(1 for l in ocr_results if l.get('preprocess') == 'mabinogi_classic')
        ng_count = sum(1 for l in ocr_results if l.get('preprocess') == 'nanum_gothic')
        detected_font = 'nanum_gothic' if ng_count > mc_count else 'mabinogi_classic'

        # Snapshot raw text, no FM
        for line in lines:
            line['raw_text'] = line.get('text', '')
            line['fm_applied'] = False

        # Parse item name from first line
        if lines:
            first_text = lines[0].get('text', '')
            if first_text:
                section_data['parsed_item_name'] = corrector.parse_item_name(first_text)

        logger.info("v3 pre_header  %d lines  font=%s", len(lines), detected_font)
        return section_data, detected_font


# ── EnchantHandler ───────────────────────────────────────────────────────────

class EnchantHandler:
    """White-mask bands, line classification, enchant OCR, Dullahan FM."""

    def process(self, seg, pipeline, *, attach_crops=False, parsed_item_name=None):
        """Full enchant lifecycle: image process → OCR → FM → structured rebuild."""
        from lib.mabinogi_tooltip_parser import detect_enchant_slot_headers

        parser = pipeline['parser']
        corrector = pipeline['corrector']
        reader = pipeline['font_reader']

        content_bgr = seg['content_crop']
        section = seg['section']
        detect_binary, ocr_binary = _bt601_binary(content_bgr)

        detected = parser.detect_text_lines(detect_binary)
        grouped = parser._group_by_y(detected)

        slot_bands = detect_enchant_slot_headers(content_bgr)

        if slot_bands:
            section_data = parser._parse_enchant_with_bands(
                content_bgr, ocr_binary, grouped, slot_bands, section, reader,
                enchant_header_reader=pipeline['enchant_header_reader'],
                attach_crops=attach_crops)
        else:
            _save = os.environ.get('SAVE_OCR_CROPS')
            ocr_results = parser._ocr_grouped_lines(
                ocr_binary, grouped, reader,
                save_crops_dir=_save,
                save_label='content_enchant',
                attach_crops=attach_crops,
                prefix_bgr=content_bgr,
                prefix_configs=[BULLET_DETECTOR, SUBBULLET_DETECTOR])
            for line in ocr_results:
                line['section'] = section
            section_data = parser._parse_enchant_section(ocr_results)

        _prepend_header(seg, section, section_data)

        # ── FM phase ──
        lines = section_data.get('lines', [])
        _snapshot_and_strip(lines, corrector)

        if not corrector._enchant_db:
            for line in lines:
                line.setdefault('fm_applied', False)
        else:
            self._apply_enchant_fm(lines, corrector, parsed_item_name)

        # Merge continuations (multi-line effects wrapped across lines)
        merge_continuations(lines)
        section_data['lines'] = [
            l for l in lines
            if not l.get('_merged') and not l.get('_cont_merged')]

        # Rebuild structured data from FM-corrected lines
        enchant_updated = parser.build_enchant_structured(section_data['lines'])
        section_data.update(enchant_updated)

        return section_data

    @staticmethod
    def _apply_enchant_fm(lines, corrector, parsed_item_name):
        """Dullahan on headers, match_enchant_effect on effects."""
        # Build P1 entries from parsed_item_name
        p1_entries = {}
        if parsed_item_name:
            for slot_type, field in [('접두', 'enchant_prefix'), ('접미', 'enchant_suffix')]:
                name = parsed_item_name.get(field)
                if name:
                    p1_entry = corrector.lookup_enchant_by_name(name, slot_type=slot_type)
                    if p1_entry:
                        p1_entries[slot_type] = p1_entry

        enchant_lines = [l for l in lines if not l.get('is_header')]
        has_slot_hdrs = any(l.get('is_enchant_hdr') for l in enchant_lines)

        if has_slot_hdrs:
            slots = []
            current_hdr, current_effects = None, []
            for line in enchant_lines:
                if line.get('is_enchant_hdr'):
                    if current_hdr is not None:
                        slots.append((current_hdr, current_effects))
                    current_hdr = line
                    current_effects = []
                elif current_hdr is not None:
                    current_effects.append(line)
            if current_hdr is not None:
                slots.append((current_hdr, current_effects))

            for hdr_line, effect_lines in slots:
                raw_hdr = hdr_line.get('text', '')
                hdr_line['_raw_enchant_header'] = raw_hdr
                effect_texts = [l.get('text', '') for l in effect_lines
                                if l.get('text', '').strip()
                                and not l.get('is_grey')]
                slot_type = hdr_line.get('enchant_slot', '')

                fm_hdr, fm_score, entry = corrector.do_dullahan(
                    raw_hdr, effect_texts, slot_type=slot_type)

                if fm_score > 0:
                    hdr_line['text'] = fm_hdr
                    hdr_line['fm_applied'] = True
                    hdr_line['_dullahan_score'] = fm_score
                    if entry:
                        hdr_line['enchant_slot'] = entry['slot']
                        hdr_line['enchant_name'] = entry['name']
                        hdr_line['enchant_rank'] = entry['rank']

                effect_entry = p1_entries.get(slot_type, entry)
                if effect_entry:
                    for eff_line in effect_lines:
                        eff_text = eff_line.get('text', '')
                        if not eff_text.strip() or eff_line.get('is_grey'):
                            continue
                        fm_eff, eff_score = corrector.match_enchant_effect(
                            eff_text, effect_entry)
                        if eff_score > 0:
                            eff_line['text'] = fm_eff
                            eff_line['fm_applied'] = True
                        elif eff_score < 0:
                            eff_line['fm_rejected'] = fm_eff
                            eff_line['fm_rejected_score'] = -eff_score
        else:
            current_entry = None
            for line in enchant_lines:
                raw_text = line.get('text', '')
                if not raw_text.strip():
                    continue
                hdr_text, hdr_score, hdr_entry = corrector.match_enchant_header(raw_text)
                if hdr_score > 0:
                    line['text'] = hdr_text
                    line['fm_applied'] = True
                    current_entry = hdr_entry
                else:
                    fm_text, fm_score = corrector.match_enchant_effect(
                        raw_text, current_entry)
                    if fm_score > 0:
                        line['text'] = fm_text
                        line['fm_applied'] = True

        for line in lines:
            line.setdefault('fm_applied', False)


# ── ReforgeHandler ───────────────────────────────────────────────────────────

class ReforgeHandler:
    """Standard OCR, FM cutoff=0, drop non-prefixed, build_reforge_structured."""

    def process(self, seg, pipeline, *, attach_crops=False, **ctx):
        """Full reforge lifecycle: OCR → FM → filter → structured rebuild."""
        parser = pipeline['parser']
        corrector = pipeline['corrector']
        reader = pipeline['font_reader']

        content_bgr = seg['content_crop']
        section = seg['section']
        detect_binary, ocr_binary = _bt601_binary(content_bgr)

        ocr_results = _ocr_lines(parser, detect_binary, ocr_binary, reader,
                                 section, content_bgr=content_bgr,
                                 attach_crops=attach_crops)

        section_data = parser._parse_reforge_section(ocr_results)
        _prepend_header(seg, section, section_data)

        # ── FM phase ──
        lines = section_data.get('lines', [])
        _snapshot_and_strip(lines, corrector)

        for line in lines:
            if line.get('is_header'):
                line['fm_applied'] = False
                continue
            _apply_line_fm(line, corrector, 'reforge', cutoff=0)

        # Drop non-prefixed content lines (prefix_required)
        sec_cfg = parser.sections_config.get('reforge', {})
        if sec_cfg.get('prefix_required'):
            section_data['lines'] = [
                l for l in lines
                if l.get('is_header') or l.get('_prefix_type') is not None
            ]

        # Rebuild structured options from corrected text
        reforge_updated = parser.build_reforge_structured(section_data['lines'])
        section_data.update(reforge_updated)

        return section_data


# ── ColorHandler ─────────────────────────────────────────────────────────────

class ColorHandler:
    """No OCR — regex RGB parse only."""

    def process(self, seg, pipeline, *, attach_crops=False, **ctx):
        """Full color lifecycle: line detect → structural parse."""
        parser = pipeline['parser']
        reader = pipeline['font_reader']

        content_bgr = seg['content_crop']
        section = seg['section']
        detect_binary, ocr_binary = _bt601_binary(content_bgr)

        detected = parser.detect_text_lines(detect_binary)
        grouped = parser._group_by_y(detected)

        _save = os.environ.get('SAVE_OCR_CROPS')
        ocr_results = parser._ocr_grouped_lines(
            ocr_binary, grouped, reader,
            save_crops_dir=_save,
            save_label='content_item_color',
            attach_crops=attach_crops)

        for line in ocr_results:
            line['section'] = section

        section_data = parser._parse_color_section(ocr_results)
        _prepend_header(seg, section, section_data)

        for line in section_data.get('lines', []):
            line['raw_text'] = line.get('text', '')
            line['fm_applied'] = False

        return section_data


# ── DefaultHandler ───────────────────────────────────────────────────────────

class DefaultHandler:
    """Standard OCR, FM cutoff=80.  Used for item_attrs, item_grade, etc."""

    def process(self, seg, pipeline, *, attach_crops=False, **ctx):
        """Full default lifecycle: OCR → FM → filter."""
        parser = pipeline['parser']
        corrector = pipeline['corrector']
        reader = pipeline['font_reader']

        content_bgr = seg['content_crop']
        section = seg['section']

        detect_binary, ocr_binary = _bt601_binary(content_bgr)

        ocr_results = _ocr_lines(parser, detect_binary, ocr_binary, reader,
                                 section, content_bgr=content_bgr,
                                 attach_crops=attach_crops)

        section_data = {
            'lines': [
                {'text': l['text'], 'confidence': l['confidence'],
                 'bounds': l['bounds'], 'section': l.get('section', section),
                 'ocr_model': l.get('ocr_model', ''),
                 '_prefix_type': l.get('_prefix_type'),
                 '_crop': l.get('_crop')}
                for l in ocr_results
            ]
        }
        _prepend_header(seg, section, section_data)

        # ── FM phase ──
        lines = section_data.get('lines', [])
        _snapshot_and_strip(lines, corrector)

        for line in lines:
            if line.get('is_header'):
                line['fm_applied'] = False
                continue
            _apply_line_fm(line, corrector, section, cutoff=80)

        # Drop non-prefixed content lines if prefix_required
        sec_cfg = parser.sections_config.get(section, {})
        if sec_cfg.get('prefix_required'):
            section_data['lines'] = [
                l for l in lines
                if l.get('is_header') or l.get('_prefix_type') is not None
            ]

        return section_data


# ── Dispatch ─────────────────────────────────────────────────────────────────

_HANDLER_MAP = {
    'enchant': EnchantHandler(),
    'reforge': ReforgeHandler(),
    'item_color': ColorHandler(),
}
_DEFAULT_HANDLER = DefaultHandler()


def get_handler(section_key):
    """Get the appropriate handler for a section key."""
    return _HANDLER_MAP.get(section_key, _DEFAULT_HANDLER)
