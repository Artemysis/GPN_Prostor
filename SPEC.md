# ПРОСТОР 2.0 — Умный конструктор ТЗ + ИИ-агент умного поиска

## Полная спецификация для генерации backend (FastAPI) и frontend (Vite + React + TypeScript)

Этот документ — самодостаточное ТЗ для ИИ-ассистента. Отправь его целиком ассистенту, который пишет код, и он сможет начать реализацию backend и frontend «под ключ».

**LLM-провайдер:** DeepSeek (OpenAI-совместимый API). Эмбеддинги — отдельной моделью (см. §4.4).
**Frontend:** Vite + React 18 + TypeScript (строгий режим). **НЕ Next.js.** Маршрутизация — react-router-dom v6. Env-переменные фронта — с префиксом `VITE_` (читаются через `import.meta.env.VITE_*`).

---

## 0. КОНТЕКСТ ПРОЕКТА (обязательно для понимания)

Платформа ПРОСТОР — внутреннее ИТ-решение ПАО «Газпром Нефть» для регистрации заявок на нефтесервисные работы. Сейчас ТЗ прикрепляется файлом Word, что не даёт автоматизировать проверку полноты, расчёт стоимости, выявление рисков и поиск аналогов.

### ⚠️ КРИТИЧЕСКОЕ ПРАВИЛО: ИИ — СОВЕТНИК, А НЕ АВТОПИЛОТ

**ИИ НИКОГДА не заполняет поля автоматически.** Все предложения ИИ — это **черновики/рекомендации**, которые требуют **явного подтверждения пользователя** (кнопка «Применить» / «Принять» / точечный выбор). Поля заявки и ТЗ заполняются:

- **полностью вручную пользователем** (без обращения к ИИ), ИЛИ
- **пользователем совместно с ИИ** в режиме диалога: пользователь спрашивает → ИИ предлагает варианты с обоснованием → пользователь обсуждает, оспаривает, уточняет → ИИ корректирует предложение → пользователь принимает/отвергает конкретные значения.

**Запрещено**: автозаполнение шапки заявки или блоков ТЗ при создании/открытии без явного действия пользователя. Каждое изменение поля, инициированное ИИ, должно попадать в форму как **pending-предложение** (`actions`) и применяться **только** через `POST /chat/sessions/{id}/apply` или `POST /chat/sessions/{id}/autofill` (с подтверждением на фронте).

**Многоитерационный диалог**: пользователь может в течение многих реплик обсуждать с ИИ выбор подрядчика/продукта/этапов, спорить, просить альтернативы. ИИ хранит контекст сессии и адаптирует предложения. ИИ не «настаивает», а помогает принять решение.

### Объединённый пользовательский сценарий (один кейс из двух исходных)

1. Пользователь открывает интерфейс ПРОСТОР, нажимает **«Создать заявку»**.
2. Открывается **модальное окно** с пустыми полями: подрядчик, договор, продукт, стоимость, сроки и т.д. **Справа в модалке — ИИ-чат**. Возможны **два пути**:
   - **Путь A (вручную):** пользователь заполняет шапку сам, без чата.
   - **Путь B (с ИИ):** пользователь пишет промпт → ИИ **предлагает** (не применяет!) варианты: классифицирует намерение, подбирает релевантные услуги/продукты, предлагает подрядчиков с обоснованием, показывает аналогичные выполненные заявки, рекомендует связанные услуги, рекомендует тип ТЗ. Пользователь **обсуждает** выбор с ИИ, уточняет, оспаривает. Когда пользователь согласен — он **явно применяет** предложенные `actions` (точечно или пакетом) к шапке. Поля при этом помечаются `filled_by: ai` (но источник — решение пользователя).
3. После выбора типа ТЗ (вручную или по рекомендации ИИ с подтверждением) **внутри фронта** открывается шаблон ТЗ, разбитый на **блоки** (Цели, Периметр, Сроки, Содержание работ = Этапы → Требования → Ожидаемые результаты, Условия, Документация, Контроль качества, Подписи). Каждый блок можно:
   - заполнить **вручную** (сохраняется как `filled_by: manual`), ИЛИ
   - нажать **«Заполнить ИИ»** — ИИ генерирует **черновик** блока, который пользователь ревьюит и сохраняет (`filled_by: ai` или `mixed` после правок). ИИ заполняет **только тот блок, который пользователь попросил**, и не трогает остальные.
4. После заполнения (ИИ или человеком) система отображает: **процент готовности**, **выявленные риски**, **рекомендации по улучшению** на основе всей информации. Пользователь может попросить ИИ объяснить риск или дать альтернативу.
5. На выгрузку формируется: **итоговый документ ТЗ**, **все приложения** (КП, РС, etc.) и **аналитический отчёт**, созданный ИИ.

### Ключевая особенность
Конструктор не просто собирает документ, а **проверяет качество**. Пример: выбран тип «Подсчёт запасов» + указано построение 3D-геомодели → система: «Готовность 78%. Риски: не указан объект работ, 3D-модель без этапа подготовки исходных данных, не указаны требования к исходным материалам, срок ниже типового. Рекомендация: добавить исходные данные, требования к 3D-модели, проверить календарный план».

---

## 1. ТЕХНОЛОГИЧЕСКИЙ СТАК

### Backend
- **Python 3.11+**
- **FastAPI** + **Uvicorn**
- **SQLAlchemy 2.0** (async) + **Alembic** (миграции)
- **Pydantic v2** (схемы)
- **asyncpg** (драйвер PostgreSQL)
- **PostgreSQL 16** + расширение **pgvector**
- **MinIO** (S3-совместимое хранилище) через **aioboto3** / **minio** SDK
- **LLM-провайдер**: **DeepSeek** (OpenAI-совместимый API, `https://api.deepseek.com/v1`). Модель `deepseek-chat` (V3) — для чата/fill-ai/анализа; `deepseek-reasoner` (R1) — опционально для сложных рассуждений (ВНИМАНИЕ: R1 не поддерживает function calling и JSON mode — использовать только для текстовых аналитических отчётов). Доступ к API через библиотеку `openai` с `base_url`. Абстракция через интерфейс `LLMClient`.
- **Embeddings** (отдельно от DeepSeek, т.к. у DeepSeek нет embeddings-API): локальная модель `sentence-transformers` (`intfloat/multilingual-e-5-base`, 768-мерные векторы, мультиязычная, работает offline) → pgvector. Альтернатива — OpenAI `text-embedding-3-small` (1536-мерные). Размерность `LLM_EMBEDDING_DIM` должна совпадать с `vector(N)` в DDL. Для MVP рекомендуется локальная модель (без внешних зависимостей/расходов).
- **Фоновые задачи**: **Celery** + **Redis** ИЛИ **FastAPI BackgroundTasks** для MVP (тяжёлые операции: анализ ТЗ, экспорт, fill-all)
- **Стриминг ИИ-ответов**: **SSE** (Server-Sent Events) через `StreamingResponse`
- **Аутентификация**: JWT (для MVP — заглушка с одним пользователем / mock-auth)
- **Логирование**: `loguru`
- **Тесты**: `pytest` + `pytest-asyncio` + `httpx` (API-тесты)

### Frontend
- **Vite 5** + **React 18** + **TypeScript** (строгий режим, `strict: true`)
- **Маршрутизация**: **react-router-dom v6** (SPA, не Next.js)
- **Сборщик**: Vite (быстрый HMR, простой конфиг)
- **UI**: **shadcn/ui** + **Tailwind CSS** (модалки, формы, таблицы)
- **Состояние**: **Zustand** (stores) + **TanStack React Query** (server state)
- **Формы**: **react-hook-form** + **zod** (валидация по схемам из OpenAPI)
- **HTTP-клиент**: **axios** или **fetch** + типизированные эндпоинты из `openapi-typescript`
- **Чат**: SSE через `EventSource` / кастомный хук `useChatStream`
- **Редактор ТЗ**: блочный редактор (каждый блок — карточка с режимами manual/ai)
- **Графики (аналитика)**: **recharts**
- **Иконки**: lucide-react
- **Тесты**: **Vitest** + **React Testing Library**

