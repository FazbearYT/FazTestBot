"""Safe initialization of persistent application state."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.migrations import DatabaseMigrator, MigrationError
from core.paths import DATABASE_PATH


def migrate_database_safely(
    db_path: str | Path | None = None,
    *,
    backup_manager: Any | None = None,
) -> list[str]:
    """Back up an existing database before applying any pending migrations."""

    path = Path(db_path or DATABASE_PATH)
    existed_with_data = path.is_file() and path.stat().st_size > 0
    migrator = DatabaseMigrator(path)
    pending = migrator.pending_versions()
    if not pending:
        return []

    if existed_with_data:
        if backup_manager is None:
            from core.backup import BackupManager

            backup_manager = BackupManager(db_path=path)
        success, message = backup_manager.create_backup(manual=False)
        if not success:
            raise MigrationError(f"pre-migration backup failed: {message}")

    return migrator.apply_migrations()
