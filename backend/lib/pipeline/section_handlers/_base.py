"""Base class for content section handlers."""

from ._helpers import bt601_binary
from lib.pipeline.line_split import group_by_y


class BaseHandler:
    """Common pipeline: bt601 → detect_text_lines → group_by_y → _process()."""

    def process(self, seg, *, font_reader, attach_crops=False, **ctx):
        from lib.pipeline.v3 import get_pipeline
        pipeline = get_pipeline()

        seg['ocr_binary'] = bt601_binary(seg['content_crop'])

        splitter = pipeline['splitter']
        detected = splitter.detect_text_lines(seg['ocr_binary'])
        grouped_lines = group_by_y(detected)

        return self._process(seg, grouped_lines, pipeline=pipeline,
                             font_reader=font_reader, attach_crops=attach_crops, **ctx)

    def _process(self, seg, grouped_lines, *, pipeline, font_reader,
                 attach_crops=False, **ctx):
        raise NotImplementedError