### Инфраструктура
- **Docker Compose**: postgres (с pgvector), minio, redis, backend, frontend, worker
- **.env** для конфигурации

---

## 2. МОДЕЛЬ ДАННЫХ (PostgreSQL DDL — реализовать в Alembic)

### 2.1 Справочники (сидируются из xlsx-выгрузки ПРОСТОР)

```sql
CREATE EXTENSION IF NOT EXISTS vector;

-- Подрядчики
CREATE TABLE companies (
    company_id      TEXT PRIMARY KEY,           -- '0ddc5d9cce269'
    name            TEXT NOT NULL,              -- 'NNG'
    info            TEXT,                       -- описание
    services        TEXT,                       -- перечень услуг (текст)
    rating          INT,                        -- 1..5
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Договоры
CREATE TABLE contracts (
    contract_id     TEXT PRIMARY KEY,
    contract_number TEXT NOT NULL,              -- '001-ГНЗ-НТЦ-Д/ГНЗ'
    company_id      TEXT NOT NULL REFERENCES companies(company_id),
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Продукты (услуги)
CREATE TABLE products (
    product_id      TEXT PRIMARY KEY,
    product_name    TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Связь договор ↔ продукт (M:N)
CREATE TABLE contract_products (
    contract_id     TEXT REFERENCES contracts(contract_id),
    product_id      TEXT REFERENCES products(product_id),
    PRIMARY KEY (contract_id, product_id)
);

-- Расценки продукта (цены по ролям/категориям)
CREATE TABLE product_rates (
    price_id        TEXT PRIMARY KEY,
    product_id      TEXT NOT NULL REFERENCES products(product_id),
    price_name      TEXT NOT NULL,              -- 'ведущий юрист', 'Бурение и ВСР L2'
    measurement_name TEXT,                      -- 'Человеко-часы', 'человеко-дни'
    measurement_type TEXT                       -- 'LaborUnit', ...
);

-- Операции продукта
CREATE TABLE product_operations (
    operation_id    TEXT PRIMARY KEY,
    product_id      TEXT NOT NULL REFERENCES products(product_id),
    operation_name  TEXT NOT NULL,
    operation_order INT
);

-- Расчёты стоимости (РС — расчётные калькуляции)
CREATE TABLE cost_calculations (
    calc_id         TEXT PRIMARY KEY,
    contract_id     TEXT NOT NULL REFERENCES contracts(contract_id),
    calc_name       TEXT NOT NULL,
    calc_start_date DATE,
    calc_end_date   DATE,
    product_id      TEXT REFERENCES products(product_id)
);

-- Этапы РС (с иерархией parent_stage_id)
CREATE TABLE calculation_stages (
    stage_id            TEXT PRIMARY KEY,
    calc_id             TEXT NOT NULL REFERENCES cost_calculations(calc_id),
    parent_stage_id     TEXT REFERENCES calculation_stages(stage_id),
    stage_name          TEXT NOT NULL,
    stage_start_date    DATE,
    stage_end_date      DATE,
    stage_order_num     INT,
    stage_documentation_list TEXT                -- 'Информационный отчет, ...'
);
```

### 2.2 Шаблоны ТЗ (загружаются из docx)

```sql
-- Каталог шаблонов ТЗ (Концепт геологии, обустройства, заканчивания, развития,
-- Сопровождение инж. работ, ПТД ННГ/ДО, ПЗ Нового м-я, Приложение 2.1 Форма ТЗ)
CREATE TABLE tz_templates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code            TEXT UNIQUE NOT NULL,       -- 'concept_geology', 'concept_facilities', ...
    name            TEXT NOT NULL,
    description     TEXT,
    minio_docx_key  TEXT NOT NULL,              -- путь к исходному docx в MinIO
    blocks_schema   JSONB NOT NULL,             -- структура блоков (см. §2.3)
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Блоки шаблона (денормализованный справочник для UI)
CREATE TABLE tz_template_blocks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id     UUID NOT NULL REFERENCES tz_templates(id) ON DELETE CASCADE,
    block_code      TEXT NOT NULL,              -- 'goals', 'scope', 'terms', 'work_content', 'conditions', 'documentation', 'quality_control', 'signatures'
    block_name      TEXT NOT NULL,
    block_order     INT NOT NULL,
    json_schema     JSONB NOT NULL,             -- поля блока + типы + required + плейсхолдеры
    UNIQUE (template_id, block_code)
);

-- Этапы-скелета шаблона (для work_content): типовые этапы под тип ТЗ
CREATE TABLE tz_template_stages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id     UUID NOT NULL REFERENCES tz_templates(id) ON DELETE CASCADE,
    stage_order     INT NOT NULL,
    stage_name      TEXT NOT NULL,              -- 'Этап 1. Формирование базы данных...'
    default_requirements TEXT,                  -- подсказка ИИ/пользователю
    default_results      TEXT
);
```

### 2.3 Заявки и конструктор ТЗ

```sql
-- Пользователи (mock для MVP)
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username        TEXT UNIQUE NOT NULL,
    full_name       TEXT,
    role            TEXT DEFAULT 'customer',    -- customer | admin
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Заявка (шапка модального окна)
CREATE TABLE requests (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    number          TEXT UNIQUE,                -- 'REQ-2026-0001'
    user_id         UUID NOT NULL REFERENCES users(id),
    status          TEXT NOT NULL DEFAULT 'draft', -- draft|in_progress|ready|submitted|archived
    -- поля модалки
    company_id      TEXT REFERENCES companies(company_id),
    contract_id     TEXT REFERENCES contracts(contract_id),
    product_id      TEXT REFERENCES products(product_id),
    title           TEXT,
    description     TEXT,
    cost_total      NUMERIC(14,2),
    currency        TEXT DEFAULT 'RUB',
    date_start      DATE,
    date_end        DATE,
    -- предзаполнение из чата
    chat_session_id UUID,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- ТЗ заявки (одна заявка = одно ТЗ)
CREATE TABLE request_tz (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id      UUID NOT NULL UNIQUE REFERENCES requests(id) ON DELETE CASCADE,
    template_id     UUID NOT NULL REFERENCES tz_templates(id),
    version         INT NOT NULL DEFAULT 1,
    completeness_pct INT NOT NULL DEFAULT 0,    -- 0..100, кэш
    payload         JSONB NOT NULL DEFAULT '{}'::jsonb, -- все блоки ТЗ в JSON
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- Блоки ТЗ (дляGranular редактирования; payload в request_tz — мастер-копия)
CREATE TABLE request_tz_blocks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tz_id           UUID NOT NULL REFERENCES request_tz(id) ON DELETE CASCADE,
    block_code      TEXT NOT NULL,
    block_name      TEXT NOT NULL,
    content         JSONB NOT NULL DEFAULT '{}'::jsonb, -- значения полей
    filled_by       TEXT NOT NULL DEFAULT 'manual', -- manual | ai | mixed
    is_complete     BOOLEAN DEFAULT FALSE,
    completeness_pct INT DEFAULT 0,
    updated_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (tz_id, block_code)
);

-- Этапы работ ТЗ (внутри блока work_content)
CREATE TABLE request_tz_stages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tz_id           UUID NOT NULL REFERENCES request_tz(id) ON DELETE CASCADE,
    stage_order     INT NOT NULL,
    stage_name      TEXT NOT NULL,
    requirements    TEXT,                       -- требования к выполнению
    expected_results TEXT,                      -- ожидаемые результаты
    description     TEXT,                       -- описание работы
    stage_start_date DATE,
    stage_end_date   DATE,
    filled_by        TEXT DEFAULT 'manual'
);

-- Анализ ТЗ (риски, % готовности, рекомендации)
CREATE TABLE request_tz_analysis (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tz_id           UUID NOT NULL REFERENCES request_tz(id) ON DELETE CASCADE,
    completeness_pct INT NOT NULL,
    risks           JSONB NOT NULL DEFAULT '[]'::jsonb,     -- [{severity, category, title, description, suggestion, block_code}]
    recommendations JSONB NOT NULL DEFAULT '[]'::jsonb,    -- [{title, description, priority, block_code}]
    block_completeness JSONB NOT NULL DEFAULT '{}'::jsonb, -- {block_code: pct}
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- История изменения % готовности (аудит)
CREATE TABLE tz_completeness_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tz_id           UUID NOT NULL REFERENCES request_tz(id) ON DELETE CASCADE,
    completeness_pct INT,
    triggered_by    TEXT,                       -- user_id | 'ai'
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Документы (сгенерированные выгрузки + загруженные приложения) — MinIO
CREATE TABLE request_documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id      UUID NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
    kind            TEXT NOT NULL,              -- 'tz_final' | 'analytical_report' | 'attachment' | 'kp' | 'rs' | 'tz_template_source'
    filename        TEXT NOT NULL,
    mime_type       TEXT,
    minio_bucket    TEXT NOT NULL,
    minio_key       TEXT NOT NULL,
    size_bytes      BIGINT,
    generated_by_ai BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Чат-сессии и сообщения
CREATE TABLE chat_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id      UUID REFERENCES requests(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id),
    title           TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE chat_messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role            TEXT NOT NULL,              -- 'user' | 'assistant' | 'system'
    content         TEXT NOT NULL,
    actions         JSONB,                      -- [{type:'set_field', field:'company_id', value, confidence, justification}, {type:'suggest_template', template_id, ...}, {type:'recommend_contractors', items:[...]}]
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Фоновые задачи
CREATE TABLE jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type            TEXT NOT NULL,              -- 'analyze' | 'export' | 'fill_ai' | 'embeddings_rebuild'
    status          TEXT NOT NULL DEFAULT 'pending', -- pending|running|done|failed
    payload         JSONB,
    result          JSONB,
    error           TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- Векторные эмбеддинги (pgvector) — для семантического поиска
CREATE TABLE embeddings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type     TEXT NOT NULL,              -- 'product' | 'operation' | 'company_services' | 'tz_template' | 'request'
    entity_id       TEXT NOT NULL,
    content         TEXT NOT NULL,              -- исходный текст
    embedding       vector(1536),               -- размерность модели эмбеддингов
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON embeddings USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX ON embeddings (entity_type, entity_id);
```

