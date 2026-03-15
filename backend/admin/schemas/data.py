from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel


class SummarySchema(BaseModel):
    enchants: int
    effects: int
    enchant_effects: int
    reforge_options: int
    echostone_options: int = 0
    murias_relic_options: int = 0
    listings: int
    game_items: int
    tags: int = 0


# --- Enchants ---

class EnchantOut(BaseModel):
    id: UUID
    slot: int
    name: str
    rank: int
    header_text: str
    effect_count: Optional[int] = 0

    class Config:
        from_attributes = True


class PaginatedEnchantResponse(BaseModel):
    limit: int
    offset: int
    rows: List[EnchantOut]


# --- Effects ---

class EffectOut(BaseModel):
    id: UUID
    name: str
    is_pct: bool

    class Config:
        from_attributes = True


class PaginatedEffectResponse(BaseModel):
    limit: int
    offset: int
    rows: List[EffectOut]


# --- Enchant Effects ---

class EnchantEffectOut(BaseModel):
    id: UUID
    enchant_id: UUID
    effect_id: Optional[UUID] = None
    effect_order: int
    condition_text: Optional[str] = None
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    raw_text: str
    enchant_name: Optional[str] = None
    effect_name: Optional[str] = None

    class Config:
        from_attributes = True


class PaginatedEnchantEffectResponse(BaseModel):
    limit: int
    offset: int
    rows: List[EnchantEffectOut]


# --- Reforge ---

class ReforgeOptionOut(BaseModel):
    id: UUID
    option_name: str

    class Config:
        from_attributes = True


class PaginatedReforgeResponse(BaseModel):
    limit: int
    offset: int
    rows: List[ReforgeOptionOut]


# --- Echostone ---

class EchostoneOptionOut(BaseModel):
    id: UUID
    option_name: str
    type: str
    max_level: Optional[int] = None
    min_level: int = 1

    class Config:
        from_attributes = True


class PaginatedEchostoneResponse(BaseModel):
    limit: int
    offset: int
    rows: List[EchostoneOptionOut]


# --- Murias ---

class MuriasRelicOptionOut(BaseModel):
    id: UUID
    option_name: str
    type: str
    max_level: Optional[int] = None
    min_level: int = 1
    value_per_level: Optional[float] = None
    option_unit: Optional[str] = None

    class Config:
        from_attributes = True


class PaginatedMuriasRelicResponse(BaseModel):
    limit: int
    offset: int
    rows: List[MuriasRelicOptionOut]


# --- Game Items ---

class GameItemOut(BaseModel):
    id: UUID
    name: str
    type: Optional[str] = None
    searchable: bool = False
    tradable: bool = True

    class Config:
        from_attributes = True


class PaginatedGameItemResponse(BaseModel):
    limit: int
    offset: int
    rows: List[GameItemOut]
