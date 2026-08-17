"""Анализатор качества ТЗ: детерминированные бизнес-правила (§10 SPEC) + опциональный LLM-слой."""

from datetime import date
from typing import Any

from app.core.config import get_settings
from app.db.models import Request, RequestTz, RequestTzStage, TzTemplate
from app.services.llm_client import DeepSeekLLMClient, get_llm_client

TYPICAL_DURATION_DAYS = 365  # типовой срок — 12 мес.

GEOMODEL_KEYWORDS = ["3d-геомодел", "3d геомодел", "геологическ", "подсчет запасов", "подсчёт запасов"]
BASE_DATA_STAGE_KEYWORDS = ["формирование базы данных", "подготовка исходных данных", "база данных"]


def _blocks_schema(template: TzTemplate) -> list[dict]:
    return sorted(template.blocks_schema.get("blocks", []), key=lambda b: b.get("order", 0))


def _field_filled(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list | dict):
        return len(value) > 0
    return True


def compute_block_completeness(block_schema: dict, content: dict[str, Any]) -> int:
    if block_schema.get("is_stages_block"):
        stages = content.get("stages", []) if isinstance(content, dict) else []
        return 100 if stages else 0
    fields = block_schema.get("fields", [])
    required_fields = [f for f in fields if f.get("required")] or fields
    if not required_fields:
        return 100 if content else 0
    filled = sum(1 for f in required_fields if _field_filled((content or {}).get(f["key"])))
    return round(100 * filled / len(required_fields))


def compute_completeness(template: TzTemplate, payload: dict[str, Any]) -> dict[str, int]:
    result = {}
    for block in _blocks_schema(template):
        code = block["code"]
        content = payload.get(code, {})
        result[code] = compute_block_completeness(block, content)
    return result


def compute_overall_completeness(template: TzTemplate, payload: dict[str, Any]) -> tuple[int, dict[str, int]]:
    block_completeness = compute_completeness(template, payload)
    blocks = _blocks_schema(template)
    weights = {b["code"]: b.get("weight", 1) for b in blocks}
    total_weight = sum(weights.values()) or 1
    weighted = sum(block_completeness.get(code, 0) * w for code, w in weights.items())
    overall = round(weighted / total_weight)
    return overall, block_completeness


