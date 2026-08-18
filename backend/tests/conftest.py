"""Инфраструктура тестов ПРОСТОР 2.0 (backend).

Принципы:
- Тесты выполняются на отдельной PostgreSQL-базе (по умолчанию ``prostor_test``),
  которая создаётся и удаляется автоматически. Dev-база не затрагивается.
- Все внешние сервисы замоканы: DeepSeek LLM, embeddings, MinIO.
- ENV-переменные выставляются ДО импорта приложения (pydantic-settings кэшируется).

Запуск:  python -m pytest  (из каталога backend/)
"""

import asyncio
import hashlib
import math
import os
import re
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

# --- Окружение тестов: ДО импорта модулей приложения ----------------------
TEST_DB_NAME = os.environ.get("PROSTOR_TEST_DB", "prostor_test")
PG_USER = os.environ.get("POSTGRES_USER", "prostor")
PG_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "prostor")
PG_HOST = os.environ.get("POSTGRES_HOST", "localhost")
PG_PORT = os.environ.get("POSTGRES_PORT", "5432")

os.environ["DATABASE_URL"] = f"postgresql+asyncpg://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{TEST_DB_NAME}"
os.environ["SEED_ON_START"] = "false"
os.environ["LLM_API_KEY"] = ""  # DeepSeek по умолчанию выключен -> детерминированные фолбэки
os.environ["EMBEDDINGS_PROVIDER"] = "local"
os.environ["LLM_EMBEDDING_DIM"] = "64"  # под размерность FakeEmbeddingsClient
os.environ["JWT_SECRET"] = "qa-jwt-secret-key-for-tests-only-32-bytes-min"  # noqa: S105 - тестовый ключ

import asyncpg  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import delete, text  # noqa: E402

from app.core.security import create_access_token  # noqa: E402
from app.db.base import Base, SessionLocal, engine  # noqa: E402
from app.db.models import Company, Embedding, Product, Request, TzTemplate, TzTemplateStage, User  # noqa: E402
from app.main import app  # noqa: E402
from app.services.docx_parser import _default_blocks, build_blocks_schema  # noqa: E402

# --- Создание/удаление тестовой БД ----------------------------------------


async def _create_test_database() -> None:
    admin_dsn = f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/postgres"
    conn = await asyncpg.connect(admin_dsn)
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}" WITH (FORCE)')
        await conn.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
    finally:
        await conn.close()


async def _drop_test_database() -> None:
    admin_dsn = f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/postgres"
    conn = await asyncpg.connect(admin_dsn)
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}" WITH (FORCE)')
    finally:
        await conn.close()


asyncio.run(_create_test_database())


# --- Заглушки внешних сервисов ---------------------------------------------


class FakeLLMClient:
    """Детерминированная заглушка DeepSeek-клиента.

    - ``stream_deltas``: список чанков, которые вернёт ``chat_stream``;
    - ``json_responses``: очередь ответов ``chat_json`` (пусто -> {});
    - ``calls``: журнал вызовов для assert-ов.
    """

    def __init__(self, *, enabled: bool = True):
        self.enabled = enabled
        self.stream_deltas: list[str] = []
        self.json_responses: list[dict[str, Any]] = []
        self.text_responses: list[str] = []
        self.calls: list[dict[str, Any]] = []

    async def chat_stream(self, messages: list[dict[str, Any]], model: str | None = None) -> AsyncIterator[str]:
        self.calls.append({"method": "chat_stream", "messages": messages})
        for delta in self.stream_deltas:
            yield delta

    async def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
        model: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append({"method": "chat_json", "system": system_prompt, "user": user_prompt})
        return self.json_responses.pop(0) if self.json_responses else {}

    async def chat_text(self, system_prompt: str, user_prompt: str, model: str | None = None) -> str:
        self.calls.append({"method": "chat_text"})
        return self.text_responses.pop(0) if self.text_responses else ""


class FakeEmbeddingsClient:
    """Детерминированные эмбеддинги «мешок слов».

    Одинаковые тексты -> идентичные векторы; общие слова -> высокая косинусная
    близость. Не зависит от sentence-transformers и сети.
    """

    def __init__(self, dim: int = 64):
        self._dim = dim
        self.calls: list[str] = []

    @property
    def dim(self) -> int:
        return self._dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.extend(texts)
        return [self._vector(t) for t in texts]

    def _vector(self, text_value: str) -> list[float]:
        vec = [0.0] * self._dim
        for token in re.findall(r"\w+", text_value.lower()):
            idx = int(hashlib.sha1(token.encode("utf-8")).hexdigest(), 16) % self._dim
            vec[idx] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec


