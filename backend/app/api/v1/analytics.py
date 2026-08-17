from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.db.models import (
    Company,
    Product,
    Request,
    RequestTz,
    RequestTzAnalysis,
    RequestTzStage,
    TzTemplate,
)
from app.schemas.analytics import SearchAnalyticsOut, TzAnalyticsOut

router = APIRouter()


@router.get("/analytics/tz", response_model=TzAnalyticsOut)
async def tz_analytics(db: AsyncSession = Depends(get_db)):
    total_tz = (await db.execute(select(func.count()).select_from(RequestTz))).scalar_one()

    by_type_rows = (
        await db.execute(
            select(TzTemplate.name, func.count(RequestTz.id))
            .join(RequestTz, RequestTz.template_id == TzTemplate.id)
            .group_by(TzTemplate.name)
        )
    ).all()
    by_type = [{"type": name, "count": count} for name, count in by_type_rows]

    stage_rows = (await db.execute(select(RequestTzStage.stage_name))).scalars().all()
    stage_counter = Counter(stage_rows)
    by_stage_popularity = [{"stage": name, "count": count} for name, count in stage_counter.most_common(20)]

    analyses = (await db.execute(select(RequestTzAnalysis))).scalars().all()
    error_counter: Counter[str] = Counter()
    for analysis in analyses:
        for risk in analysis.risks:
            error_counter[risk.get("title", "неизвестно")] += 1
    typical_errors = [{"title": title, "count": count} for title, count in error_counter.most_common(20)]

    product_rows = (
        await db.execute(select(Product.product_name, func.count(Request.id)).join(Request, Request.product_id == Product.product_id).group_by(Product.product_name))
    ).all()
    product_candidates = [{"product_name": name, "count": count} for name, count in product_rows]

    return TzAnalyticsOut(
        total_tz=total_tz,
        by_type=by_type,
        by_stage_popularity=by_stage_popularity,
        typical_errors=typical_errors,
        product_candidates=product_candidates,
    )


@router.get("/analytics/search", response_model=SearchAnalyticsOut)
async def search_analytics(db: AsyncSession = Depends(get_db)):
    product_rows = (
        await db.execute(
            select(Product.product_name, func.count(Request.id))
            .join(Request, Request.product_id == Product.product_id)
            .group_by(Product.product_name)
            .order_by(func.count(Request.id).desc())
        )
    ).all()
    top_services = [{"product_name": name, "count": count} for name, count in product_rows]

    contractor_rows = (
        await db.execute(
            select(Company.name, func.count(Request.id))
            .join(Request, Request.company_id == Company.company_id)
            .group_by(Company.name)
            .order_by(func.count(Request.id).desc())
        )
    ).all()
    top_contractors = [{"name": name, "count": count} for name, count in contractor_rows]

    requests = (await db.execute(select(Request))).scalars().all()
    unfilled_fields = []
    for field_name in ["company_id", "contract_id", "product_id", "cost_total", "date_start", "date_end"]:
        empty = sum(1 for r in requests if getattr(r, field_name) is None)
        if empty:
            unfilled_fields.append({"field": field_name, "empty_count": empty})

    return SearchAnalyticsOut(
        top_services=top_services,
        service_combinations=[],
        top_contractors=top_contractors,
        unfilled_fields=unfilled_fields,
        unrecognized_queries=[],
    )
