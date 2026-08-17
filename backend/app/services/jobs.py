import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import SessionLocal
from app.db.models import Job


async def create_job(db: AsyncSession, job_type: str, payload: dict | None = None) -> Job:
    job = Job(type=job_type, status="pending", payload=payload or {})
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def run_job(job_id: uuid.UUID, task: Callable[[AsyncSession], Awaitable[dict[str, Any]]]) -> None:
    """Выполняет фоновую задачу и обновляет статус в таблице jobs.

    Используется как FastAPI BackgroundTasks-обработчик (MVP-режим без Celery, §1 SPEC).
    """
    async with SessionLocal() as db:
        job = await db.get(Job, job_id)
        if job is None:
            return
        job.status = "running"
        await db.commit()

        try:
            result = await task(db)
            job.status = "done"
            job.result = result
        except Exception as exc:  # noqa: BLE001
            logger.exception(f"Задача {job_id} завершилась с ошибкой")
            job.status = "failed"
            job.error = str(exc)
        finally:
            await db.commit()
