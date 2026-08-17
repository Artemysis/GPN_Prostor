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


class EmbeddingsClient(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    @property
    def dim(self) -> int: ...


class LocalEmbeddingsClient:
    """sentence-transformers, лениво загружается при первом обращении.

    Использует префиксы e5: "passage: " при индексации, "query: " при поиске —
    вызывающий код обязан подставлять их сам (см. semantic_search.py).
    """

    def __init__(self, model_name: str):
        self.model_name = model_name
        self._model = None
        self._dim = settings.llm_embedding_dim

    def _load(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self.model_name)
                dim_fn = getattr(self._model, "get_embedding_dimension", None) or self._model.get_sentence_embedding_dimension
                self._dim = dim_fn()
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"Не удалось загрузить sentence-transformers ({exc}), использую hash-фолбэк")
                self._model = False
        return self._model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        model = self._load()
        if model:
            return model.encode(list(texts), normalize_embeddings=True).tolist()
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
def get_embeddings_client() -> LocalEmbeddingsClient:
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