### 2.4 Пример `blocks_schema` для шаблона «Концепт геологии»

```json
{
  "blocks": [
    {"code": "goals", "name": "Цели и задачи работ", "order": 1, "multiple": true, "fields": [
      {"key": "goal_text", "type": "text", "label": "Цель", "required": true},
      {"key": "tasks", "type": "list", "label": "Задачи", "required": true}
    ]},
    {"code": "scope", "name": "Периметр работ", "order": 2, "fields": [
      {"key": "location", "type": "text", "label": "Место оказания"},
      {"key": "field_name", "type": "text", "label": "Наименование месторождения", "placeholder": "{Наименование-Месторождения}"}
    ]},
    {"code": "terms", "name": "Сроки выполнения работ", "order": 3, "fields": [
      {"key": "date_start", "type": "date", "label": "Начало"},
      {"key": "date_end", "type": "date", "label": "Окончание"}
    ]},
    {"code": "work_content", "name": "Содержание работ", "order": 4, "is_stages_block": true},
    {"code": "conditions", "name": "Условия выполнения работы", "order": 5, "fields": [
      {"key": "source_data", "type": "text", "label": "Исходная информация от Заказчика"},
      {"key": "software", "type": "text", "label": "Программное обеспечение"}
    ]},
    {"code": "documentation", "name": "Требования к документации", "order": 6, "fields": [
      {"key": "report_formats", "type": "text", "label": "Форматы отчётов"}
    ]},
    {"code": "quality_control", "name": "Контроль качества", "order": 7, "fields": [
      {"key": "acceptance", "type": "text", "label": "Условия приёмки"}
    ]},
    {"code": "signatures", "name": "Подписи сторон", "order": 8, "fields": [
      {"key": "customer_signee", "type": "text", "label": "Подписант Заказчика"},
      {"key": "contractor_signee", "type": "text", "label": "Подписант Исполнителя"}
    ]}
  ]
}
```

---

## 3. РЕСТ API (полный, под префиксом `/api/v1`)

Все запросы/ответы — JSON. Коды ошибок: 400 (validation), 404, 409 (conflict), 500. Формат ошибки:
```json
{"error": {"code": "VALIDATION", "message": "...", "details": {...}}}
```

### 3.1 Справочники (read-only)

| # | Метод | Путь | Query | Ответ |
|---|---|---|---|---|
| 1.1 | GET | `/companies` | `?search=&min_rating=&limit=20&offset=0` | `[{company_id, name, info, services, rating}]` |
| 1.2 | GET | `/companies/{company_id}` | — | `{company_id, name, info, services, rating, contracts:[...]}` |
| 1.3 | GET | `/contracts` | `?company_id=&search=` | `[{contract_id, contract_number, company_id}]` |
| 1.4 | GET | `/contracts/{contract_id}` | — | `{...}` |
| 1.5 | GET | `/products` | `?contract_id=&search=&limit=` | `[{product_id, product_name}]` |
| 1.6 | GET | `/products/{product_id}` | — | `{product_id, product_name}` |
| 1.7 | GET | `/products/{product_id}/rates` | — | `[{price_id, price_name, measurement_name, measurement_type}]` |
| 1.8 | GET | `/products/{product_id}/operations` | — | `[{operation_id, operation_name, operation_order}]` |
| 1.9 | GET | `/cost-calculations` | `?contract_id=` | `[{calc_id, calc_name, calc_start_date, calc_end_date, product_id}]` |
| 1.10 | GET | `/cost-calculations/{calc_id}/stages` | — | `[{stage_id, stage_name, parent_stage_id, stage_order_num, stage_start_date, stage_end_date, stage_documentation_list}]` |

### 3.2 Шаблоны ТЗ

| # | Метод | Путь | Тело | Ответ |
|---|---|---|---|---|
| 2.1 | GET | `/tz-templates` | — | `[{id, code, name, description}]` |
| 2.2 | GET | `/tz-templates/{id}` | — | `{id, code, name, blocks_schema, blocks:[...], stages:[...]}` |
| 2.3 | GET | `/tz-templates/{id}/blocks` | — | `[{block_code, block_name, block_order, json_schema}]` |
| 2.4 | POST | `/tz-templates` (admin) | `{code, name, description, docx_file(multipart)}` | `{id, code, name}` — парсит docx → MinIO → блоки |
| 2.5 | POST | `/tz-templates/recommend` | `{prompt: string, request_context?: object}` | `{template_id, code, name, confidence, justification, suggested_fields:{...}}` |

**2.5 payload пример:**
```json
{"prompt": "Нужно оценить запасы по объекту и построить 3D-геомодель",
 "request_context": {"field_name": "Ваньгаяхинское"}}
```
**Ответ:**
```json
{
  "template_id": "uuid",
  "code": "concept_geology",
  "name": "Концепт геологии",
  "confidence": 0.92,
  "justification": "Запрос про оценку запасов и 3D-модель → продукт «Подсчет запасов» / «Концепт геологии»",
  "suggested_fields": {
    "product_id": "0f01990184d91",
    "field_name": "Ваньгаяхинское",
    "goals": ["Актуализация запасов...", "Построение 3D-геологической модели..."]
  }
}
```

### 3.3 Заявки

