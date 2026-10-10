"""Inspect, migrate, or back up the FazTestBot SQLite database."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from core.bootstrap import migrate_database_safely
from core.migrations import DatabaseMigrator, MigrationError
from core.paths import BACKUPS_DIR, DATABASE_PATH
from core.storage import DatabaseIntegrityError, SQLiteDatabase


def _check(path: Path) -> int:
    if not path.is_file():
        print(f"Database not found: {path}")
        return 1
    try:
        SQLiteDatabase(path).validate()
        migrator = DatabaseMigrator(path)
        current = migrator.get_current_version()
        pending = migrator.pending_versions()
    except (DatabaseIntegrityError, MigrationError, OSError, sqlite3.DatabaseError) as error:
        print(f"Database check failed: {error}")
        return 1

    print(f"Database integrity: ok ({path})")
    print(f"Schema version: {current}")
    print(f"Pending migrations: {', '.join(pending) if pending else 'none'}")
    return 0


def _migrate(path: Path, backup_dir: Path) -> int:
    from core.backup import BackupManager

    backup_manager = BackupManager(backup_dir=backup_dir, db_path=path)
    try:
        applied = migrate_database_safely(path, backup_manager=backup_manager)
    except (DatabaseIntegrityError, MigrationError, OSError, sqlite3.DatabaseError) as error:
        print(f"Database migration failed: {error}")
        return 1
    print(f"Applied migrations: {', '.join(applied) if applied else 'none'}")
    return _check(path)


def _backup(path: Path, backup_dir: Path) -> int:
    from core.backup import BackupManager

    manager = BackupManager(backup_dir=backup_dir, db_path=path)
    success, message = manager.create_backup(manual=True)
    print(message)
    return 0 if success else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "migrate", "backup"))
    parser.add_argument("--db-path", type=Path, default=DATABASE_PATH)
    parser.add_argument("--backup-dir", type=Path, default=BACKUPS_DIR)
    args = parser.parse_args()

    if args.command == "check":
        return _check(args.db_path)
    if args.command == "migrate":
        return _migrate(args.db_path, args.backup_dir)
    return _backup(args.db_path, args.backup_dir)


if __name__ == "__main__":
    raise SystemExit(main())
