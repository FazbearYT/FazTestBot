# core/migrations.py
# Система миграций базы данных FazTestBot

import sqlite3
from datetime import datetime
from typing import List, Callable
from core.paths import DATABASE_PATH


class DatabaseMigrator:
    """Управление миграциями базы данных"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DATABASE_PATH
        self.migrations = []
        self._register_migrations()

    def _register_migrations(self):
        """Регистрация всех миграций"""

        # Миграция 1: Создание таблиц users и cipher_operations
        def migration_001():
            return """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    module_stats TEXT DEFAULT '{"cipher": 0}'
                );

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
                );
            """

        # Миграция 2: Добавление таблицы easter_eggs
        def migration_002():
            return """
                CREATE TABLE IF NOT EXISTS easter_eggs (
                    user_id INTEGER PRIMARY KEY,
                    current_step INTEGER DEFAULT 0,
                    last_completed TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                );
            """

        # Миграция 3: Добавление таблицы url_shortener_logs
        def migration_003():
            return """
                CREATE TABLE IF NOT EXISTS url_shortener_logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    original_url TEXT NOT NULL,
                    shortened_url TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    clicks_count INTEGER DEFAULT 0
                );
            """

        # Миграция 4: Добавление таблицы ip_lookup_logs
        def migration_004():
            return """
                CREATE TABLE IF NOT EXISTS ip_lookup_logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    query TEXT NOT NULL,
                    ip TEXT,
                    city TEXT,
                    country TEXT,
                    isp TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """

        # Миграция 5: Добавление индексов для ускорения
        def migration_005():
            return """
                CREATE INDEX IF NOT EXISTS idx_user_id ON cipher_operations(user_id);
                CREATE INDEX IF NOT EXISTS idx_timestamp ON cipher_operations(timestamp);
                CREATE INDEX IF NOT EXISTS idx_cipher_type ON cipher_operations(cipher_type);
            """

        # Миграция 6: Таблица admin_logs
        def migration_006():
            return """
                CREATE TABLE IF NOT EXISTS admin_logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    target_user_id INTEGER,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    details TEXT
                );
            """

        # Регистрируем миграции (порядок важен!)
        self.migrations = [
            ("001", "create_base_tables", migration_001),
            ("002", "add_easter_eggs_table", migration_002),
            ("003", "add_url_shortener_table", migration_003),
            ("004", "add_ip_lookup_table", migration_004),
            ("005", "add_indexes", migration_005),
            ("006", "add_admin_logs_table", migration_006),
        ]

    def get_current_version(self) -> str:
        """Получение текущей версии БД"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Проверяем существует ли таблица миграций
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='migrations'
        """)

        if not cursor.fetchone():
            conn.close()
            return "0"

        # Получаем последнюю применённую миграцию
        cursor.execute("""
            SELECT version FROM migrations 
            ORDER BY applied_at DESC 
            LIMIT 1
        """)

        result = cursor.fetchone()
        conn.close()

        return result[0] if result else "0"

    def apply_migrations(self):
        """Применение всех неприменённых миграций"""
        current_version = self.get_current_version()
        current_index = next(
            (i for i, (ver, _, _) in enumerate(self.migrations) if ver == current_version),
            -1
        )

        print(f"📊 Текущая версия БД: {current_version}")
        print(f"📦 Доступно миграций: {len(self.migrations) - current_index - 1}")

        for i in range(current_index + 1, len(self.migrations)):
            version, name, migration_func = self.migrations[i]

            print(f"🔄 Применяю миграцию {version}: {name}...")

            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                # Создаём таблицу migrations если не существует
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS migrations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        version TEXT NOT NULL UNIQUE,
                        name TEXT NOT NULL,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Выполняем миграцию
                cursor.executescript(migration_func())

                # Записываем информацию о применённой миграции
                cursor.execute("""
                    INSERT INTO migrations (version, name)
                    VALUES (?, ?)
                """, (version, name))

                conn.commit()
                conn.close()

                print(f"✅ Миграция {version} применена успешно")

            except Exception as e:
                print(f"❌ Ошибка применения миграции {version}: {e}")
                raise

    def rollback(self, target_version: str = None):
        """
        Откат миграций до указанной версии

        :param target_version: Версия до которой откатиться (None = откат на 1 версию)
        """
        current_version = self.get_current_version()

        if current_version == "0":
            print("⚠️ Нет миграций для отката")
            return

        current_index = next(
            (i for i, (ver, _, _) in enumerate(self.migrations) if ver == current_version),
            -1
        )

        if current_index < 0:
            print("⚠️ Текущая версия не найдена в списке миграций")
            return

        # Определяем до какой версии откатываться
        if target_version:
            target_index = next(
                (i for i, (ver, _, _) in enumerate(self.migrations) if ver == target_version),
                -1
            )
        else:
            target_index = current_index - 1

        if target_index < 0:
            print("⚠️ Невозможно откатиться дальше")
            return

        print(f"⏮️  Откат с версии {current_version} до версии {self.migrations[target_index][0]}...")

        # NOTE: Для полноценного rollback нужны обратные миграции
        # Это упрощённая версия
        print("⚠️ Функция rollback требует реализации обратных миграций")


# Глобальный экземпляр
migrator = DatabaseMigrator()


def run_migrations():
    """Удобная функция для применения миграций"""
    migrator.apply_migrations()