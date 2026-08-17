import pytest


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
async def test_patch_and_submit_request(client):
    created = (await client.post("/requests", json={"title": "Заявка на изменение"})).json()
    request_id = created["id"]

    patched = await client.patch(f"/requests/{request_id}", json={"cost_total": 1000})
    assert patched.status_code == 200
    assert float(patched.json()["cost_total"]) == 1000

    submitted = await client.post(f"/requests/{request_id}/submit")
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "submitted"
