import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ChatSessionCreate(BaseModel):
    request_id: uuid.UUID | None = None
    title: str | None = None


class ChatSessionCreateOut(BaseModel):
    session_id: uuid.UUID


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    actions: list[dict[str, Any]] | None = None
    created_at: datetime


class ChatSessionOut(BaseModel):
    session_id: uuid.UUID
    request_id: uuid.UUID | None = None
    messages: list[ChatMessageOut] = []


class ChatMessageCreate(BaseModel):
    content: str
    stream: bool = True


class ChatAutofillRequest(BaseModel):
    actions: list[dict[str, Any]] | None = None


class ChatApplyRequest(BaseModel):
    actions: list[dict[str, Any]]


class AppliedField(BaseModel):
    field: str
    old: Any = None
    new: Any = None


class ChatAutofillResponse(BaseModel):
    applied: list[AppliedField]
    request_diff: dict[str, Any] = {}
    tz_diff: dict[str, Any] = {}


class ChatApplyResponse(BaseModel):
    applied: list[AppliedField]
    request_diff: dict[str, Any] = {}
    tz_diff: dict[str, Any] = {}
