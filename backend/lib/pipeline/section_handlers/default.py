"""DefaultHandler: standard OCR, FM cutoff=80."""

from ._base import BaseHandler
from ._helpers import (
    detect_prefix, ocr_lines, apply_line_fm,
    prepend_header, snapshot_and_strip,
)


class DefaultHandler(BaseHandler):
    """Standard OCR, FM cutoff=80.  Used for item_attrs, item_grade, etc."""

    @detect_prefix('bullet', 'subbullet')
    def _process(self, seg, grouped_lines, *, pipeline, font_reader,
                 attach_crops=False, **ctx):
        """Full default lifecycle: OCR → FM → filter."""
        parser = pipeline['parser']
        corrector = pipeline['corrector']
        section = seg['section']

        ocr_results = ocr_lines(seg, grouped_lines, font_reader, section,
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

        return section_data
