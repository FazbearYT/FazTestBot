import json
import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path

from core.database import DatabaseManager


class DatabaseManagerCharacterizationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "users.db"
        self.database = DatabaseManager(self.db_path, retention_days=0)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_initializes_legacy_core_schema_and_indexes(self):
        with closing(sqlite3.connect(self.db_path)) as connection:
            tables = {
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }
            indexes = {
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'index'")
            }

        self.assertTrue({"users", "cipher_operations", "easter_eggs"} <= tables)
        self.assertTrue({"idx_user_id", "idx_timestamp", "idx_cipher_type"} <= indexes)

    def test_tracks_user_module_and_cipher_statistics(self):
        self.database.create_or_update_user(42, "fazbear", "Faz", "Bear")
        self.database.increment_module_stat(42, "cipher")
        self.database.increment_module_stat(42, "steam_deals")
        self.database.log_cipher_operation(
            42,
            "caesar",
            "hello",
            "khoor",
            language="en",
            step=3,
            session_id="session-1",
        )

        user = self.database.get_user_stats(42)
        cipher = self.database.get_user_cipher_stats(42)

        self.assertEqual("Faz Bear", user["full_name"])
        self.assertEqual({"cipher": 1, "steam_deals": 1}, user["module_stats"])
        self.assertEqual(1, cipher["total_operations"])
        self.assertEqual({"caesar": 1}, cipher["cipher_distribution"])
        self.assertEqual("hello", cipher["last_operations"][0]["original_text"])

    def test_invalid_legacy_module_stats_are_recovered_on_increment(self):
        self.database.create_or_update_user(7)
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute(
                "UPDATE users SET module_stats = ? WHERE user_id = ?", ("not-json", 7)
            )
            connection.commit()

        self.database.increment_module_stat(7, "ip_lookup")

        with closing(sqlite3.connect(self.db_path)) as connection:
            raw_stats = connection.execute(
                "SELECT module_stats FROM users WHERE user_id = ?", (7,)
            ).fetchone()[0]
        self.assertEqual({"cipher": 0, "ip_lookup": 1}, json.loads(raw_stats))

    def test_retention_cleanup_removes_only_expired_cipher_operations(self):
        self.database.create_or_update_user(11)
        expired = datetime.now() - timedelta(days=31)
        current = datetime.now() - timedelta(days=1)
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.executemany(
                """
                INSERT INTO cipher_operations
                    (operation_id, user_id, cipher_type, original_text, encrypted_text, timestamp)
                VALUES (?, ?, 'caesar', 'source', 'result', ?)
                """,
                [
                    ("expired", 11, expired.strftime("%Y-%m-%d %H:%M:%S")),
                    ("current", 11, current.strftime("%Y-%m-%d %H:%M:%S")),
                ],
            )
            connection.commit()

        with redirect_stdout(StringIO()):
            DatabaseManager(self.db_path, retention_days=30)

        with closing(sqlite3.connect(self.db_path)) as connection:
            remaining = {
                row[0] for row in connection.execute("SELECT operation_id FROM cipher_operations")
            }
        self.assertEqual({"current"}, remaining)

    def test_easter_egg_state_can_be_created_updated_and_reset(self):
        self.database.create_or_update_user(99)

        self.database.update_user_easter_egg_state(99, {"current_step": 2})
        self.assertEqual(2, self.database.get_user_easter_egg_state(99)["current_step"])

        self.database.update_user_easter_egg_state(
            99, {"current_step": 3, "last_completed": "2026-10-10 10:00:00"}
        )
        updated = self.database.get_user_easter_egg_state(99)
        self.assertEqual(3, updated["current_step"])
        self.assertEqual("2026-10-10 10:00:00", updated["last_completed"])

        self.database.reset_user_easter_egg_state(99)
        reset = self.database.get_user_easter_egg_state(99)
        self.assertEqual(0, reset["current_step"])
        self.assertIsNone(reset["last_completed"])


if __name__ == "__main__":
    unittest.main()
