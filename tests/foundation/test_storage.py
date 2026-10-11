import sqlite3
import tempfile
import unittest
from pathlib import Path

from core.storage import DatabaseIntegrityError, SQLiteDatabase


class SQLiteDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.path = self.root / "nested" / "users.db"
        self.database = SQLiteDatabase(self.path, busy_timeout_ms=1_234)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_connection_applies_required_pragmas(self):
        with self.database.connection(write=True) as connection:
            foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]
            busy_timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]
            journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
            connection.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
            connection.execute("CREATE TABLE child (parent_id INTEGER REFERENCES parent(id))")

        self.assertEqual(1, foreign_keys)
        self.assertEqual(1_234, busy_timeout)
        self.assertEqual("wal", journal_mode)

        with self.assertRaises(sqlite3.IntegrityError):
            with self.database.connection(write=True) as connection:
                connection.execute("INSERT INTO child VALUES (99)")

    def test_write_transaction_rolls_back_on_failure(self):
        with self.database.connection(write=True) as connection:
            connection.execute("CREATE TABLE marker (value TEXT)")

        with self.assertRaisesRegex(RuntimeError, "fail"):
            with self.database.connection(write=True) as connection:
                connection.execute("INSERT INTO marker VALUES ('partial')")
                raise RuntimeError("fail")

        with self.database.connection() as connection:
            count = connection.execute("SELECT COUNT(*) FROM marker").fetchone()[0]
        self.assertEqual(0, count)

    def test_backup_and_restore_include_committed_wal_data(self):
        with self.database.connection(write=True) as connection:
            connection.execute("CREATE TABLE marker (value TEXT)")
            connection.execute("INSERT INTO marker VALUES ('snapshot')")

        backup_path = self.root / "backups" / "snapshot.db"
        self.database.backup_to(backup_path)

        with self.database.connection(write=True) as connection:
            connection.execute("UPDATE marker SET value = 'changed'")
        self.database.restore_from(backup_path)

        with self.database.connection() as connection:
            value = connection.execute("SELECT value FROM marker").fetchone()[0]
        self.assertEqual("snapshot", value)

    def test_invalid_database_fails_integrity_validation(self):
        broken = self.root / "broken.db"
        broken.write_bytes(b"not a sqlite database")

        with self.assertRaises((DatabaseIntegrityError, sqlite3.DatabaseError)):
            SQLiteDatabase(broken).validate()

    def test_read_only_connection_rejects_writes(self):
        with self.database.connection(write=True) as connection:
            connection.execute("CREATE TABLE marker (value TEXT)")

        with self.database.connection(read_only=True) as connection:
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute("INSERT INTO marker VALUES ('forbidden')")

        with self.assertRaisesRegex(ValueError, "both writable and read-only"):
            with self.database.connection(write=True, read_only=True):
                pass
