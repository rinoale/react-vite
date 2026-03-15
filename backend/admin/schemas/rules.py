from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class AutoTagRuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    rule_type: str
    enabled: bool = False
    priority: int = 0
    config: dict


class AutoTagRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    rule_type: Optional[str] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None
    config: Optional[dict] = None


class AutoTagRuleOut(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    rule_type: str
    enabled: bool
    priority: int
    config: dict
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
