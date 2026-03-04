"""Section handlers for V3 OCR pipeline.

Each handler owns a section's full lifecycle via a uniform interface:
  handler.process(seg, *, font_reader, ...) → section_data dict

Handlers access the pipeline singleton (parser, corrector, etc.)
internally via get_pipeline(). Only per-request state (font_reader)
is passed as an argument.
"""

from .pre_header import PreHeaderHandler
from .enchant import EnchantHandler
from .reforge import ReforgeHandler
from .color import ColorHandler
from .item_attrs import ItemAttrsHandler
from .default import DefaultHandler

_HANDLER_MAP = {
    'enchant': EnchantHandler(),
    'reforge': ReforgeHandler(),
    'item_color': ColorHandler(),
    'item_attrs': ItemAttrsHandler(),
}
_DEFAULT_HANDLER = DefaultHandler()


def get_handler(section_key):
    """Get the appropriate handler for a section key."""
    return _HANDLER_MAP.get(section_key, _DEFAULT_HANDLER)
