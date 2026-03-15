"""Data structure examples and shape validation tests.

Concrete examples of the dicts produced at each stage of the V3 pipeline.
These serve as living documentation — any change to pipeline output format
that breaks these tests signals a contract change that must be reflected
in API docs and downstream consumers.

Scenarios are drawn from real pipeline runs (e.g. dropbell enchant
continuation line, Dullahan-corrected header).
"""

from trade.schemas.examine import OcrLineResponse

# ---------------------------------------------------------------------------
# 1. Pipeline enchant effect line — stitched continuation
#    Two visual lines merged into one logical effect by merge_continuations().
#    _is_stitched=True signals the merge for admin review / DB flagging.
# ---------------------------------------------------------------------------
PIPELINE_ENCHANT_EFFECT_STITCHED = {
    'text': '엘리멘탈 웨이브 랭크 1 이상일 때 모든 속성 연금술 대미지 10 증가 (10~15)',
    'raw_text': '실리탈 레웨이드 랭크 1 이상일 때 교유투 속성 연금 스 대미지 10 증가 (10~15)',
    'confidence': 0.306,
    'line_index': 3,
    'section': 'enchant',
    'is_enchant_hdr': False,
    'is_grey': False,
    'ocr_model': 'general',
    'fm_applied': True,
    '_prefix_type': 'bullet',
    '_is_stitched': True,
    'bounds': {'x': 10, 'y': 80, 'width': 200, 'height': 14},
}

# ---------------------------------------------------------------------------
# 2. Pipeline enchant header line — Dullahan-corrected
#    OCR read "[접부] 성단" but Dullahan used effect lines to correct to 성단.
#    is_enchant_hdr=True triggers structured rebuild (build_enchant_structured).
# ---------------------------------------------------------------------------
PIPELINE_ENCHANT_HEADER = {
    'text': '[접미] 성단 (랭크 5)',
    'raw_text': '[접부] 성단 (랭크 5)',
    'confidence': 0.85,
    'line_index': 0,
    'section': 'enchant',
    'is_enchant_hdr': True,
    'enchant_slot': '접미',
    'enchant_name': '성단',
    'enchant_rank': '5',
    'ocr_model': 'enchant_header',
    'fm_applied': True,
}

# ---------------------------------------------------------------------------
# 3. HTTP response line — what the frontend receives via OcrLineResponse.
#    Internal fields (_is_stitched, raw_text, _prefix_type, etc.) are stripped
#    by the Pydantic model; only text, confidence, line_index survive.
# ---------------------------------------------------------------------------
HTTP_RESPONSE_LINE = {
    'text': '엘리멘탈 웨이브 랭크 1 이상일 때 모든 속성 연금술 대미지 10 증가 (10~15)',
    'confidence': 0.306,
    'line_index': 3,
}

# ---------------------------------------------------------------------------
# 4. ocr_results.json entry — persisted per-line data for correction lookups.
#    Built by v3._save_crops_by_section(). Includes raw_text (pre-FM snapshot)
#    and _is_stitched when applicable; does NOT include bounds, _prefix_type,
#    is_enchant_hdr, etc.
# ---------------------------------------------------------------------------
OCR_RESULTS_ENTRY = {
    'section': 'enchant',
    'line_index': 3,
    'text': '엘리멘탈 웨이브 랭크 1 이상일 때 모든 속성 연금술 대미지 10 증가 (10~15)',
    'raw_text': '실리탈 레웨이드 랭크 1 이상일 때 교유투 속성 연금 스 대미지 10 증가 (10~15)',
    'confidence': 0.306,
    'ocr_model': 'general',
    'fm_applied': True,
    '_is_stitched': True,
}

# ---------------------------------------------------------------------------
# 5. ocr_results.json entry — non-stitched (normal) line.
#    _is_stitched key is absent (not False).
# ---------------------------------------------------------------------------
OCR_RESULTS_ENTRY_NORMAL = {
    'section': 'enchant',
    'line_index': 0,
    'text': '[접미] 성단 (랭크 5)',
    'raw_text': '[접부] 성단 (랭크 5)',
    'confidence': 0.85,
    'ocr_model': 'enchant_header',
    'fm_applied': True,
}


# ===== Internal fields that must NOT leak into HTTP responses =====
_INTERNAL_FIELDS = {
    '_is_stitched', '_prefix_type', '_cont_merged', '_merged',
    '_crop', '_has_bullet', '_dullahan_score',
    'raw_text', 'section', 'is_enchant_hdr', 'is_grey',
    'enchant_slot', 'enchant_name', 'enchant_rank',
    'ocr_model', 'fm_applied', 'bounds',
    'is_reforge_sub', 'reforge_name', 'reforge_level', 'reforge_max_level',
}

# Fields accepted by OcrLineResponse
_PUBLIC_FIELDS = {'text', 'line_index'}


# ===================================================================
# Tests
# ===================================================================