| # | Метод | Путь | Тело | Ответ |
|---|---|---|---|---|
| 3.1 | POST | `/requests` | `{title, description?, company_id?, contract_id?, product_id?, cost_total?, date_start?, date_end?, template_id?, chat_session_id?}` | `{id, number, status, ...}` 201 |
| 3.2 | GET | `/requests` | `?status=&user=&limit=&offset=` | `{items:[...], total}` |
| 3.3 | GET | `/requests/{id}` | — | `{... + tz_summary:{completeness_pct, risks_count}, documents_count}` |
| 3.4 | PATCH | `/requests/{id}` | частично поля шапки | `{...}` |
| 3.5 | DELETE | `/requests/{id}` | — | 204 |
| 3.6 | POST | `/requests/{id}/submit` | — | `{status:'submitted'}` |

### 3.4 Конструктор ТЗ (блочный, шаг 3)

| # | Метод | Путь | Тело | Ответ |
|---|---|---|---|---|
| 4.1 | POST | `/requests/{id}/tz` | `{template_id, prefill_from_chat?:bool}` | `{tz_id, template_id, blocks:[...], stages:[...]}` 201 |
| 4.2 | GET | `/requests/{id}/tz` | — | `{tz_id, template_id, version, completeness_pct, payload, blocks:[{block_code, content, filled_by, completeness_pct}], stages:[...]}` |
| 4.3 | PUT | `/requests/{id}/tz` | `{payload}` | `{...}` |
| 4.4 | GET | `/requests/{id}/tz/blocks` | — | `[...]` |
| 4.5 | GET | `/requests/{id}/tz/blocks/{block_code}` | — | `{block_code, content, filled_by, is_complete, completeness_pct}` |
| 4.6 | PATCH | `/requests/{id}/tz/blocks/{block_code}` | `{content, filled_by:'manual'}` | `{...}` |
| 4.7 | POST | `/requests/{id}/tz/blocks/{block_code}/fill-ai` | `{hint?:string}` (async) | `{job_id}` |
| 4.8 | POST | `/requests/{id}/tz/fill-ai` | `{blocks?:[block_code]}` (async, по умолчанию все) | `{job_id}` |
| 4.9 | GET/POST/PATCH/DELETE | `/requests/{id}/tz/stages[/{stage_id}]` | `{stage_order, stage_name, requirements, expected_results, description, stage_start_date, stage_end_date}` | `[{...}]` |

**Пример `payload` (модель ТЗ):**
```json
{
  "goals": {"goal_text": "Актуализация запасов...", "tasks": ["...","..."]},
  "scope": {"location": "г. Тюмень", "field_name": "Ваньгаяхинское"},
  "terms": {"date_start": "2026-01-12", "date_end": "2026-12-25"},
  "work_content": {
    "stages": [
      {"stage_order":1,"stage_name":"Этап 1. Формирование базы данных...",
       "requirements":"Учет всей актуальной информации",
       "expected_results":"Формирование рабочих баз данных в ПО",
       "description":"Литолого-стратиграфическое расчленение..."}
    ]
  },
  "conditions": {"source_data":"Данные отчётов по ПЗ/ОПЗ", "software":"Isoline, T-Navigator/Petrel"},
  "documentation": {"report_formats":"DOC/DOCX, PDF, XLS/XLSX"},
  "quality_control": {"acceptance":"Приёмка каждого этапа с актом сдачи-приёмки"},
  "signatures": {"customer_signee":"", "contractor_signee":""}
}
```

### 3.5 ИИ-чат в модалке (шаг 2) — **SSE-стрим для ответа**

| # | Метод | Путь | Тело | Ответ |
|---|---|---|---|---|
| 5.1 | POST | `/chat/sessions` | `{request_id?, title?}` | `{session_id}` |
| 5.2 | GET | `/chat/sessions/{id}` | — | `{session_id, request_id, messages:[...]}` |
| 5.3 | GET | `/chat/sessions/{id}/messages` | — | `[{id, role, content, actions, created_at}]` |
| 5.4 | POST | `/chat/sessions/{id}/messages` | `{content, stream:true}` | **SSE**: `data: {delta}`… `data: [DONE]` (финальный chunk содержит `actions`) |
| 5.5 | POST | `/chat/sessions/{id}/autofill` | `{actions?:[...]}` (по умолчанию последний assistant.actions) | `{applied:[{field,old,new}], request_diff:{...}, tz_diff:{...}}` |
| 5.6 | POST | `/chat/sessions/{id}/apply` | `{actions:[{type, field, value}]}` | `{applied:[...]}` |
| 5.7 | DELETE | `/chat/sessions/{id}` | — | 204 |

**Формат SSE-сообщения (5.4):**
```
data: {"type":"delta","content":"Подобрал"}
data: {"type":"delta","content":" услугу "}
data: {"type":"products","items":[{"product_id":"0f01990184d91","product_name":"Концепт геологии","justification":"..."}]}
data: {"type":"contractors","items":[{"company_id":"...","name":"NNG","rating":5,"justification":"..."}]}
data: {"type":"similar_requests","items":[{"request_id":"...","title":"...","similarity":0.87}]}
data: {"type":"actions","actions":[
  {"type":"set_field","field":"company_id","value":"0ddc5d9cce269","confidence":0.9,"justification":"..."},
  {"type":"set_field","field":"product_id","value":"0f01990184d91","confidence":0.92},
  {"type":"suggest_template","template_id":"uuid","code":"concept_geology","confidence":0.9}
]}
data: [DONE]
```

**5.5 autofill** — применяет **выбранные пользователем** `actions` к шапке заявки и (опционально) создаёт ТЗ из рекомендованного шаблона с предзаполненными блоками. **ВНИМАНИЕ**: это endpoint подтверждения — фронт сначала показывает пользователю предложения (`actions`) в виде карточек/диффа, пользователь явно нажимает «Применить» (или выбирает часть actions), и только тогда вызывается `/autofill`/`/apply`. Автоматического вызова при получении `actions` из стрима быть не должно.

### 3.6 Анализ качества ТЗ (шаг 4)

| # | Метод | Путь | Тело | Ответ |
|---|---|---|---|---|
| 6.1 | POST | `/requests/{id}/tz/analyze` | — (async) | `{job_id}` |
| 6.2 | GET | `/requests/{id}/tz/analysis` | — | `{completeness_pct, risks:[...], recommendations:[...], block_completeness:{...}, analyzed_at}` |
| 6.3 | GET | `/requests/{id}/tz/completeness` | — | `{completeness_pct, block_completeness:{...}}` |
| 6.4 | GET | `/requests/{id}/tz/risks` | — | `[{severity:'high|medium|low', category, title, description, suggestion, block_code}]` |
| 6.5 | GET | `/requests/{id}/tz/recommendations` | — | `[{title, description, priority:1..5, block_code}]` |
| 6.6 | GET | `/jobs/{job_id}` | — | `{id, type, status, result?, error?}` |

**Пример ответа 6.2:**
```json
{
  "completeness_pct": 78,
  "block_completeness": {"goals":100,"scope":50,"terms":100,"work_content":85,"conditions":60,"documentation":100,"quality_control":100,"signatures":0},
  "risks": [
    {"severity":"high","category":"missing_data","title":"Не указан объект работ","description":"Поле scope.field_name пусто","suggestion":"Укажите наименование месторождения","block_code":"scope"},
    {"severity":"high","category":"logical","title":"3D-модель без этапа подготовки исходных данных","description":"Указано построение 3D-геомодели, но отсутствует этап формирования базы данных","suggestion":"Добавить этап 1 «Формирование базы данных»","block_code":"work_content"},
    {"severity":"medium","category":"terms","title":"Заявленный срок ниже типового","description":"date_end раньше типового срока для этого типа работ (обычно 12 мес.)","suggestion":"Проверить календарный план","block_code":"terms"}
  ],
  "recommendations": [
    {"title":"Добавить исходные данные","description":"Перед согласованием необходимо добавить требования к исходным материалам","priority":1,"block_code":"conditions"},
    {"title":"Указать требования к 3D-модели","description":"Добавить раздел требований к 3D-модели в work_content","priority":2,"block_code":"work_content"},
    {"title":"Проверить календарный план","description":"Срок работ ниже типового","priority":3,"block_code":"terms"}
  ],
  "analyzed_at": "2026-08-17T12:00:00Z"
}
```

