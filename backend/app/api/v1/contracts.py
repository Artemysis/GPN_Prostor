from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.db.models import Contract
from app.schemas.contract import ContractOut
from app.utils.errors import NotFoundError

router = APIRouter()


@router.get("/contracts", response_model=list[ContractOut])
async def list_contracts(
    company_id: str | None = Query(None),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Contract)
    if company_id:
        stmt = stmt.where(Contract.company_id == company_id)
    if search:
        stmt = stmt.where(Contract.contract_number.ilike(f"%{search}%"))
    return (await db.execute(stmt)).scalars().all()


@router.get("/contracts/{contract_id}", response_model=ContractOut)
async def get_contract(contract_id: str, db: AsyncSession = Depends(get_db)):
    contract = await db.get(Contract, contract_id)
    if contract is None:
        raise NotFoundError("Договор не найден")
    return contract
