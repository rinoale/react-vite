from typing import Dict, List, Optional, Union
from pydantic import BaseModel, field_validator


class OcrLineResponse(BaseModel):
    text: str = ''
    confidence: float = 0.0
    global_index: int

    @field_validator('confidence', mode='before')
    @classmethod
    def round_confidence(cls, v):
        return round(v, 4) if v is not None else 0.0


# --- Typed sub-models for structured section data ---

class EnchantEffectResponse(BaseModel):
    text: str
    option_name: Optional[str] = None
    option_level: Optional[Union[int, float]] = None


class EnchantSlotResponse(BaseModel):
    text: str
    name: str
    rank: str
    effects: List[EnchantEffectResponse]


class ReforgeOptionResponse(BaseModel):
    name: str
    level: Optional[int] = None
    max_level: Optional[int] = None
    effect: Optional[str] = None


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
    # reforge
    options: Optional[List[ReforgeOptionResponse]] = None
    # item_color
    parts: Optional[List[ColorPartResponse]] = None


class ExamineItemResponse(BaseModel):
    filename: str
    session_id: Optional[str] = None
    sections: Dict[str, OcrSectionResponse]
    all_lines: List[OcrLineResponse]
