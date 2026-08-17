import uuid
from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict


class TzBlockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    block_code: str
    block_name: str
    content: dict[str, Any]
    filled_by: str
    is_complete: bool
    completeness_pct: int


class TzStageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    stage_order: int
    stage_name: str
    requirements: str | None = None
    expected_results: str | None = None
    description: str | None = None
    stage_start_date: date | None = None
    stage_end_date: date | None = None
    filled_by: str


class TzStageCreate(BaseModel):
    stage_order: int
    stage_name: str
    requirements: str | None = None
    expected_results: str | None = None
    description: str | None = None
    stage_start_date: date | None = None
    stage_end_date: date | None = None


class TzStageUpdate(BaseModel):
    stage_order: int | None = None
    stage_name: str | None = None
    requirements: str | None = None
    expected_results: str | None = None
    description: str | None = None
    stage_start_date: date | None = None
    stage_end_date: date | None = None


class TzCreate(BaseModel):
    template_id: uuid.UUID
    prefill_from_chat: bool = False


class TzOut(BaseModel):
    tz_id: uuid.UUID
    template_id: uuid.UUID
    version: int = 1
    completeness_pct: int = 0
    payload: dict[str, Any] = {}
    blocks: list[TzBlockOut] = []
    stages: list[TzStageOut] = []


class TzPayloadUpdate(BaseModel):
    payload: dict[str, Any]


class TzBlockUpdate(BaseModel):
    content: dict[str, Any]
    filled_by: str = "manual"


class TzFillAiRequest(BaseModel):
    hint: str | None = None


class TzFillAllRequest(BaseModel):
    blocks: list[str] | None = None
