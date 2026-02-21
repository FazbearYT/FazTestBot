# core/database.py
# Менеджер базы данных для логирования пользователей и операций шифрования
# Версия: 4.0.1
# Дата: 21.02.2026

import sqlite3
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, List


class DatabaseManager:
    """Менеджер базы данных пользователей и операций шифрования"""

    def __init__(self, db_path: str = "users.db", retention_days: int = 30):
        self.db_path = db_path
        self.retention_days = retention_days
        self._init_database()
        self._cleanup_old_logs()

    def _init_database(self):
        """Инициализация базы данных и создание таблиц"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Таблица пользователей (сохранена из версии 3.1)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                module_stats TEXT DEFAULT '{"cipher": 0}'
            )
        """)

        # Таблица операций шифрования (версия 3.2)
        cursor.execute("""
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
        """)

        # НОВАЯ ТАБЛИЦА: Состояния пасхалок (версия 3.4.3)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS easter_eggs (
                user_id INTEGER PRIMARY KEY,
                current_step INTEGER DEFAULT 0,
                last_completed TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)

        # Индексы для ускорения поиска
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON cipher_operations(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON cipher_operations(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cipher_type ON cipher_operations(cipher_type)")

        conn.commit()
        conn.close()

    def _cleanup_old_logs(self):
        """Автоочистка логов старше retention_days дней"""
        if self.retention_days <= 0:
            return  # Отключена очистка

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        cursor.execute("""
            DELETE FROM cipher_operations 
            WHERE timestamp < ?
        """, (cutoff_date.strftime('%Y-%m-%d %H:%M:%S'),))

        deleted = cursor.rowcount
        conn.commit()
        conn.close()

        if deleted > 0:
            print(f"🧹 Очищено {deleted} старых записей логов (старше {self.retention_days} дней)")

    def create_or_update_user(self, user_id: int, username: Optional[str] = None,
                              first_name: Optional[str] = None, last_name: Optional[str] = None):
        """
        Создаёт запись о пользователе при первом взаимодействии или обновляет данные

        :param user_id: ID пользователя в Telegram
        :param username: Юзернейм (без @)
        :param first_name: Имя из профиля
        :param last_name: Фамилия из профиля
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Формируем полное имя
        full_name_parts = []
        if first_name:
            full_name_parts.append(first_name)
        if last_name:
            full_name_parts.append(last_name)
        full_name = " ".join(full_name_parts) if full_name_parts else None

        # Проверяем существование пользователя
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        exists = cursor.fetchone()

        if exists:
            # Обновляем существующую запись
            cursor.execute("""
                UPDATE users 
                SET username = ?, full_name = ?, last_active = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (username, full_name, user_id))
        else:
            # Создаём новую запись
            cursor.execute("""
                INSERT INTO users (user_id, username, full_name)
                VALUES (?, ?, ?)
            """, (user_id, username, full_name))

        conn.commit()
        conn.close()

    def increment_module_stat(self, user_id: int, module_id: str):
        """
        Увеличивает счётчик использования модуля для пользователя

        :param user_id: ID пользователя
        :param module_id: ID модуля (например, "cipher")
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Получаем текущую статистику
        cursor.execute("SELECT module_stats FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()

        if result:
            try:
                stats = json.loads(result[0])
            except:
                stats = {"cipher": 0}

            # Инкрементируем счётчик модуля
            stats[module_id] = stats.get(module_id, 0) + 1

            # Сохраняем обновлённую статистику
            cursor.execute("""
                UPDATE users 
                SET module_stats = ?, last_active = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (json.dumps(stats), user_id))
            conn.commit()

        conn.close()

    def log_cipher_operation(self, user_id: int, cipher_type: str,
                             original_text: str, encrypted_text: str,
                             language: Optional[str] = None, step: Optional[int] = None,
                             session_id: Optional[str] = None):
        """
        Логирует успешную операцию шифрования с полным контентом

        :param user_id: ID пользователя
        :param cipher_type: Тип шифра (morze, numbers, caesar, qr)
        :param original_text: Исходный текст до шифрования
        :param encrypted_text: Результат после шифрования
        :param language: Язык для Цезаря (ru/en)
        :param step: Шаг для Цезаря
        :param session_id: Идентификатор сессии для группировки операций
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        operation_id = str(uuid.uuid4())

        cursor.execute("""
            INSERT INTO cipher_operations 
            (operation_id, user_id, cipher_type, original_text, encrypted_text, 
             language, step, session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            operation_id, user_id, cipher_type, original_text, encrypted_text,
            language, step, session_id
        ))

        conn.commit()
        conn.close()

    def get_user_stats(self, user_id: int) -> Optional[Dict]:
        """
        Получает полную статистику пользователя

        :return: Словарь с данными пользователя или None
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT user_id, username, full_name, created_at, last_active, module_stats
            FROM users 
            WHERE user_id = ?
        """, (user_id,))
        result = cursor.fetchone()
        conn.close()

        if result:
            return {
                "user_id": result[0],
                "username": result[1],
                "full_name": result[2],
                "created_at": result[3],
                "last_active": result[4],
                "module_stats": json.loads(result[5]) if result[5] else {}
            }
        return None

    def get_user_cipher_stats(self, user_id: int) -> Dict:
        """
        Получает расширенную статистику шифрования для пользователя

        :return: Словарь со статистикой операций
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Общее количество операций
        cursor.execute("""
            SELECT COUNT(*) FROM cipher_operations WHERE user_id = ?
        """, (user_id,))
        total_ops = cursor.fetchone()[0]

        # Распределение по типам шифров
        cursor.execute("""
            SELECT cipher_type, COUNT(*) as count 
            FROM cipher_operations 
            WHERE user_id = ?
            GROUP BY cipher_type
            ORDER BY count DESC
        """, (user_id,))
        cipher_distribution = {row[0]: row[1] for row in cursor.fetchall()}

        # Операции за сегодня
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT COUNT(*) FROM cipher_operations 
            WHERE user_id = ? AND DATE(timestamp) = ?
        """, (user_id, today))
        today_ops = cursor.fetchone()[0]

        # Операции за неделю
        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT COUNT(*) FROM cipher_operations 
            WHERE user_id = ? AND DATE(timestamp) >= ?
        """, (user_id, week_ago))
        week_ops = cursor.fetchone()[0]

        # Операции за месяц
        month_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT COUNT(*) FROM cipher_operations 
            WHERE user_id = ? AND DATE(timestamp) >= ?
        """, (user_id, month_ago))
        month_ops = cursor.fetchone()[0]

        # Последние 5 операций
        cursor.execute("""
            SELECT cipher_type, original_text, encrypted_text, language, step, timestamp
            FROM cipher_operations 
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT 5
        """, (user_id,))
        last_operations = []
        for row in cursor.fetchall():
            op = {
                "cipher_type": row[0],
                "original_text": row[1][:50] + "..." if len(row[1]) > 50 else row[1],  # Обрезаем длинные тексты
                "encrypted_text": row[2][:50] + "..." if len(row[2]) > 50 else row[2],
                "language": row[3] or "-",
                "step": row[4] or "-",
                "timestamp": row[5]
            }
            last_operations.append(op)

        conn.close()

        return {
            "total_operations": total_ops,
            "cipher_distribution": cipher_distribution,
            "today_ops": today_ops,
            "week_ops": week_ops,
            "month_ops": month_ops,
            "last_operations": last_operations
        }

    def get_all_users(self) -> list:
        """Получает список всех пользователей"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT user_id, username, full_name, created_at, last_active, module_stats
            FROM users 
            ORDER BY last_active DESC
        """)
        results = cursor.fetchall()
        conn.close()

        users = []
        for row in results:
            users.append({
                "user_id": row[0],
                "username": row[1],
                "full_name": row[2],
                "created_at": row[3],
                "last_active": row[4],
                "module_stats": json.loads(row[5]) if row[5] else {}
            })

        return users

    # ====== НОВЫЕ МЕТОДЫ ДЛЯ ПАСХАЛОК (версия 3.4.3) ======

    def get_user_easter_egg_state(self, user_id: int) -> Optional[Dict]:
        """Получение состояния пасхалки для пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT current_step, last_completed, created_at, updated_at
            FROM easter_eggs 
            WHERE user_id = ?
        """, (user_id,))
        result = cursor.fetchone()
        conn.close()

        if result:
            return {
                "current_step": result[0],
                "last_completed": result[1],
                "created_at": result[2],
                "updated_at": result[3]
            }
        return None

    def update_user_easter_egg_state(self, user_id: int, state: Dict):
        """Обновление состояния пасхалки для пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Проверяем существование записи
        cursor.execute("SELECT user_id FROM easter_eggs WHERE user_id = ?", (user_id,))
        exists = cursor.fetchone()

        if exists:
            # Обновляем существующую запись
            cursor.execute("""
                UPDATE easter_eggs 
                SET current_step = ?, last_completed = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (state['current_step'], state.get('last_completed'), user_id))
        else:
            # Создаём новую запись
            cursor.execute("""
                INSERT INTO easter_eggs (user_id, current_step, last_completed)
                VALUES (?, ?, ?)
            """, (user_id, state['current_step'], state.get('last_completed')))

        conn.commit()
        conn.close()

    def reset_user_easter_egg_state(self, user_id: int):
        """Сброс состояния пасхалки для пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE easter_eggs 
            SET current_step = 0, last_completed = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (user_id,))

        conn.commit()
        conn.close()

    def search_cipher_operations(self, query: str) -> List[Dict]:
        """
        Поиск операций шифрования по ключевому слову

        :param query: Ключевое слово для поиска
        :return: Список найденных операций
        """
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