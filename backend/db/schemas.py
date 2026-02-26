from typing import List, Optional, Union
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
    listings: int
    game_items: int

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

class ListingOut(BaseModel):
    id: int
    name: str
    price: Optional[int] = None
    game_item_id: Optional[int] = None
    game_item_name: Optional[str] = None
    prefix_enchant_name: Optional[str] = None
    suffix_enchant_name: Optional[str] = None
    item_type: Optional[str] = None
    item_grade: Optional[str] = None
    erg_grade: Optional[str] = None
    erg_level: Optional[int] = None
    created_at: Optional[datetime] = None
    reforge_count: int = 0

    class Config:
        from_attributes = True

class PaginatedListingResponse(BaseModel):
    limit: int
    offset: int
    rows: List[ListingOut]


# --- Game item catalog ---

class GameItemOut(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

class PaginatedGameItemResponse(BaseModel):
    limit: int
    offset: int
    rows: List[GameItemOut]


# --- Listing registration + implicit correction capture ---

class RegisterEnchantEffect(BaseModel):
    text: str
    option_name: Optional[str] = None
    option_level: Optional[Union[int, float]] = None
    enchant_effect_id: Optional[int] = None

class RegisterEnchantSlot(BaseModel):
    slot: int  # 0=prefix, 1=suffix
    name: str
    rank: str
    effects: List[RegisterEnchantEffect] = []

class RegisterReforgeOption(BaseModel):
    name: str
    reforge_option_id: Optional[int] = None
    level: Optional[int] = None
    max_level: Optional[int] = None

class RegisterListingLine(BaseModel):
    global_index: int
    text: str

class RegisterListingRequest(BaseModel):
    session_id: Optional[str] = None
    name: str = ''
    price: str = ''
    category: str = 'weapon'
    game_item_id: Optional[int] = None
    item_type: Optional[str] = None
    item_grade: Optional[str] = None
    erg_grade: Optional[str] = None
    erg_level: Optional[int] = None
    lines: List[RegisterListingLine] = []
    enchants: List[RegisterEnchantSlot] = []
    reforge_options: List[RegisterReforgeOption] = []

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
    charset_mismatch: Optional[str] = None
    image_filename: str
    created_at: datetime
    trained_version: Optional[str] = None

    class Config:
        from_attributes = True


# --- Listing detail response ---

class ListingEnchantEffectOut(BaseModel):
    raw_text: str
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    value: Optional[Decimal] = None

class ListingEnchantOut(BaseModel):
    slot: int
    enchant_name: str
    rank: int
    effects: List[ListingEnchantEffectOut] = []

class ListingReforgeOptionOut(BaseModel):
    option_name: str
    level: Optional[int] = None
    max_level: Optional[int] = None

class ListingDetailOut(BaseModel):
    id: int
    name: str
    price: Optional[int] = None
    game_item_id: Optional[int] = None
    game_item_name: Optional[str] = None
    item_type: Optional[str] = None
    item_grade: Optional[str] = None
    erg_grade: Optional[str] = None
    erg_level: Optional[int] = None
    prefix_enchant: Optional[ListingEnchantOut] = None
    suffix_enchant: Optional[ListingEnchantOut] = None
    reforge_options: List[ListingReforgeOptionOut] = []
