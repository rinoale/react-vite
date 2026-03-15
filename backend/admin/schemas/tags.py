from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, field_validator


class TagCreate(BaseModel):
    target_type: str
    target_id: UUID
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
    target_id: UUID


class BulkTagCreate(BaseModel):
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


class TagTargetOut(BaseModel):
    id: UUID
    tag_id: UUID
    target_type: str
    target_id: UUID
    name: str
    weight: int = 0
    target_display_name: Optional[str] = None


class TagDetailTarget(BaseModel):
    id: UUID
    target_type: str
    target_id: UUID
    weight: int = 0
    target_display_name: Optional[str] = None


class TagDetail(BaseModel):
    id: UUID
    name: str
    weight: int = 0
    targets: List[TagDetailTarget] = []


class WeightUpdate(BaseModel):
    weight: int


class BulkWeightUpdate(BaseModel):
    ids: List[UUID]
    weight: int
