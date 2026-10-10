import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from io import StringIO
from pathlib import Path

from scripts.database import _check


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