### 3.7 Выгрузка документов (шаг 5, MinIO)

| # | Метод | Путь | Тело | Ответ |
|---|---|---|---|---|
| 7.1 | POST | `/requests/{id}/export` | `{formats:['docx','pdf'], include_analytical_report:true}` (async) | `{job_id}` |
| 7.2 | POST | `/requests/{id}/export/analytical-report` | `{format:'docx|pdf'}` (async) | `{job_id}` |
| 7.3 | GET | `/requests/{id}/documents` | `?kind=` | `[{id, kind, filename, mime_type, size_bytes, generated_by_ai, created_at}]` |
| 7.4 | GET | `/documents/{doc_id}` | — | `{... + presigned_url, expires_in}` |
| 7.5 | GET | `/documents/{doc_id}/download` | — | 302 → presigned URL MinIO |
| 7.6 | POST | `/requests/{id}/attachments` | multipart `file` + `kind` | `{id, ...}` 201 |
| 7.7 | GET | `/requests/{id}/attachments` | — | `[...]` |
| 7.8 | DELETE | `/requests/{id}/attachments/{att_id}` | — | 204 |

### 3.8 Семантический поиск / ИИ-агент (Кейс 2, pgvector)

| # | Метод | Путь | Тело | Ответ |
|---|---|---|---|---|
| 8.1 | POST | `/search/semantic` | `{query, top_k=10, filters?:{company_id?,product_id?}}` | `{intent, products:[{product_id,product_name,score,justification}], contractors:[{company_id,name,rating,score,justification}], similar_requests:[...], related_services:[...]}` |
| 8.2 | POST | `/search/similar-requests` | `{query|request_id, top_k=10}` | `[{request_id, title, similarity, status}]` |
| 8.3 | POST | `/search/recommend-contractors` | `{product_id?, query?, top_k=10}` | `[{company_id, name, rating, score, justification, done_similar_count}]` |

### 3.9 Аналитика (дашборды)

| # | Метод | Путь | Ответ |
|---|---|---|---|
| 9.1 | GET | `/analytics/tz` | `{total_tz, by_type:[{type,count}], by_stage_popularity:[{stage,count}], typical_errors:[...], product_candidates:[...]}` |
| 9.2 | GET | `/analytics/search` | `{top_services:[...], service_combinations:[...], top_contractors:[...], unfilled_fields:[...], unrecognized_queries:[...]}` |

### 3.10 Админ / ингест

| # | Метод | Путь | Тело | Ответ |
|---|---|---|---|---|
| 10.1 | POST | `/admin/ingest/companies` | multipart xlsx | `{inserted, updated}` |
| 10.2 | POST | `/admin/ingest/contracts` | multipart xlsx | `{...}` |
| 10.3 | POST | `/admin/ingest/products-rates` | multipart xlsx (два файла: 3.Договор+продукты, 4.Продукты+расценки) | `{...}` |
| 10.4 | POST | `/admin/ingest/operations` | multipart xlsx | `{...}` |
| 10.5 | POST | `/admin/ingest/calculations` | multipart xlsx (2.Договор+РС) | `{...}` |
| 10.6 | POST | `/admin/embeddings/rebuild` | `{entity_types?:[]}` (async) | `{job_id}` |

### 3.11 Аутентификация (mock для MVP)

| # | Метод | Путь | Тело | Ответ |
|---|---|---|---|---|
| 11.1 | POST | `/auth/login` | `{username}` (без пароля для MVP) | `{access_token, user:{id,username,role}}` |
| 11.2 | GET | `/auth/me` | — | `{user}` |

---

## 4. LLM-ИНТЕГРАЦИЯ (контракт для backend)

**Провайдер: DeepSeek** (OpenAI-совместимый). Два интерфейса: `LLMClient` (чат, структурированный вывод, стриминг) и `EmbeddingsClient` (векторы — отдельной моделью, т.к. DeepSeek не отдаёт эмбеддинги).

### 4.1 Абстракция `LLMClient` и `EmbeddingsClient`

```python
from typing import AsyncIterator, Protocol

class LLMClient(Protocol):
    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        json_schema: dict | None = None,   # response_format json_schema (deepseek-chat поддерживает)
        stream: bool = False,
    ) -> AsyncIterator[dict]: ...

class EmbeddingsClient(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
    @property
    def dim(self) -> int: ...
```

**Реализация `DeepSeekLLMClient`** (через `openai` SDK с `base_url`):

```python
from openai import AsyncOpenAI

class DeepSeekLLMClient:
    def __init__(self, base_url: str, api_key: str, model: str = "deepseek-chat"):
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        self.model = model

    async def chat(self, messages, tools=None, json_schema=None, stream=False):
        kwargs = {"model": self.model, "messages": messages, "stream": stream}
        if tools:
            kwargs["tools"] = tools
        if json_schema:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": json_schema["name"], "schema": json_schema["schema"], "strict": True},
            }
        return await self.client.chat.completions.create(**kwargs)
```

**Реализация `LocalEmbeddingsClient`** (рекомендуется для MVP, без внешних расходов):

```python
import sentence_transformers

class LocalEmbeddingsClient:
    def __init__(self, model_name: str = "intfloat/multilingual-e5-base"):
        self.model = sentence_transformers.SentenceTransformer(model_name)
        self._dim = self.model.get_sentence_embedding_dimension()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # e5 требует префикса "query: " / "passage: " — применять при индексации и поиске
        return self.model.encode(texts, normalize_embeddings=True).tolist()

    @property
    def dim(self) -> int:
        return self._dim
```

> ⚠️ Размерность `vector(N)` в DDL (§2.3, таблица `embeddings`) и в Alembic-миграции должна быть `LLM_EMBEDDING_DIM` (для `multilingual-e5-base` = 768). Для e5 при индексации контента использовать префикс `"passage: "`, при поисковом запросе — `"query: "`.

### 4.2 Системные промпты (какая задача → какой промпт)

> ⚠️ **Везде соблюдать правило «ИИ = советник»** (см. §0): ИИ предлагает, не применяет. Все предложения отдаются как `actions` / JSON-черновик и требуют явного подтверждения пользователя.

1. **Чат-агент** (`/chat/sessions/{id}/messages`):
   - Системный промпт: «Ты — ИИ-консультант платформы ПРОСТОР. Помогаешь пользователю оформить заявку, но **НЕ принимаешь решения за него**. На основе запроса пользователя: 1) классифицируй намерение, 2) **предложи** релевантные продукты с обоснованием (используй tool-call `search_products`), 3) **предложи** подрядчиков с обоснованием (`search_contractors`), 4) покажи аналогичные заявки (`search_similar_requests`), 5) **предложи** связанные услуги, 6) верни `actions` — это **предложения** для применения пользователем, а не автоматические изменения, 7) **рекомендуй** тип ТЗ (`recommend_template`). Если пользователь сомневается/оспаривает — приведи альтернативы, обсуди за и против. Всегда возвращай обоснования и **не применяй** ничего автоматически.»
   - Tools: `search_products(query)`, `search_contractors(product_id, top_k)`, `search_similar_requests(query)`, `recommend_template(prompt)`, `list_template_types()`. ⚠️ **НЕ делать** tool `set_request_field` — поля заполняются только через `actions` + `/apply`/`/autofill` с подтверждением пользователя.
   - RAG: в контекст подкладываются топ-K продуктов/компаний из pgvector по эмбеддингу запроса.
   - История сессии передаётся в каждый запрос (многоитерационный диалог).

