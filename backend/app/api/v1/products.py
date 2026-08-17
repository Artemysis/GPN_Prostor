from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.db.models import ContractProduct, Product, ProductOperation, ProductRate
from app.schemas.product import ProductOperationOut, ProductOut, ProductRateOut
from app.utils.errors import NotFoundError

router = APIRouter()


@router.get("/products", response_model=list[ProductOut])
async def list_products(
    contract_id: str | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(50, le=500),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Product)
    if contract_id:
        stmt = stmt.join(ContractProduct, ContractProduct.product_id == Product.product_id).where(
            ContractProduct.contract_id == contract_id
        )
    if search:
        stmt = stmt.where(Product.product_name.ilike(f"%{search}%"))
    stmt = stmt.limit(limit)
    return (await db.execute(stmt)).scalars().all()


@router.get("/products/{product_id}", response_model=ProductOut)
async def get_product(product_id: str, db: AsyncSession = Depends(get_db)):
    product = await db.get(Product, product_id)
    if product is None:
        raise NotFoundError("Продукт не найден")
    return product


@router.get("/products/{product_id}/rates", response_model=list[ProductRateOut])
async def get_product_rates(product_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(ProductRate).where(ProductRate.product_id == product_id)
    return (await db.execute(stmt)).scalars().all()


@router.get("/products/{product_id}/operations", response_model=list[ProductOperationOut])
async def get_product_operations(product_id: str, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(ProductOperation)
        .where(ProductOperation.product_id == product_id)
        .order_by(ProductOperation.operation_order)
    )
    return (await db.execute(stmt)).scalars().all()
