from typing import List, Optional
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import datetime

class EnchantBase(BaseModel):
    slot: int
    name: str
    rank: int
    header_text: str

class EnchantCreate(EnchantBase):
    pass

class Enchant(EnchantBase):
    id: int
    effect_count: Optional[int] = 0

    class Config:
        from_attributes = True

class EffectBase(BaseModel):
    name: str
    is_pct: bool

class Effect(EffectBase):
    id: int
    
    class Config:
        from_attributes = True

class EnchantEffectBase(BaseModel):
    enchant_id: int
    effect_id: Optional[int] = None
    effect_order: int
    condition_text: Optional[str] = None
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    raw_text: str

class EnchantEffect(EnchantEffectBase):
    id: int
    enchant_name: Optional[str] = None
    effect_name: Optional[str] = None

    class Config:
        from_attributes = True

class ReforgeOptionBase(BaseModel):
    option_name: str

class ReforgeOption(ReforgeOptionBase):
    id: int
    
    class Config:
        from_attributes = True

class SummarySchema(BaseModel):
    enchants: int
    effects: int
    enchant_effects: int
    reforge_options: int

class PaginatedEnchantResponse(BaseModel):
    limit: int
    offset: int
    rows: List[Enchant]

class PaginatedEffectResponse(BaseModel):
    limit: int
    offset: int
    rows: List[Effect]

class PaginatedEnchantEffectResponse(BaseModel):
    limit: int
    offset: int
    rows: List[EnchantEffect]

class PaginatedReforgeResponse(BaseModel):
    limit: int
    offset: int
    rows: List[ReforgeOption]


# --- Item registration + implicit correction capture ---

class RegisterItemLine(BaseModel):
    global_index: int
    text: str

class RegisterItemRequest(BaseModel):
    session_id: Optional[str] = None
    name: str = ''
    price: str = ''
    category: str = 'weapon'
    lines: List[RegisterItemLine] = []

class CorrectionOut(BaseModel):
    id: int
    session_id: str
    line_index: int
    original_text: str
    corrected_text: str
    confidence: Optional[Decimal] = None
    section: Optional[str] = None
    ocr_model: Optional[str] = None
    fm_applied: bool = False
    status: str
    image_filename: str
    created_at: datetime
    trained_version: Optional[str] = None

    class Config:
        from_attributes = True
