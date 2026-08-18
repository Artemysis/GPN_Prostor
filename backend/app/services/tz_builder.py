import uuid
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RequestTz, RequestTzBlock, RequestTzStage, TzCompletenessLog, TzTemplate, TzTemplateStage
from app.services.llm_client import DeepSeekLLMClient, get_llm_client
from app.services.tz_analyzer import compute_block_completeness, compute_overall_completeness


def _blocks_from_schema(blocks_schema: dict) -> list[dict]:
    return sorted(blocks_schema.get("blocks", []), key=lambda b: b.get("order", 0))


def _stage_date(value: Any) -> date | None:
    if value is None or isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


async def create_tz_from_template(
    db: AsyncSession,
    request_id: uuid.UUID,
    template: TzTemplate,
    prefill: dict[str, Any] | None = None,
) -> RequestTz:
    payload: dict[str, Any] = {}
    tz = RequestTz(request_id=request_id, template_id=template.id, payload=payload)
    db.add(tz)
    await db.flush()

    for block in _blocks_from_schema(template.blocks_schema):
        code = block["code"]
        content = (prefill or {}).get(code, {})
        completeness = compute_block_completeness(block, content) if content else 0
        db.add(
            RequestTzBlock(
                tz_id=tz.id,
                block_code=code,
                block_name=block.get("name", code),
                content=content,
                filled_by="ai" if content else "manual",
                is_complete=completeness >= 100,
                completeness_pct=completeness,
            )
        )
        payload[code] = content

    if prefill and "work_content" in prefill and isinstance(prefill["work_content"], dict):
        stages_data = prefill["work_content"].get("stages", [])
    else:
        template_stages = (
            await db.execute(
                select(TzTemplateStage)
                .where(TzTemplateStage.template_id == template.id)
                .order_by(TzTemplateStage.stage_order)
            )
        ).scalars().all()
        stages_data = [
            {
                "stage_order": s.stage_order,
                "stage_name": s.stage_name,
                "requirements": s.default_requirements,
                "expected_results": s.default_results,
            }
            for s in template_stages
        ]

    for stage in stages_data:
        db.add(
            RequestTzStage(
                tz_id=tz.id,
                stage_order=stage.get("stage_order", 0),
                stage_name=stage.get("stage_name", "Этап"),
                requirements=stage.get("requirements"),
                expected_results=stage.get("expected_results"),
                description=stage.get("description"),
                stage_start_date=_stage_date(stage.get("stage_start_date")),
                stage_end_date=_stage_date(stage.get("stage_end_date")),
                filled_by="ai" if prefill else "manual",
            )
        )

    tz.payload = payload
    overall, _ = compute_overall_completeness(template, payload)
    tz.completeness_pct = overall
    db.add(TzCompletenessLog(tz_id=tz.id, completeness_pct=overall, triggered_by="ai" if prefill else "user"))
    await db.commit()
    await db.refresh(tz)
    return tz


FILL_AI_SYSTEM_PROMPT = (
    "Ты — ИИ-консультант платформы ПРОСТОР. Заполни блок «{block_name}» ТЗ типа «{template_name}» "
    "как черновик на основе контекста заявки. Используй доменные знания нефтегазовой отрасли. "
    "Это предложение, пользователь будет его ревьюить и может отредактировать. "
    "Верни строго JSON-объект с ключами, соответствующими полям схемы блока."
)


def _json_schema_for_block(block_schema: dict) -> dict:
    fields = block_schema.get("fields", [])
    properties = {}
    required = []
    for f in fields:
        field_type = "array" if f.get("type") == "list" else "string"
        prop: dict[str, Any] = {"type": field_type}
        if field_type == "array":
            prop["items"] = {"type": "string"}
        properties[f["key"]] = prop
        if f.get("required"):
            required.append(f["key"])
    return {
        "name": "tz_block",
        "schema": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": True,
        },
    }


