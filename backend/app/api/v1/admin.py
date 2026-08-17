from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.db.models import Company, Product, Request, TzTemplate
from app.schemas.analytics import EmbeddingsRebuildRequest, IngestResult
from app.schemas.job import JobCreatedOut
from app.services import xlsx_parser
from app.services.embeddings import upsert_embedding
from app.services.jobs import create_job, run_job

router = APIRouter(prefix="/admin")


@router.post("/ingest/companies", response_model=IngestResult)
async def ingest_companies(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    result = await xlsx_parser.ingest_companies(db, await file.read())
    return IngestResult(**result)


@router.post("/ingest/contracts", response_model=IngestResult)
async def ingest_contracts(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    result = await xlsx_parser.ingest_contracts(db, await file.read())
    return IngestResult(**result)


@router.post("/ingest/products-rates", response_model=IngestResult)
async def ingest_products_rates(
    products_file: UploadFile = File(...),
    rates_file: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
):
    rates_bytes = await rates_file.read() if rates_file else None
    result = await xlsx_parser.ingest_products_rates(db, await products_file.read(), rates_bytes)
    return IngestResult(**result)


@router.post("/ingest/operations", response_model=IngestResult)
async def ingest_operations(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    result = await xlsx_parser.ingest_operations(db, await file.read())
    return IngestResult(**result)


@router.post("/ingest/calculations", response_model=IngestResult)
async def ingest_calculations(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    result = await xlsx_parser.ingest_calculations(db, await file.read())
    return IngestResult(**result)


async def _rebuild_embeddings_task(entity_types: list[str] | None):
    async def task(db: AsyncSession) -> dict:
        types = entity_types or ["product", "company_services", "tz_template", "request"]
        counts: dict[str, int] = {}

        if "product" in types:
            products = (await db.execute(select(Product))).scalars().all()
            for p in products:
                ops = ""
                await upsert_embedding(db, "product", p.product_id, f"{p.product_name} {ops}")
            counts["product"] = len(products)

        if "company_services" in types:
            companies = (await db.execute(select(Company))).scalars().all()
            for c in companies:
                await upsert_embedding(db, "company_services", c.company_id, c.services or c.name)
            counts["company_services"] = len(companies)

        if "tz_template" in types:
            templates = (await db.execute(select(TzTemplate))).scalars().all()
            for t in templates:
                await upsert_embedding(db, "tz_template", str(t.id), f"{t.name} {t.description or ''}")
            counts["tz_template"] = len(templates)

        if "request" in types:
            requests = (await db.execute(select(Request))).scalars().all()
            for r in requests:
                text = f"{r.title or ''} {r.description or ''}"
                if text.strip():
                    await upsert_embedding(db, "request", str(r.id), text)
            counts["request"] = len(requests)

        return {"counts": counts}

    return task


@router.post("/embeddings/rebuild", response_model=JobCreatedOut)
async def rebuild_embeddings(
    body: EmbeddingsRebuildRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)
):
    job = await create_job(db, "embeddings_rebuild", {"entity_types": body.entity_types})
    task = await _rebuild_embeddings_task(body.entity_types)
    background_tasks.add_task(run_job, job.id, task)
    return JobCreatedOut(job_id=job.id)
