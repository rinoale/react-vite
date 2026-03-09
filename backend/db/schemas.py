import re
from typing import Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator
from decimal import Decimal
from datetime import datetime

_HTML_TAG_RE = re.compile(r'<[^>]*>?')


# --- Auth ---

class UserUpdate(BaseModel):
    server: Optional[str] = None
    game_id: Optional[str] = None

class UserOut(BaseModel):
    id: int
    email: str
    discord_username: Optional[str] = None
    server: Optional[str] = None
    game_id: Optional[str] = None
    status: int = 0
    verified: bool = False
    roles: List[str] = []
    features: List[str] = []

    class Config:
        from_attributes = True

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

class EchostoneOptionOut(BaseModel):
    id: int
    option_name: str
    type: str
    max_level: Optional[int] = None
    min_level: int = 1

    class Config:
        from_attributes = True

class MuriasRelicOptionOut(BaseModel):
    id: int
    option_name: str
    type: str
    max_level: Optional[int] = None
    min_level: int = 1
    value_per_level: Optional[float] = None
    option_unit: str = ''

    class Config:
        from_attributes = True

class PaginatedEchostoneResponse(BaseModel):
    limit: int
    offset: int
    rows: List[EchostoneOptionOut]

class PaginatedMuriasRelicResponse(BaseModel):
    limit: int
    offset: int
    rows: List[MuriasRelicOptionOut]

class TagCreate(BaseModel):
    """Create a tag and attach to a single target."""
    target_type: str
    target_id: int
    name: str
    weight: int = 0

    @field_validator('name')
    @classmethod
    def name_max_length(cls, v):
        if len(v) > 5:
            raise ValueError('tag name must be 5 characters or fewer')
        return v


class TagTarget(BaseModel):
    target_type: str
    target_id: int


class BulkTagCreate(BaseModel):
    """Create tags and attach to multiple targets. Weights are positional unless explicit weight given."""
    targets: List[TagTarget] = []
    names: List[str]
    weight: Optional[int] = None

    @field_validator('names')
    @classmethod
    def validate_names(cls, v):
        if len(v) < 1 or len(v) > 3:
            raise ValueError('must provide 1 to 3 tag names')
        for name in v:
            if len(name) > 5:
                raise ValueError('each tag name must be 5 characters or fewer')
        return v

class TagBadge(BaseModel):
    name: str
    weight: int = 0

class TagTargetOut(BaseModel):
    """A single tag-target association row for admin display."""
    id: int  # tag_targets.id
    tag_id: int
    target_type: str
    target_id: int
    name: str
    weight: int = 0
    target_display_name: Optional[str] = None


class TagDetailTarget(BaseModel):
    id: int
    target_type: str
    target_id: int
    weight: int = 0
    target_display_name: Optional[str] = None


class TagDetail(BaseModel):
    id: int
    name: str
    weight: int = 0
    targets: List[TagDetailTarget] = []


class WeightUpdate(BaseModel):
    weight: int

class BulkWeightUpdate(BaseModel):
    ids: List[int]
    weight: int

# --- Jobs ---

class JobOut(BaseModel):
    name: str
    description: str
    schedule_seconds: Optional[int] = None
    last_run: Optional['JobRunOut'] = None

class JobRunOut(BaseModel):
    id: int
    job_name: str
    status: str
    result_summary: Optional[str] = None
    error: Optional[str] = None
    worker_id: Optional[str] = None
    started_at: datetime
    finished_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class PaginatedJobRunResponse(BaseModel):
    limit: int
    offset: int
    rows: List[JobRunOut]


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

class ListingOptionOut(BaseModel):
    option_type: str
    option_name: str
    rolled_value: Optional[Decimal] = None
    max_level: Optional[int] = None

class ListingOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price: Optional[int] = None
    game_item_id: Optional[int] = None
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
    tags: List[TagBadge] = []
    listing_options: List[ListingOptionOut] = []

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

class RegisterEnchantSlot(BaseModel):
    slot: int  # 0=prefix, 1=suffix
    name: str
    rank: str

class RegisterListingOption(BaseModel):
    option_type: str  # enchant_effects, reforge_options, echostone_options, murias_relic_options
    option_name: str
    option_id: Optional[int] = None
    rolled_value: Optional[Union[int, float]] = None
    max_level: Optional[int] = None

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
    game_item_id: Optional[int] = None
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
    is_stitched: bool = False  # continuation stitch: crop is merged from multiple lines
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

class ListingDetailOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price: Optional[int] = None
    game_item_id: Optional[int] = None
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
