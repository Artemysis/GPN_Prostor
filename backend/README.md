# ПРОСТОР 2.0 — Backend

FastAPI-бэкенд конструктора ТЗ и ИИ-агента умного поиска (см. `../SPEC.md`).

## Стек

FastAPI · SQLAlchemy 2 (async) + Alembic · PostgreSQL 16 + pgvector · MinIO ·
DeepSeek (OpenAI-совместимый API) · sentence-transformers (эмбеддинги) ·
FastAPI BackgroundTasks (фоновые задачи в MVP-режиме, см. `USE_CELERY`).

## Быстрый старт

### Через Docker Compose (из корня репозитория)

```bash
cp .env.example .env
docker compose up -d
```

Backend поднимется на `http://localhost:8000`, применит миграции и засеет
справочники/шаблоны ТЗ из `seed/` (если каталоги не пусты). Swagger — на
`/docs`, OpenAPI-схема — на `/openapi.json`.

### Локально (uv)

```bash
cd backend
cp ../.env.example .env   # поправить хосты postgres/minio/redis на localhost
uv sync
uv run alembic upgrade head
uv run python main.py     # либо: uv run uvicorn app.main:app --reload
```

## Переменные окружения

См. `.env.example` в корне репозитория. Обязательно заполните `LLM_API_KEY`,
если нужен реальный ИИ-агент — без ключа приложение продолжает работать в
детерминированном фолбэк-режиме (эвристический ответ чата, пустые черновики
`fill-ai`, текстовый аналитический отчёт по шаблону), это удобно для
локальной разработки/демо без доступа к DeepSeek.

## Миграции

```bash
uv run alembic upgrade head
uv run alembic revision -m "название" --autogenerate   # для новых миграций
```

## Тесты

Тесты гоняются на реальном PostgreSQL + pgvector (см. `tests/conftest.py`) и используют
**отдельную БД `prostor_test`** — не dev-базу `prostor` (создаётся автоматически на том же
Postgres-сервере, см. `docker/init-test-db.sql`). Фикстуры делают `create_all`/`drop_all`
перед/после прогона, так что на dev-данные это никогда не влияет:

```bash
docker compose up -d postgres
uv run pytest
```

Если `prostor_test` ещё не создана (например, volume `pgdata` был инициализирован до появления
`docker/init-test-db.sql`), создайте её вручную один раз:

```bash
docker exec <контейнер_postgres> psql -U prostor -d postgres -c "CREATE DATABASE prostor_test OWNER prostor;"
docker exec <контейнер_postgres> psql -U prostor -d prostor_test -c "CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS \"pgcrypto\";"
```

Чтобы указать свою тестовую БД (например, в CI), задайте `TEST_DATABASE_URL`.

## Сидирование данных

При старте (`SEED_ON_START=true`) приложение:

1. Загружает xlsx-выгрузки из `seed/xlsx/*.xlsx` (§6 SPEC) — если справочники пусты.
2. Парсит шаблоны ТЗ из `seed/tz_templates/*.docx` (§6 SPEC) — если таблица `tz_templates` пуста.
   Если конкретный docx не найден, используется дефолтная 8-блочная структура (§2.4 SPEC).

После ингеста нужно пересчитать эмбеддинги:

```bash
curl -X POST http://localhost:8000/api/v1/admin/embeddings/rebuild -d '{}'
```

## Правило «ИИ — советник»

Ни один эндпоинт не меняет поля заявки/ТЗ автоматически. ИИ-чат и `fill-ai`
возвращают предложения (`actions` / pending-черновики блоков); применение —
только через `POST /chat/sessions/{id}/apply` или `/autofill`, либо через
явный `PATCH` блока пользователем. См. §0 SPEC.md.