class TestHttpResponseSchema:
    """Verify OcrLineResponse strips internal fields."""

    def test_http_response_only_has_public_fields(self):
        """OcrLineResponse accepts only text/confidence/line_index."""
        resp = OcrLineResponse(**PIPELINE_ENCHANT_EFFECT_STITCHED)
        dumped = resp.model_dump()

        assert set(dumped.keys()) == _PUBLIC_FIELDS
        assert dumped['text'] == PIPELINE_ENCHANT_EFFECT_STITCHED['text']
        assert dumped['line_index'] == PIPELINE_ENCHANT_EFFECT_STITCHED['line_index']

    def test_header_line_strips_enchant_fields(self):
        """Enchant header metadata (slot, name, rank) not in HTTP response."""
        resp = OcrLineResponse(**PIPELINE_ENCHANT_HEADER)
        dumped = resp.model_dump()

        assert set(dumped.keys()) == _PUBLIC_FIELDS
        assert 'enchant_slot' not in dumped
        assert 'enchant_name' not in dumped

    def test_no_internal_fields_in_response(self):
        """No known internal field leaks into the serialized response."""
        resp = OcrLineResponse(**PIPELINE_ENCHANT_EFFECT_STITCHED)
        dumped = resp.model_dump()
        leaked = _INTERNAL_FIELDS & set(dumped.keys())
        assert leaked == set(), f"Internal fields leaked: {leaked}"


class TestOcrResultsEntry:
    """Verify ocr_results.json entry structure."""

    def test_stitch_flag_present_when_stitched(self):
        """_is_stitched=True present in stitched entry."""
        assert OCR_RESULTS_ENTRY.get('_is_stitched') is True

    def test_stitch_flag_absent_when_normal(self):
        """_is_stitched key absent (not False) for normal lines."""
        assert '_is_stitched' not in OCR_RESULTS_ENTRY_NORMAL

    def test_ocr_results_required_fields(self):
        """ocr_results.json entries must have these fields."""
        required = {'section', 'line_index', 'text', 'raw_text',
                    'confidence', 'ocr_model', 'fm_applied'}
        assert required <= set(OCR_RESULTS_ENTRY.keys())
        assert required <= set(OCR_RESULTS_ENTRY_NORMAL.keys())

    def test_raw_text_differs_from_text_when_fm_applied(self):
        """When fm_applied=True and FM made changes, raw_text != text."""
        entry = OCR_RESULTS_ENTRY
        assert entry['fm_applied'] is True
        assert entry['raw_text'] != entry['text']


class TestStitchedLineContract:
    """Verify stitched line invariants."""

    def test_stitched_line_has_merged_raw_text(self):
        """A stitched line's raw_text should contain text from both
        the anchor and continuation (longer than a single-line effect)."""
        raw = PIPELINE_ENCHANT_EFFECT_STITCHED['raw_text']
        # Raw text is the concatenation of anchor + continuation OCR output.
        # Must contain content from both sub-lines (space-joined).
        assert ' ' in raw
        # For this specific example, both sub-line fragments are present:
        assert '실리탈' in raw  # from anchor sub-line
        assert '대미지' in raw  # from continuation sub-line

    def test_stitched_line_must_be_effect_not_header(self):
        """Only effect lines can be stitched (headers are never wrapped)."""
        assert PIPELINE_ENCHANT_EFFECT_STITCHED['is_enchant_hdr'] is False
        assert PIPELINE_ENCHANT_EFFECT_STITCHED['_is_stitched'] is True

    def test_stitched_line_has_bullet_prefix(self):
        """The anchor of a stitched line must have been a bullet-prefixed effect."""
        assert PIPELINE_ENCHANT_EFFECT_STITCHED['_prefix_type'] == 'bullet'


class TestPipelineExampleConsistency:
    """Cross-check example dicts are internally consistent."""

    def test_http_response_matches_pipeline_text(self):
        """HTTP response text should match the pipeline line text."""
        assert HTTP_RESPONSE_LINE['text'] == PIPELINE_ENCHANT_EFFECT_STITCHED['text']
        assert HTTP_RESPONSE_LINE['line_index'] == PIPELINE_ENCHANT_EFFECT_STITCHED['line_index']

    def test_ocr_results_matches_pipeline(self):
        """ocr_results.json entry should match pipeline source data."""
        p = PIPELINE_ENCHANT_EFFECT_STITCHED
        o = OCR_RESULTS_ENTRY
        assert o['text'] == p['text']
        assert o['raw_text'] == p['raw_text']
        assert o['section'] == p['section']
        assert o['line_index'] == p['line_index']
        assert o['fm_applied'] == p['fm_applied']
        assert o['_is_stitched'] == p['_is_stitched']

    def test_header_ocr_results_matches_pipeline(self):
        """Header line ocr_results entry should match pipeline source."""
        p = PIPELINE_ENCHANT_HEADER
        o = OCR_RESULTS_ENTRY_NORMAL
        assert o['text'] == p['text']
        assert o['raw_text'] == p['raw_text']
        assert o['section'] == p['section']
