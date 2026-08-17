from typing import Any

from pydantic import BaseModel


class TzAnalyticsOut(BaseModel):
    total_tz: int
    by_type: list[dict[str, Any]] = []
    by_stage_popularity: list[dict[str, Any]] = []
    typical_errors: list[dict[str, Any]] = []
    product_candidates: list[dict[str, Any]] = []


class SearchAnalyticsOut(BaseModel):
    top_services: list[dict[str, Any]] = []
    service_combinations: list[dict[str, Any]] = []
    top_contractors: list[dict[str, Any]] = []
    unfilled_fields: list[dict[str, Any]] = []
    unrecognized_queries: list[dict[str, Any]] = []


class IngestResult(BaseModel):
    inserted: int = 0
    updated: int = 0
    errors: list[str] = []


class EmbeddingsRebuildRequest(BaseModel):
    entity_types: list[str] | None = None


class AuthLoginRequest(BaseModel):
    username: str


class UserOut(BaseModel):
    id: str
    username: str
    role: str


class AuthLoginResponse(BaseModel):
    access_token: str
    user: UserOut


class MeResponse(BaseModel):
    user: UserOut
