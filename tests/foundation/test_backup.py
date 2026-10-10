import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from io import StringIO
from pathlib import Path

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
        self.assertIn("не найден", message)


if __name__ == "__main__":
    unittest.main()
