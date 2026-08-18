"""Применение actions чата к заявке (§3.5.5-6 SPEC) — только по явному вызову пользователя."""

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import ChatSession, Request, RequestTz, TzTemplate
from app.services.tz_builder import create_tz_from_template, prefill_existing_tz, tz_is_empty

REQUEST_FIELDS = {"company_id", "contract_id", "product_id", "title", "description", "cost_total", "date_start", "date_end"}


def _coerce(field: str, value: Any) -> Any:
    if value is None:
        return None
    if field in {"date_start", "date_end"}:
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value)[:10])
        except (TypeError, ValueError):
            return None
    if field == "cost_total":
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    return str(value)


async def apply_actions(db: AsyncSession, request: Request, actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    applied = []
    for action in actions:
        if action.get("type") != "set_field":
            continue
        field = action.get("field")
        if field not in REQUEST_FIELDS:
            continue
        new = _coerce(field, action.get("value"))
        if new is None:
            continue
        old = getattr(request, field)
        setattr(request, field, new)
        meta = dict(request.request_metadata or {})
        filled_by = meta.setdefault("filled_by", {})
        filled_by[field] = "ai"
        request.request_metadata = meta
        applied.append({"field": field, "old": old, "new": new})
    await db.commit()
    return applied


async def _prefill_with_ai(db: AsyncSession, request: Request, template: TzTemplate) -> dict[str, Any]:
    """ИИ-черновик блоков ТЗ + оценка стоимости (если у заявки её ещё нет)."""
    from app.services.llm_client import get_llm_client
    from app.services.tz_builder import generate_tz_prefill

    await db.refresh(request)
    request_context = {
        "title": request.title,
        "description": request.description,
        "product_id": request.product_id,
        "company_id": request.company_id,
    }
    prefill, estimated_cost = await generate_tz_prefill(template, request_context, get_llm_client())
    if estimated_cost and request.cost_total is None:
        request.cost_total = estimated_cost
        meta = dict(request.request_metadata or {})
        meta.setdefault("filled_by", {})["cost_total"] = "ai"
        request.request_metadata = meta
    return prefill


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
    existing_tz = (
        (
            await db.execute(
                select(RequestTz)
                .where(RequestTz.request_id == request.id)
                .options(selectinload(RequestTz.blocks), selectinload(RequestTz.stages))
            )
        )
        .scalar_one_or_none()
    )
    if template_action and existing_tz is None:
        template = await db.get(TzTemplate, template_action["template_id"])
        if template:
            prefill = await _prefill_with_ai(db, request, template)
            tz = await create_tz_from_template(db, request.id, template, prefill=prefill)
            tz_diff = {
                "tz_id": str(tz.id),
                "template_id": str(template.id),
                "completeness_pct": tz.completeness_pct,
                "ai_draft": bool(prefill),
            }
    elif template_action and existing_tz is not None and tz_is_empty(existing_tz):
        # ТЗ создано вручную (кликом по карточке шаблона), но ни один блок не заполнен —
        # заполняем его ИИ-черновиком, как при создании с prefill. Заполненное вручную
        # ТЗ не перезаписываем.
        template = await db.get(TzTemplate, existing_tz.template_id)
        if template:
            prefill = await _prefill_with_ai(db, request, template)
            tz = await prefill_existing_tz(db, existing_tz, template, prefill) if prefill else existing_tz
            tz_diff = {
                "tz_id": str(tz.id),
                "template_id": str(template.id),
                "completeness_pct": tz.completeness_pct,
                "ai_draft": bool(prefill),
                "filled_existing": True,
            }

    request_diff = {a["field"]: a["new"] for a in applied}
    return {"applied": applied, "request_diff": request_diff, "tz_diff": tz_diff}
