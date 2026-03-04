"""ReforgeHandler: standard OCR, FM cutoff=0, structured rebuild."""

from ._base import BaseHandler
from ._helpers import (
    detect_prefix, filter_prefix, ocr_lines, apply_line_fm,
    prepend_header, snapshot_and_strip,
)


class ReforgeHandler(BaseHandler):
    """Standard OCR, FM cutoff=0, drop non-prefixed, build_reforge_structured."""

    @detect_prefix('bullet', 'subbullet')
    @filter_prefix('bullet')
    def _process(self, seg, grouped_lines, *, pipeline, font_reader,
                 attach_crops=False, **ctx):
        """Full reforge lifecycle: OCR → FM → filter → structured rebuild."""
        parser = pipeline['parser']
        corrector = pipeline['corrector']
        section = seg['section']

        ocr_results = ocr_lines(seg, grouped_lines, font_reader, section,
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

        # Rebuild structured options from corrected text
        reforge_updated = parser.build_reforge_structured(section_data['lines'])
        section_data.update(reforge_updated)

        return section_data
