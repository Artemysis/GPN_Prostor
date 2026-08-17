import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict


class TzTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    description: str | None = None


class TzTemplateBlockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    block_code: str
    block_name: str
    block_order: int
    json_schema: dict[str, Any]


class TzTemplateStageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stage_order: int
    stage_name: str
    default_requirements: str | None = None
    default_results: str | None = None


class TzTemplateDetailOut(TzTemplateOut):
    blocks_schema: dict[str, Any]
    blocks: list[TzTemplateBlockOut] = []
    stages: list[TzTemplateStageOut] = []


class TzTemplateCreateResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str


class TzTemplateRecommendRequest(BaseModel):
    prompt: str
    request_context: dict[str, Any] | None = None


class TzTemplateRecommendResponse(BaseModel):
    template_id: uuid.UUID | None = None
    code: str | None = None
    name: str | None = None
    confidence: float = 0.0
    justification: str = ""
    suggested_fields: dict[str, Any] = {}
