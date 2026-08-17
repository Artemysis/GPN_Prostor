import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class JobOut(BaseModel):
    id: uuid.UUID
    type: str
    status: str
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class JobCreatedOut(BaseModel):
    job_id: uuid.UUID
