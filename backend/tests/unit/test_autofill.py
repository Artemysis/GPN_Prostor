"""Unit-тесты применения actions чата к заявке (§3.5.5-6 SPEC).

Правило «ИИ — советник»: применяются только явные set_field по белому списку полей.
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models import ChatMessage, ChatSession, Product, Request, RequestTz, User
from app.services.autofill import apply_actions, autofill_from_session

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

    async def test_suggest_template_skipped_when_tz_exists(self, db_session, make_tz_template):
        # Arrange
        template = await make_tz_template()
        request = await _make_request(db_session)
        session = ChatSession(request_id=request.id, user_id=request.user_id)
        db_session.add(session)
        await db_session.commit()
        await autofill_from_session(
            db_session, session, request, [{"type": "suggest_template", "template_id": str(template.id)}]
        )
        actions = [{"type": "suggest_template", "template_id": str(template.id)}]

        # Act
        result = await autofill_from_session(db_session, session, request, actions)

        # Assert
        assert result["tz_diff"] == {}  # повторное применение не пересоздаёт ТЗ

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
