from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.db.models import Request
from app.schemas.search import (
    RecommendContractorsRequest,
    SemanticSearchRequest,
    SemanticSearchResponse,
    SimilarRequestsRequest,
)
from app.services.semantic_search import (
    search_contractors,
    search_products,
    search_similar_requests,
)
from app.services.template_recommender import recommend_template
from app.utils.errors import NotFoundError, ValidationError

router = APIRouter()


@router.post("/search/semantic", response_model=SemanticSearchResponse)
async def semantic_search(body: SemanticSearchRequest, db: AsyncSession = Depends(get_db)):
    products = await search_products(db, body.query, body.top_k)
    contractors = await search_contractors(db, body.query, body.top_k)
    similar = await search_similar_requests(db, body.query, body.top_k)
    template_rec = await recommend_template(db, body.query)

    if body.filters:
        if body.filters.get("company_id"):
            contractors = [c for c in contractors if c["company_id"] == body.filters["company_id"]]
        if body.filters.get("product_id"):
            products = [p for p in products if p["product_id"] == body.filters["product_id"]]

    return SemanticSearchResponse(
        intent=template_rec.get("justification", ""),
        products=products,
        contractors=contractors,
        similar_requests=similar,
        related_services=products[1:] if len(products) > 1 else [],
    )


@router.post("/search/similar-requests")
async def similar_requests(body: SimilarRequestsRequest, db: AsyncSession = Depends(get_db)):
    query = body.query
    if not query and body.request_id:
        request = await db.get(Request, body.request_id)
        if request is None:
            raise NotFoundError("Заявка не найдена")
        query = f"{request.title or ''} {request.description or ''}".strip()
    if not query:
        raise ValidationError("Нужно указать query или request_id")
    return await search_similar_requests(db, query, body.top_k)


@router.post("/search/recommend-contractors")
async def recommend_contractors(body: RecommendContractorsRequest, db: AsyncSession = Depends(get_db)):
    query = body.query or body.product_id or ""
    if not query:
        raise ValidationError("Нужно указать product_id или query")
    return await search_contractors(db, query, body.top_k)
