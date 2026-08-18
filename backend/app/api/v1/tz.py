import uuid

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_db
from app.db.models import (
    Request,
    RequestTz,
    RequestTzAnalysis,
    RequestTzBlock,
    RequestTzStage,
    TzCompletenessLog,
    TzTemplate,
)
from app.schemas.analysis import AnalysisOut, CompletenessOut, Recommendation, Risk
from app.schemas.job import JobCreatedOut
from app.schemas.tz import (
    TzBlockOut,
    TzBlockUpdate,
    TzCreate,
    TzFillAiRequest,
    TzFillAllRequest,
    TzOut,
    TzPayloadUpdate,
    TzStageCreate,
    TzStageOut,
    TzStageUpdate,
)
from app.services.jobs import create_job, run_job
from app.services.tz_analyzer import analyze_tz, compute_overall_completeness
from app.services.tz_builder import (
    create_tz_from_template,
    fill_block_with_ai,
    fill_stages_with_ai,
    find_block_schema,
)
from app.utils.errors import ConflictError, NotFoundError

router = APIRouter()


async def _get_request(db: AsyncSession, request_id: uuid.UUID) -> Request:
    request = await db.get(Request, request_id)
    if request is None:
        raise NotFoundError("Заявка не найдена")
    return request


async def _get_tz(db: AsyncSession, request_id: uuid.UUID, with_relations: bool = True) -> RequestTz:
    stmt = select(RequestTz).where(RequestTz.request_id == request_id)
    if with_relations:
        stmt = stmt.options(selectinload(RequestTz.blocks), selectinload(RequestTz.stages))
    tz = (await db.execute(stmt)).scalar_one_or_none()
    if tz is None:
        raise NotFoundError("ТЗ для заявки не создано")
    return tz


def _tz_out(tz: RequestTz) -> TzOut:
    return TzOut(
        tz_id=tz.id,
        template_id=tz.template_id,
        version=tz.version,
        completeness_pct=tz.completeness_pct,
        payload=tz.payload,
        blocks=[TzBlockOut.model_validate(b) for b in tz.blocks],
        stages=[TzStageOut.model_validate(s) for s in sorted(tz.stages, key=lambda s: s.stage_order)],
    )


async def _recalc_completeness(db: AsyncSession, tz: RequestTz, triggered_by: str = "user") -> None:
    template = await db.get(TzTemplate, tz.template_id)
    overall, _ = compute_overall_completeness(template, tz.payload)
    tz.completeness_pct = overall
    db.add(TzCompletenessLog(tz_id=tz.id, completeness_pct=overall, triggered_by=triggered_by))
    await db.commit()


@router.post("/requests/{request_id}/tz", response_model=TzOut, status_code=201)
async def create_request_tz(request_id: uuid.UUID, body: TzCreate, db: AsyncSession = Depends(get_db)):
    request = await _get_request(db, request_id)
    existing_tz = (await db.execute(select(RequestTz).where(RequestTz.request_id == request_id))).scalar_one_or_none()
    if existing_tz is not None:
        raise ConflictError("ТЗ для заявки уже существует")
    template = await db.get(TzTemplate, body.template_id)
    if template is None:
        raise NotFoundError("Шаблон ТЗ не найден")

    prefill = None
    if body.prefill_from_chat:
        from app.services.llm_client import get_llm_client
        from app.services.tz_builder import generate_tz_prefill

        request_context = {
            "title": request.title,
            "description": request.description,
            "product_id": request.product_id,
            "date_start": request.date_start.isoformat() if request.date_start else None,
            "date_end": request.date_end.isoformat() if request.date_end else None,
            "cost_total": float(request.cost_total) if request.cost_total is not None else None,
        }
        prefill, estimated_cost = await generate_tz_prefill(template, request_context, get_llm_client())
        if estimated_cost and request.cost_total is None:
            request.cost_total = estimated_cost
            meta = dict(request.request_metadata or {})
            meta.setdefault("filled_by", {})["cost_total"] = "ai"
            request.request_metadata = meta

    tz = await create_tz_from_template(db, request_id, template, prefill=prefill)
    tz = await _get_tz(db, request_id)
    return _tz_out(tz)


