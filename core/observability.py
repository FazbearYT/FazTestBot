"""Central logging configuration with structured, redacted application events."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.paths import LOGS_DIR

LOGGER_NAMESPACE = "faztestbot"
LOG_FILENAME = "faztestbot.jsonl"

_operation_id: ContextVar[str | None] = ContextVar("operation_id", default=None)
_STANDARD_FIELDS = frozenset(logging.makeLogRecord({}).__dict__) | {
    "message",
    "asctime",
}
_TELEGRAM_TOKEN = re.compile(r"(?<![A-Za-z0-9_-])\d{8,12}:[A-Za-z0-9_-]{30,}(?![A-Za-z0-9_-])")
_NAMED_SECRET = re.compile(r"(?i)\b(bot_token|api_key|secret|password)\b(\s*[:=]\s*)([^\s,;]+)")


def redact(value: Any) -> Any:
    """Return a log-safe representation without known credential forms."""

    if not isinstance(value, str):
        return value
    value = _TELEGRAM_TOKEN.sub("[REDACTED]", value)
    return _NAMED_SECRET.sub(lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", value)


class RedactingFormatter(logging.Formatter):
    """Base formatter that redacts the rendered message and exception text."""

    def format(self, record: logging.LogRecord) -> str:
        return str(redact(super().format(record)))


class JsonEventFormatter(logging.Formatter):
    """Emit one JSON object per record for ingestion by common log tooling."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
        }
        operation_id = getattr(record, "operation_id", None) or _operation_id.get()
        if operation_id:
            payload["operation_id"] = operation_id

        for key, value in record.__dict__.items():
            if key in _STANDARD_FIELDS or key.startswith("_") or key == "operation_id":
                continue
            payload[key] = redact(value) if isinstance(value, str) else value

        if record.exc_info:
            payload["exception"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, default=str)


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a logger below the application namespace."""

    namespace_logger = logging.getLogger(LOGGER_NAMESPACE)
    namespace_logger.propagate = False
    if not namespace_logger.handlers:
        null_handler = logging.NullHandler()
        null_handler._faztestbot_handler = True  # type: ignore[attr-defined]
        namespace_logger.addHandler(null_handler)
    if not name or name == LOGGER_NAMESPACE:
        return namespace_logger
    if name.startswith(f"{LOGGER_NAMESPACE}."):
        return logging.getLogger(name)
    return logging.getLogger(f"{LOGGER_NAMESPACE}.{name}")


def configure_logging(
    *,
    level: str = "INFO",
    retention_days: int = 30,
    log_dir: str | Path = LOGS_DIR,
    console: bool = True,
) -> logging.Logger:
    """Configure application logging once and return its namespace logger."""

    logger = get_logger()
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False

    for handler in list(logger.handlers):
        if getattr(handler, "_faztestbot_handler", False):
            logger.removeHandler(handler)
            handler.close()

    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            RedactingFormatter(
                "%(asctime)s %(levelname)s %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        console_handler._faztestbot_handler = True  # type: ignore[attr-defined]
        logger.addHandler(console_handler)

    directory = Path(log_dir)
    directory.mkdir(parents=True, exist_ok=True)
    file_handler = TimedRotatingFileHandler(
        directory / LOG_FILENAME,
        when="midnight",
        interval=1,
        backupCount=retention_days,
        encoding="utf-8",
        utc=True,
        delay=True,
    )
    file_handler.setFormatter(JsonEventFormatter())
    file_handler._faztestbot_handler = True  # type: ignore[attr-defined]
    logger.addHandler(file_handler)
    return logger


@contextmanager
def operation_context(operation_id: str | None = None) -> Iterator[str]:
    """Attach a non-personal correlation identifier to logs in this context."""

    identifier = operation_id or uuid4().hex
    token: Token[str | None] = _operation_id.set(identifier)
    try:
        yield identifier
    finally:
        _operation_id.reset(token)


def event_fields(event: str, **fields: Any) -> Mapping[str, Any]:
    """Build validated structured fields for ``logging``'s ``extra`` argument."""

    conflicts = _STANDARD_FIELDS.intersection(fields)
    if conflicts:
        names = ", ".join(sorted(conflicts))
        raise ValueError(f"structured log fields conflict with LogRecord attributes: {names}")
    return {"event": event, **fields}


__all__ = [
    "JsonEventFormatter",
    "configure_logging",
    "event_fields",
    "get_logger",
    "operation_context",
    "redact",
]
