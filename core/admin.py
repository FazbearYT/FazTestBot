# core/admin.py
# Система скрытой админ-панели с надёжной аутентификацией

import sqlite3
import json
import csv
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from telebot import types
from config import ADMINS, ADMIN_SECRET_CODE, ADMIN_SESSION_HOURS


class AdminManager:
    """Менеджер административного доступа и функций"""

    def __init__(self, db_path: str = "users.db"):
        self.db_path = db_path
        self.admin_sessions = {}  # {user_id: {'until': datetime}}
        self._init_admin_log_table()

    def _init_admin_log_table(self):
        """Инициализация таблицы логов админ-действий"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                target_user_id INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                details TEXT
            )
        """)

        conn.commit()
        conn.close()

    def authenticate_by_code(self, user_id: int, code: str) -> bool:
        """Аутентификация через секретное кодовое слово (получение статуса админа)"""
        if code.strip() == ADMIN_SECRET_CODE:
            # Создаём временную сессию на указанное количество часов
            expires = datetime.now() + timedelta(hours=ADMIN_SESSION_HOURS)
            self.admin_sessions[user_id] = {'until': expires}
            self._log_admin_action(user_id, "auth_by_code", None, f"Session until {expires}")
            return True
        return False

    def is_admin(self, user_id: int) -> bool:
        """Проверка прав администратора (постоянного или временного)"""
        # Проверяем постоянных админов
        if user_id in ADMINS:
            return True

        # Проверяем временные сессии
        if user_id in self.admin_sessions:
            if datetime.now() < self.admin_sessions[user_id]['until']:
                return True
            else:
                # Сессия истекла — удаляем
                self.admin_sessions.pop(user_id, None)

        return False

    def log_admin_action(self, admin_id: int, action: str, target_user_id: Optional[int] = None, details: str = ""):
        """Логирование админ-действий"""
        self._log_admin_action(admin_id, action, target_user_id, details)

    def _log_admin_action(self, admin_id: int, action: str, target_user_id: Optional[int], details: str):
        """Внутренний метод логирования админ-действий"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO admin_logs (admin_id, action, target_user_id, details)
            VALUES (?, ?, ?, ?)
        """, (admin_id, action, target_user_id, details[:500]))  # Ограничиваем длину

        conn.commit()
        conn.close()

    def get_global_stats(self) -> Dict:
        """Получение общей статистики по всем пользователям"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Общее количество пользователей
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]

        # Активные пользователи (за последние 7 дней)
        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT COUNT(*) FROM users 
            WHERE DATE(last_active) >= ?
        """, (week_ago,))
        active_users = cursor.fetchone()[0]

        # Общее количество операций
        cursor.execute("SELECT COUNT(*) FROM cipher_operations")
        total_ops = cursor.fetchone()[0]

        # Операции за сегодня
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT COUNT(*) FROM cipher_operations 
            WHERE DATE(timestamp) = ?
        """, (today,))
        today_ops = cursor.fetchone()[0]

        # Распределение по типам шифров
        cursor.execute("""
            SELECT cipher_type, COUNT(*) as count 
            FROM cipher_operations 
            GROUP BY cipher_type
            ORDER BY count DESC
        """)
        cipher_dist = {row[0]: row[1] for row in cursor.fetchall()}

        conn.close()

        return {
            "total_users": total_users,
            "active_users": active_users,
            "total_operations": total_ops,
            "today_operations": today_ops,
            "cipher_distribution": cipher_dist
        }

    def get_user_profile(self, user_id: int) -> Optional[Dict]:
        """Получение полного профиля пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Основная информация
        cursor.execute("""
            SELECT user_id, username, full_name, created_at, last_active, module_stats
            FROM users 
            WHERE user_id = ?
        """, (user_id,))
        user_row = cursor.fetchone()

        if not user_row:
            conn.close()
            return None

        # Последние 5 операций
        cursor.execute("""
            SELECT cipher_type, original_text, encrypted_text, timestamp
            FROM cipher_operations 
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT 5
        """, (user_id,))
        last_ops = cursor.fetchall()

        conn.close()

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
                    "timestamp": op[3]
                }
                for op in last_ops
            ]
        }

    def search_operations(self, query: str) -> List[Dict]:
        """Поиск операций шифрования по ключевому слову"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Поиск по исходному тексту и результату
        cursor.execute("""
            SELECT operation_id, user_id, cipher_type, original_text, encrypted_text, timestamp
            FROM cipher_operations 
            WHERE original_text LIKE ? OR encrypted_text LIKE ?
            ORDER BY timestamp DESC
            LIMIT 20
        """, (f"%{query}%", f"%{query}%"))

        results = []
        for row in cursor.fetchall():
            results.append({
                "operation_id": row[0],
                "user_id": row[1],
                "cipher_type": row[2],
                "original_text": row[3][:50] + "..." if len(row[3]) > 50 else row[3],
                "encrypted_text": row[4][:50] + "..." if len(row[4]) > 50 else row[4],
                "timestamp": row[5]
            })

        conn.close()
        return results

    def export_to_csv(self, filename: str = "export.csv"):
        """Экспорт всех операций в CSV"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT timestamp, user_id, cipher_type, original_text, encrypted_text, language, step
            FROM cipher_operations
            ORDER BY timestamp DESC
        """)

        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(
                ['timestamp', 'user_id', 'cipher_type', 'original_text', 'encrypted_text', 'language', 'step'])
            writer.writerows(cursor.fetchall())

        conn.close()
        return filename

    def export_to_json(self, filename: str = "export.json"):
        """Экспорт всех операций в JSON"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT operation_id, timestamp, user_id, cipher_type, 
                   original_text, encrypted_text, language, step
            FROM cipher_operations
            ORDER BY timestamp DESC
        """)

        operations = []
        for row in cursor.fetchall():
            operations.append({
                "operation_id": row[0],
                "timestamp": row[1],
                "user_id": row[2],
                "cipher_type": row[3],
                "original_text": row[4],
                "encrypted_text": row[5],
                "language": row[6],
                "step": row[7]
            })

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(operations, f, ensure_ascii=False, indent=2)

        conn.close()
        return filename

    def cleanup_logs(self, days: int):
        """Ручная очистка логов старше указанного количества дней"""
        if days <= 0:
            return 0

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cutoff_date = datetime.now() - timedelta(days=days)
        cursor.execute("""
            DELETE FROM cipher_operations 
            WHERE timestamp < ?
        """, (cutoff_date.strftime('%Y-%m-%d %H:%M:%S'),))

        deleted = cursor.rowcount
        conn.commit()
        conn.close()

        return deleted

    def emergency_clear_all(self):
        """Экстренная полная очистка ВСЕХ логов (требует подтверждения)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Очищаем операции
        cursor.execute("DELETE FROM cipher_operations")
        ops_deleted = cursor.rowcount

        # Очищаем пользователей (кроме админов)
        cursor.execute("DELETE FROM users WHERE user_id NOT IN ({})".format(','.join(map(str, ADMINS))))
        users_deleted = cursor.rowcount

        conn.commit()
        conn.close()

        return ops_deleted, users_deleted


# Глобальный экземпляр админ-менеджера
admin_manager = AdminManager()