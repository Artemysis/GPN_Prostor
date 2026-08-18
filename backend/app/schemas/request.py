import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator


class RequestCreate(BaseModel):
    title: str | None = None
    description: str | None = None
    company_id: str | None = None
    contract_id: str | None = None
    product_id: str | None = None
    cost_total: float | None = None
    date_start: date | None = None
    date_end: date | None = None
    template_id: uuid.UUID | None = None
    chat_session_id: uuid.UUID | None = None


class RequestUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    company_id: str | None = None
    contract_id: str | None = None
    product_id: str | None = None
    cost_total: float | None = None
    currency: str | None = None
    date_start: date | None = None
    date_end: date | None = None
    status: Literal["draft", "submitted"] | None = None


class RequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    number: str | None = None
    status: str
    company_id: str | None = None
    contract_id: str | None = None
    product_id: str | None = None
    title: str | None = None
    description: str | None = None
    cost_total: float | None = None
    currency: str
    date_start: date | None = None
    date_end: date | None = None
    chat_session_id: uuid.UUID | None = None
    request_metadata: dict[str, Any] = {}
    deleted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _apply_deleted_status(self) -> "RequestOut":
        if self.deleted_at is not None:
            self.status = "deleted"
        return self


class TzSummary(BaseModel):
    completeness_pct: int = 0
    risks_count: int = 0


class RequestDetailOut(RequestOut):
    tz_summary: TzSummary = TzSummary()
    documents_count: int = 0


class RequestListOut(BaseModel):
    items: list[RequestOut]
    total: int
