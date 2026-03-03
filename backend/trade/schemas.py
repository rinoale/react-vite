from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, field_validator


class OcrLineResponse(BaseModel):
    text: str = ''
    confidence: float = 0.0
    line_index: int

    @field_validator('confidence', mode='before')
    @classmethod
    def round_confidence(cls, v):
        return round(v, 4) if v is not None else 0.0


# --- Typed sub-models for structured section data ---

class EnchantEffectResponse(BaseModel):
    text: str
    option_name: Optional[str] = None
    option_level: Optional[Union[int, float]] = None
    db_effect: Optional[str] = None
    rolled_value: Optional[Union[int, float]] = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    line_index: Optional[int] = None


class EnchantSlotResponse(BaseModel):
    text: str
    name: str
    rank: str
    effects: List[EnchantEffectResponse]
    source: Optional[str] = None


class EnchantResolutionCandidateResponse(BaseModel):
    name: Optional[str] = None
    score: Optional[Union[int, float]] = None
    raw_text: Optional[str] = None


class EnchantResolutionSlotResponse(BaseModel):
    winner: Optional[str] = None
    p1: Optional[EnchantResolutionCandidateResponse] = None
    p2: Optional[EnchantResolutionCandidateResponse] = None
    p3: Optional[EnchantResolutionCandidateResponse] = None


class EnchantResolutionResponse(BaseModel):
    prefix: Optional[EnchantResolutionSlotResponse] = None
    suffix: Optional[EnchantResolutionSlotResponse] = None


class ReforgeOptionResponse(BaseModel):
    name: str
    level: Optional[int] = None
    max_level: Optional[int] = None
    effect: Optional[str] = None
    text: Optional[str] = None
    line_index: Optional[int] = None


class ColorPartResponse(BaseModel):
    part: str
    r: Optional[int] = None
    g: Optional[int] = None
    b: Optional[int] = None


class OcrSectionResponse(BaseModel):
    header_text: Optional[str] = None
    header_confidence: Optional[float] = None
    header_index: Optional[int] = None
    lines: Optional[List[OcrLineResponse]] = None
    text: Optional[str] = None
    skipped: Optional[bool] = None
    # enchant
    prefix: Optional[EnchantSlotResponse] = None
    suffix: Optional[EnchantSlotResponse] = None
    resolution: Optional[EnchantResolutionResponse] = None
    # reforge
    options: Optional[List[ReforgeOptionResponse]] = None
    # item_color
    parts: Optional[List[ColorPartResponse]] = None
    # pre_header
    item_name: Optional[str] = None
    enchant_prefix: Optional[str] = None
    enchant_suffix: Optional[str] = None


class ExamineItemResponse(BaseModel):
    filename: str
    session_id: Optional[str] = None
    sections: Dict[str, OcrSectionResponse]
    abbreviated: bool = True
