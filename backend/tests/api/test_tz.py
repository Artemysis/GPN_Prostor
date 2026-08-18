import uuid

import pytest

from app.db.models import TzTemplate

SAMPLE_BLOCKS_SCHEMA = {
    "blocks": [
        {"code": "goals", "name": "Цели и задачи работ", "order": 1, "fields": [
            {"key": "goal_text", "type": "text", "label": "Цель", "required": True},
        ]},
        {"code": "scope", "name": "Периметр работ", "order": 2, "fields": [
            {"key": "field_name", "type": "text", "label": "Наименование месторождения", "required": True},
        ]},
        {"code": "work_content", "name": "Содержание работ", "order": 3, "is_stages_block": True},
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
async def test_create_tz_and_patch_block(client, db_session):
    template = await _create_template(db_session)

    request = (await client.post("/requests", json={"title": "Заявка с ТЗ"})).json()
    request_id = request["id"]

    created = await client.post(f"/requests/{request_id}/tz", json={"template_id": str(template.id)})
    assert created.status_code == 201
    assert created.json()["completeness_pct"] == 0

    patched = await client.patch(
        f"/requests/{request_id}/tz/blocks/scope",
        json={"content": {"field_name": "Ваньгаяхинское"}, "filled_by": "manual"},
    )
    assert patched.status_code == 200
    assert patched.json()["completeness_pct"] == 100

    completeness = await client.get(f"/requests/{request_id}/tz/completeness")
    assert completeness.status_code == 200
    assert 0 < completeness.json()["completeness_pct"] < 100


@pytest.mark.asyncio
async def test_duplicate_tz_conflict(client, db_session):
    template = await _create_template(db_session)
    request = (await client.post("/requests", json={"title": "Заявка"})).json()
    request_id = request["id"]

    first = await client.post(f"/requests/{request_id}/tz", json={"template_id": str(template.id)})
    assert first.status_code == 201

    second = await client.post(f"/requests/{request_id}/tz", json={"template_id": str(template.id)})
    assert second.status_code == 409
