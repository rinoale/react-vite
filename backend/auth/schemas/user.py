import re
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, field_validator


class UserUpdate(BaseModel):
    server: Optional[str] = None
    game_id: Optional[str] = None


class UserOut(BaseModel):
    id: UUID
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


_FEATURE_FLAG_NAME_RE = re.compile(r'^(read|manage)_[a-z][a-z0-9_]*$')


class FeatureFlagCreate(BaseModel):
    name: str

    @field_validator('name')
    @classmethod
    def validate_flag_name(cls, v: str) -> str:
        if not _FEATURE_FLAG_NAME_RE.match(v):
            raise ValueError('Flag name must match (read|manage)_<resource> pattern')
        return v
