import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RequestDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    filename: str
    mime_type: str | None = None
    size_bytes: int | None = None
    generated_by_ai: bool
    created_at: datetime


class RequestDocumentDetailOut(RequestDocumentOut):
    presigned_url: str
    expires_in: int


class ExportRequest(BaseModel):
    formats: list[str] = ["docx"]
    include_analytical_report: bool = True


class AnalyticalReportRequest(BaseModel):
    format: str = "docx"
