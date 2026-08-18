import asyncio
import hashlib
from functools import lru_cache
from typing import Protocol

import numpy as np
from loguru import logger
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Embedding

settings = get_settings()

MODEL_LOAD_TIMEOUT_S = 180


class EmbeddingsClient(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    @property
    def dim(self) -> int: ...


class OpenRouterEmbeddingsClient:
    """Эмбеддинги через OpenAI-совместимый API (OpenRouter и т.п.).

    Используется, когда EMBEDDINGS_PROVIDER указывает на внешний API
    (`openai` / `openrouter`) — векторизация выполняется удалённой моделью
    через POST {embeddings_api_base}/embeddings, а не локально.
    """

    def __init__(self, base_url: str, api_key: str, model: str, dim: int):
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        self._dim = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            # dimensions — Matryoshka-обрезка вектора под размер колонки в pgvector
            # (например, qwen3-embedding-8b по умолчанию отдаёт 4096, а не 1536).
            response = await self._client.embeddings.create(
                model=self.model, input=texts, dimensions=self._dim
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Провайдер эмбеддингов не поддержал dimensions={self._dim} ({exc}), повтор без параметра")
            response = await self._client.embeddings.create(model=self.model, input=texts)
        ordered = sorted(response.data, key=lambda item: item.index)
        vectors = [list(item.embedding) for item in ordered]
        if vectors and len(vectors[0]) != self._dim:
            logger.warning(
                f"Модель эмбеддингов вернула размерность {len(vectors[0])}, ожидалось {self._dim} — обрезаю вектор"
            )
            vectors = [v[: self._dim] for v in vectors]
        return vectors

    @property
    def dim(self) -> int:
        return self._dim


class LocalEmbeddingsClient:
    """sentence-transformers, лениво загружается при первом обращении.

    Загрузка/инференс выполняются в отдельном потоке, чтобы не блокировать
    event loop; при невозможности загрузить модель за отведённый таймаут
    используется детерминированный hash-фолбэк (демо/офлайн-режим).

    Использует префиксы e5: "passage: " при индексации, "query: " при поиске —
    вызывающий код обязан подставлять их сам (см. semantic_search.py).
    """

    def __init__(self, model_name: str):
        self.model_name = model_name
        self._model = None
        self._dim = settings.llm_embedding_dim
        self._lock = asyncio.Lock()

    async def _ensure_model(self):
        if self._model is not None or self._model is False:
            return
        async with self._lock:
            if self._model is not None or self._model is False:
                return

            def _load_sync():
                from sentence_transformers import SentenceTransformer

                model = SentenceTransformer(self.model_name)
                dim_fn = getattr(model, "get_embedding_dimension", None) or model.get_sentence_embedding_dimension
                return model, dim_fn()

            try:
                self._model, self._dim = await asyncio.wait_for(
                    asyncio.to_thread(_load_sync), timeout=MODEL_LOAD_TIMEOUT_S
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"Не удалось загрузить sentence-transformers ({exc}), использую hash-фолбэк")
                self._model = False

    async def embed(self, texts: list[str]) -> list[list[float]]:
        await self._ensure_model()
        model = self._model
        if model:

            def _encode_sync():
                return model.encode(list(texts), normalize_embeddings=True).tolist()

            return await asyncio.to_thread(_encode_sync)
        return [_hash_embedding(text, self._dim) for text in texts]

    @property
    def dim(self) -> int:
        return self._dim


def _hash_embedding(text: str, dim: int) -> list[float]:
    """Детерминированный фолбэк-эмбеддинг на случай отсутствия модели (демо/офлайн)."""
    rng = np.random.default_rng(int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16) % (2**32))
    vec = rng.normal(size=dim)
    vec = vec / (np.linalg.norm(vec) + 1e-9)
    return vec.tolist()


@lru_cache
def get_embeddings_client() -> EmbeddingsClient:
    provider = (settings.embeddings_provider or "local").strip().lower()
    if provider in ("openai", "openrouter", "api"):
        if not settings.embeddings_api_key:
            logger.warning(
                f"EMBEDDINGS_PROVIDER={provider}, но EMBEDDINGS_API_KEY не задан — "
                "использую локальную модель эмбеддингов вместо API"
            )
        else:
            return OpenRouterEmbeddingsClient(
                base_url=settings.embeddings_api_base,
                api_key=settings.embeddings_api_key,
                model=settings.embeddings_model,
                dim=settings.llm_embedding_dim,
            )
    return LocalEmbeddingsClient(settings.embeddings_model)


async def upsert_embedding(
    db: AsyncSession,
    entity_type: str,
    entity_id: str,
    content: str,
    metadata: dict | None = None,
) -> None:
    client = get_embeddings_client()
    vector = (await client.embed([f"passage: {content}"]))[0]
    await db.execute(
        delete(Embedding).where(Embedding.entity_type == entity_type, Embedding.entity_id == entity_id)
    )
    db.add(
        Embedding(
            entity_type=entity_type,
            entity_id=entity_id,
            content=content,
            embedding=vector,
            embedding_metadata=metadata or {},
        )
    )
    await db.commit()


async def embed_query(text: str) -> list[float]:
    client = get_embeddings_client()
    return (await client.embed([f"query: {text}"]))[0]


async def search_embeddings(
    db: AsyncSession, entity_type: str, query: str, top_k: int = 10
) -> list[tuple[Embedding, float]]:
    vector = await embed_query(query)
    stmt = (
        select(Embedding, Embedding.embedding.cosine_distance(vector).label("distance"))
        .where(Embedding.entity_type == entity_type)
        .order_by("distance")
        .limit(top_k)
    )
    rows = (await db.execute(stmt)).all()
    return [(row[0], 1 - row[1]) for row in rows]
