"""LLM-эвал заполнения блока ТЗ («Заполнить ИИ», `fill_block_with_ai`, §4.2.2 SPEC)."""

import pytest
from deepeval import assert_test
from deepeval.metrics import FaithfulnessMetric
from deepeval.test_case import LLMTestCase

from app.services.tz_builder import fill_block_with_ai
from tests.evals.conftest import requires_real_llm

pytestmark = [pytest.mark.eval, requires_real_llm]


@pytest.mark.asyncio
async def test_goals_block_stays_grounded_in_request_context(make_tz_template, judge_model):
    template = await make_tz_template(name="Концепт геологии")
    block_schema = {
        "code": "goals",
        "name": "Цели и задачи работ",
        "fields": [
            {"key": "goal_text", "type": "text", "label": "Цель", "required": True},
            {"key": "tasks", "type": "list", "label": "Задачи", "required": True},
        ],
    }
    request_context = {
        "title": "Оценка запасов Ваньгаяхинского месторождения",
        "description": "Актуализация запасов и построение 3D-геологической модели пласта",
    }

    content = await fill_block_with_ai(
        template=template,
        block_code="goals",
        block_schema=block_schema,
        request_context=request_context,
        other_blocks={},
    )

    assert content.get("goal_text")
    assert content.get("tasks")

    actual_output = f"Цель: {content.get('goal_text')}\nЗадачи: {'; '.join(content.get('tasks') or [])}"

    faithfulness = FaithfulnessMetric(threshold=0.6, model=judge_model)
    test_case = LLMTestCase(
        input="Сгенерируй блок «Цели и задачи работ» по контексту заявки",
        actual_output=actual_output,
        retrieval_context=[
            f"Название заявки: {request_context['title']}",
            f"Описание заявки: {request_context['description']}",
        ],
    )
    assert_test(test_case, [faithfulness])
