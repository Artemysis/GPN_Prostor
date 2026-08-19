# ПРОСТОР 2.0 — Умный конструктор ТЗ + ИИ-агент умного поиска

Прототип модуля платформы **ПРОСТОР** (ПАО «Газпром Нефть») для регистрации заявок на нефтесервисные работы. Объединяет два кейса хакатона в одном приложении с общей навигацией:

- **Кейс 1. Умный конструктор ТЗ** — сборка технического задания из типовых блоков вместо загрузки файла Word, с проверкой полноты, рисками и рекомендациями.
- **Кейс 2. ИИ-агент умного поиска** — чат-консультант на естественном языке, который подбирает услуги и подрядчиков и позволяет одним переходом сформировать ТЗ в конструкторе с предзаполненными данными.


## Состав репозитория

| Каталог | Назначение | README |
|---|---|---|
| [`backend/`](backend) | FastAPI-бэкенд: REST API, БД, LLM-интеграция, экспорт документов | [backend/README.md](backend/README.md) |
| [`frontend/`](frontend) | Vite + React + TypeScript SPA | [frontend/README.md](frontend/README.md) |
| [`ci/`](ci) | Скрипты для локального прогона docker-compose (up/down/logs/smoke) | [ci/README.md](ci/README.md) |
| [`docs/`](docs) | Диаграммы (use case) | — |
| [`seed/`](seed) | Данные для сидирования: xlsx-выгрузки справочников и docx-шаблоны ТЗ | — |

## Технологический стек

**Backend:** FastAPI · SQLAlchemy 2 (async) + Alembic · PostgreSQL 16 + pgvector · MinIO · DeepSeek (OpenAI-совместимый API) · sentence-transformers (эмбеддинги).

**Frontend:** Vite + React 18 + TypeScript (strict) · react-router-dom v6 · shadcn/ui + Tailwind CSS · Zustand + TanStack Query · react-hook-form + zod · recharts.

**Инфраструктура:** Docker Compose (postgres, minio, redis, backend, frontend).


## Быстрый старт

```bash
cp .env.example .env
docker compose up -d
```

Поднимает весь стек целиком (postgres, minio, redis, backend, frontend); frontend — на `http://localhost:3000`.

## Правило «ИИ — советник»

Ни один эндпоинт не меняет поля заявки или ТЗ автоматически. ИИ-чат и «Заполнить ИИ» возвращают предложения (`actions` / pending-черновики блоков); применение — только через явное действие пользователя (`POST /chat/sessions/{id}/apply`, `/autofill` или `PATCH` блока). Подробности — §0 и §4.2 [SPEC.md](SPEC.md).
