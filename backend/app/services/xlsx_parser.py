"""Парсер xlsx-выгрузок ПРОСТОР (§6, §2.1 SPEC).

Колонки в реальных выгрузках могут отличаться по регистру/написанию, поэтому
сопоставление ведётся по нормализованным именам с несколькими синонимами.
"""

import io
from datetime import date

import pandas as pd
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    CalculationStage,
    Company,
    Contract,
    ContractProduct,
    CostCalculation,
    Product,
    ProductOperation,
    ProductRate,
)


def _norm(s: str) -> str:
    return str(s).strip().lower().replace(" ", "_").replace("-", "_")


def _read(file_bytes: bytes) -> pd.DataFrame:
    return pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")


def _col(df: pd.DataFrame, *candidates: str) -> str | None:
    normed = {_norm(c): c for c in df.columns}
    for cand in candidates:
        if cand in normed:
            return normed[cand]
    return None


def _to_date(value) -> date | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return pd.to_datetime(value).date()
    except Exception:  # noqa: BLE001
        return None


def _val(row, col) -> str | None:
    if col is None:
        return None
    v = row[col]
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    return str(v).strip()


async def ingest_companies(db: AsyncSession, file_bytes: bytes) -> dict:
    df = _read(file_bytes)
    id_col = _col(df, "company_id", "id", "код")
    name_col = _col(df, "name", "наименование", "компания")
    info_col = _col(df, "info", "описание")
    services_col = _col(df, "services", "услуги", "перечень_услуг")
    rating_col = _col(df, "rating", "рейтинг")

    inserted, updated = 0, 0
    for _, row in df.iterrows():
        company_id = _val(row, id_col)
        name = _val(row, name_col)
        if not company_id or not name:
            continue
        existing = await db.get(Company, company_id)
        rating_raw = _val(row, rating_col)
        rating = int(float(rating_raw)) if rating_raw else None
        if existing:
            existing.name = name
            existing.info = _val(row, info_col)
            existing.services = _val(row, services_col)
            existing.rating = rating
            updated += 1
        else:
            db.add(
                Company(
                    company_id=company_id,
                    name=name,
                    info=_val(row, info_col),
                    services=_val(row, services_col),
                    rating=rating,
                )
            )
            inserted += 1
    await db.commit()
    return {"inserted": inserted, "updated": updated}


async def ingest_contracts(db: AsyncSession, file_bytes: bytes) -> dict:
    df = _read(file_bytes)
    id_col = _col(df, "contract_id", "id", "код")
    number_col = _col(df, "contract_number", "номер_договора", "номер")
    company_col = _col(df, "company_id", "компания_id", "id_компании")

    inserted, updated = 0, 0
    for _, row in df.iterrows():
        contract_id = _val(row, id_col)
        number = _val(row, number_col)
        company_id = _val(row, company_col)
        if not contract_id or not number or not company_id:
            continue
        if not await db.get(Company, company_id):
            logger.warning(f"Договор {contract_id}: компания {company_id} не найдена, пропуск")
            continue
        existing = await db.get(Contract, contract_id)
        if existing:
            existing.contract_number = number
            existing.company_id = company_id
            updated += 1
        else:
            db.add(Contract(contract_id=contract_id, contract_number=number, company_id=company_id))
            inserted += 1
    await db.commit()
    return {"inserted": inserted, "updated": updated}


async def ingest_products_rates(db: AsyncSession, products_file: bytes, rates_file: bytes | None = None) -> dict:
    df = _read(products_file)
    product_id_col = _col(df, "product_id", "id", "код_продукта")
    product_name_col = _col(df, "product_name", "наименование_продукта", "продукт")
    contract_id_col = _col(df, "contract_id", "id_договора")

    inserted, updated = 0, 0
    for _, row in df.iterrows():
        product_id = _val(row, product_id_col)
        product_name = _val(row, product_name_col)
        if not product_id or not product_name:
            continue
        existing = await db.get(Product, product_id)
        if existing:
            existing.product_name = product_name
            updated += 1
        else:
            db.add(Product(product_id=product_id, product_name=product_name))
            inserted += 1

        contract_id = _val(row, contract_id_col)
        if contract_id and await db.get(Contract, contract_id):
            link = await db.get(ContractProduct, {"contract_id": contract_id, "product_id": product_id})
            if not link:
                db.add(ContractProduct(contract_id=contract_id, product_id=product_id))
    await db.commit()

    if rates_file:
        rdf = _read(rates_file)
        price_id_col = _col(rdf, "price_id", "id")
        price_product_col = _col(rdf, "product_id", "id_продукта")
        price_name_col = _col(rdf, "price_name", "наименование_расценки", "категория")
        measurement_name_col = _col(rdf, "measurement_name", "ед_изм", "единица_измерения")
        measurement_type_col = _col(rdf, "measurement_type", "тип_ед_изм")

        for _, row in rdf.iterrows():
            price_id = _val(row, price_id_col)
            price_product_id = _val(row, price_product_col)
            price_name = _val(row, price_name_col)
            if not price_id or not price_product_id or not price_name:
                continue
            if not await db.get(Product, price_product_id):
                continue
            existing_rate = await db.get(ProductRate, price_id)
            if existing_rate:
                existing_rate.price_name = price_name
                existing_rate.measurement_name = _val(row, measurement_name_col)
                existing_rate.measurement_type = _val(row, measurement_type_col)
                updated += 1
            else:
                db.add(
                    ProductRate(
                        price_id=price_id,
                        product_id=price_product_id,
                        price_name=price_name,
                        measurement_name=_val(row, measurement_name_col),
                        measurement_type=_val(row, measurement_type_col),
                    )
                )
                inserted += 1
        await db.commit()

    return {"inserted": inserted, "updated": updated}


