"""ИИ-чат-агент модалки создания заявки (§3.5, §4.2 SPEC).

Правило «ИИ — советник»: агент никогда не применяет изменения сам, а только
формирует `actions`, которые фронт показывает пользователю как pending-предложения.
"""

import json
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatMessage, ChatSession
from app.services.llm_client import DeepSeekLLMClient, get_llm_client
from app.services.semantic_search import (
    search_contractors,
    search_products,
    search_similar_requests,
)
from app.services.template_recommender import recommend_template

CHAT_SYSTEM_PROMPT = (
    "Ты — ИИ-консультант платформы ПРОСТОР. Помогаешь пользователю оформить заявку на "
    "нефтесервисные работы, но НЕ принимаешь решения за него. На основе запроса пользователя: "
    "классифицируй намерение, предложи релевантные продукты и подрядчиков с обоснованием, "
    "покажи аналогичные заявки, порекомендуй тип ТЗ. Всё это — предложения, которые пользователь "
    "явно применит сам. Приводи альтернативы, если пользователь сомневается. Отвечай по-русски, "
    "кратко и по делу."
)


async def _history_messages(db: AsyncSession, session_id) -> list[dict[str, str]]:
    stmt = select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at)
    rows = (await db.execute(stmt)).scalars().all()
    messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
    for m in rows:
        if m.role in ("user", "assistant"):
            messages.append({"role": m.role, "content": m.content})
    return messages


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


async def run_chat_turn(
    db: AsyncSession,
    session: ChatSession,
    user_content: str,
    request_context: dict[str, Any] | None,
    llm: DeepSeekLLMClient | None = None,
) -> AsyncIterator[str]:
    llm = llm or get_llm_client()

    user_msg = ChatMessage(session_id=session.id, role="user", content=user_content)
    db.add(user_msg)
    await db.commit()

    # RAG: подбор продуктов/подрядчиков/аналогов по эмбеддингам (§4.3 SPEC).
    products = await search_products(db, user_content, top_k=3)
    contractors = await search_contractors(db, user_content, top_k=3)
    similar = await search_similar_requests(db, user_content, top_k=3)
    template_rec = await recommend_template(db, user_content, request_context, llm)

    full_text = ""
    messages = await _history_messages(db, session.id)
    if llm.enabled:
        async for delta in llm.chat_stream(messages):
            if delta:
                full_text += delta
                yield _sse({"type": "delta", "content": delta})
    else:
        fallback = _build_fallback_reply(user_content, products, contractors, template_rec)
        for chunk in _chunk_text(fallback):
            full_text += chunk
            yield _sse({"type": "delta", "content": chunk})

    if products:
        yield _sse({"type": "products", "items": products})
    if contractors:
        yield _sse({"type": "contractors", "items": contractors})
    if similar:
        yield _sse({"type": "similar_requests", "items": similar})

    actions: list[dict[str, Any]] = []
    if products:
        top = products[0]
        actions.append(
            {
                "type": "set_field",
                "field": "product_id",
                "value": top["product_id"],
                "confidence": top["score"],
                "justification": top["justification"],
            }
        )
    if contractors:
        top = contractors[0]
        actions.append(
            {
                "type": "set_field",
                "field": "company_id",
                "value": top["company_id"],
                "confidence": top["score"],
                "justification": top["justification"],
            }
        )
    if template_rec.get("template_id"):
        actions.append(
            {
                "type": "suggest_template",
                "template_id": str(template_rec["template_id"]),
                "code": template_rec["code"],
                "confidence": template_rec["confidence"],
                "justification": template_rec["justification"],
            }
        )

    if actions:
        yield _sse({"type": "actions", "actions": actions})

    assistant_msg = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=full_text or "Готово.",
        actions=actions or None,
    )
    db.add(assistant_msg)
    await db.commit()

    yield "data: [DONE]\n\n"


def _chunk_text(text: str, size: int = 24) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)] or [text]


def _build_fallback_reply(
    user_content: str,
    products: list[dict],
    contractors: list[dict],
    template_rec: dict[str, Any],
) -> str:
    """Детерминированный ответ на случай отсутствия ключа LLM (демо-режим)."""
    parts = [f"Разобрал запрос «{user_content}»."]
    if products:
        parts.append(f"Подобрал услугу «{products[0]['product_name']}».")
    if contractors:
        parts.append(f"Рекомендую подрядчика «{contractors[0]['name']}» (рейтинг {contractors[0].get('rating', '-')}).")
    if template_rec.get("name"):
        parts.append(f"Похоже, подойдёт тип ТЗ «{template_rec['name']}».")
    parts.append("Проверьте предложения ниже и примените нужные — я ничего не меняю сам.")
    return " ".join(parts)
