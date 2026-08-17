from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_db
from app.db.models import Company
from app.schemas.company import CompanyDetailOut, CompanyOut
from app.utils.errors import NotFoundError

router = APIRouter()


@router.get("/companies", response_model=list[CompanyOut])
async def list_companies(
    search: str | None = Query(None),
    min_rating: int | None = Query(None),
    limit: int = Query(20, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Company)
    if search:
        stmt = stmt.where(Company.name.ilike(f"%{search}%"))
    if min_rating is not None:
        stmt = stmt.where(Company.rating >= min_rating)
    stmt = stmt.order_by(Company.name).limit(limit).offset(offset)
    return (await db.execute(stmt)).scalars().all()


@router.get("/companies/{company_id}", response_model=CompanyDetailOut)
async def get_company(company_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Company).where(Company.company_id == company_id).options(selectinload(Company.contracts))
    company = (await db.execute(stmt)).scalar_one_or_none()
    if company is None:
        raise NotFoundError("Компания не найдена")
    return company
