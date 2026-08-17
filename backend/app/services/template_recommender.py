from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TzTemplate
from app.services.llm_client import DeepSeekLLMClient, get_llm_client
from app.services.semantic_search import search_tz_templates

RECOMMEND_SYSTEM_PROMPT = (
    "Выбери подходящий тип ТЗ из списка под запрос пользователя. Это рекомендация — "
    "пользователь подтвердит выбор сам, ничего не применяется автоматически. "
    "Верни JSON {template_code, confidence, justification, suggested_fields}."
)


async def recommend_template(
    db: AsyncSession,
    prompt: str,
    request_context: dict[str, Any] | None = None,
    llm: DeepSeekLLMClient | None = None,
) -> dict[str, Any]:
    llm = llm or get_llm_client()
    templates = (await db.execute(select(TzTemplate).where(TzTemplate.is_active.is_(True)))).scalars().all()
    if not templates:
        return {"template_id": None, "code": None, "name": None, "confidence": 0.0, "justification": "Нет доступных шаблонов", "suggested_fields": {}}

    catalog = [{"code": t.code, "name": t.name, "description": t.description} for t in templates]
    result: dict[str, Any] = {}
    if llm.enabled:
        json_schema = {
            "name": "template_recommendation",
            "schema": {
                "type": "object",
                "properties": {
                    "template_code": {"type": "string"},
                    "confidence": {"type": "number"},
                    "justification": {"type": "string"},
                    "suggested_fields": {"type": "object"},
                },
                "required": ["template_code", "confidence", "justification"],
            },
        }
        user_prompt = f"Каталог шаблонов: {catalog}\nЗапрос пользователя: {prompt}\nКонтекст: {request_context or {}}"
        result = await llm.chat_json(RECOMMEND_SYSTEM_PROMPT, user_prompt, json_schema)

    template: TzTemplate | None = None
    confidence = float(result.get("confidence", 0)) if result else 0.0
    if result.get("template_code"):
        template = next((t for t in templates if t.code == result["template_code"]), None)

    if template is None:
        # Фолбэк без LLM/при неудачном ответе — семантический поиск по эмбеддингам шаблонов.
        hits = await search_tz_templates(db, prompt, top_k=1)
        if hits:
            template = next((t for t in templates if str(t.id) == hits[0]["template_id"]), None)
            confidence = hits[0]["score"]
        if template is None:
            template = templates[0]
            confidence = 0.3

    justification = result.get("justification") or f"Наиболее подходящий тип ТЗ по запросу «{prompt}»"
    return {
        "template_id": template.id,
        "code": template.code,
        "name": template.name,
        "confidence": round(confidence, 2),
        "justification": justification,
        "suggested_fields": result.get("suggested_fields", {}),
    }
