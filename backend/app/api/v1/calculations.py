from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.db.models import CalculationStage, CostCalculation
from app.schemas.product import CalculationStageOut, CostCalculationOut

router = APIRouter()


@router.get("/cost-calculations", response_model=list[CostCalculationOut])
async def list_cost_calculations(contract_id: str | None = Query(None), db: AsyncSession = Depends(get_db)):
    stmt = select(CostCalculation)
    if contract_id:
        stmt = stmt.where(CostCalculation.contract_id == contract_id)
    return (await db.execute(stmt)).scalars().all()


@router.get("/cost-calculations/{calc_id}/stages", response_model=list[CalculationStageOut])
async def list_calculation_stages(calc_id: str, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(CalculationStage)
        .where(CalculationStage.calc_id == calc_id)
        .order_by(CalculationStage.stage_order_num)
    )
    return (await db.execute(stmt)).scalars().all()
