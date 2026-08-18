"""Интеграционные тесты заявок: создание, редактирование, статусы, удаление."""

import uuid

import pytest

pytestmark = pytest.mark.integration


class TestCreateRequest:
    async def test_create_minimal_request(self, client):
        # Arrange
        payload = {"title": "Заявка QA: минимальная"}

        # Act
        response = await client.post("/requests", json=payload)

        # Assert
        assert response.status_code == 201
        body = response.json()
        assert body["title"] == "Заявка QA: минимальная"
        assert body["status"] == "draft"
        assert body["number"].startswith("REQ-")
        assert body["currency"] == "RUB"

    async def test_create_with_dates(self, client):
        # Arrange
        payload = {"date_start": "2026-02-01", "date_end": "2026-08-01", "cost_total": 123456.78}

        # Act
        response = await client.post("/requests", json=payload)

        # Assert
        assert response.status_code == 201
        assert response.json()["date_start"] == "2026-02-01"
        assert float(response.json()["cost_total"]) == 123456.78

    async def test_create_with_template_initializes_tz(self, client, make_tz_template):
        # Arrange
        template = await make_tz_template()
        payload = {"title": "Заявка с шаблоном", "template_id": str(template.id)}

        # Act
        created = await client.post("/requests", json=payload)
        tz_response = await client.get(f"/requests/{created.json()['id']}/tz")

        # Assert
        assert created.status_code == 201
        assert tz_response.status_code == 200
        tz = tz_response.json()
        assert tz["template_id"] == str(template.id)
        assert len(tz["blocks"]) == 8

    async def test_create_with_invalid_date_is_400(self, client):
        # Arrange
        payload = {"date_start": "01.02.2026"}

        # Act
        response = await client.post("/requests", json=payload)

        # Assert
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "VALIDATION"


class TestGetRequest:
    async def test_get_missing_request_returns_404_envelope(self, client):
        # Arrange
        missing_id = uuid.uuid4()

        # Act
        response = await client.get(f"/requests/{missing_id}")

        # Assert
        assert response.status_code == 404
        error = response.json()["error"]
        assert error["code"] == "NOT_FOUND"
        assert "не найдена" in error["message"].lower()

    async def test_get_detail_contains_tz_summary(self, client):
        # Arrange
        created = (await client.post("/requests", json={"title": "Заявка с деталями"})).json()

        # Act
        response = await client.get(f"/requests/{created['id']}")

        # Assert
        assert response.status_code == 200
        detail = response.json()
        assert detail["tz_summary"] == {"completeness_pct": 0, "risks_count": 0}
        assert detail["documents_count"] == 0


class TestUpdateRequest:
    async def test_patch_updates_fields(self, client):
        # Arrange
        created = (await client.post("/requests", json={"title": "До правки"})).json()

        # Act
        response = await client.patch(f"/requests/{created['id']}", json={"title": "После правки", "cost_total": 999})

        # Assert
        assert response.status_code == 200
        body = response.json()
        assert body["title"] == "После правки"
        assert float(body["cost_total"]) == 999

    async def test_patch_missing_returns_404(self, client):
        # Arrange / Act
        response = await client.patch(f"/requests/{uuid.uuid4()}", json={"title": "x"})

        # Assert
        assert response.status_code == 404


class TestListRequests:
    async def test_list_filters_by_status(self, client):
        # Arrange
        marker = f"QA-LIST-{uuid.uuid4().hex[:6]}"
        created = (await client.post("/requests", json={"title": marker})).json()
        await client.post(f"/requests/{created['id']}/submit")

        # Act
        drafts = await client.get("/requests", params={"status": "draft"})
        submitted = await client.get("/requests", params={"status": "submitted", "limit": 200})

        # Assert
        assert drafts.status_code == submitted.status_code == 200
        assert drafts.json()["total"] >= 1
        assert all(r["status"] == "draft" for r in drafts.json()["items"])
        assert any(r["id"] == created["id"] for r in submitted.json()["items"])

    async def test_list_pagination(self, client):
        # Arrange / Act
        response = await client.get("/requests", params={"limit": 1, "offset": 0})

        # Assert
        assert response.status_code == 200
        assert len(response.json()["items"]) <= 1
        assert response.json()["total"] >= 1


class TestLifecycle:
    async def test_submit_changes_status(self, client):
        # Arrange
        created = (await client.post("/requests", json={"title": "На согласование"})).json()

        # Act
        response = await client.post(f"/requests/{created['id']}/submit")

        # Assert
        assert response.status_code == 200
        assert response.json()["status"] == "submitted"

    async def test_delete_request(self, client):
        # Arrange
        created = (await client.post("/requests", json={"title": "На удаление"})).json()

        # Act
        deleted = await client.delete(f"/requests/{created['id']}")
        fetched = await client.get(f"/requests/{created['id']}")

        # Assert
        assert deleted.status_code == 204
        assert fetched.status_code == 404
