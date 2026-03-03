"""EnchantHandler: white-mask bands, line classification, enchant OCR, Dullahan FM."""

import os

from lib.pipeline.line_split import (
    group_by_y, merge_group_bounds, merge_continuations, trim_outlier_tail,
    promote_grey_by_prefix, determine_enchant_slots, count_effects_per_header,
)
from lib.image_processors.prefix_detector import BULLET_DETECTOR, SUBBULLET_DETECTOR
from lib.image_processors.mabinogi_processor import (
    classify_enchant_line, detect_enchant_slot_headers,
)

from ._helpers import bt601_binary, prepend_header, snapshot_and_strip
from ._ocr import ocr_grouped_lines, ocr_enchant_headers


class EnchantHandler:
    """White-mask bands, line classification, enchant OCR, Dullahan FM."""

    def process(self, seg, *, font_reader, attach_crops=False, parsed_item_name=None, **ctx):
        """Full enchant lifecycle: image process → OCR → FM → structured rebuild."""
        from lib.pipeline.v3 import get_pipeline

        pipeline = get_pipeline()
        parser = pipeline['parser']
        splitter = pipeline['splitter']
        corrector = pipeline['corrector']

        content_bgr = seg['content_crop']
        section = seg['section']
        detect_binary, ocr_binary = bt601_binary(content_bgr)

        detected = splitter.detect_text_lines(detect_binary)
        grouped = group_by_y(detected)

        slot_bands = detect_enchant_slot_headers(content_bgr)

        if slot_bands:
            section_data = _parse_enchant_with_bands(
                parser, content_bgr, ocr_binary, grouped, slot_bands,
                section, font_reader,
                enchant_header_reader=pipeline['enchant_header_reader'],
                attach_crops=attach_crops)
        else:
            _save = os.environ.get('SAVE_OCR_CROPS')
            ocr_results = ocr_grouped_lines(
                ocr_binary, grouped, font_reader,
                save_crops_dir=_save,
                save_label='content_enchant',
                attach_crops=attach_crops,
                prefix_bgr=content_bgr,
                prefix_configs=[BULLET_DETECTOR, SUBBULLET_DETECTOR])
            for line in ocr_results:
                line['section'] = section
            section_data = parser._parse_enchant_section(ocr_results)

        prepend_header(seg, section, section_data)

        # ── FM phase ──
        lines = section_data.get('lines', [])
        snapshot_and_strip(lines, corrector)

        # Merge continuations BEFORE FM so FM sees the complete line
        # and extracts rolled numbers correctly.
        merge_continuations(lines)

        if not corrector._enchant_db:
            for line in lines:
                line.setdefault('fm_applied', False)
        else:
            _apply_enchant_fm(lines, corrector, parsed_item_name)

        section_data['lines'] = [
            l for l in lines
            if not l.get('_merged') and not l.get('_cont_merged')]

        # Rebuild structured data from FM-corrected lines
        enchant_updated = parser.build_enchant_structured(section_data['lines'])
        section_data.update(enchant_updated)

        return section_data


def _parse_enchant_with_bands(parser, content_bgr, binary, grouped,
                              bands, section, reader,
                              enchant_header_reader=None,
                              attach_crops=False):
    """Parse enchant section with white-mask bands.

    Classifies each line group as header/effect/grey BEFORE OCR.
    Grey lines are skipped entirely. Headers and effects are OCR'd.
    """
    # 1. Classify each group
    classifications = []
    for group in grouped:
        bounds = merge_group_bounds(group)
        line_type = classify_enchant_line(content_bgr, bounds, bands)
        classifications.append((group, bounds, line_type))

    # 2. Trim leaked non-enchant lines at segment bottom
    classifications = trim_outlier_tail(
        classifications, header_test=lambda lt: lt == 'header')

    # 3. Promote grey lines with bullet prefix to effect
    promote_grey_by_prefix(classifications, content_bgr)

    # 4. Batch OCR: headers and effects separately
    header_classifications = [(g, b, lt) for g, b, lt in classifications if lt == 'header']
    effect_groups = [g for g, _, lt in classifications if lt == 'effect']

    hdr_reader = enchant_header_reader if enchant_header_reader is not None else reader
    _save = os.environ.get('SAVE_OCR_CROPS')
    header_batch = (ocr_enchant_headers(
                        content_bgr, binary, header_classifications, bands,
                        hdr_reader, save_crops_dir=_save,
                        attach_crops=attach_crops)
                    if header_classifications else [])
    effect_batch = (ocr_grouped_lines(binary, effect_groups, reader,
                                      save_crops_dir=_save,
                                      save_label='content_enchant',
                                      attach_crops=attach_crops,
                                      prefix_bgr=content_bgr,
                                      prefix_config=BULLET_DETECTOR)
                    if effect_groups else [])

    header_iter = iter(header_batch)
    effect_iter = iter(effect_batch)

    # 5. Assemble results
    hdr_model_name = ('enchant_header' if enchant_header_reader is not None
                      else 'general')
    slot_queue = determine_enchant_slots(classifications)
    slot_iter = iter(slot_queue)
    ocr_results = []
    for group, bounds, line_type in classifications:
        if line_type == 'grey':
            ocr_results.append({
                'text': '',
                'confidence': 0.0,
                'sub_count': len(group),
                'bounds': bounds,
                'sub_lines': [],
                'section': section,
                'is_enchant_hdr': False,
                'is_grey': True,
                'ocr_model': '',
            })
        elif line_type == 'header':
            line = next(header_iter)
            line['section'] = section
            line['is_enchant_hdr'] = True
            line['ocr_model'] = hdr_model_name
            line['enchant_slot'] = next(slot_iter, '')
            line['enchant_name'] = ''
            line['enchant_rank'] = ''
            ocr_results.append(line)
        else:  # effect
            line = next(effect_iter)
            line['section'] = section
            line['is_enchant_hdr'] = False
            line.setdefault('ocr_model', 'general')
            ocr_results.append(line)

    effect_counts = count_effects_per_header(ocr_results)

    return {'lines': ocr_results, 'effect_counts': effect_counts}


def _assign_effects_batch(effect_lines, entry, corrector):
    """Greedy 1:1 assignment of OCR effect lines to DB effects.

    When the enchant header is known, we know exactly which effects should
    appear. Uses find_best_pairs for 1:1 assignment, then match_enchant_effect
    with force_idx to generate corrected text.
    """
    from lib.text_processors.common import find_best_pairs

    valid = [(i, line) for i, line in enumerate(effect_lines)
             if line.get('text', '').strip() and not line.get('is_grey')]
    if not valid:
        return

    effects_norm = entry.get('effects_norm', [])
    if not effects_norm:
        return

    # Pre-compute score matrix (N texts × M effects)
    score_rows = [corrector.score_enchant_effects(line['text'], entry)
                  for _, line in valid]

    def scorer(qi, ci):
        return score_rows[qi][ci]

    pairs = find_best_pairs(
        list(range(len(valid))), list(range(len(effects_norm))),
        scorer=scorer)

    for li, (ei, _score) in enumerate(pairs):
        if ei < 0:
            continue
        line = valid[li][1]
        fm_eff, eff_score = corrector.match_enchant_effect(
            line['text'], entry, force_idx=ei)
        if eff_score > 0:
            line['text'] = fm_eff
            line['fm_applied'] = True


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
                _assign_effects_batch(effect_lines, effect_entry, corrector)
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
