import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_optional, get_db
from app.db.models import Request, RequestDocument, RequestTz, RequestTzAnalysis, TzTemplate, User
from app.schemas.request import (
    RequestCreate,
    RequestDetailOut,
    RequestListOut,
    RequestOut,
    RequestUpdate,
    TzSummary,
)
from app.services.tz_builder import create_tz_from_template
from app.utils.errors import NotFoundError
from app.utils.numbering import generate_request_number

router = APIRouter()


@router.post("/requests", response_model=RequestOut, status_code=201)
async def create_request(
    body: RequestCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_optional),
):
    request = Request(
        number=generate_request_number(),
        user_id=user.id,
        company_id=body.company_id,
        contract_id=body.contract_id,
        product_id=body.product_id,
        title=body.title,
        description=body.description,
        cost_total=body.cost_total,
        date_start=body.date_start,
        date_end=body.date_end,
        chat_session_id=body.chat_session_id,
    )
    db.add(request)
    await db.flush()

    if body.template_id:
        template = await db.get(TzTemplate, body.template_id)
        if template:
            await create_tz_from_template(db, request.id, template)

    await db.commit()
    await db.refresh(request)
    return request


@router.get("/requests", response_model=RequestListOut)
async def list_requests(
    status: str | None = Query(None),
    user: str | None = Query(None),
    limit: int = Query(20, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Request)
    count_stmt = select(func.count()).select_from(Request)
    if status:
        stmt = stmt.where(Request.status == status)
        count_stmt = count_stmt.where(Request.status == status)
    if user:
        stmt = stmt.where(Request.user_id == user)
        count_stmt = count_stmt.where(Request.user_id == user)
    stmt = stmt.order_by(Request.created_at.desc()).limit(limit).offset(offset)

    items = (await db.execute(stmt)).scalars().all()
    total = (await db.execute(count_stmt)).scalar_one()
    return RequestListOut(items=items, total=total)


@router.get("/requests/{request_id}", response_model=RequestDetailOut)
async def get_request(request_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    request = await db.get(Request, request_id)
    if request is None:
        raise NotFoundError("Заявка не найдена")

    tz_summary = TzSummary()
    tz = (await db.execute(select(RequestTz).where(RequestTz.request_id == request_id))).scalar_one_or_none()
    if tz:
        latest_analysis = (
            await db.execute(
                select(RequestTzAnalysis)
                .where(RequestTzAnalysis.tz_id == tz.id)
                .order_by(RequestTzAnalysis.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        tz_summary = TzSummary(
            completeness_pct=tz.completeness_pct,
            risks_count=len(latest_analysis.risks) if latest_analysis else 0,
        )

    documents_count = (
        await db.execute(select(func.count()).select_from(RequestDocument).where(RequestDocument.request_id == request_id))
    ).scalar_one()

    data = RequestOut.model_validate(request).model_dump()
    return RequestDetailOut(**data, tz_summary=tz_summary, documents_count=documents_count)


@router.patch("/requests/{request_id}", response_model=RequestOut)
async def update_request(request_id: uuid.UUID, body: RequestUpdate, db: AsyncSession = Depends(get_db)):
    request = await db.get(Request, request_id)
    if request is None:
        raise NotFoundError("Заявка не найдена")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(request, field, value)
    await db.commit()
    await db.refresh(request)
    return request


@router.delete("/requests/{request_id}", status_code=204)
async def delete_request(request_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    request = await db.get(Request, request_id)
    if request is None:
        raise NotFoundError("Заявка не найдена")
    await db.delete(request)
    await db.commit()


@router.post("/requests/{request_id}/submit", response_model=RequestOut)
async def submit_request(request_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    request = await db.get(Request, request_id)
    if request is None:
        raise NotFoundError("Заявка не найдена")
    request.status = "submitted"
    await db.commit()
    await db.refresh(request)
    return request
