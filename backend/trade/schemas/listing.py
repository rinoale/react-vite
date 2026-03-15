import re
from decimal import Decimal
from datetime import datetime
from typing import Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


_HTML_TAG_RE = re.compile(r'<[^>]*>?')

VALID_OPTION_TYPES = frozenset({
    'enchant_effects', 'reforge_options', 'echostone_options', 'murias_relic_options',
})


# --- Registration request ---

class RegisterEnchantSlot(BaseModel):
    id: UUID
    slot: int  # 0=prefix, 1=suffix
    name: str
    rank: str


class RegisterListingOption(BaseModel):
    option_type: str
    option_name: str
    option_id: UUID
    rolled_value: Optional[Union[int, float]] = None
    max_level: Optional[int] = None

    @field_validator('option_type')
    @classmethod
    def validate_option_type(cls, v):
        if v not in VALID_OPTION_TYPES:
            raise ValueError(f'invalid option_type: {v}')
        return v


class RegisterListingLine(BaseModel):
    section: str
    line_index: int
    text: str


class RegisterListingRequest(BaseModel):
    session_id: Optional[str] = None
    name: str = ''
    description: Optional[str] = Field(None, max_length=50)
    price: str = ''
    category: str = 'weapon'
    game_item_id: Optional[UUID] = None
    item_type: Optional[str] = None
    item_grade: Optional[str] = None
    erg_grade: Optional[str] = None
    erg_level: Optional[int] = None
    special_upgrade_type: Optional[str] = None
    special_upgrade_level: Optional[int] = None
    attrs: Optional[Dict[str, str]] = None
    lines: List[RegisterListingLine] = []
    enchants: List[RegisterEnchantSlot] = []
    listing_options: List[RegisterListingOption] = []
    tags: List[str] = []

    @field_validator('name', 'description', mode='before')
    @classmethod
    def strip_html(cls, v, info):
        if not v:
            return v
        cleaned = _HTML_TAG_RE.sub('', v).strip()
        if not cleaned:
            return '' if info.field_name == 'name' else None
        return cleaned

    @field_validator('tags')
    @classmethod
    def tags_max_length(cls, v):
        for tag in v:
            if len(tag) > 5:
                raise ValueError('each tag must be 5 characters or fewer')
        return v


# --- Response ---

class TagBadge(BaseModel):
    name: str
    weight: int = 0


class ListingOptionOut(BaseModel):
    option_type: str
    option_name: str
    rolled_value: Optional[Decimal] = None
    max_level: Optional[int] = None


class ListingOut(BaseModel):
    id: UUID
    status: int = 0
    name: str
    description: Optional[str] = None
    price: Optional[int] = None
    game_item_id: Optional[UUID] = None
    game_item_name: Optional[str] = None
    prefix_enchant_name: Optional[str] = None
    suffix_enchant_name: Optional[str] = None
    item_type: Optional[str] = None
    item_grade: Optional[str] = None
    erg_grade: Optional[str] = None
    erg_level: Optional[int] = None
    special_upgrade_type: Optional[str] = None
    special_upgrade_level: Optional[int] = None
    damage: Optional[int] = None
    magic_damage: Optional[int] = None
    additional_damage: Optional[int] = None
    balance: Optional[int] = None
    defense: Optional[int] = None
    protection: Optional[int] = None
    magic_defense: Optional[int] = None
    magic_protection: Optional[int] = None
    durability: Optional[int] = None
    piercing_level: Optional[int] = None
    created_at: Optional[datetime] = None
    seller_server: Optional[str] = None
    seller_game_id: Optional[str] = None
    seller_verified: bool = False
    tags: List[TagBadge] = []
    listing_options: List[ListingOptionOut] = []

    class Config:
        from_attributes = True


class PaginatedListingResponse(BaseModel):
    limit: int
    offset: int
    rows: List[ListingOut]


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


class ListingDetailOut(BaseModel):
    id: UUID
    status: int = 0
    name: str
    description: Optional[str] = None
    price: Optional[int] = None
    game_item_id: Optional[UUID] = None
    game_item_name: Optional[str] = None
    item_type: Optional[str] = None
    item_grade: Optional[str] = None
    erg_grade: Optional[str] = None
    erg_level: Optional[int] = None
    special_upgrade_type: Optional[str] = None
    special_upgrade_level: Optional[int] = None
    damage: Optional[int] = None
    magic_damage: Optional[int] = None
    additional_damage: Optional[int] = None
    balance: Optional[int] = None
    defense: Optional[int] = None
    protection: Optional[int] = None
    magic_defense: Optional[int] = None
    magic_protection: Optional[int] = None
    durability: Optional[int] = None
    piercing_level: Optional[int] = None
    prefix_enchant: Optional[ListingEnchantOut] = None
    suffix_enchant: Optional[ListingEnchantOut] = None
    listing_options: List[ListingOptionOut] = []
    tags: List[TagBadge] = []
    seller_server: Optional[str] = None
    seller_game_id: Optional[str] = None
    seller_discord_id: Optional[str] = None
    seller_verified: bool = False
