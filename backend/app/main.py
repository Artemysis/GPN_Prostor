from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi import Request as FastApiRequest
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from app.api.v1 import api_router
from app.core.config import get_settings
from app.db.base import SessionLocal

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if settings.seed_on_start:
        from app.services.seed import run_seed

        async with SessionLocal() as db:
            try:
                await run_seed(db)
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"Сидирование при старте завершилось с ошибкой: {exc}")
    yield


app = FastAPI(
    title="ПРОСТОР 2.0 — API",
    description="Умный конструктор ТЗ + ИИ-агент умного поиска",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: FastApiRequest, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "HTTP_ERROR", "message": str(exc.detail), "details": None}},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: FastApiRequest, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"error": {"code": "VALIDATION", "message": "Ошибка валидации запроса", "details": {"errors": exc.errors()}}},
    )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


app.include_router(api_router, prefix="/api/v1")
