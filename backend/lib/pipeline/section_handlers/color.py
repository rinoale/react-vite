"""ColorHandler: no OCR — regex RGB parse only."""

import os

from lib.pipeline.line_split import group_by_y
from ._helpers import bt601_preprocessed, prepend_header
from ._ocr import ocr_grouped_lines


class ColorHandler:
    """No OCR — regex RGB parse only."""

    @bt601_preprocessed
    def process(self, seg, *, font_reader, attach_crops=False, **ctx):
        """Full color lifecycle: line detect → structural parse."""
        from lib.pipeline.v3 import get_pipeline

        pipeline = get_pipeline()
        parser = pipeline['parser']
        splitter = pipeline['splitter']

        content_bgr = seg['content_crop']
        section = seg['section']
        detect_binary = seg['detect_binary']
        ocr_binary = seg['ocr_binary']

        detected = splitter.detect_text_lines(detect_binary)
        grouped = group_by_y(detected)

        _save = os.environ.get('SAVE_OCR_CROPS')
        ocr_results = ocr_grouped_lines(
            ocr_binary, grouped, font_reader,
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