async def fill_block_with_ai(
    template: TzTemplate,
    block_code: str,
    block_schema: dict,
    request_context: dict[str, Any],
    other_blocks: dict[str, Any],
    hint: str | None = None,
    llm: DeepSeekLLMClient | None = None,
) -> dict[str, Any]:
    llm = llm or get_llm_client()
    system_prompt = FILL_AI_SYSTEM_PROMPT.format(block_name=block_schema.get("name", block_code), template_name=template.name)
    user_prompt = (
        f"Контекст заявки: {request_context}\n"
        f"Остальные блоки ТЗ: {other_blocks}\n"
        f"Схема блока: {block_schema}\n"
        + (f"Дополнительное пожелание пользователя: {hint}\n" if hint else "")
        + "Верни JSON только с данными по полям этого блока."
    )
    json_schema = _json_schema_for_block(block_schema)
    result = await llm.chat_json(system_prompt, user_prompt, json_schema)
    if not result:
        result = _fallback_block_content(block_schema)
    return result


def _fallback_block_content(block_schema: dict) -> dict[str, Any]:
    """Заглушка на случай недоступности LLM — пустой черновик по схеме полей."""
    content: dict[str, Any] = {}
    for f in block_schema.get("fields", []):
        content[f["key"]] = [] if f.get("type") == "list" else ""
    return content


def find_block_schema(template: TzTemplate, block_code: str) -> dict | None:
    for block in _blocks_from_schema(template.blocks_schema):
        if block["code"] == block_code:
            return block
    return None


STAGES_FILL_SYSTEM_PROMPT = (
    "Ты — ИИ-консультант платформы ПРОСТОР. Предложи недостающие этапы содержания работ "
    "для ТЗ типа «{template_name}» как черновик — пользователь их проверит и добавит вручную. "
    "Не повторяй уже добавленные этапы. Верни строго JSON {{\"stages\": [...]}}."
)


