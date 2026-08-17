from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Company, Product, Request
from app.services.embeddings import search_embeddings


async def search_products(db: AsyncSession, query: str, top_k: int = 10) -> list[dict]:
    hits = await search_embeddings(db, "product", query, top_k)
    results = []
    for emb, score in hits:
        product = await db.get(Product, emb.entity_id)
        if product is None:
            continue
        results.append(
            {
                "product_id": product.product_id,
                "product_name": product.product_name,
                "score": round(score, 4),
                "justification": f"Семантическое совпадение с запросом «{query}»",
            }
        )
    return results


async def search_contractors(db: AsyncSession, query: str, top_k: int = 10) -> list[dict]:
    hits = await search_embeddings(db, "company_services", query, top_k)
    results = []
    for emb, score in hits:
        company = await db.get(Company, emb.entity_id)
        if company is None:
            continue
        results.append(
            {
                "company_id": company.company_id,
                "name": company.name,
                "rating": company.rating,
                "score": round(score, 4),
                "justification": f"Профиль услуг соответствует запросу «{query}»",
                "done_similar_count": 0,
            }
        )
    return results


async def search_similar_requests(db: AsyncSession, query: str, top_k: int = 10) -> list[dict]:
    hits = await search_embeddings(db, "request", query, top_k)
    results = []
    for emb, score in hits:
        try:
            req = await db.get(Request, emb.entity_id)
        except Exception:  # noqa: BLE001
            req = None
        if req is None:
            continue
        results.append(
            {
                "request_id": str(req.id),
                "title": req.title,
                "similarity": round(score, 4),
                "status": req.status,
            }
        )
    return results


async def search_tz_templates(db: AsyncSession, query: str, top_k: int = 5) -> list[dict]:
    hits = await search_embeddings(db, "tz_template", query, top_k)
    return [
        {"template_id": emb.entity_id, "content": emb.content, "score": round(score, 4)} for emb, score in hits
    ]
