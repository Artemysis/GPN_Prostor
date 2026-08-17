"""Фикстуры API-тестов.

Тесты рассчитаны на реальный PostgreSQL + pgvector (см. DATABASE_URL в .env) —
это соответствует требованию SPEC.md к стеку. Перед прогоном поднимите
`docker compose up -d postgres` или укажите свой DATABASE_URL.
"""

import asyncio

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db.base import Base, SessionLocal, engine
from app.main import app


@pytest_asyncio.fixture(scope="session", autouse=True)
async def prepare_database():
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "pgcrypto"'))
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as ac:
        yield ac


@pytest_asyncio.fixture
async def db_session():
    async with SessionLocal() as session:
        yield session
