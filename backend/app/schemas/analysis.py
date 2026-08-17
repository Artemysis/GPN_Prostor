from datetime import datetime

from pydantic import BaseModel


class Risk(BaseModel):
    severity: str
    category: str
    title: str
    description: str
    suggestion: str
    block_code: str


class Recommendation(BaseModel):
    title: str
    description: str
    priority: int
    block_code: str


class AnalysisOut(BaseModel):
    completeness_pct: int
    risks: list[Risk] = []
    recommendations: list[Recommendation] = []
    block_completeness: dict[str, int] = {}
    analyzed_at: datetime | None = None


class CompletenessOut(BaseModel):
    completeness_pct: int
    block_completeness: dict[str, int] = {}
