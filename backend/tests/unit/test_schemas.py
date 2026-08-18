"""Unit-тесты Pydantic-схем (валидация входных/выходных моделей)."""

import uuid
from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from app.schemas.chat import ChatApplyRequest, ChatMessageCreate
from app.schemas.request import RequestCreate, RequestDetailOut, RequestOut, RequestUpdate
from app.schemas.search import SemanticSearchRequest

pytestmark = pytest.mark.unit


class TestRequestCreateSchema:
    def test_minimal_payload_defaults_to_none(self):
        # Arrange
        payload = {}

        # Act
        model = RequestCreate(**payload)

        # Assert
        assert model.title is None
        assert model.company_id is None
        assert model.cost_total is None
        assert model.template_id is None

    def test_dates_parsed_from_iso_strings(self):
        # Arrange
        payload = {"date_start": "2026-01-15", "date_end": "2026-12-31"}

        # Act
        model = RequestCreate(**payload)

        # Assert
        assert model.date_start == date(2026, 1, 15)
        assert model.date_end == date(2026, 12, 31)

    def test_invalid_date_rejected(self):
        # Arrange
        payload = {"date_start": "15.01.2026"}

        # Act / Assert
        with pytest.raises(ValidationError):
            RequestCreate(**payload)

    def test_template_id_parsed_from_string(self):
        # Arrange
        template_uuid = uuid.uuid4()
        payload = {"template_id": str(template_uuid)}

        # Act
        model = RequestCreate(**payload)

        # Assert
        assert model.template_id == template_uuid


class TestRequestOutSchema:
    def test_from_attributes_round_trip(self):
        # Arrange
        request_id = uuid.uuid4()
        orm_like = {
            "id": request_id,
            "number": "REQ-2026-000001",
            "status": "draft",
            "title": "ТЗ на ГРП",
            "currency": "RUB",
            "created_at": datetime(2026, 1, 1, tzinfo=UTC),
            "updated_at": datetime(2026, 1, 2, tzinfo=UTC),
        }

        # Act
        model = RequestOut.model_validate(orm_like, from_attributes=True)

        # Assert
        assert model.id == request_id
        assert model.status == "draft"
        assert model.currency == "RUB"

    def test_detail_defaults_for_empty_tz(self):
        # Arrange
        base = {
            "id": uuid.uuid4(),
            "status": "draft",
            "currency": "RUB",
            "created_at": datetime(2026, 1, 1, tzinfo=UTC),
            "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
        }

        # Act
        model = RequestDetailOut(**base)

        # Assert
        assert model.tz_summary.completeness_pct == 0
        assert model.tz_summary.risks_count == 0
        assert model.documents_count == 0


class TestRequestUpdateSchema:
    def test_partial_update_keeps_unset_fields(self):
        # Arrange
        payload = {"cost_total": 1500.5}

        # Act
        model = RequestUpdate(**payload)
        dumped = model.model_dump(exclude_unset=True)

        # Assert
        assert dumped == {"cost_total": 1500.5}
        assert "title" not in dumped


class TestChatSchemas:
    def test_message_content_required(self):
        # Arrange / Act / Assert
        with pytest.raises(ValidationError):
            ChatMessageCreate()

    def test_apply_actions_required(self):
        # Arrange / Act / Assert
        with pytest.raises(ValidationError):
            ChatApplyRequest()

    def test_apply_actions_accepts_set_field(self):
        # Arrange
        payload = {"actions": [{"type": "set_field", "field": "title", "value": "Новое"}]}

        # Act
        model = ChatApplyRequest(**payload)

        # Assert
        assert model.actions[0]["field"] == "title"


class TestSemanticSearchRequest:
    def test_top_k_default_and_filters(self):
        # Arrange
        payload = {"query": "грп"}

        # Act
        model = SemanticSearchRequest(**payload)

        # Assert
        assert model.top_k == 10
        assert model.filters is None

    def test_query_required(self):
        # Arrange / Act / Assert
        with pytest.raises(ValidationError):
            SemanticSearchRequest()
