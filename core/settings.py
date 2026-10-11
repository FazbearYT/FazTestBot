"""Typed application settings loaded from environment variables.

The process environment has precedence over values from the local ``.env`` file.
No secret value is logged or embedded in defaults.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import time
from pathlib import Path

from dotenv import dotenv_values


class ConfigurationError(ValueError):
    """Raised when configuration cannot be parsed or used safely."""


def _parse_bool(name: str, value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{name} must be a boolean (true/false)")


def _parse_int(name: str, value: str, *, minimum: int = 0) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be an integer") from error
    if parsed < minimum:
        raise ConfigurationError(f"{name} must be at least {minimum}")
    return parsed


def _parse_ids(value: str, *, name: str) -> tuple[int, ...]:
    if not value.strip():
        return ()
    ids = tuple(
        _parse_int(name, item.strip(), minimum=1) for item in value.split(",") if item.strip()
    )
    if len(ids) != len(set(ids)):
        raise ConfigurationError(f"{name} must not contain duplicate user IDs")
    return ids


def _parse_backup_time(value: str) -> str:
    try:
        time.fromisoformat(value)
    except ValueError as error:
        raise ConfigurationError("BACKUP_TIME must use HH:MM format") from error
    if len(value) != 5:
        raise ConfigurationError("BACKUP_TIME must use HH:MM format")
    return value


def _choice(name: str, value: str, choices: set[str]) -> str:
    normalized = value.strip().lower()
    if normalized not in choices:
        expected = ", ".join(sorted(choices))
        raise ConfigurationError(f"{name} must be one of: {expected}")
    return normalized


@dataclass(frozen=True, slots=True)
class Settings:
    bot_token: str = field(default="", repr=False)
    admins: tuple[int, ...] = ()
    admin_secret_code: str = field(default="", repr=False)
    admin_session_hours: int = 24
    url_shortener_service: str = "tinyurl"
    cuttly_api_key: str = field(default="", repr=False)
    media_downloader_enabled: bool = False
    max_download_size_mb: int = 50
    max_downloads_per_user_per_day: int = 10
    ip_info_api_service: str = "ipapi"
    ipinfo_api_key: str = field(default="", repr=False)
    groq_api_key: str = field(default="", repr=False)
    cheapshark_api_key: str = field(default="", repr=False)
    log_retention_days: int = 30
    log_level: str = "INFO"
    backup_enabled: bool = True
    backup_time: str = "03:00"
    backup_retention_count: int = 7
    backup_retention_days: int = 30
    blocked_users: tuple[int, ...] = ()

    def startup_errors(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.bot_token:
            errors.append("BOT_TOKEN is required")
        if self.url_shortener_service == "cuttly" and not self.cuttly_api_key:
            errors.append("CUTTLY_API_KEY is required when URL_SHORTENER_SERVICE=cuttly")
        if self.ip_info_api_service == "ipinfo" and not self.ipinfo_api_key:
            errors.append("IPINFO_API_KEY is required when IP_INFO_API_SERVICE=ipinfo")
        return tuple(errors)

    def require_startup_ready(self) -> None:
        errors = self.startup_errors()
        if errors:
            raise ConfigurationError("; ".join(errors))


def _merged_environment(
    environ: Mapping[str, str] | None,
    env_file: str | Path | None,
) -> dict[str, str]:
    path = (
        Path(env_file) if env_file is not None else Path(__file__).resolve().parent.parent / ".env"
    )
    values = {key: value for key, value in dotenv_values(path).items() if value is not None}
    values.update(dict(os.environ if environ is None else environ))
    return values


def load_settings(
    environ: Mapping[str, str] | None = None,
    *,
    env_file: str | Path | None = None,
) -> Settings:
    """Load and validate settings without changing ``os.environ``."""

    values = _merged_environment(environ, env_file)

    def get(name: str, default: str = "") -> str:
        return values.get(name, default).strip()

    return Settings(
        bot_token=get("BOT_TOKEN"),
        admins=_parse_ids(get("ADMINS"), name="ADMINS"),
        admin_secret_code=get("ADMIN_SECRET_CODE"),
        admin_session_hours=_parse_int(
            "ADMIN_SESSION_HOURS", get("ADMIN_SESSION_HOURS", "24"), minimum=1
        ),
        url_shortener_service=_choice(
            "URL_SHORTENER_SERVICE",
            get("URL_SHORTENER_SERVICE", "tinyurl"),
            {"tinyurl", "cuttly"},
        ),
        cuttly_api_key=get("CUTTLY_API_KEY"),
        media_downloader_enabled=_parse_bool(
            "MEDIA_DOWNLOADER_ENABLED", get("MEDIA_DOWNLOADER_ENABLED", "false")
        ),
        max_download_size_mb=_parse_int(
            "MAX_DOWNLOAD_SIZE_MB", get("MAX_DOWNLOAD_SIZE_MB", "50"), minimum=1
        ),
        max_downloads_per_user_per_day=_parse_int(
            "MAX_DOWNLOADS_PER_USER_PER_DAY",
            get("MAX_DOWNLOADS_PER_USER_PER_DAY", "10"),
            minimum=1,
        ),
        ip_info_api_service=_choice(
            "IP_INFO_API_SERVICE",
            get("IP_INFO_API_SERVICE", "ipapi"),
            {"ipapi", "ipinfo"},
        ),
        ipinfo_api_key=get("IPINFO_API_KEY"),
        groq_api_key=get("GROQ_API_KEY"),
        cheapshark_api_key=get("CHEAPSHARK_API_KEY"),
        log_retention_days=_parse_int(
            "LOG_RETENTION_DAYS", get("LOG_RETENTION_DAYS", "30"), minimum=1
        ),
        log_level=_choice(
            "LOG_LEVEL",
            get("LOG_LEVEL", "INFO"),
            {"critical", "error", "warning", "info", "debug"},
        ).upper(),
        backup_enabled=_parse_bool("BACKUP_ENABLED", get("BACKUP_ENABLED", "true")),
        backup_time=_parse_backup_time(get("BACKUP_TIME", "03:00")),
        backup_retention_count=_parse_int(
            "BACKUP_RETENTION_COUNT", get("BACKUP_RETENTION_COUNT", "7"), minimum=1
        ),
        backup_retention_days=_parse_int(
            "BACKUP_RETENTION_DAYS", get("BACKUP_RETENTION_DAYS", "30"), minimum=1
        ),
        blocked_users=_parse_ids(get("BLOCKED_USERS"), name="BLOCKED_USERS"),
    )
