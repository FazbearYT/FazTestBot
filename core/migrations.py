"""Ordered, transactional SQLite schema migrations for FazTestBot."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from core.paths import DATABASE_PATH
from core.storage import SQLiteDatabase


class MigrationError(RuntimeError):
    """Raised when the on-disk schema cannot be migrated safely."""


@dataclass(frozen=True, slots=True)
class Migration:
    version: str
    name: str
    statements: tuple[str, ...]
    apply: Callable[[sqlite3.Connection], None] | None = None


def _add_steam_app_id(connection: sqlite3.Connection) -> None:
    """Add the regional Steam identifier without replaying destructive conversion."""

    columns = {row[1] for row in connection.execute("PRAGMA table_info(steam_wishlist)").fetchall()}
    if "steam_app_id" in columns:
        return
    connection.execute("ALTER TABLE steam_wishlist ADD COLUMN steam_app_id TEXT")
    connection.execute(
        """
        UPDATE steam_wishlist
        SET current_price = NULL,
            historical_low = NULL,
            discount_percent = NULL
        """
    )


MIGRATIONS = (
    Migration(
        "001",
        "create_base_tables",
        (
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                module_stats TEXT DEFAULT '{"cipher": 0}'
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS cipher_operations (
                operation_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                cipher_type TEXT NOT NULL,
                original_text TEXT NOT NULL,
                encrypted_text TEXT NOT NULL,
                language TEXT,
                step INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                session_id TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
            """,
        ),
    ),
    Migration(
        "002",
        "add_easter_eggs_table",
        (
            """
            CREATE TABLE IF NOT EXISTS easter_eggs (
                user_id INTEGER PRIMARY KEY,
                current_step INTEGER DEFAULT 0,
                last_completed TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
            """,
        ),
    ),
    Migration(
        "003",
        "add_url_shortener_table",
        (
            """
            CREATE TABLE IF NOT EXISTS url_shortener_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                original_url TEXT NOT NULL,
                shortened_url TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                clicks_count INTEGER DEFAULT 0
            )
            """,
        ),
    ),
    Migration(
        "004",
        "add_ip_lookup_table",
        (
            """
            CREATE TABLE IF NOT EXISTS ip_lookup_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                query TEXT NOT NULL,
                ip TEXT,
                city TEXT,
                country TEXT,
                isp TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
        ),
    ),
    Migration(
        "005",
        "add_indexes",
        (
            "CREATE INDEX IF NOT EXISTS idx_user_id ON cipher_operations(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_timestamp ON cipher_operations(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_cipher_type ON cipher_operations(cipher_type)",
        ),
    ),
    Migration(
        "006",
        "add_admin_logs_table",
        (
            """
            CREATE TABLE IF NOT EXISTS admin_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                target_user_id INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                details TEXT
            )
            """,
        ),
    ),
    Migration(
        "007",
        "add_decision_maker_tables",
        (
            """
            CREATE TABLE IF NOT EXISTS decision_maker_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                result TEXT,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS coin_flip_stats (
                user_id INTEGER PRIMARY KEY,
                heads_count INTEGER DEFAULT 0,
                tails_count INTEGER DEFAULT 0,
                total_count INTEGER DEFAULT 0,
                last_flip TIMESTAMP
            )
            """,
        ),
    ),
    Migration(
        "008",
        "add_media_downloader_table",
        (
            """
            CREATE TABLE IF NOT EXISTS media_downloader_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                media_type TEXT NOT NULL,
                platform TEXT,
                title TEXT,
                file_path TEXT,
                file_size INTEGER,
                quality TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
        ),
    ),
    Migration(
        "009",
        "add_steam_deals_tables",
        (
            """
            CREATE TABLE IF NOT EXISTS steam_wishlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                game_id TEXT NOT NULL,
                game_name TEXT NOT NULL,
                current_price REAL,
                historical_low REAL,
                discount_percent REAL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, game_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS steam_cache (
                cache_key TEXT PRIMARY KEY,
                cache_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
        ),
    ),
    Migration(
        "010",
        "add_steam_app_id",
        (),
        apply=_add_steam_app_id,
    ),
)


class DatabaseMigrator:
    """Apply every missing known migration exactly once."""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path or DATABASE_PATH)
        self.database = SQLiteDatabase(self.db_path)
        self.migrations = MIGRATIONS

    def _ensure_migration_table(self) -> None:
        with self.database.connection(write=True) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS migrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def _read_applied_versions(self) -> set[str]:
        if not self.db_path.is_file():
            return set()
        with self.database.connection(read_only=True) as connection:
            table_exists = connection.execute(
                """
                SELECT 1 FROM sqlite_master
                WHERE type = 'table' AND name = 'migrations'
                """
            ).fetchone()
            if table_exists is None:
                return set()
            rows = connection.execute("SELECT version FROM migrations").fetchall()
        applied = {row[0] for row in rows}
        known = {migration.version for migration in self.migrations}
        unknown = sorted(applied - known)
        if unknown:
            versions = ", ".join(unknown)
            raise MigrationError(f"database contains unknown migration versions: {versions}")
        return applied

    def _applied_versions(self) -> set[str]:
        self._ensure_migration_table()
        return self._read_applied_versions()

    def pending_versions(self) -> list[str]:
        applied = self._read_applied_versions()
        return [
            migration.version for migration in self.migrations if migration.version not in applied
        ]

    def get_current_version(self) -> str:
        applied = self._read_applied_versions()
        current = "0"
        for migration in self.migrations:
            if migration.version in applied:
                current = migration.version
        return current

    def apply_migrations(self) -> list[str]:
        applied = self._applied_versions()
        completed: list[str] = []

        for migration in self.migrations:
            if migration.version in applied:
                continue
            try:
                with self.database.connection(write=True) as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    if migration.apply is not None:
                        migration.apply(connection)
                    else:
                        for statement in migration.statements:
                            connection.execute(statement)
                    connection.execute(
                        "INSERT INTO migrations (version, name) VALUES (?, ?)",
                        (migration.version, migration.name),
                    )
            except Exception as error:
                raise MigrationError(
                    f"failed to apply migration {migration.version} ({migration.name})"
                ) from error
            completed.append(migration.version)

        return completed

    def rollback(self, target_version: str | None = None) -> None:
        del target_version
        raise MigrationError("automatic migration rollback is not supported; restore a backup")


migrator = DatabaseMigrator()


def run_migrations() -> list[str]:
    return migrator.apply_migrations()