async def ingest_operations(db: AsyncSession, file_bytes: bytes) -> dict:
    df = _read(file_bytes)
    op_id_col = _col(df, "operation_id", "id")
    product_id_col = _col(df, "product_id", "id_продукта")
    op_name_col = _col(df, "operation_name", "наименование_операции", "операция")
    order_col = _col(df, "operation_order", "порядок")

    inserted, updated = 0, 0
    for _, row in df.iterrows():
        operation_id = _val(row, op_id_col)
        product_id = _val(row, product_id_col)
        operation_name = _val(row, op_name_col)
        if not operation_id or not product_id or not operation_name:
            continue
        if not await db.get(Product, product_id):
            continue
        order_raw = _val(row, order_col)
        existing = await db.get(ProductOperation, operation_id)
        if existing:
            existing.operation_name = operation_name
            existing.operation_order = int(float(order_raw)) if order_raw else None
            updated += 1
        else:
            db.add(
                ProductOperation(
                    operation_id=operation_id,
                    product_id=product_id,
                    operation_name=operation_name,
                    operation_order=int(float(order_raw)) if order_raw else None,
                )
            )
            inserted += 1
    await db.commit()
    return {"inserted": inserted, "updated": updated}


async def ingest_calculations(db: AsyncSession, file_bytes: bytes) -> dict:
    df = _read(file_bytes)
    calc_id_col = _col(df, "calc_id", "id")
    contract_id_col = _col(df, "contract_id", "id_договора")
    calc_name_col = _col(df, "calc_name", "наименование_рс", "наименование")
    start_col = _col(df, "calc_start_date", "дата_начала")
    end_col = _col(df, "calc_end_date", "дата_окончания")
    product_id_col = _col(df, "product_id", "id_продукта")

    stage_id_col = _col(df, "stage_id")
    parent_col = _col(df, "parent_stage_id")
    stage_name_col = _col(df, "stage_name", "наименование_этапа")
    stage_start_col = _col(df, "stage_start_date")
    stage_end_col = _col(df, "stage_end_date")
    stage_order_col = _col(df, "stage_order_num", "порядок")
    stage_docs_col = _col(df, "stage_documentation_list", "документация")

    inserted, updated = 0, 0
    for _, row in df.iterrows():
        calc_id = _val(row, calc_id_col)
        contract_id = _val(row, contract_id_col)
        calc_name = _val(row, calc_name_col)
        if not calc_id or not contract_id or not calc_name:
            continue
        if not await db.get(Contract, contract_id):
            continue
        existing = await db.get(CostCalculation, calc_id)
        if not existing:
            db.add(
                CostCalculation(
                    calc_id=calc_id,
                    contract_id=contract_id,
                    calc_name=calc_name,
                    calc_start_date=_to_date(row[start_col]) if start_col else None,
                    calc_end_date=_to_date(row[end_col]) if end_col else None,
                    product_id=_val(row, product_id_col),
                )
            )
            inserted += 1
        else:
            updated += 1

        stage_id = _val(row, stage_id_col)
        if stage_id and not await db.get(CalculationStage, stage_id):
            order_raw = _val(row, stage_order_col)
            db.add(
                CalculationStage(
                    stage_id=stage_id,
                    calc_id=calc_id,
                    parent_stage_id=_val(row, parent_col),
                    stage_name=_val(row, stage_name_col) or "Этап",
                    stage_start_date=_to_date(row[stage_start_col]) if stage_start_col else None,
                    stage_end_date=_to_date(row[stage_end_col]) if stage_end_col else None,
                    stage_order_num=int(float(order_raw)) if order_raw else None,
                    stage_documentation_list=_val(row, stage_docs_col),
                )
            )
    await db.commit()
    return {"inserted": inserted, "updated": updated}
