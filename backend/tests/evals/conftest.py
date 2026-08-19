"""Инфраструктура LLM-эвалов (DeepEval) — см. `tests/evals/README.md`.

В отличие от `tests/unit|api|integration`, эти тесты обращаются к **реальному**
DeepSeek API (и как тестируемая система, и как LLM-судья метрик DeepEval) —
без ключа они ничего не проверяют по существу, поэтому весь пакет
скипается, если ключ недоступен. Корневой `tests/conftest.py` намеренно
зануляет `LLM_API_KEY` в `os.environ`, чтобы обычные unit/api/integration
тесты не ходили в сеть — поэтому здесь ключ читается отдельно, до этого
зануления не долетая: из `DEEPEVAL_LLM_API_KEY`/`LLM_API_KEY_REAL`, либо
напрямую из корневого `.env`.
"""

import os
import re
from pathlib import Path

import pytest
import pytest_asyncio

from app.services.deepeval_model import DeepSeekEvalModel
from app.services.llm_client import DeepSeekLLMClient


def _read_root_env_value(key: str) -> str:
    env_path = Path(__file__).resolve().parents[3] / ".env"
    if not env_path.exists():
        return ""
    pattern = re.compile(rf"^{key}=(.*)$")
    for line in env_path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line.strip())
        if match:
            return match.group(1).strip().strip('"').strip("'")
    return ""


def _real_llm_api_key() -> str:
    for env_var in ("DEEPEVAL_LLM_API_KEY", "LLM_API_KEY_REAL"):
        value = os.environ.get(env_var, "")
        if value and value.isascii():
            return value
    value = _read_root_env_value("LLM_API_KEY")
    return value if value.isascii() else ""


_API_KEY = _real_llm_api_key()
_BASE_URL = os.environ.get("DEEPEVAL_LLM_API_BASE") or _read_root_env_value("LLM_API_BASE") or "https://api.deepseek.com/v1"
_MODEL = os.environ.get("DEEPEVAL_LLM_MODEL") or _read_root_env_value("LLM_MODEL") or "deepseek-chat"

requires_real_llm = pytest.mark.skipif(
    not _API_KEY,
    reason=(
        "Эвалы DeepEval требуют реальный ключ DeepSeek: задайте DEEPEVAL_LLM_API_KEY "
        "(или заполните LLM_API_KEY в корневом .env) и запустите "
        "`uv run pytest tests/evals -m eval`."
    ),
)


@pytest.fixture(scope="session")
def real_llm() -> DeepSeekLLMClient:
    return DeepSeekLLMClient(base_url=_BASE_URL, api_key=_API_KEY, model=_MODEL, reasoner_model=_MODEL)


@pytest.fixture(scope="session")
def judge_model(real_llm: DeepSeekLLMClient) -> DeepSeekEvalModel:
    """LLM-судья для метрик DeepEval (GEval и т.п.) — тот же DeepSeek."""
    return DeepSeekEvalModel(real_llm)


@pytest_asyncio.fixture(autouse=True)
async def _use_real_llm_for_services(monkeypatch, real_llm: DeepSeekLLMClient):
    """Подменяет get_llm_client() реальным клиентом только в пакете evals."""
    import app.services.chat_agent
    import app.services.template_recommender
    import app.services.tz_analyzer
    import app.services.tz_builder

    for module in (
        app.services.chat_agent,
        app.services.template_recommender,
        app.services.tz_analyzer,
        app.services.tz_builder,
    ):
        monkeypatch.setattr(module, "get_llm_client", lambda: real_llm)
    yield
