"""Read-only application readiness diagnostics."""

from __future__ import annotations

import shutil
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from core.migrations import DatabaseMigrator, MigrationError
from core.paths import DATABASE_PATH, ROOT_DIR, SECRETS_FILE
from core.settings import Settings
from core.storage import DatabaseIntegrityError, SQLiteDatabase

MINIMUM_FREE_BYTES = 100 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class HealthCheck:
    name: str
    status: str
    summary: str
    details: dict[str, Any]


@dataclass(frozen=True, slots=True)
class HealthReport:
    ready: bool
    checks: tuple[HealthCheck, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "checks": [asdict(check) for check in self.checks],
        }


def _configuration_check(settings: Settings) -> HealthCheck:
    errors = settings.startup_errors()
    if errors:
        return HealthCheck(
            "configuration",
            "error",
            "configuration is incomplete",
            {"errors": list(errors)},
        )
    return HealthCheck(
        "configuration",
        "ok",
        "configuration is valid for startup",
        {
            "administrator_count": len(settings.admins),
            "automatic_backups": settings.backup_enabled,
            "media_downloader": settings.media_downloader_enabled,
        },
    )


def _database_check(path: Path) -> HealthCheck:
    if not path.is_file():
        return HealthCheck(
            "database",
            "warning",
            "database is not initialized; startup will create it",
            {"schema_version": "0", "pending_migrations": "all"},
        )
    try:
        SQLiteDatabase(path).validate()
        migrator = DatabaseMigrator(path)
        current = migrator.get_current_version()
        pending = migrator.pending_versions()
    except (DatabaseIntegrityError, MigrationError, OSError, sqlite3.DatabaseError) as error:
        return HealthCheck(
            "database",
            "error",
            "database validation failed",
            {"error_type": type(error).__name__},
        )
    if pending:
        return HealthCheck(
            "database",
            "warning",
            "database is valid and requires migration",
            {"schema_version": current, "pending_migrations": pending},
        )
    return HealthCheck(
        "database",
        "ok",
        "database is valid and current",
        {"schema_version": current, "pending_migrations": []},
    )


def _disk_check(path: Path) -> HealthCheck:
    try:
        free_bytes = shutil.disk_usage(path).free
    except OSError as error:
        return HealthCheck(
            "disk",
            "error",
            "disk capacity could not be inspected",
            {"error_type": type(error).__name__},
        )
    status = "ok" if free_bytes >= MINIMUM_FREE_BYTES else "warning"
    summary = "disk space is sufficient" if status == "ok" else "disk space is low"
    return HealthCheck("disk", status, summary, {"free_bytes": free_bytes})


def _legacy_secrets_check(path: Path) -> HealthCheck:
    if path.exists():
        return HealthCheck(
            "legacy_secrets",
            "warning",
            "legacy secrets.py exists and can shadow the Python standard library",
            {},
        )
    return HealthCheck("legacy_secrets", "ok", "legacy secrets.py is absent", {})


def build_health_report(
    settings: Settings,
    *,
    db_path: str | Path = DATABASE_PATH,
    root_path: str | Path = ROOT_DIR,
    secrets_path: str | Path = SECRETS_FILE,
) -> HealthReport:
    """Inspect local readiness without migrations, writes, or network requests."""

    checks = (
        _configuration_check(settings),
        _database_check(Path(db_path)),
        _disk_check(Path(root_path)),
        _legacy_secrets_check(Path(secrets_path)),
    )
    return HealthReport(
        ready=all(check.status != "error" for check in checks),
        checks=checks,
    )


__all__ = ["HealthCheck", "HealthReport", "build_health_report"]
