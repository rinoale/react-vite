from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel


class JobRunOut(BaseModel):
    id: UUID
    job_name: str
    status: str
    payload: Optional[str] = None
    result_summary: Optional[str] = None
    error: Optional[str] = None
    worker_id: Optional[str] = None
    started_at: datetime
    finished_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class JobOut(BaseModel):
    name: str
    description: str
    schedule_seconds: Optional[int] = None
    queue: str = "default"
    workers: int = 0
    last_run: Optional[JobRunOut] = None


class PaginatedJobRunResponse(BaseModel):
    limit: int
    offset: int
    rows: List[JobRunOut]
