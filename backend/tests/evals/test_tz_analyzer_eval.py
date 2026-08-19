"""LLM-эвал анализа качества ТЗ (`analyze_tz`, §3.6/§10 SPEC).

Сценарий — ключевой пример из §0 SPEC: тип «Концепт геологии» + построение
3D-геомодели без этапа подготовки исходных данных, объект работ не указан.
"""

import uuid

import pytest
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, SingleTurnParams

from app.db.models import RequestTz
from app.services.tz_analyzer import analyze_tz
from tests.evals.conftest import requires_real_llm

pytestmark = [pytest.mark.eval, requires_real_llm]


@pytest.mark.asyncio
async def test_analysis_flags_3d_geomodel_without_prep_stage(db_session, make_tz_template, test_user, judge_model):
    from app.db.models import Request

    template = await make_tz_template(name="Концепт геологии")
    request = Request(
        number=f"QA-{uuid.uuid4().hex[:8]}",
        user_id=test_user.id,
        title="Оценка запасов и построение 3D-геомодели",
        description="Актуализация запасов по объекту, построение 3D-геологической модели",
    )
    db_session.add(request)
    await db_session.flush()

    tz = RequestTz(
        request_id=request.id,
        template_id=template.id,
        payload={
            "goals": {"goal_text": "Актуализация запасов", "tasks": ["Построить 3D-геомодель"]},
            "scope": {"location": "", "field_name": ""},
            "work_content": {"stages": [{"stage_order": 1, "stage_name": "Построение 3D-геологической модели"}]},
        },
    )
    db_session.add(tz)
    await db_session.commit()
    await db_session.refresh(tz)

    result = await analyze_tz(template=template, tz=tz, stages=[], request=request)

    assert result["risks"], "Анализ должен найти хотя бы один риск для заведомо неполного ТЗ"
    risks_text = "\n".join(f"- [{r.get('severity')}] {r.get('title')}: {r.get('description')}" for r in result["risks"])
    recs_text = "\n".join(f"- {r.get('title')}: {r.get('description')}" for r in result["recommendations"])

    quality = GEval(
        name="KachestvoAnalizaRiskov",
        criteria=(
            "Список рисков и рекомендаций (actual_output) должен по существу отражать проблемы, "
            "явно описанные в контексте: не указан объект работ (scope.field_name пуст) и построение "
            "3D-геомодели заявлено без этапа подготовки/формирования исходных данных. Пункты не должны "
            "быть общими фразами не по теме заявки."
        ),
        evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT, SingleTurnParams.CONTEXT],
        model=judge_model,
        threshold=0.6,
    )
    test_case = LLMTestCase(
        input="Проанализируй ТЗ «Концепт геологии» с 3D-геомоделью без объекта работ и без этапа подготовки данных",
        actual_output=f"Риски:\n{risks_text}\n\nРекомендации:\n{recs_text}",
        context=[
            "scope.field_name (объект работ) пуст",
            "work_content содержит только этап «Построение 3D-геологической модели», без этапа "
            "формирования базы данных / подготовки исходных данных",
        ],
    )
    assert_test(test_case, [quality])
