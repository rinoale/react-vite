"""DefaultHandler: standard OCR, FM cutoff=80."""

from ._helpers import (
    bt601_preprocessed, ocr_lines, apply_line_fm,
    prepend_header, snapshot_and_strip,
)


class DefaultHandler:
    """Standard OCR, FM cutoff=80.  Used for item_attrs, item_grade, etc."""

    @bt601_preprocessed
    def process(self, seg, *, font_reader, attach_crops=False, **ctx):
        """Full default lifecycle: OCR → FM → filter."""
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
        prepend_header(seg, section, section_data)

        # ── FM phase ──
        lines = section_data.get('lines', [])
        snapshot_and_strip(lines, corrector)

        for line in lines:
            if line.get('is_header'):
                line['fm_applied'] = False
                continue
            apply_line_fm(line, corrector, section, cutoff=80)

        # Drop non-prefixed content lines if prefix_required
        sec_cfg = parser.sections_config.get(section, {})
        if sec_cfg.get('prefix_required'):
            section_data['lines'] = [
                l for l in lines
                if l.get('is_header') or l.get('_prefix_type') is not None
            ]

        return section_data
