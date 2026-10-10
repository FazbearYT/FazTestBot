# core/admin.py
# Система скрытой админ-панели с надёжной аутентификацией

import csv
import hmac
import json
from collections.abc import Callable
from datetime import datetime, timedelta

from config import ADMIN_SECRET_CODE, ADMIN_SESSION_HOURS, ADMINS
from core.migrations import DatabaseMigrator
from core.paths import DATABASE_PATH, EXPORTS_DIR
from core.storage import SQLiteDatabase


class AdminManager:
    """Менеджер административного доступа и функций"""

    def __init__(
        self,
        db_path: str = None,
        *,
        admins: tuple[int, ...] | list[int] | None = None,
        secret_code: str | None = None,
        session_hours: int | None = None,
        auth_max_failures: int = 5,
        auth_window_minutes: int = 15,
        auth_lockout_minutes: int = 15,
        now: Callable[[], datetime] = datetime.now,
    ):
        self.db_path = db_path or DATABASE_PATH
        self.database = SQLiteDatabase(self.db_path)
        self.admins = tuple(ADMINS if admins is None else admins)
        self.secret_code = ADMIN_SECRET_CODE if secret_code is None else secret_code
        self.session_hours = ADMIN_SESSION_HOURS if session_hours is None else session_hours
        self.auth_max_failures = auth_max_failures
        self.auth_window = timedelta(minutes=auth_window_minutes)
        self.auth_lockout = timedelta(minutes=auth_lockout_minutes)
        self.now = now
        self.admin_sessions = {}
        self._auth_failures: dict[int, dict[str, object]] = {}
        self._init_admin_log_table()

    def _init_admin_log_table(self):
        """Инициализация таблицы логов админ-действий"""
        DatabaseMigrator(self.db_path).apply_migrations()

    def authenticate_by_code(self, user_id: int, code: str) -> bool:
        """Аутентификация через секретное кодовое слово"""
        if not self.secret_code:
            return False
        now = self.now()
        attempt = self._auth_failures.get(user_id)
        if attempt is not None:
            locked_until = attempt.get("locked_until")
            if isinstance(locked_until, datetime) and now < locked_until:
                return False
            first_failure = attempt["first_failure"]
            if not isinstance(first_failure, datetime) or now - first_failure >= self.auth_window:
                self._auth_failures.pop(user_id, None)
                attempt = None
        supplied = code.strip().encode("utf-8")
        expected = self.secret_code.encode("utf-8")
        if hmac.compare_digest(supplied, expected):
            self._auth_failures.pop(user_id, None)
            expires = now + timedelta(hours=self.session_hours)
            self.admin_sessions[user_id] = {"until": expires}
            self._log_admin_action(user_id, "auth_by_code", None, f"Session until {expires}")
            return True
        if attempt is None:
            attempt = {"count": 0, "first_failure": now, "locked_until": None}
            self._auth_failures[user_id] = attempt
        attempt["count"] = int(attempt["count"]) + 1
        if attempt["count"] >= self.auth_max_failures:
            attempt["locked_until"] = now + self.auth_lockout
        return False

    def is_admin(self, user_id: int) -> bool:
        """Проверка прав администратора"""
        if user_id in self.admins:
            return True

        if user_id in self.admin_sessions:
            if self.now() < self.admin_sessions[user_id]["until"]:
                return True
            else:
                self.admin_sessions.pop(user_id, None)

        return False

    def revoke_session(self, user_id: int) -> bool:
        """Revoke a code-authenticated session; configured admins remain admins."""

        return self.admin_sessions.pop(user_id, None) is not None

    def log_admin_action(
        self, admin_id: int, action: str, target_user_id: int | None = None, details: str = ""
    ):
        """Логирование админ-действий"""
        self._log_admin_action(admin_id, action, target_user_id, details)

    def _log_admin_action(
        self, admin_id: int, action: str, target_user_id: int | None, details: str
    ):
        """Внутренний метод логирования"""
        with self.database.connection(write=True) as connection:
            connection.execute(
                """
                INSERT INTO admin_logs (admin_id, action, target_user_id, details)
                VALUES (?, ?, ?, ?)
                """,
                (admin_id, action, target_user_id, details[:500]),
            )

    def get_global_stats(self) -> dict:
        """Получение общей статистики"""
        with self.database.connection() as connection:
            total_users = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]

            week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            active_users = connection.execute(
                """
                SELECT COUNT(*) FROM users
                WHERE DATE(last_active) >= ?
                """,
                (week_ago,),
            ).fetchone()[0]

            total_ops = connection.execute("SELECT COUNT(*) FROM cipher_operations").fetchone()[0]

            today = datetime.now().strftime("%Y-%m-%d")
            today_ops = connection.execute(
                """
                SELECT COUNT(*) FROM cipher_operations
                WHERE DATE(timestamp) = ?
                """,
                (today,),
            ).fetchone()[0]

            rows = connection.execute(
                """
                SELECT cipher_type, COUNT(*) as count
                FROM cipher_operations
                GROUP BY cipher_type
                ORDER BY count DESC
                """
            ).fetchall()
            cipher_dist = {row[0]: row[1] for row in rows}

        return {
            "total_users": total_users,
            "active_users": active_users,
            "total_operations": total_ops,
            "today_operations": today_ops,
            "cipher_distribution": cipher_dist,
        }

    def get_user_profile(self, user_id: int) -> dict | None:
        """Получение полного профиля пользователя"""
        with self.database.connection() as connection:
            user_row = connection.execute(
                """
                SELECT user_id, username, full_name, created_at, last_active, module_stats
                FROM users
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()

            if not user_row:
                return None

            last_ops = connection.execute(
                """
                SELECT cipher_type, original_text, encrypted_text, timestamp
                FROM cipher_operations
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT 5
                """,
                (user_id,),
            ).fetchall()

        return {
            "user_id": user_row[0],
            "username": user_row[1] or "—",
            "full_name": user_row[2] or "—",
            "created_at": user_row[3],
            "last_active": user_row[4],
            "module_stats": json.loads(user_row[5]) if user_row[5] else {},
            "last_operations": [
                {
                    "cipher_type": op[0],
                    "original_text": op[1][:30] + "..." if len(op[1]) > 30 else op[1],
                    "encrypted_text": op[2][:30] + "..." if len(op[2]) > 30 else op[2],
                    "timestamp": op[3],
                }
                for op in last_ops
            ],
        }

    def search_operations(self, query: str) -> list[dict]:
        """Поиск операций шифрования"""
        with self.database.connection() as connection:
            rows = connection.execute(
                """
                SELECT operation_id, user_id, cipher_type, original_text, encrypted_text, timestamp
                FROM cipher_operations
                WHERE original_text LIKE ? OR encrypted_text LIKE ?
                ORDER BY timestamp DESC
                LIMIT 20
                """,
                (f"%{query}%", f"%{query}%"),
            ).fetchall()

        results = []
        for row in rows:
            results.append(
                {
                    "operation_id": row[0],
                    "user_id": row[1],
                    "cipher_type": row[2],
                    "original_text": row[3][:50] + "..." if len(row[3]) > 50 else row[3],
                    "encrypted_text": row[4][:50] + "..." if len(row[4]) > 50 else row[4],
                    "timestamp": row[5],
                }
            )
        return results

    def export_to_csv(self, filename: str = None) -> str:
        """Экспорт всех операций в CSV - ИСПРАВЛЕНО: сохранение в temp/exports/"""
        if not filename:
            filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        # ИСПРАВЛЕНО: Сохранение в temp/exports/
        filepath = EXPORTS_DIR / filename

        with self.database.connection() as connection:
            rows = connection.execute(
                """
                SELECT timestamp, user_id, cipher_type, original_text,
                       encrypted_text, language, step
                FROM cipher_operations
                ORDER BY timestamp DESC
                """
            ).fetchall()

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "timestamp",
                    "user_id",
                    "cipher_type",
                    "original_text",
                    "encrypted_text",
                    "language",
                    "step",
                ]
            )
            writer.writerows(rows)

        return str(filepath)

    def export_to_json(self, filename: str = None) -> str:
        """Экспорт всех операций в JSON - ИСПРАВЛЕНО: сохранение в temp/exports/"""
        if not filename:
            filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        # ИСПРАВЛЕНО: Сохранение в temp/exports/
        filepath = EXPORTS_DIR / filename

        with self.database.connection() as connection:
            rows = connection.execute(
                """
                SELECT operation_id, timestamp, user_id, cipher_type,
                       original_text, encrypted_text, language, step
                FROM cipher_operations
                ORDER BY timestamp DESC
                """
            ).fetchall()

        operations = []
        for row in rows:
            operations.append(
                {
                    "operation_id": row[0],
                    "timestamp": row[1],
                    "user_id": row[2],
                    "cipher_type": row[3],
                    "original_text": row[4],
                    "encrypted_text": row[5],
                    "language": row[6],
                    "step": row[7],
                }
            )

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(operations, f, ensure_ascii=False, indent=2)
        return str(filepath)

    def cleanup_logs(self, days: int):
        """Ручная очистка логов"""
        if days <= 0:
            return 0

        cutoff_date = datetime.now() - timedelta(days=days)
        with self.database.connection(write=True) as connection:
            cursor = connection.execute(
                """
                DELETE FROM cipher_operations
                WHERE timestamp < ?
                """,
                (cutoff_date.strftime("%Y-%m-%d %H:%M:%S"),),
            )
            deleted = cursor.rowcount

        return deleted

    def emergency_clear_all(self):
        """Экстренная полная очистка"""
        with self.database.connection(write=True) as connection:
            cursor = connection.execute("DELETE FROM cipher_operations")
            ops_deleted = cursor.rowcount

            # ИСПРАВЛЕНО: SQL injection через параметризованный запрос
            if self.admins:
                placeholders = ",".join(["?" for _ in self.admins])
                cursor = connection.execute(
                    f"DELETE FROM users WHERE user_id NOT IN ({placeholders})",
                    self.admins,
                )
            else:
                cursor = connection.execute("DELETE FROM users")

            users_deleted = cursor.rowcount

        return ops_deleted, users_deleted


# Глобальный экземпляр
admin_manager = AdminManager()
