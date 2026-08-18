import uuid

import pytest

from app.db.models import TzTemplate

SAMPLE_BLOCKS_SCHEMA = {
    "blocks": [
        {"code": "goals", "name": "Цели и задачи работ", "order": 1, "fields": [
            {"key": "goal_text", "type": "text", "label": "Цель", "required": True},
        ]},
        {"code": "work_content", "name": "Содержание работ", "order": 2, "is_stages_block": True},
    ]
}


async def _create_template(db_session) -> TzTemplate:
    template = TzTemplate(
        code=f"test_template_{uuid.uuid4().hex[:8]}",
        name="Тестовый шаблон",
        minio_docx_key="templates/test.docx",
        blocks_schema=SAMPLE_BLOCKS_SCHEMA,
    )
    db_session.add(template)
    await db_session.commit()
    await db_session.refresh(template)
    return template


@pytest.mark.asyncio
async def test_create_and_get_request(client):
    response = await client.post("/requests", json={"title": "Тестовая заявка"})
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Тестовая заявка"
    assert body["status"] == "draft"

    request_id = body["id"]
    response = await client.get(f"/requests/{request_id}")
    assert response.status_code == 200
    assert response.json()["tz_summary"]["completeness_pct"] == 0


@pytest.mark.asyncio
async def test_list_requests(client):
    await client.post("/requests", json={"title": "Заявка 1"})
    response = await client.get("/requests")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1


@pytest.mark.asyncio
async def test_patch_and_submit_request(client, db_session):
    created = (await client.post("/requests", json={"title": "Заявка на изменение"})).json()
    request_id = created["id"]

    patched = await client.patch(f"/requests/{request_id}", json={"cost_total": 1000})
    assert patched.status_code == 200
    assert float(patched.json()["cost_total"]) == 1000

    # без ТЗ отправка заблокирована (нет данных для валидации обязательных полей)
    submitted = await client.post(f"/requests/{request_id}/submit")
    assert submitted.status_code == 400

    template = await _create_template(db_session)
    await client.post(f"/requests/{request_id}/tz", json={"template_id": str(template.id)})

    # ТЗ создано, но обязательное поле блока и этапы работ ещё не заполнены
    submitted = await client.post(f"/requests/{request_id}/submit")
    assert submitted.status_code == 400
    assert "missing_fields" in submitted.json()["error"]["details"]

    await client.patch(
        f"/requests/{request_id}/tz/blocks/goals",
        json={"content": {"goal_text": "Актуализация запасов"}, "filled_by": "manual"},
    )
    await client.post(f"/requests/{request_id}/tz/stages", json={"stage_name": "Этап 1", "stage_order": 1})

    submitted = await client.post(f"/requests/{request_id}/submit")
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "submitted"


@pytest.mark.asyncio
async def test_soft_delete_request(client):
    created = (await client.post("/requests", json={"title": "Заявка на удаление"})).json()
    request_id = created["id"]

    response = await client.delete(f"/requests/{request_id}")
    assert response.status_code == 204

    # исключена из списка по умолчанию…
    listed = await client.get("/requests")
    assert all(item["id"] != request_id for item in listed.json()["items"])

    # …но видна по фильтру status=deleted и данные не удалены физически
    listed_deleted = await client.get("/requests", params={"status": "deleted"})
    ids = [item["id"] for item in listed_deleted.json()["items"]]
    assert request_id in ids

    detail = await client.get(f"/requests/{request_id}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "deleted"
