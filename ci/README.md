# CI — локальный стенд ПРОСТОР 2.0

Один скрипт поднимает всё приложение целиком в Docker: базу (PostgreSQL + pgvector),
MinIO, Redis, backend (FastAPI) и frontend (React SPA за nginx).

## Быстрый старт

```powershell
.\ci\up.ps1
```

Что делает скрипт:
1. Создаёт `.env` из `.env.example`, если его ещё нет (и предупреждает про пустой `LLM_API_KEY`).
2. Собирает образы (первая сборка долгая — качаются Python/Node/PyTorch).
3. Поднимает контейнеры, прогоняет миграции БД (`alembic upgrade head`) и сеет справочники.
4. Ждёт готовности backend и frontend, печатает адреса.

## Адреса стенда

| Что | URL |
|---|---|
| Frontend (SPA) | http://localhost:3000 |
| Backend API + Swagger | http://localhost:8000/docs |
| Health-check | http://localhost:8000/health |
| MinIO Console | http://localhost:9001 (minioadmin/minioadmin) |

## Команды

| Скрипт | Что делает |
|---|---|
| `.\ci\up.ps1` | собрать и поднять стенд |
| `.\ci\smoke.ps1` | проверки: health, API, SPA, прокси nginx -> backend |
| `.\ci\logs.ps1` | логи всех контейнеров (Ctrl+C — выйти); можно `.\ci\logs.ps1 backend` |
| `.\ci\down.ps1` | остановить стенд (данные остаются в docker-томах) |
| `.\ci\down.ps1 -Volumes` | остановить и удалить тома (полный сброс БД и файлов) |

## Конфигурация

Все настройки — в корневом `.env` (см. `.env.example`). Для ИИ-функций
(чат, fill-ai, анализ ТЗ) обязательно заполните `LLM_API_KEY` — ключ DeepSeek.
Без ключа стенд поднимется, но ИИ-эндпоинты будут возвращать ошибки.

## Как устроено

- `frontend/Dockerfile` — двухэтапная сборка: Node 20 собирает SPA (`VITE_API_URL=/api/v1`),
  nginx раздаёт статику и проксирует `/api/` на backend (SSE-стриминг поддержан,
  `proxy_buffering off`).
- `backend/Dockerfile` — Python 3.13 + `uv sync` по lock-файлу, старт с миграциями.
- `docker-compose.yml` — postgres (pgvector), minio, redis, backend (+healthcheck), frontend.
