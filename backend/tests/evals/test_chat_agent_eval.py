"""LLM-эвал ИИ-чата модалки (`run_chat_turn`, §3.5/§4.2.1 SPEC).

Проверяет и содержательное качество ответа (GEval), и правило «ИИ —
советник» (§0 SPEC): ответ агента — предложения с обоснованием, а не
автоприменённые изменения.
"""

import json

import pytest
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, SingleTurnParams

from app.db.models import ChatSession
from app.services.chat_agent import run_chat_turn
from tests.evals.conftest import requires_real_llm

pytestmark = [pytest.mark.eval, requires_real_llm]


async def _collect_turn(db_session, session, prompt):
    full_text = ""
    actions: list[dict] = []
    async for event in run_chat_turn(db_session, session, prompt, request_context={}):
        if not event.startswith("data: ") or event.strip() == "data: [DONE]":
            continue
        payload = json.loads(event[len("data: ") :])
        if payload.get("type") == "delta":
            full_text += payload["content"]
        elif payload.get("type") == "actions":
            actions = payload["actions"]
    return full_text, actions


@pytest.mark.asyncio
async def test_chat_reply_is_advisory_not_autopilot(db_session, test_user, seed_search_corpus, judge_model):
    session = ChatSession(user_id=test_user.id)
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    full_text, actions = await _collect_turn(
        db_session, session, "Нужен подрядчик для гидравлического разрыва пласта, подбери варианты"
    )

    assert full_text.strip(), "Агент должен вернуть текстовый ответ"

    # Структурная проверка правила «ИИ — советник» (§0 SPEC): каждое предложение
    # изменить поле — это action с обоснованием, а не примененное значение.
    for action in actions:
        if action.get("type") == "set_field":
            assert "confidence" in action and "justification" in action, (
                f"action без обоснования нарушает правило «ИИ — советник»: {action}"
            )

    tone = GEval(
        name="SovetnikNeAvtopilot",
        criteria=(
            "Ответ ассистента (actual_output) на запрос пользователя (input) должен звучать как "
            "консультация с предложениями и обоснованием, а не как утверждение о том, что что-то уже "
            "сделано/применено/сохранено без участия пользователя."
        ),
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
        model=judge_model,
        threshold=0.6,
    )
    test_case = LLMTestCase(
        input="Нужен подрядчик для гидравлического разрыва пласта, подбери варианты",
        actual_output=full_text,
    )
    assert_test(test_case, [tone])
