from typing import Any

from pydantic import BaseModel


class SemanticSearchRequest(BaseModel):
    query: str
    top_k: int = 10
    filters: dict[str, Any] | None = None


class ProductMatch(BaseModel):
    product_id: str
    product_name: str
    score: float
    justification: str = ""


class ContractorMatch(BaseModel):
    company_id: str
    name: str
    rating: int | None = None
    score: float
    justification: str = ""
    done_similar_count: int = 0


class SimilarRequestMatch(BaseModel):
    request_id: str
    title: str | None = None
    similarity: float
    status: str | None = None


class SemanticSearchResponse(BaseModel):
    intent: str = ""
    products: list[ProductMatch] = []
    contractors: list[ContractorMatch] = []
    similar_requests: list[SimilarRequestMatch] = []
    related_services: list[ProductMatch] = []


class SimilarRequestsRequest(BaseModel):
    query: str | None = None
    request_id: str | None = None
    top_k: int = 10


class RecommendContractorsRequest(BaseModel):
    product_id: str | None = None
    query: str | None = None
    top_k: int = 10