def _apply_business_rules(
    template: TzTemplate,
    payload: dict[str, Any],
    stages: list[RequestTzStage],
    request: Request | None,
) -> tuple[list[dict], list[dict]]:
    risks: list[dict] = []
    recommendations: list[dict] = []

    scope = payload.get("scope", {}) or {}
    if not _field_filled(scope.get("field_name")):
        risks.append(
            {
                "severity": "high",
                "category": "missing_data",
                "title": "Не указан объект работ",
                "description": "Поле scope.field_name пусто",
                "suggestion": "Укажите наименование месторождения",
                "block_code": "scope",
            }
        )
        recommendations.append(
            {
                "title": "Указать объект работ",
                "description": "Заполните наименование месторождения в блоке «Периметр работ»",
                "priority": 1,
                "block_code": "scope",
            }
        )

    goals = payload.get("goals", {}) or {}
    template_text = f"{template.name} {template.description or ''} {goals}".lower()
    if any(kw in template_text for kw in GEOMODEL_KEYWORDS):
        stage_texts = " ".join(f"{s.stage_name} {s.description or ''}".lower() for s in stages)
        if not any(kw in stage_texts for kw in BASE_DATA_STAGE_KEYWORDS):
            risks.append(
                {
                    "severity": "high",
                    "category": "logical",
                    "title": "3D-модель без этапа подготовки исходных данных",
                    "description": (
                        "Указано построение 3D-геомодели, но отсутствует этап формирования базы данных"
                    ),
                    "suggestion": "Добавить этап «Формирование базы данных»",
                    "block_code": "work_content",
                }
            )
            recommendations.append(
                {
                    "title": "Указать требования к 3D-модели",
                    "description": "Добавить раздел требований к 3D-модели в блок «Содержание работ»",
                    "priority": 2,
                    "block_code": "work_content",
                }
            )

    terms = payload.get("terms", {}) or {}
    date_start = terms.get("date_start") or (request.date_start.isoformat() if request and request.date_start else None)
    date_end = terms.get("date_end") or (request.date_end.isoformat() if request and request.date_end else None)
    if date_start and date_end:
        try:
            d_start = date.fromisoformat(str(date_start)[:10])
            d_end = date.fromisoformat(str(date_end)[:10])
            if (d_end - d_start).days < TYPICAL_DURATION_DAYS:
                risks.append(
                    {
                        "severity": "medium",
                        "category": "terms",
                        "title": "Заявленный срок ниже типового",
                        "description": "date_end раньше типового срока для этого типа работ (обычно 12 мес.)",
                        "suggestion": "Проверить календарный план",
                        "block_code": "terms",
                    }
                )
                recommendations.append(
                    {
                        "title": "Проверить календарный план",
                        "description": "Срок работ ниже типового",
                        "priority": 3,
                        "block_code": "terms",
                    }
                )
        except ValueError:
            pass

    conditions = payload.get("conditions", {}) or {}
    if not _field_filled(conditions.get("source_data")):
        risks.append(
            {
                "severity": "medium",
                "category": "missing_data",
                "title": "Не указаны требования к исходным материалам",
                "description": "Поле conditions.source_data пусто",
                "suggestion": "Укажите исходную информацию от заказчика",
                "block_code": "conditions",
            }
        )
        recommendations.append(
            {
                "title": "Добавить исходные данные",
                "description": "Перед согласованием необходимо добавить требования к исходным материалам",
                "priority": 1,
                "block_code": "conditions",
            }
        )

    signatures = payload.get("signatures", {}) or {}
    if not _field_filled(signatures.get("customer_signee")) or not _field_filled(signatures.get("contractor_signee")):
        risks.append(
            {
                "severity": "low",
                "category": "compliance",
                "title": "Не заполнены подписанты",
                "description": "Блок «Подписи сторон» не заполнен — не блокирует черновик, но нужен для готовности 100%",
                "suggestion": "Укажите подписантов заказчика и исполнителя",
                "block_code": "signatures",
            }
        )

    return risks, recommendations


async def analyze_tz(
    template: TzTemplate,
    tz: RequestTz,
    stages: list[RequestTzStage],
    request: Request | None,
    llm: DeepSeekLLMClient | None = None,
) -> dict:
    settings = get_settings()
    overall, block_completeness = compute_overall_completeness(template, tz.payload)
    risks, recommendations = _apply_business_rules(template, tz.payload, stages, request)

    llm = llm or get_llm_client()
    if llm.enabled:
        # deepseek-reasoner не поддерживает JSON-mode (§1, §4.4 SPEC) — структурный анализ всегда идёт через deepseek-chat.
        json_schema = {
            "name": "tz_analysis",
            "schema": {
                "type": "object",
                "properties": {
                    "risks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "severity": {"type": "string"},
                                "category": {"type": "string"},
                                "title": {"type": "string"},
                                "description": {"type": "string"},
                                "suggestion": {"type": "string"},
                                "block_code": {"type": "string"},
                            },
                            "required": ["severity", "category", "title", "description", "suggestion", "block_code"],
                        },
                    },
                    "recommendations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "description": {"type": "string"},
                                "priority": {"type": "integer"},
                                "block_code": {"type": "string"},
                            },
                            "required": ["title", "description", "priority", "block_code"],
                        },
                    },
                },
                "required": ["risks", "recommendations"],
            },
        }
        system_prompt = (
            "Проанализируй ТЗ нефтесервисной заявки и дополни список рисков и рекомендаций сверх "
            "уже найденных детерминированными правилами. Не дублируй уже найденные пункты. "
            "Верни JSON по заданной схеме."
        )
        user_prompt = (
            f"Шаблон: {template.name}. Payload: {tz.payload}. "
            f"Уже найденные риски: {risks}. % готовности по блокам: {block_completeness}."
        )
        extra = await llm.chat_json(system_prompt, user_prompt, json_schema, model=settings.llm_model)
        risks.extend(extra.get("risks", []))
        recommendations.extend(extra.get("recommendations", []))

    return {
        "completeness_pct": overall,
        "block_completeness": block_completeness,
        "risks": risks,
        "recommendations": recommendations,
    }
