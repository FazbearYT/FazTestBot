import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from io import StringIO
from pathlib import Path

from core.backup import BackupManager
from core.migrations import DatabaseMigrator
from scripts.database import _check, _restore


class DatabaseCliTests(unittest.TestCase):
    def test_check_is_read_only_for_legacy_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.db"
            with closing(sqlite3.connect(path)) as connection:
                connection.execute("CREATE TABLE marker (value TEXT)")
                connection.commit()

            with redirect_stdout(StringIO()) as output:
                result = _check(path)

            with closing(sqlite3.connect(path)) as connection:
                migration_table = connection.execute(
                    "SELECT name FROM sqlite_master WHERE name = 'migrations'"
                ).fetchone()

        self.assertEqual(0, result)
        self.assertIn("Pending migrations: 001", output.getvalue())
        self.assertIsNone(migration_table)

    def test_check_rejects_corrupt_database(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.db"
            path.write_bytes(b"not sqlite")

            with redirect_stdout(StringIO()):
                result = _check(path)

        self.assertEqual(1, result)

    def test_restore_replaces_database_and_runs_integrity_check(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "users.db"
            backups = root / "backups"
            DatabaseMigrator(path).apply_migrations()
            manager = BackupManager(backup_dir=backups, db_path=path)
            with manager.database.connection(write=True) as connection:
                connection.execute("INSERT INTO users (user_id) VALUES (1)")
            created, _ = manager.create_backup(manual=True)
            self.assertTrue(created)
            filename = manager.get_backup_list()[0]["filename"]
            with manager.database.connection(write=True) as connection:
                connection.execute("INSERT INTO users (user_id) VALUES (2)")

            with redirect_stdout(StringIO()) as output:
                result = _restore(path, backups, filename)
            with manager.database.connection() as connection:
                user_ids = [row[0] for row in connection.execute("SELECT user_id FROM users")]

        self.assertEqual(0, result)
        self.assertEqual([1], user_ids)
        self.assertIn("Database integrity: ok", output.getvalue())
