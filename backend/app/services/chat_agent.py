"""ИИ-чат-агент модалки создания заявки (§3.5, §4.2 SPEC).

Правило «ИИ — советник»: агент никогда не применяет изменения сам, а только
формирует `actions`, которые фронт показывает пользователю как pending-предложения.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatMessage, ChatSession, Contract, ContractProduct
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

HEADER_DRAFT_SYSTEM_PROMPT = (
    "Ты — помощник платформы ПРОСТОР. Составь черновик шапки заявки на нефтесервисные работы "
    "по описанию задачи пользователя. Название — краткое и конкретное (до 90 символов). "
    "Описание — 2-3 предложения: цель, объект, состав работ. Даты — реалистичные сроки для "
    "подобных работ (ISO, ГГГГ-ММ-ДД, начало не раньше чем через 2 недели от сегодняшней). "
    "Это черновик: пользователь проверит и исправит. Отвечай строго JSON."
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

    # 1) Текст ответа стримится сразу — подбор/рекомендации не должны задерживать первый токен.
    full_text = ""
    messages = await _history_messages(db, session.id)
    if llm.enabled:
        async for delta in llm.chat_stream(messages):
            if delta:
                full_text += delta
                yield _sse({"type": "delta", "content": delta})
    else:
        products = await search_products(db, user_content, top_k=3)
        contractors = await search_contractors(db, user_content, top_k=3)
        template_rec = await recommend_template(db, user_content, request_context, llm)
        fallback = _build_fallback_reply(user_content, products, contractors, template_rec)
        for chunk in _chunk_text(fallback):
            full_text += chunk
            yield _sse({"type": "delta", "content": chunk})

    # 2) RAG и рекомендации — после текста, тяжёлые LLM-вызовы параллельно.
    if llm.enabled:
        products, contractors, similar = await asyncio.gather(
            search_products(db, user_content, top_k=3),
            search_contractors(db, user_content, top_k=3),
            search_similar_requests(db, user_content, top_k=3),
        )
        template_rec, header_draft = await asyncio.gather(
            recommend_template(db, user_content, request_context, llm),
            _draft_header_fields(llm, user_content, products, contractors, None),
        )
    else:
        similar = await search_similar_requests(db, user_content, top_k=3)
        header_draft = await _draft_header_fields(llm, user_content, products, contractors, template_rec)

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
        contract_id = await _pick_contract(db, top["company_id"], products[0]["product_id"] if products else None)
        if contract_id:
            actions.append(
                {
                    "type": "set_field",
                    "field": "contract_id",
                    "value": contract_id,
                    "confidence": 0.8,
                    "justification": "Договор рекомендованного подрядчика, покрывающий выбранную услугу",
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

    # header_draft уже вычислен выше (в gather при llm.enabled или в fallback-ветке) —
    # повторный вызов лишь дублировал LLM-запрос на каждый ход чата.
    for field, value, confidence, why in header_draft:
        if request_context and request_context.get(field):
            continue  # не перезаписываем то, что пользователь уже заполнил
        actions.append(
            {
                "type": "set_field",
                "field": field,
                "value": value,
                "confidence": confidence,
                "justification": why,
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


async def _pick_contract(db: AsyncSession, company_id: str, product_id: str | None) -> str | None:
    """Договор подрядчика, покрывающий продукт; иначе любой договор подрядчика."""
    stmt = (
        select(Contract.contract_id)
        .join(ContractProduct, ContractProduct.contract_id == Contract.contract_id)
        .where(Contract.company_id == company_id)
    )
    if product_id:
        covering = stmt.where(ContractProduct.product_id == product_id).limit(1)
        row = (await db.execute(covering)).scalar_one_or_none()
        if row:
            return row
    row = (await db.execute(stmt.limit(1))).scalar_one_or_none()
    return row


def _valid_iso_date(value: Any) -> str | None:
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except (TypeError, ValueError):
        return None


async def _draft_header_fields(
    llm: DeepSeekLLMClient,
    user_content: str,
    products: list[dict],
    contractors: list[dict],
    template_rec: dict[str, Any],
) -> list[tuple[str, Any, float, str]]:
    """Черновик текстовых полей шапки (название/описание/сроки) — как предложения."""
    today = date.today()
    drafts: list[tuple[str, Any, float, str]] = []

    title = description = None
    date_start = (today + timedelta(days=30)).isoformat()
    date_end = (today + timedelta(days=395)).isoformat()

    if llm.enabled:
        schema = {
            "name": "request_header_draft",
            "schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "date_start": {"type": "string"},
                    "date_end": {"type": "string"},
                },
                "required": ["title", "description", "date_start", "date_end"],
            },
        }
        user_prompt = (
            f"Запрос пользователя: {user_content}\n"
            f"Подобранная услуга: {products[0]['product_name'] if products else 'не определена'}\n"
            f"Рекомендованный подрядчик: {contractors[0]['name'] if contractors else 'не определён'}\n"
            f"Сегодня: {today.isoformat()}\n"
            "Верни JSON с черновиком шапки заявки."
        )
        result = await llm.chat_json(HEADER_DRAFT_SYSTEM_PROMPT, user_prompt, schema)
        if result.get("title"):
            title = str(result["title"]).strip()[:200]
        if result.get("description"):
            description = str(result["description"]).strip()
        date_start = _valid_iso_date(result.get("date_start")) or date_start
        date_end = _valid_iso_date(result.get("date_end")) or date_end

    if not title:
        title = user_content.strip()[:90] or "Черновик заявки"
    if not description:
        description = user_content.strip()

    if date_end < date_start:
        date_end = date_start

    drafts.append(("title", title, 0.7, "Сформулировано ИИ по описанию задачи — проверьте формулировку"))
    drafts.append(("description", description, 0.6, "Черновик описания от ИИ"))
    drafts.append(("date_start", date_start, 0.5, "Предложенный срок начала работ"))
    drafts.append(("date_end", date_end, 0.5, "Предложенный срок окончания работ"))
    return drafts
