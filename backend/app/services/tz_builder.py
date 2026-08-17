import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RequestTz, RequestTzBlock, RequestTzStage, TzTemplate, TzTemplateStage
from app.services.llm_client import DeepSeekLLMClient, get_llm_client


def _blocks_from_schema(blocks_schema: dict) -> list[dict]:
    return sorted(blocks_schema.get("blocks", []), key=lambda b: b.get("order", 0))


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
        filled_by = "ai" if content else "manual"
        db.add(
            RequestTzBlock(
                tz_id=tz.id,
                block_code=code,
                block_name=block.get("name", code),
                content=content,
                filled_by=filled_by,
                is_complete=False,
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
                filled_by="ai" if prefill else "manual",
            )
        )

    tz.payload = payload
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
