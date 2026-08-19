"""LLM-эвал рекомендации типа ТЗ (`recommend_template`, §3.2.2.5 SPEC)."""

import pytest
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, SingleTurnParams

from app.services.template_recommender import recommend_template
from tests.evals.conftest import requires_real_llm

pytestmark = [pytest.mark.eval, requires_real_llm]


@pytest.mark.asyncio
async def test_recommends_geology_template_for_3d_geomodel_prompt(db_session, make_tz_template, judge_model):
    await make_tz_template(
        name="Концепт геологии",
        code="concept_geology",
        description="Оценка запасов, построение геологических моделей объекта разработки",
    )
    await make_tz_template(
        name="Концепт обустройства",
        code="concept_facilities",
        description="Проектирование объектов наземного обустройства месторождения",
    )

    prompt = "Нужно оценить запасы по объекту и построить 3D-геомодель"
    result = await recommend_template(db_session, prompt)

    assert result["code"] == "concept_geology", f"Ожидали concept_geology, получили {result}"
    assert result["justification"]

    justification_quality = GEval(
        name="ObosnovanieRekomendatsii",
        criteria=(
            "Обоснование (actual_output) должно быть релевантно запросу пользователя (input) и выбранному "
            "шаблону ТЗ из контекста — не противоречить им и не быть пустой отпиской не по теме. Достаточно "
            "краткого, но верного по сути указания на совпадение (например, упоминания оценки запасов и/или "
            "геомодели/геологии) — не требуется развёрнутое многословное объяснение."
        ),
        evaluation_params=[
            SingleTurnParams.INPUT,
            SingleTurnParams.ACTUAL_OUTPUT,
            SingleTurnParams.CONTEXT,
        ],
        model=judge_model,
        threshold=0.5,
    )
    test_case = LLMTestCase(
        input=prompt,
        actual_output=result["justification"],
        context=["Выбранный шаблон: Концепт геологии — оценка запасов, построение геологических моделей объекта."],
    )
    assert_test(test_case, [justification_quality])
