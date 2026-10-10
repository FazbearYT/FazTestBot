import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from core.backup import BackupManager


class BackupManagerCharacterizationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.db_path = self.root / "users.db"
        self.backup_dir = self.root / "backups"
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute("CREATE TABLE marker (value TEXT NOT NULL)")
            connection.execute("INSERT INTO marker VALUES ('original')")
            connection.commit()
        with redirect_stdout(StringIO()):
            self.manager = BackupManager(self.backup_dir, self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_created_backup_is_a_readable_database_copy(self):
        with redirect_stdout(StringIO()):
            success, _ = self.manager.create_backup(manual=True)

        self.assertTrue(success)
        backups = self.manager.get_backup_list()
        self.assertEqual(1, len(backups))
        with closing(sqlite3.connect(backups[0]["path"])) as connection:
            value = connection.execute("SELECT value FROM marker").fetchone()[0]
        self.assertEqual("original", value)

    def test_backup_includes_committed_wal_pages_from_open_connection(self):
        with closing(sqlite3.connect(self.db_path)) as writer:
            writer.execute("PRAGMA journal_mode = WAL")
            writer.execute("UPDATE marker SET value = 'wal-value'")
            writer.commit()

            with redirect_stdout(StringIO()):
                success, _ = self.manager.create_backup(manual=True)

        self.assertTrue(success)
        backup_path = self.manager.get_backup_list()[0]["path"]
        with closing(sqlite3.connect(backup_path)) as connection:
            value = connection.execute("SELECT value FROM marker").fetchone()[0]
        self.assertEqual("wal-value", value)

    def test_restore_replaces_database_after_safety_backup(self):
        with redirect_stdout(StringIO()):
            success, _ = self.manager.create_backup(manual=True)
        self.assertTrue(success)
        source_name = self.manager.get_backup_list()[0]["filename"]

        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute("UPDATE marker SET value = 'changed'")
            connection.commit()

        with redirect_stdout(StringIO()):
            restored, _ = self.manager.restore_backup(source_name)

        self.assertTrue(restored)
        with closing(sqlite3.connect(self.db_path)) as connection:
            value = connection.execute("SELECT value FROM marker").fetchone()[0]
        self.assertEqual("original", value)

    def test_rejects_non_backup_filename(self):
        success, message = self.manager.delete_backup("notes.txt")

        self.assertFalse(success)
        self.assertIn("Неверный формат", message)

    def test_rejects_path_traversal(self):
        success, message = self.manager.restore_backup("users_/../../outside.db")

        self.assertFalse(success)
        self.assertIn("Неверный формат", message)

    def test_invalid_snapshot_does_not_modify_live_database(self):
        invalid_name = "users_manual_20261010_120000_000000.db"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        (self.backup_dir / invalid_name).write_bytes(b"not sqlite")

        with redirect_stdout(StringIO()):
            restored, _ = self.manager.restore_backup(invalid_name)

        self.assertFalse(restored)
        with closing(sqlite3.connect(self.db_path)) as connection:
            value = connection.execute("SELECT value FROM marker").fetchone()[0]
        self.assertEqual("original", value)

    def test_restore_aborts_when_safety_backup_fails(self):
        with redirect_stdout(StringIO()):
            success, _ = self.manager.create_backup(manual=True)
        self.assertTrue(success)
        source_name = self.manager.get_backup_list()[0]["filename"]

        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute("UPDATE marker SET value = 'keep-me'")
            connection.commit()

        with (
            patch.object(self.manager, "create_backup", return_value=(False, "disk full")),
            redirect_stdout(StringIO()),
        ):
            restored, message = self.manager.restore_backup(source_name)

        self.assertFalse(restored)
        self.assertIn("Защитный бэкап не создан", message)
        with closing(sqlite3.connect(self.db_path)) as connection:
            value = connection.execute("SELECT value FROM marker").fetchone()[0]
        self.assertEqual("keep-me", value)

    def test_restore_does_not_rotate_selected_snapshot_before_use(self):
        self.manager.retention_count = 1
        with redirect_stdout(StringIO()):
            success, _ = self.manager.create_backup(manual=True)
        self.assertTrue(success)
        source_name = self.manager.get_backup_list()[0]["filename"]

        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute("UPDATE marker SET value = 'changed'")
            connection.commit()

        with redirect_stdout(StringIO()):
            restored, _ = self.manager.restore_backup(source_name)

        self.assertTrue(restored)
        with closing(sqlite3.connect(self.db_path)) as connection:
            value = connection.execute("SELECT value FROM marker").fetchone()[0]
        self.assertEqual("original", value)
        self.assertEqual(1, len(self.manager.get_backup_list()))


if __name__ == "__main__":
    unittest.main()
