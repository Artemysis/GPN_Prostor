"""Применение actions чата к заявке (§3.5.5-6 SPEC) — только по явному вызову пользователя."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatSession, Request, RequestTz, TzTemplate
from app.services.tz_builder import create_tz_from_template

REQUEST_FIELDS = {"company_id", "contract_id", "product_id", "title", "description", "cost_total", "date_start", "date_end"}


async def apply_actions(db: AsyncSession, request: Request, actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    applied = []
    for action in actions:
        if action.get("type") != "set_field":
            continue
        field = action.get("field")
        if field not in REQUEST_FIELDS:
            continue
        old = getattr(request, field)
        new = action.get("value")
        setattr(request, field, new)
        meta = dict(request.request_metadata or {})
        filled_by = meta.setdefault("filled_by", {})
        filled_by[field] = "ai"
        request.request_metadata = meta
        applied.append({"field": field, "old": old, "new": new})
    await db.commit()
    return applied


async def autofill_from_session(
    db: AsyncSession,
    session: ChatSession,
    request: Request,
    actions: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    if actions is None:
        last_assistant = next((m for m in reversed(session.messages) if m.role == "assistant" and m.actions), None)
        actions = last_assistant.actions if last_assistant else []

    field_actions = [a for a in actions if a.get("type") == "set_field"]
    applied = await apply_actions(db, request, field_actions)

    tz_diff: dict[str, Any] = {}
    template_action = next((a for a in actions if a.get("type") == "suggest_template"), None)
    existing_tz = (await db.execute(select(RequestTz).where(RequestTz.request_id == request.id))).scalar_one_or_none()
    if template_action and existing_tz is None:
        template = await db.get(TzTemplate, template_action["template_id"])
        if template:
            tz = await create_tz_from_template(db, request.id, template)
            tz_diff = {"tz_id": str(tz.id), "template_id": str(template.id)}

    request_diff = {a["field"]: a["new"] for a in applied}
    return {"applied": applied, "request_diff": request_diff, "tz_diff": tz_diff}
