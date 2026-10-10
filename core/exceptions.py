"""Application error taxonomy and safe user-facing exception reporting."""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from enum import Enum
from typing import Any

from core.observability import event_fields


class ErrorCategory(str, Enum):
    """Operational class used for logging, alerting, and retry decisions."""

    USER = "user"
    TRANSIENT = "transient"
    SYSTEM = "system"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class ErrorDisposition:
    """Safe handling decision derived from an exception."""

    code: str
    category: ErrorCategory
    user_message: str
    retryable: bool
    log_level: int


class FazTestBotException(Exception):
    """Base exception carrying stable operational metadata."""

    def __init__(
        self,
        message: str,
        code: str = "UNKNOWN_ERROR",
        *,
        category: ErrorCategory = ErrorCategory.SYSTEM,
        retryable: bool = False,
        user_message: str | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.category = category
        self.retryable = retryable
        self.user_message = user_message or message


class ModuleNotFound(FazTestBotException):
    def __init__(self, module_id: str):
        super().__init__(f"Модуль '{module_id}' не найден", "MODULE_NOT_FOUND")
        self.module_id = module_id


class ModuleLoadError(FazTestBotException):
    def __init__(self, module_id: str, reason: str):
        super().__init__(
            f"Не удалось загрузить модуль '{module_id}': {reason}",
            "MODULE_LOAD_ERROR",
            category=ErrorCategory.CRITICAL,
            user_message="Модуль временно недоступен.",
        )
        self.module_id = module_id
        self.reason = reason


class ModuleValidationError(FazTestBotException):
    def __init__(self, module_id: str, errors: list[str]):
        message = f"Модуль '{module_id}' не прошёл валидацию:\n" + "\n".join(errors)
        super().__init__(
            message,
            "MODULE_VALIDATION_ERROR",
            category=ErrorCategory.CRITICAL,
            user_message="Модуль временно недоступен.",
        )
        self.module_id = module_id
        self.errors = errors


class DatabaseError(FazTestBotException):
    def __init__(
        self,
        message: str,
        operation: str | None = None,
        *,
        code: str = "DATABASE_ERROR",
        category: ErrorCategory = ErrorCategory.SYSTEM,
        retryable: bool = False,
    ):
        super().__init__(
            message,
            code,
            category=category,
            retryable=retryable,
            user_message="Ошибка базы данных. Попробуйте позже.",
        )
        self.operation = operation


class DatabaseConnectionError(DatabaseError):
    def __init__(self, details: str | None = None):
        message = "Не удалось подключиться к базе данных"
        if details:
            message += f": {details}"
        super().__init__(
            message,
            operation="connect",
            code="DB_CONNECTION_ERROR",
            category=ErrorCategory.CRITICAL,
            retryable=True,
        )


class DatabaseQueryError(DatabaseError):
    def __init__(self, query: str, details: str | None = None):
        message = "Ошибка выполнения запроса"
        if details:
            message += f": {details}"
        super().__init__(message, operation="query", code="DB_QUERY_ERROR")
        self.query = query


class APIError(FazTestBotException):
    def __init__(
        self,
        service: str,
        message: str,
        status_code: int | None = None,
        *,
        code: str = "API_ERROR",
        category: ErrorCategory = ErrorCategory.TRANSIENT,
        retryable: bool = True,
    ):
        super().__init__(
            f"API {service}: {message}",
            code,
            category=category,
            retryable=retryable,
            user_message="Внешний сервис временно недоступен. Попробуйте позже.",
        )
        self.service = service
        self.status_code = status_code


class APIRateLimitError(APIError):
    def __init__(self, service: str, retry_after: int | None = None):
        message = "Превышен лимит запросов"
        if retry_after:
            message += f". Повторите через {retry_after} сек"
        super().__init__(service, message, 429, code="API_RATE_LIMIT")
        self.retry_after = retry_after


class APIAuthenticationError(APIError):
    def __init__(self, service: str):
        super().__init__(
            service,
            "Неверный API ключ или токен",
            401,
            code="API_AUTH_ERROR",
            category=ErrorCategory.SYSTEM,
            retryable=False,
        )


class UserInputError(FazTestBotException):
    def __init__(self, message: str, field: str | None = None, *, code: str = "USER_INPUT_ERROR"):
        super().__init__(message, code, category=ErrorCategory.USER, user_message=message)
        self.field = field


class ValidationError(UserInputError):
    def __init__(self, field: str, message: str):
        super().__init__(f"Поле '{field}': {message}", field, code="VALIDATION_ERROR")


class LimitExceededError(FazTestBotException):
    def __init__(self, limit_type: str, limit_value: int, current_value: int | None = None):
        message = f"Превышен лимит {limit_type}: {limit_value}"
        if current_value is not None:
            message += f" (текущее: {current_value})"
        super().__init__(message, "LIMIT_EXCEEDED", category=ErrorCategory.USER)
        self.limit_type = limit_type
        self.limit_value = limit_value
        self.current_value = current_value


class AdminPermissionError(FazTestBotException):
    def __init__(self, action: str):
        super().__init__(
            f"Недостаточно прав для действия: {action}",
            "ADMIN_PERMISSION_ERROR",
            category=ErrorCategory.USER,
        )
        self.action = action


class AdminAuthenticationError(FazTestBotException):
    def __init__(self, reason: str = "Неверный код"):
        super().__init__(reason, "ADMIN_AUTH_ERROR", category=ErrorCategory.USER)


class FileError(FazTestBotException):
    def __init__(
        self,
        message: str,
        filepath: str | None = None,
        *,
        code: str = "FILE_ERROR",
    ):
        super().__init__(
            message,
            code,
            user_message="Ошибка работы с файлом. Попробуйте позже.",
        )
        self.filepath = filepath


class FileNotFound(FileError):
    def __init__(self, filepath: str):
        super().__init__(f"Файл не найден: {filepath}", filepath, code="FILE_NOT_FOUND")


class FilePermissionError(FileError):
    def __init__(self, filepath: str, operation: str):
        super().__init__(
            f"Нет прав на {operation} файла: {filepath}",
            filepath,
            code="FILE_PERMISSION_ERROR",
        )
        self.operation = operation


def classify_exception(exc: Exception) -> ErrorDisposition:
    """Map any exception to stable, non-sensitive handling metadata."""

    if isinstance(exc, FazTestBotException):
        level = {
            ErrorCategory.USER: logging.INFO,
            ErrorCategory.TRANSIENT: logging.WARNING,
            ErrorCategory.SYSTEM: logging.ERROR,
            ErrorCategory.CRITICAL: logging.CRITICAL,
        }[exc.category]
        return ErrorDisposition(
            exc.code,
            exc.category,
            f"❌ {exc.user_message}",
            exc.retryable,
            level,
        )
    if isinstance(exc, sqlite3.Error):
        return ErrorDisposition(
            "SQLITE_ERROR",
            ErrorCategory.SYSTEM,
            "❌ Ошибка базы данных. Попробуйте позже.",
            False,
            logging.ERROR,
        )
    if isinstance(exc, (ValueError, TypeError)):
        return ErrorDisposition(
            "INVALID_VALUE",
            ErrorCategory.USER,
            "❌ Некорректное значение.",
            False,
            logging.INFO,
        )
    if isinstance(exc, PermissionError):
        return ErrorDisposition(
            "PERMISSION_ERROR",
            ErrorCategory.SYSTEM,
            "❌ Нет прав доступа.",
            False,
            logging.ERROR,
        )
    if isinstance(exc, FileNotFoundError):
        return ErrorDisposition(
            "FILE_NOT_FOUND",
            ErrorCategory.SYSTEM,
            "❌ Файл не найден.",
            False,
            logging.ERROR,
        )
    return ErrorDisposition(
        "UNEXPECTED_ERROR",
        ErrorCategory.SYSTEM,
        "❌ Произошла непредвиденная ошибка. Попробуйте позже.",
        False,
        logging.ERROR,
    )


def handle_exception(
    exc: Exception,
    logger: logging.Logger | None = None,
    *,
    event: str = "application.operation_failed",
    context: dict[str, Any] | None = None,
) -> str:
    """Log diagnostic detail and return a safe localized message."""

    disposition = classify_exception(exc)
    if logger:
        fields = {
            "error_code": disposition.code,
            "error_category": disposition.category.value,
            "retryable": disposition.retryable,
            **(context or {}),
        }
        log_message = "%s" if disposition.category is ErrorCategory.USER else "%s: %s"
        log_arguments = (
            (type(exc).__name__,)
            if disposition.category is ErrorCategory.USER
            else (
                type(exc).__name__,
                exc,
            )
        )
        logger.log(
            disposition.log_level,
            log_message,
            *log_arguments,
            exc_info=disposition.category is not ErrorCategory.USER,
            extra=event_fields(event, **fields),
        )
    return disposition.user_message


def is_user_error(exc: Exception) -> bool:
    return classify_exception(exc).category is ErrorCategory.USER


def is_system_error(exc: Exception) -> bool:
    return classify_exception(exc).category in {ErrorCategory.SYSTEM, ErrorCategory.CRITICAL}


def is_critical_error(exc: Exception) -> bool:
    return classify_exception(exc).category is ErrorCategory.CRITICAL


__all__ = [
    "APIAuthenticationError",
    "APIError",
    "APIRateLimitError",
    "AdminAuthenticationError",
    "AdminPermissionError",
    "DatabaseConnectionError",
    "DatabaseError",
    "DatabaseQueryError",
    "ErrorCategory",
    "ErrorDisposition",
    "FazTestBotException",
    "FileError",
    "FileNotFound",
    "FilePermissionError",
    "LimitExceededError",
    "ModuleLoadError",
    "ModuleNotFound",
    "ModuleValidationError",
    "UserInputError",
    "ValidationError",
    "classify_exception",
    "handle_exception",
    "is_critical_error",
    "is_system_error",
    "is_user_error",
]
