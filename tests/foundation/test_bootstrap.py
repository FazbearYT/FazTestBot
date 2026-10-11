import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock

from core.bootstrap import migrate_database_safely
from core.migrations import DatabaseMigrator, MigrationError


class DatabaseBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "users.db"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_new_database_migrates_without_pointless_backup(self):
        backup_manager = Mock()

        applied = migrate_database_safely(self.db_path, backup_manager=backup_manager)

        self.assertEqual([f"{version:03d}" for version in range(1, 11)], applied)
        backup_manager.create_backup.assert_not_called()

    def test_existing_database_is_backed_up_before_migration(self):
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute("CREATE TABLE legacy_marker (value TEXT)")
            connection.execute("INSERT INTO legacy_marker VALUES ('preserved')")
            connection.commit()
        backup_manager = Mock()

        def assert_schema_is_still_legacy(*, manual):
            self.assertFalse(manual)
            with closing(sqlite3.connect(self.db_path)) as connection:
                users_table = connection.execute(
                    "SELECT name FROM sqlite_master WHERE name = 'users'"
                ).fetchone()
            self.assertIsNone(users_table)
            return True, "created"

        backup_manager.create_backup.side_effect = assert_schema_is_still_legacy

        applied = migrate_database_safely(self.db_path, backup_manager=backup_manager)

        backup_manager.create_backup.assert_called_once_with(manual=False)
        self.assertEqual("010", applied[-1])
        with closing(sqlite3.connect(self.db_path)) as connection:
            value = connection.execute("SELECT value FROM legacy_marker").fetchone()[0]
        self.assertEqual("preserved", value)

    def test_failed_pre_migration_backup_aborts_without_schema_changes(self):
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute("CREATE TABLE legacy_marker (value TEXT)")
            connection.commit()
        backup_manager = Mock()
        backup_manager.create_backup.return_value = (False, "disk full")

        with self.assertRaisesRegex(MigrationError, "pre-migration backup failed"):
            migrate_database_safely(self.db_path, backup_manager=backup_manager)

        with closing(sqlite3.connect(self.db_path)) as connection:
            users_table = connection.execute(
                "SELECT name FROM sqlite_master WHERE name = 'users'"
            ).fetchone()
        self.assertIsNone(users_table)

    def test_current_database_does_not_create_startup_backup(self):
        DatabaseMigrator(self.db_path).apply_migrations()
        backup_manager = Mock()

        applied = migrate_database_safely(self.db_path, backup_manager=backup_manager)

        self.assertEqual([], applied)
        backup_manager.create_backup.assert_not_called()