2. **Заполнение блока ТЗ** (`fill-ai`) — вызывается **только** по явному действию пользователя (кнопка «Заполнить ИИ» на конкретном блоке):
   - Промпт: «Заполни блок `{block_name}` ТЗ типа `{template_name}` как **черновик**. Контекст заявки: {request+other_blocks}. Верни JSON по схеме: {json_schema}. Используй доменные знания нефтегазовой отрасли. Это предложение — пользователь будет ревьюить.»
   - Function calling / JSON-mode (`response_format: json_schema`) для структурированного вывода.
   - Результат сохраняется в `request_tz_blocks` с `filled_by: 'ai'` и **отдаётся в UI как pending-черновик** для подтверждения. Пользователь может отредактировать → тогда `filled_by` становится `'mixed'`.

3. **Анализ ТЗ** (`analyze`) — вызывается по кнопке «Анализировать»:
   - Промпт: «Проанализируй ТЗ. Версия: {payload}. Шаблон: {template}. Для каждого блока вычисли % заполнения. Найди риски (missing_data, logical, terms, compliance). Дай рекомендации. Верни JSON по схеме ответа 6.2. Учти бизнес-правила (пример: 3D-геомодель требует этапа подготовки исходных данных; типовой срок по типу работ = 12 мес.; обязательно указать объект работ и т.д.).»
   - Можно использовать `deepseek-reasoner` для более глубокого анализа (без JSON-mode — тогда парсить JSON из контента).
   - RAG по историческим ТЗ и НМД (если загрузить).

4. **Аналитический отчёт ИИ** (для экспорта) — `deepseek-chat` или `deepseek-reasoner`:
   - Промпт: «Сформируй аналитический отчёт по ТЗ {payload} и результатам анализа {analysis}. Разделы: сводка, качество ТЗ, риски, рекомендации, сравнение с типовым, прогноз сроков/стоимости. Стиль — деловой, для руководителя.»
   - Это текстовый документ (не JSON), идёт в docx-генератор.

5. **Рекомендация шаблона ТЗ** (`/tz-templates/recommend`) — `deepseek-chat` с JSON-mode:
   - Промпт: «Выбери подходящий тип ТЗ из списка {[code,name,description]} под запрос пользователя `{prompt}`. Верни JSON {template_id, confidence, justification, suggested_fields} с полями, которые можно извлечь из запроса. Это **рекомендация** — пользователь подтвердит выбор.»

### 4.3 Эмбеддинги в pgvector

Что индексируется (entity_type, content):
- `product` — `passage: ` + `product_name + список operations + rates`
- `company_services` — `passage: ` + `services` поле companies
- `tz_template` — `passage: ` + `name + description + блоки (схема как текст)`
- `request` — `passage: ` + `title + description + payload (текстовое представление блоков)` (для `/search/similar-requests`)

При поиске — запрос пользователя оборачивается префиксом `query: ` и векторизуется, дальше `embedding <=> query_vector` (cosine distance) в pgvector, `ORDER BY` + `LIMIT top_k`.

Эмбеддинги пересчитываются через `/admin/embeddings/rebuild` после ингеста или при сохранении ТЗ (для `entity_type='request'`).

### 4.4 Выбор модели по задаче (шпаргалка)

| Задача | Модель DeepSeek | JSON-mode | Стриминг |
|---|---|---|---|
| Чат-агент в модалке | `deepseek-chat` | + (для actions в финале) | + (SSE) |
| fill-ai блока ТЗ | `deepseek-chat` | + (json_schema) | опц. |
| Рекомендация шаблона ТЗ | `deepseek-chat` | + (json_schema) | нет |
| Анализ ТЗ (риски/%) | `deepseek-chat` (быстро) ИЛИ `deepseek-reasoner` (глубже) | + для chat / парсить из контента для reasoner | нет |
| Аналитический отчёт | `deepseek-reasoner` | нет (текст) | опц. |

---

## 5. MINIO — БАКЕТЫ

| Бакет | Назначение | Пример ключа |
|---|---|---|
| `prostor-tz-templates` | исходные docx шаблонов | `templates/{template_id}.docx` |
| `prostor-exports` | сгенерённые выгрузки (ТЗ, аналит. отчёт, КП, РС) | `exports/{request_id}/{document_id}.docx` |
| `prostor-attachments` | приложения, загруженные пользователем | `attachments/{request_id}/{attachment_id}.{ext}` |
| `prostor-ingest` | загруженные xlsx-выгрузки из системы | `ingest/{timestamp}_{type}.xlsx` |

- Отдача через **presigned URL** (GET `/documents/{id}` → `presigned_url` с TTL 15 мин).
- Загрузка через multipart напрямую в backend (прокси в MinIO) — для простоты MVP.

---

## 6. ПАРСЕР DOCX ШАБЛОНОВ (для `/tz-templates` POST и сидирования)

Реализовать модуль `app/services/docx_parser.py`:
1. Открывает docx (python-docx).
2. Извлекает структуру по заголовкам (Heading 1/2/3) → блоки.
3. Распознаёт плейсхолдеры `{...}` → превращает в поля схемы с `placeholder`.
4. Распознаёт таблицы «Требования / Ожидаемые результаты» → `work_content` с этапами.
5. Формирует `blocks_schema` (JSONB) и `tz_template_stages` (скелет этапов).
6. Загружает исходный docx в MinIO.

**Сидирование**: при старте приложения, если `tz_templates` пуст, парсит все docx из папки `seed/tz_templates/` и создаёт записи. Список шаблонов:
- `ТЗ Концепт геологии`
- `ТЗ Концепт обустройства`
- `ТЗ Интегрированный концепт заканчивания`
- `ТЗ Интегрированный концепт развития`
- `ТЗ Сопровождение инженерных работ и высокорисковых операций`
- `Приложение 1. ТЗ (шаблон ПТД ННГ)_2026`
- `Приложение 1. ТЗ (шаблон ПТД ДО)_2026`
- `Приложение 1. ТЗ (ПЗ Нового м-я)`
- `Приложение 3. ТЗ ПТД_ОПЗ УВС Песц НГКМ`
- `Прил 1_ТЗ_ПТД`
- `Приложение № 2.1 Форма Технического задания`

**Парсер xlsx-ингеста** `app/services/xlsx_parser.py` — читает выгрузки ПРОСТОР по схемам из §2.1 и заливает в БД. Файлы:
- `0. Компании.xlsx` → companies
- `1. Договоры.xlsx` → contracts
- `2. Договор + РС.xlsx` → cost_calculations, calculation_stages
- `3. Договор + продукты.xlsx` → products, contract_products
- `4. Продукты + расценки.xlsx` → product_rates
- `5. Продукты + Операции.xlsx` → product_operations

---

## 7. СТРУКТУРА ПРОЕКТА (backend)

```
prostor-backend/
├── app/
│   ├── main.py                  # FastAPI app, роутеры, CORS, lifespan (сидирование)
│   ├── core/
│   │   ├── config.py            # pydantic-settings: DB, MinIO, LLM, JWT
│   │   ├── deps.py              # зависимости: get_db, get_current_user, get_llm, get_minio
│   │   └── security.py          # JWT mock
│   ├── db/
│   │   ├── base.py              # Base, engine, Session
│   │   ├── models.py            # SQLAlchemy ORM (все таблицы §2)
│   │   └── session.py
│   ├── schemas/                 # Pydantic v2
│   │   ├── company.py contract.py product.py request.py tz.py chat.py analysis.py document.py job.py
│   ├── api/v1/
│   │   ├── companies.py contracts.py products.py calculations.py
│   │   ├── tz_templates.py requests.py tz.py chat.py analysis.py documents.py search.py analytics.py admin.py auth.py
│   ├── services/
│   │   ├── llm_client.py        # OpenAI-совместимый клиент
│   │   ├── embeddings.py        # embed + pgvector upsert
│   │   ├── semantic_search.py   # search/semantic, similar, recommend
│   │   ├── tz_builder.py        # создание ТЗ из шаблона, автозаполнение
│   │   ├── tz_analyzer.py       # анализ рисков/готовности
│   │   ├── tz_exporter.py       # генерация docx/pdf (python-docx + reportlab/weasyprint)
│   │   ├── docx_parser.py       # парсер шаблонов
│   │   ├── xlsx_parser.py       # ингест выгрузки
│   │   ├── minio_client.py      # S3 клиент, presigned URL
│   │   └── jobs.py              #Celery tasks ИЛИ BackgroundTasks
│   ├── repositories/            # тонкий слой доступа к данным (опционально)
│   └── utils/
├── alembic/                     # миграции
├── seed/
│   ├── tz_templates/*.docx
│   └── xlsx/*.xlsx
├── tests/
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml / requirements.txt
├── .env.example
└── README.md
```

