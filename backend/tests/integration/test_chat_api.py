"""Интеграционные тесты чата: SSE-стриминг с замоканным LLM, автозаполнение, применение actions."""

import json
import uuid

import pytest

pytestmark = pytest.mark.integration


def parse_sse_events(raw: str) -> list[dict]:
    """Парсит тело text/event-stream в список JSON-событий (без [DONE])."""
    events = []
    for line in raw.splitlines():
        if line.startswith("data: ") and line != "data: [DONE]":
            events.append(json.loads(line[len("data: ") :]))
    return events


@pytest.fixture
async def chat_context(client):
    """Заявка + привязанная чат-сессия."""
    request = (await client.post("/requests", json={"title": "Заявка для чата"})).json()
    session = (await client.post("/chat/sessions", json={"request_id": request["id"], "title": "QA сессия"})).json()
    return {"request": request, "session": session}


class TestChatSessionLifecycle:
    async def test_create_and_get_session(self, client):
        # Arrange
        request = (await client.post("/requests", json={"title": "Для сессии"})).json()

        # Act
        created = await client.post("/chat/sessions", json={"request_id": request["id"]})
        fetched = await client.get(f"/chat/sessions/{created.json()['session_id']}")

        # Assert
        assert created.status_code == 201
        assert fetched.status_code == 200
        body = fetched.json()
        assert body["request_id"] == request["id"]
        assert body["messages"] == []

    async def test_get_missing_session_404(self, client):
        # Arrange / Act
        response = await client.get(f"/chat/sessions/{uuid.uuid4()}")

        # Assert
        assert response.status_code == 404


class TestChatSseStreaming:
    async def test_stream_with_mocked_llm_emits_full_event_chain(
        self, client, chat_context, seed_search_corpus, make_tz_template, mock_llm
    ):
        # Arrange
        template = await make_tz_template()
        mock_llm.stream_deltas = ["Готов ", "помочь ", "с ГРП."]
        mock_llm.json_responses.append(
            {
                "template_code": template.code,
                "confidence": 0.9,
                "justification": "QA: типовые работы",
                "suggested_fields": {},
            }
        )
        corpus = seed_search_corpus

        # Act
        response = await client.post(
            f"/chat/sessions/{chat_context['session']['session_id']}/messages",
            json={"content": "нужен гидравлический разрыв пласта"},
        )

        # Assert
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        raw = response.text
        assert raw.endswith("data: [DONE]\n\n")

        events = parse_sse_events(raw)
        by_type = {e["type"]: e for e in events}

        deltas = "".join(e["content"] for e in events if e["type"] == "delta")
        assert deltas == "Готов помочь с ГРП."  # чанки склеены без потерь

        assert by_type["products"]["items"][0]["product_id"] == corpus["product_burn"].product_id
        assert by_type["contractors"]["items"][0]["company_id"] == corpus["company"].company_id
        assert by_type["similar_requests"]["items"][0]["request_id"] == str(corpus["request"].id)

        action_types = {a["type"] for a in by_type["actions"]["actions"]}
        assert action_types == {"set_field", "suggest_template"}
        set_fields = {a["field"]: a for a in by_type["actions"]["actions"] if a["type"] == "set_field"}
        assert set_fields["product_id"]["value"] == corpus["product_burn"].product_id
        assert set_fields["company_id"]["value"] == corpus["company"].company_id

    async def test_stream_persists_user_and_assistant_messages(
        self, client, chat_context, seed_search_corpus, mock_llm
    ):
        # Arrange
        mock_llm.stream_deltas = ["Ответ ", "агента."]
        session_id = chat_context["session"]["session_id"]

        # Act
        await client.post(f"/chat/sessions/{session_id}/messages", json={"content": "вопрос QA"})
        messages = (await client.get(f"/chat/sessions/{session_id}/messages")).json()

        # Assert
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "вопрос QA"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] == "Ответ агента."

    async def test_fallback_mode_without_llm_key(self, client, chat_context, seed_search_corpus):
        # Arrange — mock_llm НЕ используется: LLM_API_KEY пуст -> демо-режим

        # Act
        response = await client.post(
            f"/chat/sessions/{chat_context['session']['session_id']}/messages",
            json={"content": "гидравлический разрыв пласта"},
        )
        events = parse_sse_events(response.text)
        deltas = "".join(e["content"] for e in events if e["type"] == "delta")

        # Assert — детерминированный фолбэк упоминает подобранную услугу
        assert "Гидравлический разрыв пласта" in deltas
        assert "ничего не меняю сам" in deltas


class TestApplyActions:
    async def test_apply_updates_request_fields(self, client, chat_context):
        # Arrange
        session_id = chat_context["session"]["session_id"]
        request_id = chat_context["request"]["id"]
        actions = [{"type": "set_field", "field": "title", "value": "Заголовок из чата"}]

        # Act
        response = await client.post(f"/chat/sessions/{session_id}/apply", json={"actions": actions})

        # Assert
        assert response.status_code == 200
        assert response.json()["applied"][0]["field"] == "title"
        stored = (await client.get(f"/requests/{request_id}")).json()
        assert stored["title"] == "Заголовок из чата"

    async def test_apply_does_not_touch_non_whitelisted_fields(self, client, chat_context):
        # Arrange
        session_id = chat_context["session"]["session_id"]
        actions = [{"type": "set_field", "field": "status", "value": "submitted"}]

        # Act
        response = await client.post(f"/chat/sessions/{session_id}/apply", json={"actions": actions})

        # Assert
        assert response.status_code == 200
        assert response.json()["applied"] == []

    async def test_apply_without_bound_request_is_400(self, client):
        # Arrange
        session = (await client.post("/chat/sessions", json={"title": "без заявки"})).json()

        # Act
        response = await client.post(
            f"/chat/sessions/{session['session_id']}/apply",
            json={"actions": [{"type": "set_field", "field": "title", "value": "x"}]},
        )

        # Assert
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "VALIDATION"


class TestAutofill:
    async def test_autofill_with_suggest_template_creates_tz(self, client, chat_context, make_tz_template):
        # Arrange
        template = await make_tz_template()
        actions = [{"type": "suggest_template", "template_id": str(template.id), "code": template.code}]

        # Act
        response = await client.post(
            f"/chat/sessions/{chat_context['session']['session_id']}/autofill", json={"actions": actions}
        )

        # Assert
        assert response.status_code == 200
        body = response.json()
        assert body["tz_diff"]["template_id"] == str(template.id)
        tz = (await client.get(f"/requests/{chat_context['request']['id']}/tz")).json()
        assert tz["template_id"] == str(template.id)

    async def test_autofill_without_bound_request_is_400(self, client):
        # Arrange
        session = (await client.post("/chat/sessions", json={})).json()

        # Act
        response = await client.post(f"/chat/sessions/{session['session_id']}/autofill", json={})

        # Assert
        assert response.status_code == 400
