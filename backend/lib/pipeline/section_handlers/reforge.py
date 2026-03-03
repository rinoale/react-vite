"""ReforgeHandler: standard OCR, FM cutoff=0, structured rebuild."""

from ._helpers import (
    bt601_preprocessed, ocr_lines, apply_line_fm,
    prepend_header, snapshot_and_strip,
)


class ReforgeHandler:
    """Standard OCR, FM cutoff=0, drop non-prefixed, build_reforge_structured."""

    @bt601_preprocessed
    def process(self, seg, *, font_reader, attach_crops=False, **ctx):
        """Full reforge lifecycle: OCR → FM → filter → structured rebuild."""
        from lib.pipeline.v3 import get_pipeline

        pipeline = get_pipeline()
        parser = pipeline['parser']
        splitter = pipeline['splitter']
        corrector = pipeline['corrector']

        content_bgr = seg['content_crop']
        section = seg['section']
        detect_binary = seg['detect_binary']
        ocr_binary = seg['ocr_binary']

        ocr_results = ocr_lines(parser, splitter, detect_binary, ocr_binary,
                                font_reader, section, content_bgr=content_bgr,
                                attach_crops=attach_crops)

        section_data = parser._parse_reforge_section(ocr_results)
        prepend_header(seg, section, section_data)

        # ── FM phase ──
        lines = section_data.get('lines', [])
        snapshot_and_strip(lines, corrector)

        for line in lines:
            if line.get('is_header'):
                line['fm_applied'] = False
                continue
            apply_line_fm(line, corrector, 'reforge', cutoff=0)

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
