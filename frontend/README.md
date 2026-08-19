# ПРОСТОР 2.0 — Frontend

SPA-фронтенд конструктора ТЗ и ИИ-агента умного поиска (см. `../SPEC.md`, разделы 8 и далее).

## Стек

Vite 5 · React 18 · TypeScript (strict) · react-router-dom v6 (SPA, не Next.js) ·
shadcn/ui + Tailwind CSS · Zustand (клиентское состояние) + TanStack React Query
(server state) · react-hook-form + zod · axios · recharts (аналитика) ·
Vitest + React Testing Library + MSW (тесты).

## Быстрый старт

Требуется запущенный backend (локально или в Docker) — см. `../backend/README.md` или корневой `../README.md`.

```bash
cd frontend
npm install
npm run dev
```

Dev-сервер поднимется на `http://localhost:3000` (порт зафиксирован в `vite.config.ts`, `strictPort: true`).

### Через Docker Compose (из корня репозитория)

```bash
cp ../.env.example ../.env
docker compose up -d frontend
```

Собирается по `frontend/Dockerfile` (multi-stage: сборка Vite → nginx), отдаётся на `http://localhost:3000`, проксирует `/api` на backend-контейнер (см. `nginx.conf`).

## Переменные окружения

Все переменные — с префиксом `VITE_`, читаются через `import.meta.env.VITE_*`. Задаются в `.env` (для `npm run dev`) или как build-arg (`VITE_API_URL` в `docker-compose.yml` для сборки образа).

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000/api/v1` | Базовый URL backend REST API (см. `src/lib/api/client.ts`) |

## Скрипты

| Команда | Назначение |
|---|---|
| `npm run dev` | Dev-сервер с HMR |
| `npm run build` | Проверка типов (`tsc --noEmit`) + продакшн-сборка Vite |
| `npm run preview` | Локальный просмотр продакшн-сборки |
| `npm run typecheck` | Только проверка типов |
| `npm run test` | Тесты (Vitest, `vitest run`) |

## Структура

```
src/
├── main.tsx                  # точка входа: Router, QueryClient, Zustand-провайдеры
├── App.tsx                   # корневой компонент с <Routes>
├── routes/                   # страницы
│   ├── Login.tsx
│   ├── RequestsList.tsx      # список заявок
│   ├── RequestDetail.tsx     # карточка заявки + конструктор ТЗ
│   ├── Analytics.tsx         # дашборды (Кейс 1 + Кейс 2)
│   └── Admin.tsx             # ингест справочников
├── components/
│   ├── requests/
│   │   ├── CreateRequestModal.tsx  # модалка создания заявки (шаги 1–5 сценария)
│   │   ├── RequestHeaderForm.tsx   # шапка: подрядчик/договор/продукт/стоимость/сроки
│   │   ├── AiChat.tsx              # ИИ-чат справа от шапки, SSE-стрим
│   │   ├── ChatMessage.tsx         # рендер actions (карточки продуктов/исполнителей, apply)
│   │   ├── TzBuilder.tsx           # блочный редактор ТЗ
│   │   ├── TzBlockCard.tsx         # один блок ТЗ (manual / «Заполнить ИИ»)
│   │   ├── TzStageEditor.tsx       # этапы работ внутри блока work_content
│   │   ├── TzAnalysisPanel.tsx     # % готовности, риски, рекомендации
│   │   ├── EstimatedCostCard.tsx   # оценка стоимости
│   │   ├── ExportPanel.tsx         # выгрузка итоговых документов
│   │   └── RequestWorkspace.tsx    # композиция шагов конструктора внутри заявки
│   ├── layout/                # общая навигация приложения
│   ├── ui/                    # shadcn-компоненты
│   └── shared/
├── lib/
│   ├── api/                   # HTTP-клиент и типы
│   │   ├── client.ts          # axios-инстанс, VITE_API_URL
│   │   ├── httpApi.ts         # типизированные вызовы эндпоинтов
│   │   ├── drafts.ts          # работа с pending-предложениями ИИ (actions)
│   │   └── types.ts           # типы запросов/ответов API
│   ├── hooks/
│   │   ├── useChatStream.ts   # SSE-хук для чата (EventSource, парсинг delta/actions)
│   │   └── useJobPolling.ts   # поллинг фоновых задач (`/jobs/{id}`)
│   └── stores/                # zustand: authStore, uiStore
└── __tests__/                 # unit / components / e2e / msw-моки
```

## Ключевое правило: ИИ — советник

Компоненты `AiChat`/`ChatMessage`/`TzBlockCard` показывают предложения ИИ (`actions`,
черновики блоков ТЗ) как **pending**-состояние с явной кнопкой подтверждения
(«Применить»/«Принять»). Ни один хук не применяет `actions` автоматически при получении
из SSE-стрима — применение всегда идёт через отдельный вызов API (`/apply`, `/autofill`,
`PATCH` блока) по действию пользователя. См. §0 `../SPEC.md`.

## Тесты

Vitest + React Testing Library, HTTP замоканы через MSW (`src/__tests__/msw`). Юнит- и
компонентные тесты — `src/__tests__/unit`, `src/__tests__/components`; сценарные —
`src/__tests__/e2e`.

```bash
npm run test
```
