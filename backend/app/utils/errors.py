from typing import Any

from fastapi import HTTPException


class ApiError(HTTPException):
    def __init__(self, status_code: int, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(status_code=status_code, detail={"error": {"code": code, "message": message, "details": details}})


class NotFoundError(ApiError):
    def __init__(self, message: str = "Объект не найден", details: dict[str, Any] | None = None):
        super().__init__(404, "NOT_FOUND", message, details)


class ValidationError(ApiError):
    def __init__(self, message: str = "Ошибка валидации", details: dict[str, Any] | None = None):
        super().__init__(400, "VALIDATION", message, details)


class ConflictError(ApiError):
    def __init__(self, message: str = "Конфликт", details: dict[str, Any] | None = None):
        super().__init__(409, "CONFLICT", message, details)
