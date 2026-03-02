"""V3 OCR pipeline: segment → split lines → handle sections.

Public API re-exported here for convenient imports.
"""

from .v3 import init_pipeline, get_pipeline, run_v3_pipeline, prepare_sections_for_response
