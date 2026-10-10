import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from io import StringIO
from pathlib import Path

from core.database import DatabaseManager
from core.migrations import DatabaseMigrator, Migration, MigrationError


class DatabaseMigrationCharacterizationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "users.db"

    def tearDown(self):
        self.temp_dir.cleanup()

    def apply(self, migrator):
        with redirect_stdout(StringIO()):
            migrator.apply_migrations()

    def test_blank_database_reaches_latest_legacy_schema(self):
        migrator = DatabaseMigrator(self.db_path)

        self.apply(migrator)

        self.assertEqual("009", migrator.get_current_version())
        with closing(sqlite3.connect(self.db_path)) as connection:
            tables = {
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }
        self.assertTrue(
            {
                "users",
                "cipher_operations",
                "easter_eggs",
                "url_shortener_logs",
                "ip_lookup_logs",
                "admin_logs",
                "decision_maker_logs",
                "coin_flip_stats",
                "media_downloader_logs",
                "steam_wishlist",
                "steam_cache",
                "migrations",
            }
            <= tables
        )

    def test_migrations_are_idempotent(self):
        migrator = DatabaseMigrator(self.db_path)
        self.apply(migrator)

        self.apply(migrator)

        with closing(sqlite3.connect(self.db_path)) as connection:
            versions = connection.execute("SELECT version FROM migrations ORDER BY id").fetchall()
        self.assertEqual([(f"{version:03d}",) for version in range(1, 10)], versions)

    def test_existing_legacy_data_survives_schema_baselining(self):
        database = DatabaseManager(self.db_path, retention_days=0)
        database.create_or_update_user(123, "legacy-user", "Legacy", "User")
        database.log_cipher_operation(123, "caesar", "abc", "def")

        migrator = DatabaseMigrator(self.db_path)
        self.apply(migrator)

        with closing(sqlite3.connect(self.db_path)) as connection:
            user = connection.execute("SELECT username FROM users WHERE user_id = 123").fetchone()
            operation_count = connection.execute(
                "SELECT COUNT(*) FROM cipher_operations WHERE user_id = 123"
            ).fetchone()[0]
        self.assertEqual(("legacy-user",), user)
        self.assertEqual(1, operation_count)

    def test_missing_earlier_version_is_applied_without_replaying_later_version(self):
        migrator = DatabaseMigrator(self.db_path)
        self.apply(migrator)
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute("DELETE FROM migrations WHERE version = '004'")
            connection.commit()

        self.assertEqual(["004"], migrator.apply_migrations())
        self.assertEqual("009", migrator.get_current_version())

    def test_unknown_future_version_stops_migration(self):
        migrator = DatabaseMigrator(self.db_path)
        self.apply(migrator)
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute("INSERT INTO migrations (version, name) VALUES ('999', 'future')")
            connection.commit()

        with self.assertRaisesRegex(MigrationError, "unknown migration versions: 999"):
            migrator.apply_migrations()

    def test_failed_migration_rolls_back_schema_and_version_record(self):
        migrator = DatabaseMigrator(self.db_path)
        migrator.migrations = (
            Migration(
                "001",
                "broken",
                (
                    "CREATE TABLE partial_table (id INTEGER PRIMARY KEY)",
                    "INSERT INTO table_that_does_not_exist VALUES (1)",
                ),
            ),
        )

        with self.assertRaisesRegex(MigrationError, "failed to apply migration 001"):
            migrator.apply_migrations()

        with closing(sqlite3.connect(self.db_path)) as connection:
            table = connection.execute(
                "SELECT name FROM sqlite_master WHERE name = 'partial_table'"
            ).fetchone()
            versions = connection.execute("SELECT version FROM migrations").fetchall()
        self.assertIsNone(table)
        self.assertEqual([], versions)

    def test_existing_module_table_data_survives_registration(self):
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute(
                """
                CREATE TABLE decision_maker_logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    action_type TEXT NOT NULL,
                    result TEXT,
                    details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                INSERT INTO decision_maker_logs (user_id, action_type, result)
                VALUES (42, 'coin', 'heads')
                """
            )
            connection.commit()

        migrator = DatabaseMigrator(self.db_path)
        self.apply(migrator)

        with closing(sqlite3.connect(self.db_path)) as connection:
            row = connection.execute("SELECT user_id, result FROM decision_maker_logs").fetchone()
        self.assertEqual((42, "heads"), row)


if __name__ == "__main__":
    unittest.main()
