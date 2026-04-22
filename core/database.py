import sqlite3
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from core.paths import DATABASE_PATH


class DatabaseManager:
    """Менеджер базы данных пользователей и операций"""

    def __init__(self, db_path: str = None, retention_days: int = 30):
        self.db_path = db_path or DATABASE_PATH
        self.retention_days = retention_days
        self._init_database()
        self._cleanup_old_logs()

    def _init_database(self):
        """Инициализация базы данных и создание таблиц"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Таблица пользователей
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

        # Таблица операций шифрования
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

        # Таблица состояний пасхалок
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

        # ===== НОВОЕ: Таблица загрузок медиа =====
        cursor.execute("""
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)

        # Индексы для ускорения поиска
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON cipher_operations(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON cipher_operations(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cipher_type ON cipher_operations(cipher_type)")

        # Индексы для медиа-загрузок
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_media_user_id ON media_downloader_logs(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_media_timestamp ON media_downloader_logs(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_media_platform ON media_downloader_logs(platform)")

        conn.commit()
        conn.close()

    def _cleanup_old_logs(self):
        """Автоочистка логов старше retention_days дней"""
        if self.retention_days <= 0:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        cutoff_str = cutoff_date.strftime('%Y-%m-%d %H:%M:%S')

        # Очистка операций шифрования
        cursor.execute("""
            DELETE FROM cipher_operations 
            WHERE timestamp < ?
        """, (cutoff_str,))
        cipher_deleted = cursor.rowcount

        # Очистка логов медиа-загрузок
        cursor.execute("""
            DELETE FROM media_downloader_logs 
            WHERE created_at < ?
        """, (cutoff_str,))
        media_deleted = cursor.rowcount

        conn.commit()
        conn.close()

        total_deleted = cipher_deleted + media_deleted
        if total_deleted > 0:
            print(f"🧹 Очищено {total_deleted} старых записей логов")

    def create_or_update_user(self, user_id: int, username: Optional[str] = None,
                              first_name: Optional[str] = None, last_name: Optional[str] = None):
        """Создаёт запись о пользователе или обновляет данные"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        full_name_parts = []
        if first_name:
            full_name_parts.append(first_name)
        if last_name:
            full_name_parts.append(last_name)
        full_name = " ".join(full_name_parts) if full_name_parts else None

        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        exists = cursor.fetchone()

        if exists:
            cursor.execute("""
                UPDATE users 
                SET username = ?, full_name = ?, last_active = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (username, full_name, user_id))
        else:
            cursor.execute("""
                INSERT INTO users (user_id, username, full_name)
                VALUES (?, ?, ?)
            """, (user_id, username, full_name))

        conn.commit()
        conn.close()

    def increment_module_stat(self, user_id: int, module_id: str):
        """Увеличивает счётчик использования модуля"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT module_stats FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()

        if result:
            try:
                stats = json.loads(result[0])
            except:
                stats = {"cipher": 0}

            stats[module_id] = stats.get(module_id, 0) + 1

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
        """Логирует успешную операцию шифрования"""
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
        """Получает полную статистику пользователя"""
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
        """Получает расширенную статистику шифрования"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) FROM cipher_operations WHERE user_id = ?
        """, (user_id,))
        total_ops = cursor.fetchone()[0]

        cursor.execute("""
            SELECT cipher_type, COUNT(*) as count 
            FROM cipher_operations 
            WHERE user_id = ?
            GROUP BY cipher_type
            ORDER BY count DESC
        """, (user_id,))
        cipher_distribution = {row[0]: row[1] for row in cursor.fetchall()}

        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT COUNT(*) FROM cipher_operations 
            WHERE user_id = ? AND DATE(timestamp) = ?
        """, (user_id, today))
        today_ops = cursor.fetchone()[0]

        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT COUNT(*) FROM cipher_operations 
            WHERE user_id = ? AND DATE(timestamp) >= ?
        """, (user_id, week_ago))
        week_ops = cursor.fetchone()[0]

        month_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT COUNT(*) FROM cipher_operations 
            WHERE user_id = ? AND DATE(timestamp) >= ?
        """, (user_id, month_ago))
        month_ops = cursor.fetchone()[0]

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
                "original_text": row[1][:50] + "..." if len(row[1]) > 50 else row[1],
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

    def get_user_easter_egg_state(self, user_id: int) -> Optional[Dict]:
        """Получение состояния пасхалки"""
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
        """Обновление состояния пасхалки"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT user_id FROM easter_eggs WHERE user_id = ?", (user_id,))
        exists = cursor.fetchone()

        if exists:
            cursor.execute("""
                UPDATE easter_eggs 
                SET current_step = ?, last_completed = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (state['current_step'], state.get('last_completed'), user_id))
        else:
            cursor.execute("""
                INSERT INTO easter_eggs (user_id, current_step, last_completed)
                VALUES (?, ?, ?)
            """, (user_id, state['current_step'], state.get('last_completed')))

        conn.commit()
        conn.close()

    def reset_user_easter_egg_state(self, user_id: int):
        """Сброс состояния пасхалки"""
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
        """Поиск операций шифрования по ключевому слову"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

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

    # ===== МЕТОДЫ ДЛЯ MEDIA DOWNLOADER =====

    def log_media_download(self, user_id: int, url: str, media_type: str,
                           platform: str, title: str, file_path: str,
                           file_size: int, quality: str):
        """
        Логирование успешной загрузки медиа
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO media_downloader_logs 
            (user_id, url, media_type, platform, title, file_path, file_size, quality)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, url, media_type, platform, title, file_path, file_size, quality))

        conn.commit()
        conn.close()

    def get_user_media_downloads(self, user_id: int, limit: int = 10) -> List[Dict]:
        """
        Получение истории загрузок пользователя
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT url, media_type, platform, title, file_size, quality, created_at
            FROM media_downloader_logs
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (user_id, limit))

        results = []
        for row in cursor.fetchall():
            results.append({
                "url": row[0],
                "media_type": row[1],
                "platform": row[2],
                "title": row[3],
                "file_size": row[4],
                "quality": row[5],
                "created_at": row[6]
            })

        conn.close()
        return results

    def get_media_download_stats(self, user_id: int) -> Dict:
        """
        Получение статистики загрузок пользователя
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Всего загрузок
        cursor.execute("""
            SELECT COUNT(*) FROM media_downloader_logs WHERE user_id = ?
        """, (user_id,))
        total_downloads = cursor.fetchone()[0]

        # По платформам
        cursor.execute("""
            SELECT platform, COUNT(*) as count 
            FROM media_downloader_logs 
            WHERE user_id = ?
            GROUP BY platform
            ORDER BY count DESC
        """, (user_id,))
        platform_distribution = {row[0]: row[1] for row in cursor.fetchall()}

        # По типам
        cursor.execute("""
            SELECT media_type, COUNT(*) as count 
            FROM media_downloader_logs 
            WHERE user_id = ?
            GROUP BY media_type
        """, (user_id,))
        type_distribution = {row[0]: row[1] for row in cursor.fetchall()}

        # Сегодня
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT COUNT(*) FROM media_downloader_logs 
            WHERE user_id = ? AND DATE(created_at) = ?
        """, (user_id, today))
        today_downloads = cursor.fetchone()[0]

        conn.close()

        return {
            "total_downloads": total_downloads,
            "platform_distribution": platform_distribution,
            "type_distribution": type_distribution,
            "today_downloads": today_downloads
        }