# LLM-эвалы (DeepEval)

Отдельный набор тестов `tests/evals/`, который оценивает **качество** ответов
LLM-компонентов (не только их структуру, как `tests/unit`/`tests/api`) —
через [DeepEval](https://github.com/confident-ai/deepeval). Судьёй метрик
(`GEval`, `FaithfulnessMetric`) выступает сам DeepSeek через обёртку
`app/services/deepeval_model.py` (у нас нет ключа OpenAI, см. SPEC §1/§4.1).

Что покрыто:

- `test_template_recommender_eval.py` — `recommend_template` выбирает верный
  тип ТЗ и даёт содержательное обоснование (§3.2.2.5 SPEC).
- `test_tz_analyzer_eval.py` — `analyze_tz` находит риски/рекомендации по
  ключевому демо-сценарию §0 SPEC (3D-геомодель без этапа подготовки данных).
- `test_fill_ai_eval.py` — `fill_block_with_ai` не галлюцинирует, черновик
  блока опирается на контекст заявки (`FaithfulnessMetric`).
- `test_chat_agent_eval.py` — ответ чат-агента звучит как предложение с
  обоснованием, а не как автоприменённое действие (правило «ИИ — советник»,
  §0 SPEC) — и структурно (`action` без `confidence`/`justification` —
  падение теста), и по тону (`GEval`).

## Почему это отдельный набор

В отличие от `tests/unit`/`tests/api`/`tests/integration`, эти тесты **не
мокают** `LLMClient` — они дергают реальный DeepSeek API (и как тестируемую
систему, и как судью). Поэтому:

- они помечены маркером `eval` и **не запускаются** обычным `uv run pytest`
  (см. `addopts = -m "not eval"` в `pytest.ini`);
- без реального ключа они skip'аются (`requires_real_llm` в `conftest.py`);
- они не детерминированы (LLM-судья) — не гонять в обычном CI на каждый PR,
  использовать как точечный прогон при изменении промптов/LLM-логики.

## Запуск

Корневой `tests/conftest.py` намеренно зануляет `LLM_API_KEY` в окружении
(чтобы обычные тесты не ходили в сеть), поэтому ключ для эвалов передаётся
отдельной переменной:

```bash
cd backend
export DEEPEVAL_LLM_API_KEY=sk-...твой_ключ_deepseek...
uv run pytest tests/evals -m eval -v
```

Либо — если в корневом `.env` уже заполнен `LLM_API_KEY` — эвалы подхватят
его сами (парсят `.env` напрямую), достаточно:

```bash
uv run pytest tests/evals -m eval -v
```

Опционально переопределяются `DEEPEVAL_LLM_API_BASE` / `DEEPEVAL_LLM_MODEL`
(по умолчанию — те же значения, что и `LLM_API_BASE`/`LLM_MODEL`).
