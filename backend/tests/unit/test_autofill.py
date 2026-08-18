"""Unit-тесты применения actions чата к заявке (§3.5.5-6 SPEC).

Правило «ИИ — советник»: применяются только явные set_field по белому списку полей.
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models import ChatMessage, ChatSession, Product, Request, RequestTz, RequestTzBlock, User
from app.services.autofill import apply_actions, autofill_from_session
from app.services.tz_builder import create_tz_from_template
from tests.conftest import FakeLLMClient

pytestmark = pytest.mark.unit


async def _make_request(db_session, **attrs) -> Request:
    user = User(username=f"qa_af_{uuid.uuid4().hex[:8]}")
    db_session.add(user)
    await db_session.flush()
    request = Request(user_id=user.id, **attrs)
    db_session.add(request)
    await db_session.commit()
    await db_session.refresh(request)
    return request


async def _make_product(db_session) -> Product:
    product = Product(product_id=f"P-{uuid.uuid4().hex[:8]}", product_name="Услуга QA")
    db_session.add(product)
    await db_session.commit()
    return product


class TestApplyActions:
    async def test_whitelisted_field_updated_with_metadata(self, db_session):
        # Arrange
        request = await _make_request(db_session, title="Старый заголовок")
        actions = [{"type": "set_field", "field": "title", "value": "Новый заголовок от ИИ"}]

        # Act
        applied = await apply_actions(db_session, request, actions)

        # Assert
        assert applied == [{"field": "title", "old": "Старый заголовок", "new": "Новый заголовок от ИИ"}]
        assert request.title == "Новый заголовок от ИИ"
        assert request.request_metadata["filled_by"]["title"] == "ai"

    async def test_non_whitelisted_field_ignored(self, db_session):
        # Arrange
        request = await _make_request(db_session, status="draft")
        actions = [{"type": "set_field", "field": "status", "value": "submitted"}]  # нет в REQUEST_FIELDS

        # Act
        applied = await apply_actions(db_session, request, actions)

        # Assert
        assert applied == []
        assert request.status == "draft"

    async def test_unknown_action_type_skipped(self, db_session):
        # Arrange
        request = await _make_request(db_session, title="Осталось")
        actions = [{"type": "delete_request", "value": None}]

        # Act
        applied = await apply_actions(db_session, request, actions)

        # Assert
        assert applied == []
        assert request.title == "Осталось"


class TestAutofillFromSession:
    async def test_suggest_template_creates_tz_when_missing(self, db_session, make_tz_template):
        # Arrange
        template = await make_tz_template()
        product = await _make_product(db_session)
        request = await _make_request(db_session)
        session = ChatSession(request_id=request.id, user_id=request.user_id)
        db_session.add(session)
        await db_session.commit()
        actions = [
            {"type": "set_field", "field": "product_id", "value": product.product_id},
            {"type": "suggest_template", "template_id": str(template.id), "code": template.code},
        ]

        # Act
        result = await autofill_from_session(db_session, session, request, actions)

        # Assert
        assert result["request_diff"] == {"product_id": product.product_id}
        assert result["tz_diff"]["template_id"] == str(template.id)
        tz = (await db_session.execute(select(RequestTz).where(RequestTz.request_id == request.id))).scalar_one()
        assert tz.template_id == template.id

    async def test_suggest_template_marks_existing_empty_tz_without_llm(self, db_session, make_tz_template):
        # Arrange: первое применение создало пустое ТЗ (LLM выключен) — второе не пересоздаёт его
        template = await make_tz_template()
        request = await _make_request(db_session)
        session = ChatSession(request_id=request.id, user_id=request.user_id)
        db_session.add(session)
        await db_session.commit()
        await autofill_from_session(
            db_session, session, request, [{"type": "suggest_template", "template_id": str(template.id)}]
        )
        tz_before = (await db_session.execute(select(RequestTz).where(RequestTz.request_id == request.id))).scalar_one()
        actions = [{"type": "suggest_template", "template_id": str(template.id)}]

        # Act
        result = await autofill_from_session(db_session, session, request, actions)

        # Assert: ТЗ то же самое, без ИИ-черновика, но явно помечено в tz_diff
        tz_after = (await db_session.execute(select(RequestTz).where(RequestTz.request_id == request.id))).scalar_one()
        assert tz_after.id == tz_before.id
        assert result["tz_diff"]["tz_id"] == str(tz_before.id)
        assert result["tz_diff"]["filled_existing"] is True
        assert result["tz_diff"]["ai_draft"] is False

    async def test_apply_fills_manually_created_empty_tz(self, db_session, make_tz_template, monkeypatch):
        # Arrange: пользователь создал ТЗ кликом по карточке шаблона (все блоки пустые),
        # затем в чате нажал «Применить и создать ТЗ»
        template = await make_tz_template()
        request = await _make_request(db_session, title="Оценка запасов")
        session = ChatSession(request_id=request.id, user_id=request.user_id)
        db_session.add(session)
        await db_session.commit()
        await create_tz_from_template(db_session, request.id, template)

        fake_llm = FakeLLMClient()
        fake_llm.json_responses.append(
            {
                "goals": {"goal_text": "Построить 3D-геомодель", "tasks": ["Анализ данных"]},
                "work_content": {"stages": [{"stage_name": "Этап от ИИ", "requirements": "Требование", "expected_results": "Результат"}]},
                "estimated_cost_rub": 1500000,
            }
        )
        monkeypatch.setattr("app.services.llm_client.get_llm_client", lambda: fake_llm)
        actions = [{"type": "suggest_template", "template_id": str(template.id)}]

        # Act
        result = await autofill_from_session(db_session, session, request, actions)

        # Assert: то же ТЗ заполнено ИИ-черновиком
        tz = (
            await db_session.execute(
                select(RequestTz)
                .where(RequestTz.request_id == request.id)
                .options(selectinload(RequestTz.blocks), selectinload(RequestTz.stages))
            )
        ).scalar_one()
        goals = next(b for b in tz.blocks if b.block_code == "goals")
        assert goals.content == {"goal_text": "Построить 3D-геомодель", "tasks": ["Анализ данных"]}
        assert goals.filled_by == "ai"
        assert [s.stage_name for s in tz.stages] == ["Этап от ИИ"]
        assert request.cost_total == 1500000.0
        assert result["tz_diff"]["filled_existing"] is True
        assert result["tz_diff"]["ai_draft"] is True
        assert result["tz_diff"]["completeness_pct"] > 0

    async def test_apply_does_not_touch_filled_tz(self, db_session, make_tz_template, monkeypatch):
        # Arrange: ТЗ с заполненным вручную блоком — применение не перезаписывает его
        template = await make_tz_template()
        request = await _make_request(db_session)
        session = ChatSession(request_id=request.id, user_id=request.user_id)
        db_session.add(session)
        await db_session.commit()
        await create_tz_from_template(db_session, request.id, template)
        tz = (
            await db_session.execute(
                select(RequestTz).where(RequestTz.request_id == request.id).options(selectinload(RequestTz.blocks))
            )
        ).scalar_one()
        goals_row = next(b for b in tz.blocks if b.block_code == "goals")
        goals_row.content = {"goal_text": "Ручная цель"}
        await db_session.commit()

        fake_llm = FakeLLMClient()
        monkeypatch.setattr("app.services.llm_client.get_llm_client", lambda: fake_llm)
        actions = [{"type": "suggest_template", "template_id": str(template.id)}]

        # Act
        result = await autofill_from_session(db_session, session, request, actions)

        # Assert
        assert result["tz_diff"] == {}
        await db_session.refresh(goals_row)
        assert goals_row.content == {"goal_text": "Ручная цель"}
        assert fake_llm.calls == []  # LLM даже не вызывается

    async def test_none_actions_uses_last_assistant_message(self, db_session):
        # Arrange
        request = await _make_request(db_session, title="Черновик")
        session = ChatSession(request_id=request.id, user_id=request.user_id)
        db_session.add(session)
        await db_session.flush()
        db_session.add(
            ChatMessage(
                session_id=session.id,
                role="assistant",
                content="Предлагаю обновить заголовок",
                actions=[{"type": "set_field", "field": "title", "value": "Заголовок из чата"}],
            )
        )
        await db_session.commit()
        session = (
            await db_session.execute(
                select(ChatSession).where(ChatSession.id == session.id).options(selectinload(ChatSession.messages))
            )
        ).scalar_one()

        # Act
        result = await autofill_from_session(db_session, session, request, None)

        # Assert
        assert result["applied"][0]["field"] == "title"
        assert request.title == "Заголовок из чата"
