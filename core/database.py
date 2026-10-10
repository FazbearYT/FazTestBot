"""Database access for users, cipher operations, and easter-egg state."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from core.migrations import DatabaseMigrator
from core.paths import DATABASE_PATH
from core.storage import SQLiteDatabase


class DatabaseManager:
    """Preserve the legacy data API on top of the shared SQLite layer."""

    def __init__(self, db_path: str | Path | None = None, retention_days: int = 30):
        self.db_path = Path(db_path or DATABASE_PATH)
        self.database = SQLiteDatabase(self.db_path)
        self.retention_days = retention_days
        DatabaseMigrator(self.db_path).apply_migrations()
        self._cleanup_old_logs()

    def _cleanup_old_logs(self) -> None:
        """Keep the existing cipher-log retention behavior unchanged."""

        if self.retention_days <= 0:
            return
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        with self.database.connection(write=True) as connection:
            cursor = connection.execute(
                "DELETE FROM cipher_operations WHERE timestamp < ?",
                (cutoff_date.strftime("%Y-%m-%d %H:%M:%S"),),
            )
            deleted = cursor.rowcount
        if deleted > 0:
            print(f"🧹 Очищено {deleted} старых записей логов")

    def create_or_update_user(
        self,
        user_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> None:
        full_name_parts = [part for part in (first_name, last_name) if part]
        full_name = " ".join(full_name_parts) if full_name_parts else None
        with self.database.connection(write=True) as connection:
            connection.execute(
                """
                INSERT INTO users (user_id, username, full_name)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    full_name = excluded.full_name,
                    last_active = CURRENT_TIMESTAMP
                """,
                (user_id, username, full_name),
            )

    def increment_module_stat(self, user_id: int, module_id: str) -> None:
        with self.database.connection(write=True) as connection:
            connection.execute("BEGIN IMMEDIATE")
            result = connection.execute(
                "SELECT module_stats FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
            if result is None:
                return
            try:
                stats = json.loads(result[0])
            except (TypeError, json.JSONDecodeError):
                stats = {"cipher": 0}
            stats[module_id] = stats.get(module_id, 0) + 1
            connection.execute(
                """
                UPDATE users
                SET module_stats = ?, last_active = CURRENT_TIMESTAMP
                WHERE user_id = ?
                """,
                (json.dumps(stats), user_id),
            )

    def log_cipher_operation(
        self,
        user_id: int,
        cipher_type: str,
        original_text: str,
        encrypted_text: str,
        language: str | None = None,
        step: int | None = None,
        session_id: str | None = None,
    ) -> None:
        with self.database.connection(write=True) as connection:
            connection.execute(
                """
                INSERT INTO cipher_operations
                    (operation_id, user_id, cipher_type, original_text, encrypted_text,
                     language, step, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    user_id,
                    cipher_type,
                    original_text,
                    encrypted_text,
                    language,
                    step,
                    session_id,
                ),
            )

    def get_user_stats(self, user_id: int) -> dict[str, Any] | None:
        with self.database.connection() as connection:
            result = connection.execute(
                """
                SELECT user_id, username, full_name, created_at, last_active, module_stats
                FROM users WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
        if result is None:
            return None
        return {
            "user_id": result[0],
            "username": result[1],
            "full_name": result[2],
            "created_at": result[3],
            "last_active": result[4],
            "module_stats": json.loads(result[5]) if result[5] else {},
        }

    def get_user_cipher_stats(self, user_id: int) -> dict[str, Any]:
        today = datetime.now().strftime("%Y-%m-%d")
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        with self.database.connection() as connection:
            total_ops = connection.execute(
                "SELECT COUNT(*) FROM cipher_operations WHERE user_id = ?", (user_id,)
            ).fetchone()[0]
            rows = connection.execute(
                """
                SELECT cipher_type, COUNT(*) AS count
                FROM cipher_operations WHERE user_id = ?
                GROUP BY cipher_type ORDER BY count DESC
                """,
                (user_id,),
            ).fetchall()
            cipher_distribution = {row[0]: row[1] for row in rows}
            today_ops = connection.execute(
                """
                SELECT COUNT(*) FROM cipher_operations
                WHERE user_id = ? AND DATE(timestamp) = ?
                """,
                (user_id, today),
            ).fetchone()[0]
            week_ops = connection.execute(
                """
                SELECT COUNT(*) FROM cipher_operations
                WHERE user_id = ? AND DATE(timestamp) >= ?
                """,
                (user_id, week_ago),
            ).fetchone()[0]
            month_ops = connection.execute(
                """
                SELECT COUNT(*) FROM cipher_operations
                WHERE user_id = ? AND DATE(timestamp) >= ?
                """,
                (user_id, month_ago),
            ).fetchone()[0]
            recent_rows = connection.execute(
                """
                SELECT cipher_type, original_text, encrypted_text, language, step, timestamp
                FROM cipher_operations WHERE user_id = ?
                ORDER BY timestamp DESC LIMIT 5
                """,
                (user_id,),
            ).fetchall()

        last_operations = [
            {
                "cipher_type": row[0],
                "original_text": self._preview(row[1]),
                "encrypted_text": self._preview(row[2]),
                "language": row[3] or "-",
                "step": row[4] or "-",
                "timestamp": row[5],
            }
            for row in recent_rows
        ]
        return {
            "total_operations": total_ops,
            "cipher_distribution": cipher_distribution,
            "today_ops": today_ops,
            "week_ops": week_ops,
            "month_ops": month_ops,
            "last_operations": last_operations,
        }

    def get_all_users(self) -> list[dict[str, Any]]:
        with self.database.connection() as connection:
            rows = connection.execute(
                """
                SELECT user_id, username, full_name, created_at, last_active, module_stats
                FROM users ORDER BY last_active DESC
                """
            ).fetchall()
        return [
            {
                "user_id": row[0],
                "username": row[1],
                "full_name": row[2],
                "created_at": row[3],
                "last_active": row[4],
                "module_stats": json.loads(row[5]) if row[5] else {},
            }
            for row in rows
        ]

    def get_user_easter_egg_state(self, user_id: int) -> dict[str, Any] | None:
        with self.database.connection() as connection:
            result = connection.execute(
                """
                SELECT current_step, last_completed, created_at, updated_at
                FROM easter_eggs WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
        if result is None:
            return None
        return {
            "current_step": result[0],
            "last_completed": result[1],
            "created_at": result[2],
            "updated_at": result[3],
        }

    def update_user_easter_egg_state(self, user_id: int, state: dict[str, Any]) -> None:
        with self.database.connection(write=True) as connection:
            connection.execute(
                """
                INSERT INTO easter_eggs (user_id, current_step, last_completed)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    current_step = excluded.current_step,
                    last_completed = excluded.last_completed,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user_id, state["current_step"], state.get("last_completed")),
            )

    def reset_user_easter_egg_state(self, user_id: int) -> None:
        with self.database.connection(write=True) as connection:
            connection.execute(
                """
                UPDATE easter_eggs
                SET current_step = 0, last_completed = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                """,
                (user_id,),
            )

    def search_cipher_operations(self, query: str) -> list[dict[str, Any]]:
        with self.database.connection() as connection:
            rows = connection.execute(
                """
                SELECT operation_id, user_id, cipher_type, original_text,
                       encrypted_text, timestamp
                FROM cipher_operations
                WHERE original_text LIKE ? OR encrypted_text LIKE ?
                ORDER BY timestamp DESC LIMIT 20
                """,
                (f"%{query}%", f"%{query}%"),
            ).fetchall()
        return [
            {
                "operation_id": row[0],
                "user_id": row[1],
                "cipher_type": row[2],
                "original_text": self._preview(row[3]),
                "encrypted_text": self._preview(row[4]),
                "timestamp": row[5],
            }
            for row in rows
        ]

    @staticmethod
    def _preview(value: str) -> str:
        return value[:50] + "..." if len(value) > 50 else value
