"""ColorHandler: no OCR — regex RGB parse only."""

import os

from ._base import BaseHandler
from ._helpers import prepend_header
from ._ocr import ocr_grouped_lines


class ColorHandler(BaseHandler):
    """No OCR — regex RGB parse only."""

    def _process(self, seg, grouped_lines, *, pipeline, font_reader,
                 attach_crops=False, **ctx):
        """Full color lifecycle: line detect → structural parse."""
        parser = pipeline['parser']

        section = seg['section']
        ocr_binary = seg['ocr_binary']

        _save = os.environ.get('SAVE_OCR_CROPS')
        ocr_results = ocr_grouped_lines(
            ocr_binary, grouped_lines, font_reader,
            save_crops_dir=_save,
            save_label='content_item_color',
            attach_crops=attach_crops)

        for line in ocr_results:
            line['section'] = section

        section_data = parser._parse_color_section(ocr_results)
        prepend_header(seg, section, section_data)

        for line in section_data.get('lines', []):
            line['raw_text'] = line.get('text', '')
            line['fm_applied'] = False

        return section_data
