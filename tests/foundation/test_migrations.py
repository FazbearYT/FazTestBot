import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from io import StringIO
from pathlib import Path

from core.database import DatabaseManager
from core.migrations import DatabaseMigrator


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

        self.assertEqual("006", migrator.get_current_version())
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
        self.assertEqual([(f"{version:03d}",) for version in range(1, 7)], versions)

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


if __name__ == "__main__":
    unittest.main()
