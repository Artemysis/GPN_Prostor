"""Unit-тесты чистых функций чат-агента: SSE-форматирование, чанкинг, фолбэк-ответ."""

import json

import pytest

from app.services.chat_agent import _build_fallback_reply, _chunk_text, _sse
from app.services.embeddings import _hash_embedding

pytestmark = pytest.mark.unit


class TestSseFormat:
    def test_payload_is_valid_json_event(self):
        # Arrange
        payload = {"type": "delta", "content": "Привет"}

        # Act
        event = _sse(payload)

        # Assert
        assert event.startswith("data: ")
        assert event.endswith("\n\n")
        assert json.loads(event[len("data: ") : -2]) == payload

    def test_cyrillic_not_escaped(self):
        # Arrange
        payload = {"type": "delta", "content": "ГРП"}

        # Act
        event = _sse(payload)

        # Assert
        assert "ГРП" in event  # ensure_ascii=False


class TestChunkText:
    def test_chunks_respect_max_size(self):
        # Arrange
        text = "а" * 50

        # Act
        chunks = _chunk_text(text, size=24)

        # Assert
        assert [len(c) for c in chunks] == [24, 24, 2]
        assert "".join(chunks) == text

    def test_empty_text_returns_single_chunk(self):
        # Arrange / Act
        chunks = _chunk_text("")

        # Assert
        assert chunks == [""]


class TestFallbackReply:
    def test_includes_recommendations(self):
        # Arrange
        products = [{"product_name": "ГРП", "product_id": "P1"}]
        contractors = [{"name": "ГеоСервис", "company_id": "C1", "rating": 5}]
        template_rec = {"name": "ТЗ ПТД"}

        # Act
        reply = _build_fallback_reply("нужен ГРП", products, contractors, template_rec)

        # Assert
        assert "нужен ГРП" in reply
        assert "ГРП" in reply and "ГеоСервис" in reply
        assert "ТЗ ПТД" in reply
        assert "ничего не меняю сам" in reply  # ИИ — советник

    def test_without_data_still_polite(self):
        # Arrange / Act
        reply = _build_fallback_reply("запрос", [], [], {})

        # Assert
        assert "запрос" in reply
        assert "Подобрал" not in reply


class TestHashEmbedding:
    def test_deterministic_and_normalized(self):
        # Arrange
        text = "гидравлический разрыв пласта"

        # Act
        v1 = _hash_embedding(text, 64)
        v2 = _hash_embedding(text, 64)

        # Assert
        assert v1 == v2
        assert len(v1) == 64
        assert abs(sum(x * x for x in v1) - 1.0) < 1e-6

    def test_different_texts_differ(self):
        # Arrange
        text_a, text_b = "грп", "бурение"

        # Act
        v1 = _hash_embedding(text_a, 64)
        v2 = _hash_embedding(text_b, 64)

        # Assert
        assert v1 != v2
