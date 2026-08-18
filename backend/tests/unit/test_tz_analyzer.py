"""Unit-тесты анализатора ТЗ: заполненность блоков и бизнес-правила рисков (§10 SPEC)."""

from datetime import date
from typing import Any

import pytest

from app.db.models import Request, RequestTz, RequestTzStage, TzTemplate
from app.services.docx_parser import _default_blocks, build_blocks_schema
from app.services.tz_analyzer import (
    TYPICAL_DURATION_DAYS,
    analyze_tz,
    compute_block_completeness,
    compute_overall_completeness,
)
from tests.conftest import FakeLLMClient

pytestmark = pytest.mark.unit


def make_template(name: str = "ТЗ ПТД", description: str | None = None) -> TzTemplate:
    return TzTemplate(
        code="QA-TPL",
        name=name,
        description=description,
        minio_docx_key="templates/qa.docx",
        blocks_schema=build_blocks_schema(_default_blocks()),
    )


def full_payload() -> dict[str, Any]:
    return {
        "goals": {"goal_text": "Построение модели", "tasks": ["Анализ данных"]},
        "scope": {"location": "ЯНАО", "field_name": "Восточно-Уренгойский лицензионный участок"},
        "terms": {"date_start": "2026-01-01", "date_end": "2027-01-05"},
        "work_content": {"stages": [{"stage_name": "Формирование базы данных"}]},
        "conditions": {"source_data": "Сейсмика 3D, ГИС", "software": "Petrel"},
        "documentation": {"report_formats": "DOCX, PDF"},
        "quality_control": {"acceptance": "По акту приёмки"},
        "signatures": {"customer_signee": "Иванов И.И.", "contractor_signee": "Петров П.П."},
    }


class TestBlockCompleteness:
    def test_stages_block_binary(self):
        # Arrange
        schema = {"is_stages_block": True}

        # Act / Assert
        assert compute_block_completeness(schema, {"stages": [{"stage_name": "Этап"}]}) == 100
        assert compute_block_completeness(schema, {}) == 0

    def test_partial_required_fields(self):
        # Arrange
        schema = {"fields": [
            {"key": "a", "required": True},
            {"key": "b", "required": True},
        ]}

        # Act
        pct = compute_block_completeness(schema, {"a": "заполнено", "b": ""})

        # Assert
        assert pct == 50

    def test_all_fields_filled_gives_100(self):
        # Arrange
        schema = {"fields": [
            {"key": "a", "required": True},
            {"key": "b", "required": True},
        ]}

        # Act
        pct = compute_block_completeness(schema, {"a": "x", "b": ["y"]})

        # Assert
        assert pct == 100

    def test_whitespace_string_counts_as_empty(self):
        # Arrange
        schema = {"fields": [{"key": "a", "required": True}]}

        # Act
        pct = compute_block_completeness(schema, {"a": "   "})

        # Assert
        assert pct == 0


class TestOverallCompleteness:
    def test_full_payload_is_100(self):
        # Arrange
        template = make_template()
        payload = full_payload()

        # Act
        overall, blocks = compute_overall_completeness(template, payload)

        # Assert
        assert overall == 100
        assert all(v == 100 for v in blocks.values())
        assert len(blocks) == 8

    def test_empty_payload_is_0(self):
        # Arrange
        template = make_template()

        # Act
        overall, blocks = compute_overall_completeness(template, {})

        # Assert
        assert overall == 0
        assert set(blocks.values()) == {0}

    def test_weighted_average(self):
        # Arrange
        template = make_template()
        payload = full_payload()
        payload.pop("signatures")  # 7 из 8 блоков заполнены

        # Act
        overall, blocks = compute_overall_completeness(template, payload)

        # Assert
        assert blocks["signatures"] == 0
        assert overall == round(100 * 7 / 8)


class TestBusinessRules:
    async def test_empty_payload_reports_expected_risks(self):
        # Arrange
        template = make_template()
        tz = RequestTz(payload={}, template_id=template.id)
        request = Request(user_id=None, title="QA", date_start=date(2026, 1, 1), date_end=date(2027, 6, 1))

        # Act
        result = await analyze_tz(template, tz, stages=[], request=request, llm=FakeLLMClient(enabled=False))

        # Assert
        risks = {(r["category"], r["severity"]) for r in result["risks"]}
        assert ("missing_data", "high") in risks      # scope.field_name пусто
        assert ("missing_data", "medium") in risks    # conditions.source_data пусто
        assert ("compliance", "low") in risks         # подписанты не заполнены
        assert result["completeness_pct"] == 0

    async def test_geomodel_without_base_data_stage_is_high_risk(self):
        # Arrange
        template = make_template(name="ТЗ: построение 3D-геомодели")
        tz = RequestTz(payload=full_payload(), template_id=template.id)
        stages = [RequestTzStage(stage_order=1, stage_name="Построение модели")]  # без этапа БД

        # Act
        result = await analyze_tz(template, tz, stages=stages, request=None, llm=FakeLLMClient(enabled=False))

        # Assert
        logical = [r for r in result["risks"] if r["category"] == "logical"]
        assert len(logical) == 1
        assert logical[0]["severity"] == "high"
        assert "базы данных" in logical[0]["suggestion"]

    async def test_geomodel_with_base_data_stage_no_logical_risk(self):
        # Arrange
        template = make_template(name="ТЗ: построение 3D-геомодели")
        tz = RequestTz(payload=full_payload(), template_id=template.id)
        stages = [RequestTzStage(stage_order=1, stage_name="Формирование базы данных и подготовка исходных данных")]

        # Act
        result = await analyze_tz(template, tz, stages=stages, request=None, llm=FakeLLMClient(enabled=False))

        # Assert
        assert all(r["category"] != "logical" for r in result["risks"])

    async def test_short_terms_reported_as_medium_risk(self):
        # Arrange
        template = make_template()
        payload = full_payload()
        payload["terms"] = {"date_start": "2026-01-01", "date_end": "2026-06-01"}  # ~5 мес < 12 мес
        tz = RequestTz(payload=payload, template_id=template.id)

        # Act
        result = await analyze_tz(template, tz, stages=[], request=None, llm=FakeLLMClient(enabled=False))

        # Assert
        terms_risks = [r for r in result["risks"] if r["category"] == "terms"]
        assert len(terms_risks) == 1
        assert terms_risks[0]["severity"] == "medium"
        assert TYPICAL_DURATION_DAYS == 365

    async def test_full_payload_has_no_risks(self):
        # Arrange
        template = make_template(name="ТЗ без ключевых слов геомодели")
        tz = RequestTz(payload=full_payload(), template_id=template.id)
        stages = [RequestTzStage(stage_order=1, stage_name="Формирование базы данных")]

        # Act
        result = await analyze_tz(template, tz, stages=stages, request=None, llm=FakeLLMClient(enabled=False))

        # Assert
        assert result["risks"] == []
        assert result["recommendations"] == []
        assert result["completeness_pct"] == 100