---

## 8. СТРУКТУРА ПРОЕКТА (frontend)

```
prostor-frontend/
├── src/
│   ├── main.tsx                  # точка входа Vite, провайдеры (Router, QueryClient, Zustand)
│   ├── App.tsx                   # корневой компонент + <Routes>
│   ├── routes/                   # страницы (react-router-dom v6)
│   │   ├── RootLayout.tsx        # лэйаут: сайдбар + <Outlet/>
│   │   ├── Login.tsx
│   │   ├── RequestsList.tsx      # список заявок
│   │   ├── RequestDetail.tsx     # карточка заявки + ТЗ
│   │   ├── Analytics.tsx         # дашборды
│   │   └── Admin.tsx             # ингест
│   ├── components/
│   │   ├── requests/
│   │   │   ├── RequestList.tsx
│   │   │   ├── CreateRequestModal.tsx   # МОДАЛКА (шаги 1–5)
│   │   │   ├── RequestHeaderForm.tsx    # шапка: подрядчик/договор/продукт/стоимость/сроки
│   │   │   ├── AiChat.tsx               # чат справа, SSE
│   │   │   ├── ChatMessage.tsx          # рендер actions (карточки продуктов/исполнителей/apply-кнопки)
│   │   │   ├── TzBuilder.tsx            # блочный редактор ТЗ
│   │   │   ├── TzBlockCard.tsx          # один блок (manual/ai-fill кнопка)
│   │   │   ├── TzStageEditor.tsx        # этапы внутри work_content
│   │   │   ├── TzAnalysisPanel.tsx      # % готовности, риски, рекомендации (шаг 4)
│   │   │   └── ExportPanel.tsx          # выгрузка (шаг 5)
│   │   ├── ui/                       # shadcn-компоненты
│   │   └── shared/
│   ├── lib/
│   │   ├── api/                      # типизированные клиенты (openapi-typescript)
│   │   │   ├── client.ts             # axios-инстанс + интерсепторы (JWT, baseURL из env)
│   │   │   ├── types.ts              # сгенерённые TS-типы из /openapi.json
│   │   │   └── endpoints/            # по файлу на группу ручек
│   │   ├── stores/                   # zustand: useRequestStore, useChatStore, useTzStore
│   │   ├── hooks/
│   │   │   ├── useChatStream.ts      # SSE хук (EventSource + парсинг delta/actions)
│   │   │   ├── useTzAnalysis.ts
│   │   │   ├── useAutofill.ts
│   │   │   └── useJobPolling.ts      # polling /jobs/{id}
│   │   ├── schemas/                  # zod-схемы (из openapi / вручную)
│   │   └── utils/
├── public/
├── index.html                    # Vite entry
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json                 # strict: true
├── package.json
└── Dockerfile
```

### UX-последовательность в `CreateRequestModal.tsx`

> ⚠️ Главный принцип: **ИИ предлагает — пользователь решает.** Поля не меняются сами. Любое действие ИИ требует явного подтверждения. Пользователь может вообще не пользоваться чатом и заполнить всё вручную.

1. Модалка открывается → **пустая** шапка (пользователь может начать заполнять сам) + чат справа.
2. **Путь пользователя выбирается свободно:**
   - **Вручную:** пользователь вводит подрядчика/договор/продукт/стоимость/сроки сам → переходит к шагу 4.
   - **С ИИ:** пользователь пишет промпт → SSE-стрим → приходят `products`, `contractors`, `similar_requests`, `actions` как **предложения**.
3. В чате рендерятся карточки предложений (продукт + обоснование, подрядчик + рейтинг + обоснование, аналог). У каждого — кнопки «Применить» / «Применить всё» / «Отклонить». Пользователь может **отвечать в чат**, оспаривать, просить альтернативы — ИИ уточняет. Только после нажатия «Применить» вызывается `/chat/sessions/{id}/apply` (точечно) или `/autofill` (пакетом), и поля шапки обновляются с пометкой `filled_by: ai`.
4. Тип ТЗ: либо пользователь выбирает сам из списка (`GET /tz-templates`), либо принимает рекомендацию ИИ из `actions` (кнопка «Создать ТЗ из рекомендации») → `POST /requests/{id}/tz` (с prefill из чата, но блоки всё равно проверяются пользователем) → открывается `TzBuilder`.
5. `TzBuilder` рендерит блоки по `blocks_schema`. Каждый блок — карточка с двумя режимами:
   - **ручной** — пользователь вводит поля → `PATCH /requests/{id}/tz/blocks/{block_code}` (`filled_by: manual`),
   - **ИИ-черновик** — кнопка «Заполнить ИИ» → `POST /fill-ai` → блок получает **pending-черновик** → пользователь ревьюит, правит, подтверждает сохранение (`filled_by: ai` → `mixed` при правках). ИИ заполняет **только этот блок**, остальные не трогает.
6. `work_content` — отдельный `TzStageEditor` (этапы: имя, требования, результаты, сроки). Этапы можно добавлять/редактировать вручную или попросить ИИ дополнить.
7. После изменений — debounce-вызов `GET /requests/{id}/tz/completeness` → прогресс-бар (пересчёт детерминированный, без ИИ).
8. Кнопка «Анализировать» → `POST /analyze` → polling `/jobs/{id}` → `TzAnalysisPanel` показывает %, риски, рекомендации. По каждому риску — кнопка «Объяснить» / «Исправить с ИИ» (открывает контекст в чат).
9. Кнопка «Выгрузить» → `POST /export` → polling → список документов (`/documents`) с download-ссылками: ТЗ, приложения, аналит. отчёт ИИ.

---

## 9. ПОРЯДОК РЕАЛИЗАЦИИ (рекомендованный для ИИ-кодера)

### Backend — этап 1 (MVP-ядро, ~3 дня)
1. Скелет FastAPI + config + Docker Compose (pg+pgvector, minio, redis, backend).
2. Alembic: все таблицы §2.1 + §2.2 + §2.3.
3. ORM-модели, Pydantic-схемы.
4. Сидирование из `seed/xlsx/*.xlsx` через `xlsx_parser.py` при старте (если БД пуста).
5. Сидирование шаблонов ТЗ из `seed/tz_templates/*.docx` через `docx_parser.py`.
6. Справочники: §3.1 (companies, contracts, products, calculations) — read-only ручки.
7. Заявки: §3.3 (CRUD).
8. Шаблоны ТЗ: §3.2 (list, get, recommend-заглушка через LLM).

### Backend — этап 2 (конструктор + чат, ~3 дня)
9. ТЗ: §3.4 (create из шаблона, get, PATCH блоков, stages CRUD).
10. LLM-клиент + embeddings (pgvector upsert после ингеста).
11. Чат: §3.5 (sessions, messages, **SSE-стрим** с actions).
12. `fill-ai` блоков (§3.4.7–8) через LLM JSON-mode.
13. `autofill`/`apply` (§3.5.5–6).

### Backend — этап 3 (анализ + экспорт + поиск, ~2 дня)
14. Анализ ТЗ: §3.6 (`analyze` async, `analysis`, `risks`, `recommendations`).
15. Экспорт: §3.7 (`export` → docx через python-docx, аналит. отчёт ИИ).
16. MinIO: загрузка/скачивание, presigned URL.
17. Семантический поиск: §3.8 (pgvector cosine).
18. Аналитика: §3.9 (агрегатные запросы).
19. Админ-ингест: §3.10.

