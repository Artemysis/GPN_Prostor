import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.deps import get_db
from app.db.models import TzTemplate, TzTemplateBlock, TzTemplateStage
from app.schemas.tz_template import (
    TzTemplateBlockOut,
    TzTemplateCreateResponse,
    TzTemplateDetailOut,
    TzTemplateOut,
    TzTemplateRecommendRequest,
    TzTemplateRecommendResponse,
)
from app.services.docx_parser import build_blocks_schema, new_template_docx_key, parse_docx_template
from app.services.minio_client import get_minio_service
from app.services.template_recommender import recommend_template
from app.utils.errors import ConflictError, NotFoundError

router = APIRouter()
settings = get_settings()


@router.get("/tz-templates", response_model=list[TzTemplateOut])
async def list_tz_templates(db: AsyncSession = Depends(get_db)):
    stmt = select(TzTemplate).where(TzTemplate.is_active.is_(True))
    return (await db.execute(stmt)).scalars().all()


@router.get("/tz-templates/{template_id}", response_model=TzTemplateDetailOut)
async def get_tz_template(template_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(TzTemplate)
        .where(TzTemplate.id == template_id)
        .options(selectinload(TzTemplate.blocks), selectinload(TzTemplate.stages))
    )
    template = (await db.execute(stmt)).scalar_one_or_none()
    if template is None:
        raise NotFoundError("Шаблон не найден")
    return template


@router.get("/tz-templates/{template_id}/blocks", response_model=list[TzTemplateBlockOut])
async def get_tz_template_blocks(template_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(TzTemplateBlock)
        .where(TzTemplateBlock.template_id == template_id)
        .order_by(TzTemplateBlock.block_order)
    )
    return (await db.execute(stmt)).scalars().all()


@router.post("/tz-templates", response_model=TzTemplateCreateResponse, status_code=201)
async def create_tz_template(
    code: str = Form(...),
    name: str = Form(...),
    description: str | None = Form(None),
    docx_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    existing = (await db.execute(select(TzTemplate).where(TzTemplate.code == code))).scalar_one_or_none()
    if existing:
        raise ConflictError(f"Шаблон с кодом {code} уже существует")

    file_bytes = await docx_file.read()
    parsed = parse_docx_template(file_bytes)

    template = TzTemplate(
        code=code,
        name=name,
        description=description,
        minio_docx_key="",
        blocks_schema=build_blocks_schema(parsed.blocks),
    )
    db.add(template)
    await db.flush()

    docx_key = new_template_docx_key(template.id)
    template.minio_docx_key = docx_key
    get_minio_service().upload_bytes(
        settings.minio_bucket_templates,
        docx_key,
        file_bytes,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    for block in parsed.blocks:
        db.add(
            TzTemplateBlock(
                template_id=template.id,
                block_code=block.code,
                block_name=block.name,
                block_order=block.order,
                json_schema={"fields": block.fields, "is_stages_block": block.is_stages_block},
            )
        )
    for stage in parsed.stages:
        db.add(
            TzTemplateStage(
                template_id=template.id,
                stage_order=stage["stage_order"],
                stage_name=stage["stage_name"],
                default_requirements=stage.get("default_requirements"),
                default_results=stage.get("default_results"),
            )
        )

    await db.commit()
    await db.refresh(template)
    return TzTemplateCreateResponse(id=template.id, code=template.code, name=template.name)


@router.post("/tz-templates/recommend", response_model=TzTemplateRecommendResponse)
async def recommend_tz_template(body: TzTemplateRecommendRequest, db: AsyncSession = Depends(get_db)):
    result = await recommend_template(db, body.prompt, body.request_context)
    return TzTemplateRecommendResponse(**result)