class FakeMinioService:
    """Заглушка MinIO: хранит файлы в памяти, отдаёт фиктивные presigned-URL."""

    def __init__(self):
        self.uploaded: dict[str, bytes] = {}
        self.deleted: list[str] = []

    def ensure_buckets(self) -> None:
        pass

    def upload_bytes(self, bucket: str, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self.uploaded[key] = bytes(data)

    def download_bytes(self, bucket: str, key: str) -> bytes:
        return self.uploaded[key]

    def presigned_url(self, bucket: str, key: str, expires_minutes: int = 15) -> str:
        return f"http://minio.test/{bucket}/{key}?expires={expires_minutes}"

    def delete(self, bucket: str, key: str) -> None:
        self.deleted.append(key)
        self.uploaded.pop(key, None)


# --- Фикстуры БД и HTTP-клиента --------------------------------------------


@pytest_asyncio.fixture(scope="session", autouse=True)
async def prepare_database() -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "pgcrypto"'))
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    await _drop_test_database()


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator:
    async with SessionLocal() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def _clean_embeddings(prepare_database) -> AsyncIterator[None]:
    """Изоляция тестов: таблица эмбеддингов чистится после каждого теста.

    Иначе одинаковые тексты из разных корпусов дают одинаковые векторы
    и нестабильный порядок в семантическом поиске.
    """
    yield
    async with SessionLocal() as session:
        await session.execute(delete(Embedding))
        await session.commit()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as ac:
        yield ac


# --- Пользователи и JWT -----------------------------------------------------


@pytest_asyncio.fixture
async def test_user(db_session) -> User:
    user = User(username=f"qa_{uuid.uuid4().hex[:10]}", full_name="QA Тестовый пользователь", role="customer")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict[str, str]:
    token = create_access_token(test_user.id, test_user.username, test_user.role)
    return {"Authorization": f"Bearer {token}"}


# --- Моки внешних сервисов ---------------------------------------------------


@pytest.fixture
def mock_llm(monkeypatch) -> FakeLLMClient:
    """Подменяет get_llm_client() во всех модулях-потребителях."""
    fake = FakeLLMClient()
    import app.services.chat_agent
    import app.services.template_recommender
    import app.services.tz_analyzer
    import app.services.tz_builder

    modules = (
        app.services.chat_agent,
        app.services.template_recommender,
        app.services.tz_analyzer,
        app.services.tz_builder,
    )
    for module in modules:
        monkeypatch.setattr(module, "get_llm_client", lambda: fake)
    return fake


@pytest.fixture
def mock_embeddings(monkeypatch) -> FakeEmbeddingsClient:
    """Подменяет get_embeddings_client() — без загрузки sentence-transformers."""
    from app.services import embeddings as embeddings_module

    fake = FakeEmbeddingsClient()
    monkeypatch.setattr(embeddings_module, "get_embeddings_client", lambda: fake)
    return fake


@pytest.fixture
def mock_minio(monkeypatch) -> FakeMinioService:
    """Подменяет MinIO в API документов."""
    from app.api.v1 import documents as documents_module

    fake = FakeMinioService()
    monkeypatch.setattr(documents_module, "get_minio_service", lambda: fake)
    return fake


# --- Фабрики тестовых данных --------------------------------------------------


@pytest_asyncio.fixture
async def make_tz_template(db_session) -> Callable[..., TzTemplate]:
    """Шаблон ТЗ с канонической схемой блоков (как в docx_parser._default_blocks)."""

    async def _make(name: str = "ТЗ ПТД (QA)", **overrides) -> TzTemplate:
        params: dict[str, Any] = {
            "code": f"QA-{uuid.uuid4().hex[:8]}",
            "name": name,
            "description": "Шаблон для автотестов",
            "minio_docx_key": f"templates/{uuid.uuid4().hex}.docx",
            "blocks_schema": build_blocks_schema(_default_blocks()),
            "is_active": True,
        }
        params.update(overrides)
        template = TzTemplate(**params)
        db_session.add(template)
        await db_session.flush()
        for order, (stage_name, req, res) in enumerate(
            [
                ("Формирование базы данных", "Исходные данные заказчика", "База данных проекта"),
                ("Построение 3D-геомодели", "Геологическая модель", "Согласованная 3D-модель"),
            ],
            start=1,
        ):
            db_session.add(
                TzTemplateStage(
                    template_id=template.id,
                    stage_order=order,
                    stage_name=stage_name,
                    default_requirements=req,
                    default_results=res,
                )
            )
        await db_session.commit()
        await db_session.refresh(template)
        return template

    return _make


@pytest_asyncio.fixture
async def seed_search_corpus(db_session, mock_embeddings) -> dict[str, Any]:
    """Наполняет БД продуктами/подрядчиком/заявкой + их эмбеддингами."""
    from app.services.embeddings import upsert_embedding

    company = Company(company_id=f"QA-C-{uuid.uuid4().hex[:6]}", name="ГеоСервис QA", rating=5)
    product_burn = Product(product_id=f"QA-P-{uuid.uuid4().hex[:6]}", product_name="Гидравлический разрыв пласта")
    product_geomodel = Product(product_id=f"QA-P-{uuid.uuid4().hex[:6]}", product_name="Построение 3D-геомодели")
    db_session.add_all([company, product_burn, product_geomodel])
    await db_session.flush()

    user = User(username=f"qa_corpus_{uuid.uuid4().hex[:6]}", role="customer")
    db_session.add(user)
    await db_session.flush()
    request = Request(
        number=f"QA-{uuid.uuid4().hex[:8]}",
        user_id=user.id,
        title="ГРП на скважине 1234",
        description="Проведение гидравлического разрыва пласта",
    )
    db_session.add(request)
    await db_session.commit()

    await upsert_embedding(db_session, "product", product_burn.product_id, product_burn.product_name)
    await upsert_embedding(db_session, "product", product_geomodel.product_id, product_geomodel.product_name)
    company_services = "Гидравлический разрыв пласта ГРП нефтесервис"
    await upsert_embedding(db_session, "company_services", company.company_id, company_services)
    await upsert_embedding(db_session, "request", str(request.id), f"{request.title} {request.description}")

    return {
        "company": company,
        "product_burn": product_burn,
        "product_geomodel": product_geomodel,
        "request": request,
    }