### Frontend — параллельно
20. Скелет Vite + React + TS + shadcn + Tailwind + zustand + react-query + react-router.
21. Сгенерировать API-клиент из OpenAPI (FastAPI отдаёт `/openapi.json`).
22. Экраны: список заявок, `CreateRequestModal` (шапка + чат + TZBuilder + Analysis + Export).
23. SSE-хук для чата.
24. Дашборды аналитики (recharts).

### Тесты (бонус на хакатоне)
25. `tests/api/test_companies.py`, `test_requests.py`, `test_tz.py`, `test_chat.py` (httpx + AsyncClient), `test_analysis.py` (mock LLM).

---

## 10. БИЗНЕС-ПРАВИЛА (для анализатора ТЗ — реализовать как набор правил + LLM)

- Если тип ТЗ = «Концепт геологии» / «Подсчет запасов» и указано построение 3D-геомодели → должен быть этап «Формирование базы данных» / «Подготовка исходных данных».
- Обязательно поле `scope.field_name` (объект работ).
- Срок `terms.date_end - date_start` < типового (по типу ТЗ, например 12 мес.) → риск `terms:below_typical`.
- Если выбран продукт с операциями → в `work_content` должны быть отражены ключевые операции.
- Блок `signatures` обязателен для готовности 100%, но не блокирует черновик.
- Каждое обязательное поле блока (`required:true` в json_schema) влияет на `completeness_pct` блока.
- `completeness_pct` ТЗ = среднее (взвешенное) по блокам; веса задаются в `blocks_schema` (по умолчанию равны).

---

## 11. КОНФИГ (.env.example)

```env
# DB
POSTGRES_USER=prostor
POSTGRES_PASSWORD=prostor
POSTGRES_DB=prostor
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
DATABASE_URL=postgresql+asyncpg://prostor:prostor@postgres:5432/prostor

# MinIO
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_SECURE=false
MINIO_BUCKET_TEMPLATES=prostor-tz-templates
MINIO_BUCKET_EXPORTS=prostor-exports
MINIO_BUCKET_ATTACHMENTS=prostor-attachments
MINIO_BUCKET_INGEST=prostor-ingest

# LLM (DeepSeek — OpenAI-совместимый API)
LLM_API_BASE=https://api.deepseek.com/v1
LLM_API_KEY=sk-...твой_токен_deepseek...
LLM_MODEL=deepseek-chat
LLM_REASONER_MODEL=deepseek-reasoner
# Использовать deepseek-reasoner для аналит. отчёта и (опц.) анализа ТЗ
LLM_USE_REASONER_FOR_ANALYSIS=false
LLM_USE_REASONER_FOR_REPORT=true

# Embeddings (отдельно от DeepSeek — у него нет embeddings API)
# Вар. 1 (рекомендуется для MVP): локальная sentence-transformers
EMBEDDINGS_PROVIDER=local
EMBEDDINGS_MODEL=intfloat/multilingual-e5-base
LLM_EMBEDDING_DIM=768
# Вар. 2: OpenAI (если есть ключ)
# EMBEDDINGS_PROVIDER=openai
# EMBEDDINGS_API_BASE=https://api.openai.com/v1
# EMBEDDINGS_API_KEY=sk-...
# EMBEDDINGS_MODEL=text-embedding-3-small
# LLM_EMBEDDING_DIM=1536

# Redis / Celery (опционально)
REDIS_URL=redis://redis:6379/0
USE_CELERY=false

# Auth
JWT_SECRET=change-me
JWT_ALG=HS256
JWT_TTL_HOURS=24

# App
ENV=development
CORS_ORIGINS=http://localhost:3000
SEED_ON_START=true
```

---

## 12. docker-compose.yml (скелет)

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: prostor
      POSTGRES_PASSWORD: prostor
      POSTGRES_DB: prostor
    ports: ["5432:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    ports: ["9000:9000", "9001:9001"]
    volumes: [miniodata:/data]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  backend:
    build: ./prostor-backend
    env_file: .env
    depends_on: [postgres, minio, redis]
    ports: ["8000:8000"]
    volumes:
      - ./prostor-backend:/app
      - ./seed:/app/seed

  frontend:
    build: ./prostor-frontend
    environment:
      VITE_API_URL: http://localhost:8000/api/v1
    depends_on: [backend]
    ports: ["3000:3000"]   # Vite dev server (npm run dev -- --host) или preview после build

volumes:
  pgdata:
  miniodata:
```

---

## 13. ЧЕК-ЛИСТ ПРИЁМКИ MVP

- [ ] Сиды (companies, contracts, products, rates, operations, calculations, tz_templates) загружаются при первом старте.
- [ ] `GET /companies`, `/products`, `/contracts`, `/cost-calculations` работают.
- [ ] `POST /requests` создаёт заявку, `GET /requests` отдаёт список.
- [ ] `POST /tz-templates/recommend` возвращает рекомендацию шаблона по промпту.
- [ ] `POST /chat/sessions/{id}/messages` стримит SSE с actions.
- [ ] `POST /chat/sessions/{id}/autofill` применяет actions к заявке и создаёт ТЗ с предзаполнением.
- [ ] `POST /requests/{id}/tz` создаёт ТЗ из шаблона.
- [ ] `PATCH /requests/{id}/tz/blocks/{block_code}` сохраняет ручные правки.
- [ ] `POST /requests/{id}/tz/blocks/{block_code}/fill-ai` заполняет блок ИИ.
- [ ] `GET /requests/{id}/tz/completeness` возвращает %.
- [ ] `POST /requests/{id}/tz/analyze` → `GET /requests/{id}/tz/analysis` показывает риски + рекомендации.
- [ ] `POST /requests/{id}/export` генерирует docx ТЗ + аналит. отчёт, `GET /documents/{id}/download` отдаёт файл.
- [ ] `POST /search/semantic` отдаёт продукты/исполнителей/аналоги по NL-запросу.
- [ ] Фронт: модалка создания заявки с чатом, блочный редактор ТЗ, панель анализа, выгрузка — работают end-to-end.
- [ ] Дашборды аналитики отображаются.

---

## 14. ИНСТРУКЦИЯ ИИ-КОДЕРУ

1. Создай два проекта: `prostor-backend` (FastAPI) и `prostor-frontend` (Vite + React + TypeScript) в репозитории.
2. Начни с backend: скелет → Docker Compose → Alembic → модели → сидирование → справочники → заявки → ТЗ → чат → анализ → экспорт → поиск → аналитика.
3. Параллельно поднимай frontend по структуре §8.
4. Все LLM-вызовы — через `LLMClient` с поддержкой стриминга и function-calling / JSON-mode.
5. Все тяжёлые операции — через `jobs` (async + polling).
6. Все файлы — в MinIO, отдача через presigned URL.
7. Используй **только** зависимости из `requirements.txt` (FastAPI, SQLAlchemy 2 async, asyncpg, alembic, pydantic v2, python-docx, openpyxl, aioboto3, openai, sentence-transformers, pgvector, loguru, pytest).
8. Код — на английском (идентификаторы), пользовательские строки/промпты — на русском (домен российский).
9. Не добавляй комментарии, если не просят; пиши чисто и идиоматично.
10. После реализации каждого этапа запускай `pytest` и `alembic upgrade head`.

**Цель MVP**: продемонстрировать на демо полный сценарий §0: пользователь пишет в чат «Нужно оценить запасы по объекту и построить 3D-модель» → ИИ предзаполняет заявку и рекомендует ТЗ «Концепт геологии» → пользователь правит блоки вручную и через «Заполнить ИИ» → система показывает «Готовность 78%, риски: …, рекомендации: …» → пользователь выгружает итоговый ТЗ + аналит. отчёт.
