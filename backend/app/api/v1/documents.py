import asyncio
import urllib.parse
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.deps import get_db
from app.db.models import (
    Company,
    Contract,
    Product,
    ProductRate,
    Request,
    RequestDocument,
    RequestTz,
    RequestTzAnalysis,
    TzTemplate,
)
from app.schemas.document import (
    AnalyticalReportRequest,
    ExportRequest,
    RequestDocumentDetailOut,
    RequestDocumentOut,
)
from app.schemas.job import JobCreatedOut
from app.services.jobs import create_job, run_job
from app.services.minio_client import get_minio_service
from app.services.package_exporter import (
    PACKAGE_DOCS,
    render_kp_xlsx,
    render_naryad_zakaz_docx,
    render_rs_xlsx,
    render_tz_appendix1_docx,
    render_tz_form_2_1_docx,
)
from app.services.tz_exporter import (
    generate_analytical_report_text,
    render_report_docx,
    render_text_pdf,
    render_tz_docx,
    tz_payload_as_text,
    upload_export,
)
from app.utils.errors import NotFoundError

router = APIRouter()
settings = get_settings()


async def _get_request(db: AsyncSession, request_id: uuid.UUID) -> Request:
    request = await db.get(Request, request_id)
    if request is None:
        raise NotFoundError("Заявка не найдена")
    return request