async def fill_stages_with_ai(
    template: TzTemplate,
    template_stages: list[TzTemplateStage],
    request_context: dict[str, Any],
    existing_stage_names: list[str],
    hint: str | None = None,
    llm: DeepSeekLLMClient | None = None,
) -> list[dict[str, Any]]:
    llm = llm or get_llm_client()
    system_prompt = STAGES_FILL_SYSTEM_PROMPT.format(template_name=template.name)
    user_prompt = (
        f"Контекст заявки: {request_context}\n"
        f"Уже добавленные этапы: {existing_stage_names}\n"
        + (f"Пожелание пользователя: {hint}\n" if hint else "")
        + "Верни JSON {\"stages\": [{\"stage_name\": ..., \"requirements\": ..., \"expected_results\": ...}]}."
    )
    json_schema = {
        "name": "tz_stages",
        "schema": {
            "type": "object",
            "properties": {
                "stages": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "stage_name": {"type": "string"},
                            "requirements": {"type": "string"},
                            "expected_results": {"type": "string"},
                        },
                        "required": ["stage_name", "requirements", "expected_results"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["stages"],
            "additionalProperties": False,
        },
    }
    result = await llm.chat_json(system_prompt, user_prompt, json_schema)
    stages = result.get("stages") if result else None
    if not stages:
        stages = [
            {
                "stage_name": s.stage_name,
                "requirements": s.default_requirements or "",
                "expected_results": s.default_results or "",
            }
            for s in template_stages
            if s.stage_name not in existing_stage_names
        ]
    return stages


TZ_PREFILL_SYSTEM_PROMPT = (
    "Ты — ИИ-консультант платформы ПРОСТОР. Заполни черновик технического задания типа «{template_name}» "
    "по контексту заявки. Используй domain-знания нефтегазовой отрасли: формулируй конкретно и профессионально. "
    "Это предложение-черновик: пользователь проверит и отредактирует. Отвечай строго JSON."
)


def _prefill_json_schema(blocks: list[dict]) -> dict:
    properties: dict[str, Any] = {}
    for block in blocks:
        code = block["code"]
        if block.get("is_stages_block"):
            properties[code] = {
                "type": "object",
                "properties": {
                    "stages": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "stage_name": {"type": "string"},
                                "requirements": {"type": "string"},
                                "expected_results": {"type": "string"},
                            },
                            "required": ["stage_name", "requirements", "expected_results"],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["stages"],
                "additionalProperties": False,
            }
        else:
            field_props: dict[str, Any] = {}
            for f in block.get("fields", []):
                if f.get("type") == "list":
                    field_props[f["key"]] = {"type": "array", "items": {"type": "string"}}
                else:
                    field_props[f["key"]] = {"type": "string"}
            properties[code] = {
                "type": "object",
                "properties": field_props,
                "required": list(field_props.keys()),
                "additionalProperties": False,
            }
    properties["estimated_cost_rub"] = {"type": "number"}
    return {
        "name": "tz_prefill",
        "schema": {
            "type": "object",
            "properties": properties,
            "required": list(properties.keys()),
            "additionalProperties": False,
        },
    }


def _sanitize_prefill(blocks: list[dict], raw: dict[str, Any] | None) -> dict[str, Any]:
    """Приводит ответ LLM к схеме блоков: отбрасывает пустое и неверное."""
    result: dict[str, Any] = {}
    if not isinstance(raw, dict):
        return result
    for block in blocks:
        code = block["code"]
        value = raw.get(code)
        if not isinstance(value, dict):
            continue
        if block.get("is_stages_block"):
            stages: list[dict[str, Any]] = []
            for s in value.get("stages") or []:
                if not isinstance(s, dict):
                    continue
                name = str(s.get("stage_name") or "").strip()
                if not name:
                    continue
                stages.append(
                    {
                        "stage_order": len(stages) + 1,
                        "stage_name": name,
                        "requirements": str(s.get("requirements") or "").strip() or None,
                        "expected_results": str(s.get("expected_results") or "").strip() or None,
                    }
                )
            if stages:
                result[code] = {"stages": stages}
        else:
            content: dict[str, Any] = {}
            for f in block.get("fields", []):
                v = value.get(f["key"])
                if v is None:
                    continue
                if f.get("type") == "list":
                    if isinstance(v, list):
                        items = [str(x).strip() for x in v if str(x).strip()]
                        if items:
                            content[f["key"]] = items
                else:
                    text = str(v).strip()
                    if text:
                        content[f["key"]] = text
            if content:
                result[code] = content
    return result


async def generate_tz_prefill(
    template: TzTemplate,
    request_context: dict[str, Any],
    llm: DeepSeekLLMClient | None = None,
) -> tuple[dict[str, Any], float | None]:
    """Черновик всех блоков ТЗ + оценка стоимости одним LLM-вызовом.

    Оценка стоимости выполняется в конце — на основе сгенерированного содержания ТЗ.
    При недоступности LLM — пустой prefill без оценки.
    """
    llm = llm or get_llm_client()
    blocks = _blocks_from_schema(template.blocks_schema)
    if not llm.enabled:
        return {}, None

    system_prompt = TZ_PREFILL_SYSTEM_PROMPT.format(template_name=template.name)
    user_prompt = (
        f"Контекст заявки: {request_context}\n"
        f"Структура блоков ТЗ: {[(b['code'], b.get('name')) for b in blocks]}\n"
        "Верни JSON, где ключ верхнего уровня — код блока, значение — объект с полями блока "
        "(для блока содержания работ — ключ stages с массивом этапов). "
        "Дополнительно оцени суммарную стоимость работ в рублях по содержанию ТЗ — "
        "ключ estimated_cost_rub."
    )
    raw = await llm.chat_json(system_prompt, user_prompt, _prefill_json_schema(blocks))
    estimated_cost = None
    if isinstance(raw, dict):
        try:
            value = float(raw.get("estimated_cost_rub") or 0)
            if value > 0:
                estimated_cost = value
        except (TypeError, ValueError):
            estimated_cost = None
    return _sanitize_prefill(blocks, raw), estimated_cost
