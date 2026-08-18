"""Unit-тесты конструктора ТЗ: генерация из шаблона и ИИ-заполнение блоков."""

from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models import Request, RequestTz, RequestTzStage, User
from app.services.tz_builder import (
    _json_schema_for_block,
    create_tz_from_template,
    fill_block_with_ai,
    find_block_schema,
)
from tests.conftest import FakeLLMClient

pytestmark = pytest.mark.unit


class TestFindBlockSchema:
    async def test_returns_block_schema(self, make_tz_template):
        # Arrange
        template = await make_tz_template()

        # Act
        schema = find_block_schema(template, "scope")

        # Assert
        assert schema is not None
        assert schema["name"] == "Периметр работ"

    async def test_unknown_code_returns_none(self, make_tz_template):
        # Arrange
        template = await make_tz_template()

        # Act
        schema = find_block_schema(template, "no_such_block")

        # Assert
        assert schema is None


class TestJsonSchemaForBlock:
    def test_list_field_becomes_string_array(self):
        # Arrange
        block_schema = {"fields": [
            {"key": "tasks", "type": "list", "required": True},
            {"key": "note", "type": "text", "required": False},
        ]}

        # Act
        result = _json_schema_for_block(block_schema)

        # Assert
        props = result["schema"]["properties"]
        assert props["tasks"] == {"type": "array", "items": {"type": "string"}}
        assert props["note"] == {"type": "string"}
        assert result["schema"]["required"] == ["tasks"]


class TestFillBlockWithAi:
    async def test_returns_llm_json_as_content(self, make_tz_template):
        # Arrange
        template = await make_tz_template()
        llm = FakeLLMClient()
        llm.json_responses.append({"goal_text": "Цель от ИИ", "tasks": ["Задача 1"]})

        # Act
        content = await fill_block_with_ai(
            template=template,
            block_code="goals",
            block_schema=find_block_schema(template, "goals"),
            request_context={"title": "Заявка QA"},
            other_blocks={},
            llm=llm,
        )

        # Assert
        assert content == {"goal_text": "Цель от ИИ", "tasks": ["Задача 1"]}
        assert llm.calls[0]["method"] == "chat_json"
        assert "goals" not in llm.calls[0]["system"]  # системный промпт про блок, не про код

    async def test_empty_llm_answer_falls_back_to_schema_skeleton(self, make_tz_template):
        # Arrange
        template = await make_tz_template()
        llm = FakeLLMClient()  # json_responses пуст -> chat_json вернёт {}

        # Act
        content = await fill_block_with_ai(
            template=template,
            block_code="goals",
            block_schema=find_block_schema(template, "goals"),
            request_context={},
            other_blocks={},
            llm=llm,
        )

        # Assert
        assert content == {"goal_text": "", "tasks": []}


class TestCreateTzFromTemplate:
    async def test_creates_all_blocks_and_stages(self, db_session, make_tz_template):
        # Arrange
        template = await make_tz_template()
        user = User(username=f"qa_builder_{id(template):x}")
        db_session.add(user)
        await db_session.flush()
        request = Request(user_id=user.id, title="Заявка для ТЗ")
        db_session.add(request)
        await db_session.flush()

        # Act
        tz = await create_tz_from_template(db_session, request.id, template)
        tz = (
            await db_session.execute(
                select(RequestTz)
                .where(RequestTz.request_id == request.id)
                .options(selectinload(RequestTz.blocks), selectinload(RequestTz.stages))
            )
        ).scalar_one()

        # Assert
        assert tz.request_id == request.id
        assert len(tz.blocks) == 8
        codes_by_order = [b["code"] for b in sorted(template.blocks_schema["blocks"], key=lambda x: x["order"])]
        assert sorted((b.block_code for b in tz.blocks), key=codes_by_order.index) == codes_by_order  # порядок по order
        assert all(b.filled_by == "manual" and not b.is_complete for b in tz.blocks)
        stage_names = [s.stage_name for s in tz.stages]
        assert "Формирование базы данных" in stage_names

    async def test_prefill_marks_blocks_as_ai(self, db_session, make_tz_template):
        # Arrange
        template = await make_tz_template()
        user = User(username=f"qa_prefill_{id(template):x}")
        db_session.add(user)
        await db_session.flush()
        request = Request(user_id=user.id)
        db_session.add(request)
        await db_session.flush()
        prefill: dict[str, Any] = {"goals": {"goal_text": "Готовая цель"}}

        # Act
        tz = await create_tz_from_template(db_session, request.id, template, prefill=prefill)
        tz = (
            await db_session.execute(
                select(RequestTz).where(RequestTz.request_id == request.id).options(selectinload(RequestTz.blocks))
            )
        ).scalar_one()

        # Assert
        goals = next(b for b in tz.blocks if b.block_code == "goals")
        scope = next(b for b in tz.blocks if b.block_code == "scope")
        assert goals.filled_by == "ai"
        assert goals.content == {"goal_text": "Готовая цель"}
        assert scope.filled_by == "manual"

    async def test_prefill_stages_override_template_stages(self, db_session, make_tz_template):
        # Arrange
        template = await make_tz_template()
        user = User(username=f"qa_stages_{id(template):x}")
        db_session.add(user)
        await db_session.flush()
        request = Request(user_id=user.id)
        db_session.add(request)
        await db_session.flush()
        prefill = {
            "work_content": {
                "stages": [
                    {
                        "stage_order": 1,
                        "stage_name": "Пользовательский этап",
                        "requirements": "Требование",
                        "expected_results": "Результат",
                    }
                ]
            }
        }

        # Act
        tz = await create_tz_from_template(db_session, request.id, template, prefill=prefill)
        tz = (
            await db_session.execute(
                select(RequestTz).where(RequestTz.request_id == request.id).options(selectinload(RequestTz.stages))
            )
        ).scalar_one()

        # Assert
        assert len(tz.stages) == 1
        stage: RequestTzStage = tz.stages[0]
        assert stage.stage_name == "Пользовательский этап"
        assert stage.filled_by == "ai"