async def _export_task(request_id: uuid.UUID, formats: list[str], include_report: bool, include_package: bool):
    async def task(db: AsyncSession) -> dict:
        request = await _get_request(db, request_id)
        stmt = select(RequestTz).where(RequestTz.request_id == request_id).options(selectinload(RequestTz.stages))
        tz = (await db.execute(stmt)).scalar_one_or_none()
        if tz is None:
            raise ValueError("ТЗ для заявки не создано")
        template = await db.get(TzTemplate, tz.template_id)
        stages = tz.stages

        minio = get_minio_service()
        documents = []

        for fmt in formats:
            doc_id = uuid.uuid4()
            if fmt == "docx":
                data = render_tz_docx(request, template, tz, stages)
            elif fmt == "pdf":
                data = render_text_pdf(f"ТЗ {template.name}", tz_payload_as_text(request, template, tz, stages))
            else:
                continue
            bucket, key = upload_export(minio, request_id, doc_id, data, fmt)
            doc = RequestDocument(
                id=doc_id,
                request_id=request_id,
                kind="tz_final",
                filename=f"tz_{request.number or request_id}.{fmt}",
                mime_type="application/octet-stream",
                minio_bucket=bucket,
                minio_key=key,
                size_bytes=len(data),
                generated_by_ai=False,
            )
            db.add(doc)
            documents.append(str(doc_id))

        if include_report:
            analysis = (
                await db.execute(
                    select(RequestTzAnalysis)
                    .where(RequestTzAnalysis.tz_id == tz.id)
                    .order_by(RequestTzAnalysis.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            analysis_dict = (
                {
                    "completeness_pct": analysis.completeness_pct,
                    "risks": analysis.risks,
                    "recommendations": analysis.recommendations,
                }
                if analysis
                else {"completeness_pct": tz.completeness_pct, "risks": [], "recommendations": []}
            )
            report_text = await generate_analytical_report_text(request, tz, analysis_dict)
            doc_id = uuid.uuid4()
            data = render_report_docx(f"Аналитический отчёт по заявке {request.number}", report_text)
            bucket, key = upload_export(minio, request_id, doc_id, data, "docx")
            db.add(
                RequestDocument(
                    id=doc_id,
                    request_id=request_id,
                    kind="analytical_report",
                    filename=f"report_{request.number or request_id}.docx",
                    mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    minio_bucket=bucket,
                    minio_key=key,
                    size_bytes=len(data),
                    generated_by_ai=True,
                )
            )
            documents.append(str(doc_id))

        if include_package:
            company = await db.get(Company, request.company_id) if request.company_id else None
            contract = await db.get(Contract, request.contract_id) if request.contract_id else None
            product = await db.get(Product, request.product_id) if request.product_id else None
            rates: list[ProductRate] = []
            if request.product_id:
                rates = (
                    await db.execute(select(ProductRate).where(ProductRate.product_id == request.product_id))
                ).scalars().all()

            package_data = {
                "naryad_zakaz": render_naryad_zakaz_docx(request, company, contract, product, tz),
                "tz_appendix1": render_tz_appendix1_docx(request, template, tz, stages),
                "tz_form_2_1": render_tz_form_2_1_docx(request, template, tz, stages),
                "kp": render_kp_xlsx(request, stages, company),
                "rs": render_rs_xlsx(request, stages, rates),
            }
            for kind, filename_prefix, mime_type, ext in PACKAGE_DOCS:
                data = package_data[kind]
                doc_id = uuid.uuid4()
                bucket, key = upload_export(minio, request_id, doc_id, data, ext)
                db.add(
                    RequestDocument(
                        id=doc_id,
                        request_id=request_id,
                        kind=kind,
                        filename=f"{filename_prefix}_{request.number or request_id}.{ext}",
                        mime_type=mime_type,
                        minio_bucket=bucket,
                        minio_key=key,
                        size_bytes=len(data),
                        generated_by_ai=False,
                    )
                )
                documents.append(str(doc_id))

        await db.commit()
        return {"documents": documents}

    return task


@router.post("/requests/{request_id}/export", response_model=JobCreatedOut)
async def export_request(request_id: uuid.UUID, body: ExportRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    await _get_request(db, request_id)
    job = await create_job(db, "export", {"request_id": str(request_id), "formats": body.formats})
    task = await _export_task(request_id, body.formats, body.include_analytical_report, body.include_package)
    background_tasks.add_task(run_job, job.id, task)
    return JobCreatedOut(job_id=job.id)


async def _export_report_task(request_id: uuid.UUID, fmt: str):
    async def task(db: AsyncSession) -> dict:
        request = await _get_request(db, request_id)
        tz = (await db.execute(select(RequestTz).where(RequestTz.request_id == request_id))).scalar_one_or_none()
        if tz is None:
            raise ValueError("ТЗ для заявки не создано")
        analysis = (
            await db.execute(
                select(RequestTzAnalysis)
                .where(RequestTzAnalysis.tz_id == tz.id)
                .order_by(RequestTzAnalysis.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        analysis_dict = (
            {"completeness_pct": analysis.completeness_pct, "risks": analysis.risks, "recommendations": analysis.recommendations}
            if analysis
            else {"completeness_pct": tz.completeness_pct, "risks": [], "recommendations": []}
        )
        report_text = await generate_analytical_report_text(request, tz, analysis_dict)
        title = f"Аналитический отчёт по заявке {request.number}"
        data = render_report_docx(title, report_text) if fmt == "docx" else render_text_pdf(title, report_text)

        doc_id = uuid.uuid4()
        minio = get_minio_service()
        bucket, key = upload_export(minio, request_id, doc_id, data, fmt)
        db.add(
            RequestDocument(
                id=doc_id,
                request_id=request_id,
                kind="analytical_report",
                filename=f"report_{request.number or request_id}.{fmt}",
                mime_type="application/octet-stream",
                minio_bucket=bucket,
                minio_key=key,
                size_bytes=len(data),
                generated_by_ai=True,
            )
        )
        await db.commit()
        return {"document_id": str(doc_id)}

    return task


@router.post("/requests/{request_id}/export/analytical-report", response_model=JobCreatedOut)
async def export_analytical_report(
    request_id: uuid.UUID, body: AnalyticalReportRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)
):
    await _get_request(db, request_id)
    job = await create_job(db, "export", {"request_id": str(request_id), "kind": "analytical_report"})
    task = await _export_report_task(request_id, body.format)
    background_tasks.add_task(run_job, job.id, task)
    return JobCreatedOut(job_id=job.id)


@router.get("/requests/{request_id}/documents", response_model=list[RequestDocumentOut])
async def list_request_documents(request_id: uuid.UUID, kind: str | None = Query(None), db: AsyncSession = Depends(get_db)):
    stmt = select(RequestDocument).where(RequestDocument.request_id == request_id)
    if kind:
        stmt = stmt.where(RequestDocument.kind == kind)
    return (await db.execute(stmt)).scalars().all()


async def _get_document(db: AsyncSession, doc_id: uuid.UUID) -> RequestDocument:
    doc = await db.get(RequestDocument, doc_id)
    if doc is None:
        raise NotFoundError("Документ не найден")
    return doc


@router.get("/documents/{doc_id}", response_model=RequestDocumentDetailOut)
async def get_document(doc_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    doc = await _get_document(db, doc_id)
    # Ссылка через API-прокси: presigned-URL с внутренним адресом MinIO (minio:9000)
    # неразрешим из браузера на хосте.
    url = f"/api/v1/documents/{doc_id}/download"
    data = RequestDocumentOut.model_validate(doc).model_dump()
    return RequestDocumentDetailOut(**data, presigned_url=url, expires_in=900)


@router.get("/documents/{doc_id}/download")
async def download_document(doc_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    doc = await _get_document(db, doc_id)
    # Отдаём файл через бэкенд: redirect на presigned-URL MinIO ломается в docker-сети
    # (браузер не резолвит minio:9000), а подмена хоста в подписанном URL ломает подпись.
    data = await asyncio.to_thread(get_minio_service().download_bytes, doc.minio_bucket, doc.minio_key)
    filename = doc.filename.replace('"', "'")
    quoted = urllib.parse.quote(filename)
    disposition = f"attachment; filename=\"{quoted}\"; filename*=UTF-8''{quoted}"
    return Response(
        content=data,
        media_type=doc.mime_type or "application/octet-stream",
        headers={
            "Content-Disposition": disposition,
            "Content-Length": str(len(data)),
        },
    )


@router.post("/requests/{request_id}/attachments", response_model=RequestDocumentOut, status_code=201)
async def upload_attachment(
    request_id: uuid.UUID,
    kind: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    await _get_request(db, request_id)
    data = await file.read()
    doc_id = uuid.uuid4()
    key = f"attachments/{request_id}/{doc_id}.{(file.filename or 'bin').split('.')[-1]}"
    get_minio_service().upload_bytes(settings.minio_bucket_attachments, key, data, file.content_type or "application/octet-stream")

    doc = RequestDocument(
        id=doc_id,
        request_id=request_id,
        kind=kind,
        filename=file.filename or str(doc_id),
        mime_type=file.content_type,
        minio_bucket=settings.minio_bucket_attachments,
        minio_key=key,
        size_bytes=len(data),
        generated_by_ai=False,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


@router.get("/requests/{request_id}/attachments", response_model=list[RequestDocumentOut])
async def list_attachments(request_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    stmt = select(RequestDocument).where(RequestDocument.request_id == request_id, RequestDocument.kind == "attachment")
    return (await db.execute(stmt)).scalars().all()


@router.delete("/requests/{request_id}/attachments/{att_id}", status_code=204)
async def delete_attachment(request_id: uuid.UUID, att_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    doc = await _get_document(db, att_id)
    if doc.request_id != request_id:
        raise NotFoundError("Приложение не найдено")
    try:
        get_minio_service().delete(doc.minio_bucket, doc.minio_key)
    except Exception:  # noqa: BLE001
        pass
    await db.delete(doc)
    await db.commit()
