"""ReforgeHandler: standard OCR, FM cutoff=0, structured rebuild."""

from lib.pipeline.line_split import merge_continuations

from ._base import BaseHandler
from ._helpers import (
    detect_prefix, skip_ocr_prefix, ocr_lines, apply_line_fm,
    prepend_header, snapshot_and_strip,
)


def _has_any_prefix(grouped_lines):
    """Check if any group has a detected prefix (bullet or subbullet)."""
    for group in grouped_lines:
        if (group[0].get('_prefix_info') or {}).get('type') is not None:
            return True
    return False


class ReforgeHandler(BaseHandler):
    """Standard OCR, FM cutoff=0, continuation merge, build_reforge_structured."""

    @detect_prefix('bullet', 'subbullet')
    @skip_ocr_prefix('subbullet')
    def _process(self, seg, grouped_lines, *, pipeline, font_reader,
                 attach_crops=False, **ctx):
        """Full reforge lifecycle: OCR → merge continuations → FM → structured rebuild."""
        parser = pipeline['parser']
        corrector = pipeline['corrector']
        section = seg['section']

        # Guard: no prefixed lines → all grey descriptions, skip OCR
        if not _has_any_prefix(grouped_lines):
            section_data = {'lines': []}
            prepend_header(seg, section, section_data)
            return section_data

        ocr_results = ocr_lines(seg, grouped_lines, font_reader, section,
                                attach_crops=attach_crops)

        section_data = parser._parse_reforge_section(ocr_results)
        prepend_header(seg, section, section_data)

        # ── Merge continuations ──
        # Stitch non-prefixed lines into preceding bullet line before FM,
        # so FM sees the complete text (same pattern as enchant handler).
        lines = section_data.get('lines', [])
        merge_continuations(lines)

        # ── FM phase ──
        snapshot_and_strip(lines, corrector)

        for line in lines:
            if line.get('is_header'):
                line['fm_applied'] = False
                continue
            apply_line_fm(line, corrector, 'reforge', cutoff=0)

        # Drop merged continuation lines from final output
        section_data['lines'] = [
            l for l in lines if not l.get('_cont_merged')]

        # Rebuild structured options from corrected text
        reforge_updated = parser.build_reforge_structured(section_data['lines'])
        section_data.update(reforge_updated)

        return section_data