@router.get("/requests/{request_id}/tz", response_model=TzOut)
async def get_request_tz(request_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    tz = await _get_tz(db, request_id)
    return _tz_out(tz)


@router.put("/requests/{request_id}/tz", response_model=TzOut)
async def replace_request_tz_payload(request_id: uuid.UUID, body: TzPayloadUpdate, db: AsyncSession = Depends(get_db)):
    tz = await _get_tz(db, request_id)
    tz.payload = body.payload
    for block in tz.blocks:
        if block.block_code in body.payload:
            block.content = body.payload[block.block_code]
    await db.commit()
    await _recalc_completeness(db, tz)
    tz = await _get_tz(db, request_id)
    return _tz_out(tz)


@router.get("/requests/{request_id}/tz/blocks", response_model=list[TzBlockOut])
async def list_tz_blocks(request_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    tz = await _get_tz(db, request_id)
    return [TzBlockOut.model_validate(b) for b in tz.blocks]


async def _get_block(db: AsyncSession, tz_id: uuid.UUID, block_code: str) -> RequestTzBlock:
    stmt = select(RequestTzBlock).where(RequestTzBlock.tz_id == tz_id, RequestTzBlock.block_code == block_code)
    block = (await db.execute(stmt)).scalar_one_or_none()
    if block is None:
        raise NotFoundError("Блок ТЗ не найден")
    return block


@router.get("/requests/{request_id}/tz/blocks/{block_code}", response_model=TzBlockOut)
async def get_tz_block(request_id: uuid.UUID, block_code: str, db: AsyncSession = Depends(get_db)):
    tz = await _get_tz(db, request_id, with_relations=False)
    block = await _get_block(db, tz.id, block_code)
    return TzBlockOut.model_validate(block)


@router.patch("/requests/{request_id}/tz/blocks/{block_code}", response_model=TzBlockOut)
async def update_tz_block(request_id: uuid.UUID, block_code: str, body: TzBlockUpdate, db: AsyncSession = Depends(get_db)):
    tz = await _get_tz(db, request_id)
    block = await _get_block(db, tz.id, block_code)
    block.content = body.content
    block.filled_by = body.filled_by
    template = await db.get(TzTemplate, tz.template_id)
    schema = find_block_schema(template, block_code)
    from app.services.tz_analyzer import compute_block_completeness

    block.completeness_pct = compute_block_completeness(schema, block.content) if schema else 0
    block.is_complete = block.completeness_pct >= 100

    payload = dict(tz.payload)
    payload[block_code] = block.content
    tz.payload = payload

    await db.commit()
    await _recalc_completeness(db, tz)
    await db.refresh(block)
    return TzBlockOut.model_validate(block)


async def _fill_ai_task(request_id: uuid.UUID, block_code: str, hint: str | None):
    async def task(db: AsyncSession) -> dict:
        tz = await _get_tz(db, request_id)
        request = await _get_request(db, request_id)
        stmt = select(TzTemplate).where(TzTemplate.id == tz.template_id).options(selectinload(TzTemplate.stages))
        template = (await db.execute(stmt)).scalar_one()
        schema = find_block_schema(template, block_code)
        if schema is None:
            raise ValueError(f"Блок {block_code} не найден в схеме шаблона")

        if schema.get("is_stages_block"):
            stages = await fill_stages_with_ai(
                template=template,
                template_stages=template.stages,
                request_context={"title": request.title, "description": request.description},
                existing_stage_names=[s.stage_name for s in tz.stages],
                hint=hint,
            )
            return {"block_code": block_code, "stages": stages}

        block = await _get_block(db, tz.id, block_code)
        content = await fill_block_with_ai(
            template=template,
            block_code=block_code,
            block_schema=schema,
            request_context={
                "title": request.title,
                "description": request.description,
                "company_id": request.company_id,
                "product_id": request.product_id,
            },
            other_blocks={k: v for k, v in tz.payload.items() if k != block_code},
            hint=hint,
        )
        block.content = content
        block.filled_by = "ai"
        from app.services.tz_analyzer import compute_block_completeness

        block.completeness_pct = compute_block_completeness(schema, content)
        block.is_complete = block.completeness_pct >= 100
        payload = dict(tz.payload)
        payload[block_code] = content
        tz.payload = payload
        await db.commit()
        await _recalc_completeness(db, tz, triggered_by="ai")
        return {"block_code": block_code, "content": content}

    return task


@router.post("/requests/{request_id}/tz/blocks/{block_code}/fill-ai", response_model=JobCreatedOut)
async def fill_block_ai(
    request_id: uuid.UUID,
    block_code: str,
    body: TzFillAiRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    await _get_tz(db, request_id, with_relations=False)
    job = await create_job(db, "fill_ai", {"request_id": str(request_id), "block_code": block_code, "hint": body.hint})
    task = await _fill_ai_task(request_id, block_code, body.hint)
    background_tasks.add_task(run_job, job.id, task)
    return JobCreatedOut(job_id=job.id)


async def _fill_all_task(request_id: uuid.UUID, block_codes: list[str] | None):
    async def task(db: AsyncSession) -> dict:
        tz = await _get_tz(db, request_id)
        request = await _get_request(db, request_id)
        template = await db.get(TzTemplate, tz.template_id)
        codes = block_codes or [b.block_code for b in tz.blocks]
        from app.services.tz_analyzer import compute_block_completeness

        filled = []
        for code in codes:
            schema = find_block_schema(template, code)
            if schema is None or schema.get("is_stages_block"):
                continue
            block = await _get_block(db, tz.id, code)
            content = await fill_block_with_ai(
                template=template,
                block_code=code,
                block_schema=schema,
                request_context={"title": request.title, "description": request.description},
                other_blocks={k: v for k, v in tz.payload.items() if k != code},
            )
            block.content = content
            block.filled_by = "ai"
            block.completeness_pct = compute_block_completeness(schema, content)
            block.is_complete = block.completeness_pct >= 100
            payload = dict(tz.payload)
            payload[code] = content
            tz.payload = payload
            filled.append(code)
        await db.commit()
        await _recalc_completeness(db, tz, triggered_by="ai")
        return {"filled_blocks": filled}

    return task


@router.post("/requests/{request_id}/tz/fill-ai", response_model=JobCreatedOut)
async def fill_all_ai(
    request_id: uuid.UUID,
    body: TzFillAllRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    await _get_tz(db, request_id, with_relations=False)
    job = await create_job(db, "fill_ai", {"request_id": str(request_id), "blocks": body.blocks})
    task = await _fill_all_task(request_id, body.blocks)
    background_tasks.add_task(run_job, job.id, task)
    return JobCreatedOut(job_id=job.id)


# --- Этапы (work_content) -----------------------------------------------


@router.get("/requests/{request_id}/tz/stages", response_model=list[TzStageOut])
async def list_tz_stages(request_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    tz = await _get_tz(db, request_id)
    return [TzStageOut.model_validate(s) for s in sorted(tz.stages, key=lambda s: s.stage_order)]


@router.post("/requests/{request_id}/tz/stages", response_model=TzStageOut, status_code=201)
async def create_tz_stage(request_id: uuid.UUID, body: TzStageCreate, db: AsyncSession = Depends(get_db)):
    tz = await _get_tz(db, request_id, with_relations=False)
    stage = RequestTzStage(tz_id=tz.id, **body.model_dump())
    db.add(stage)
    await db.commit()
    await db.refresh(stage)
    await _recalc_completeness(db, tz)
    return TzStageOut.model_validate(stage)


async def _get_stage(db: AsyncSession, tz_id: uuid.UUID, stage_id: uuid.UUID) -> RequestTzStage:
    stage = await db.get(RequestTzStage, stage_id)
    if stage is None or stage.tz_id != tz_id:
        raise NotFoundError("Этап не найден")
    return stage


@router.patch("/requests/{request_id}/tz/stages/{stage_id}", response_model=TzStageOut)
async def update_tz_stage(request_id: uuid.UUID, stage_id: uuid.UUID, body: TzStageUpdate, db: AsyncSession = Depends(get_db)):
    tz = await _get_tz(db, request_id, with_relations=False)
    stage = await _get_stage(db, tz.id, stage_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(stage, field, value)
    if body.model_dump(exclude_unset=True):
        stage.filled_by = "mixed" if stage.filled_by == "ai" else stage.filled_by
    await db.commit()
    await db.refresh(stage)
    await _recalc_completeness(db, tz)
    return TzStageOut.model_validate(stage)


@router.delete("/requests/{request_id}/tz/stages/{stage_id}", status_code=204)
async def delete_tz_stage(request_id: uuid.UUID, stage_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    tz = await _get_tz(db, request_id, with_relations=False)
    stage = await _get_stage(db, tz.id, stage_id)
    await db.delete(stage)
    await db.commit()
    await _recalc_completeness(db, tz)


# --- Анализ качества (§3.6) ----------------------------------------------


async def _analyze_task(request_id: uuid.UUID):
    async def task(db: AsyncSession) -> dict:
        tz = await _get_tz(db, request_id)
        request = await _get_request(db, request_id)
        template = await db.get(TzTemplate, tz.template_id)
        analysis = await analyze_tz(template, tz, tz.stages, request)

        tz.completeness_pct = analysis["completeness_pct"]
        db.add(
            RequestTzAnalysis(
                tz_id=tz.id,
                completeness_pct=analysis["completeness_pct"],
                risks=analysis["risks"],
                recommendations=analysis["recommendations"],
                block_completeness=analysis["block_completeness"],
            )
        )
        db.add(TzCompletenessLog(tz_id=tz.id, completeness_pct=analysis["completeness_pct"], triggered_by="ai"))
        await db.commit()
        return analysis

    return task


@router.post("/requests/{request_id}/tz/analyze", response_model=JobCreatedOut)
async def analyze_request_tz(request_id: uuid.UUID, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    await _get_tz(db, request_id, with_relations=False)
    job = await create_job(db, "analyze", {"request_id": str(request_id)})
    task = await _analyze_task(request_id)
    background_tasks.add_task(run_job, job.id, task)
    return JobCreatedOut(job_id=job.id)


async def _latest_analysis(db: AsyncSession, request_id: uuid.UUID) -> RequestTzAnalysis:
    tz = await _get_tz(db, request_id, with_relations=False)
    stmt = (
        select(RequestTzAnalysis)
        .where(RequestTzAnalysis.tz_id == tz.id)
        .order_by(RequestTzAnalysis.created_at.desc())
        .limit(1)
    )
    analysis = (await db.execute(stmt)).scalar_one_or_none()
    if analysis is None:
        raise NotFoundError("Анализ ещё не выполнялся, вызовите POST /tz/analyze")
    return analysis


@router.get("/requests/{request_id}/tz/analysis", response_model=AnalysisOut)
async def get_tz_analysis(request_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    analysis = await _latest_analysis(db, request_id)
    return AnalysisOut(
        completeness_pct=analysis.completeness_pct,
        risks=[Risk(**r) for r in analysis.risks],
        recommendations=[Recommendation(**r) for r in analysis.recommendations],
        block_completeness=analysis.block_completeness,
        analyzed_at=analysis.created_at,
    )


@router.get("/requests/{request_id}/tz/completeness", response_model=CompletenessOut)
async def get_tz_completeness(request_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    tz = await _get_tz(db, request_id)
    template = await db.get(TzTemplate, tz.template_id)
    overall, block_completeness = compute_overall_completeness(template, tz.payload)
    return CompletenessOut(completeness_pct=overall, block_completeness=block_completeness)


@router.get("/requests/{request_id}/tz/risks", response_model=list[Risk])
async def get_tz_risks(request_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    analysis = await _latest_analysis(db, request_id)
    return [Risk(**r) for r in analysis.risks]


@router.get("/requests/{request_id}/tz/recommendations", response_model=list[Recommendation])
async def get_tz_recommendations(request_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    analysis = await _latest_analysis(db, request_id)
    return [Recommendation(**r) for r in analysis.recommendations]
