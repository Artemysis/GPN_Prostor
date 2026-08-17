import pytest


@pytest.mark.asyncio
async def test_list_companies_empty(client):
    response = await client.get("/companies")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_company_not_found(client):
    response = await client.get("/companies/unknown")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
