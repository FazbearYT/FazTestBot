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

        self.assertEqual("010", migrator.get_current_version())
        with closing(sqlite3.connect(self.db_path)) as connection:
            tables = {
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }
            steam_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(steam_wishlist)")
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
        self.assertIn("steam_app_id", steam_columns)

    def test_migrations_are_idempotent(self):
        migrator = DatabaseMigrator(self.db_path)
        self.apply(migrator)

        self.apply(migrator)

        with closing(sqlite3.connect(self.db_path)) as connection:
            versions = connection.execute("SELECT version FROM migrations ORDER BY id").fetchall()
        self.assertEqual([(f"{version:03d}",) for version in range(1, 11)], versions)

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
        self.assertEqual("010", migrator.get_current_version())

    def test_steam_currency_migration_resets_legacy_prices_once(self):
        migrator = DatabaseMigrator(self.db_path)
        migrator.migrations = migrator.migrations[:-1]
        self.apply(migrator)
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute(
                """
                INSERT INTO steam_wishlist
                    (user_id, game_id, game_name, current_price, historical_low,
                     discount_percent)
                VALUES (1, 'game', 'Game', 10, 5, 50)
                """
            )
            connection.commit()

        upgraded = DatabaseMigrator(self.db_path)
        self.assertEqual(["010"], upgraded.apply_migrations())

        with closing(sqlite3.connect(self.db_path)) as connection:
            row = connection.execute(
                """
                SELECT steam_app_id, current_price, historical_low, discount_percent
                FROM steam_wishlist
                """
            ).fetchone()
        self.assertEqual((None, None, None, None), row)

    def test_existing_steam_app_column_is_accepted_without_data_loss(self):
        migrator = DatabaseMigrator(self.db_path)
        migrator.migrations = migrator.migrations[:-1]
        self.apply(migrator)
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute("ALTER TABLE steam_wishlist ADD COLUMN steam_app_id TEXT")
            connection.execute(
                """
                INSERT INTO steam_wishlist
                    (user_id, game_id, game_name, steam_app_id, current_price)
                VALUES (1, 'game', 'Game', '123', 999)
                """
            )
            connection.commit()

        upgraded = DatabaseMigrator(self.db_path)
        self.assertEqual(["010"], upgraded.apply_migrations())

        with closing(sqlite3.connect(self.db_path)) as connection:
            row = connection.execute(
                "SELECT steam_app_id, current_price FROM steam_wishlist"
            ).fetchone()
        self.assertEqual(("123", 999.0), row)

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
