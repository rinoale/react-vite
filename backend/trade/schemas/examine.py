from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, field_validator


class OcrLineResponse(BaseModel):
    text: str = ''
    line_index: int


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
    lines: Optional[List[OcrLineResponse]] = None
    text: Optional[str] = None
    skipped: Optional[bool] = None
    # enchant
    prefix: Optional[EnchantSlotResponse] = None
    suffix: Optional[EnchantSlotResponse] = None
    # reforge
    options: Optional[List[ReforgeOptionResponse]] = None
    # item_attrs
    attrs: Optional[Dict[str, str]] = None

    @field_validator('attrs', mode='before')
    @classmethod
    def _strip_hidden_attrs(cls, v):
        hidden = {'additional_piercing'}
        if isinstance(v, dict):
            return {k: val for k, val in v.items() if k not in hidden}
        return v
    # set_item
    set_effects: Optional[List[Dict[str, Any]]] = None
    # erg
    erg_grade: Optional[str] = None
    erg_level: Optional[int] = None
    erg_max_level: Optional[int] = None
    # item_mod
    has_special_upgrade: Optional[bool] = None
    special_upgrade_type: Optional[str] = None
    special_upgrade_level: Optional[int] = None
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
