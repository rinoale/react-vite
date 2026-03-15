from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class CorrectionOut(BaseModel):
    id: UUID
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
    is_stitched: bool = False
    created_at: datetime
    trained_version: Optional[str] = None

    class Config:
        from_attributes = True
