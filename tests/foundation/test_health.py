import json
import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from io import StringIO
from pathlib import Path

from core.health import build_health_report
from core.migrations import DatabaseMigrator
from core.settings import Settings
from scripts.doctor import main


class HealthReportTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.db_path = self.root / "users.db"
        self.secrets_path = self.root / "secrets.py"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_current_database_is_ready(self):
        DatabaseMigrator(self.db_path).apply_migrations()

        report = build_health_report(
            Settings(bot_token="configured"),
            db_path=self.db_path,
            root_path=self.root,
            secrets_path=self.secrets_path,
        )

        self.assertTrue(report.ready)
        statuses = {check.name: check.status for check in report.checks}
        self.assertEqual("ok", statuses["configuration"])
        self.assertEqual("ok", statuses["database"])
        self.assertEqual("ok", statuses["legacy_secrets"])

    def test_missing_database_is_warning_not_startup_failure(self):
        report = build_health_report(
            Settings(bot_token="configured"),
            db_path=self.db_path,
            root_path=self.root,
            secrets_path=self.secrets_path,
        )

        database = next(check for check in report.checks if check.name == "database")
        self.assertTrue(report.ready)
        self.assertEqual("warning", database.status)
        self.assertFalse(self.db_path.exists())

    def test_corrupt_database_makes_report_not_ready_without_exposing_details(self):
        self.db_path.write_bytes(b"not sqlite")

        report = build_health_report(
            Settings(bot_token="configured"),
            db_path=self.db_path,
            root_path=self.root,
            secrets_path=self.secrets_path,
        )

        database = next(check for check in report.checks if check.name == "database")
        self.assertFalse(report.ready)
        self.assertEqual("error", database.status)
        self.assertEqual({"error_type": "DatabaseError"}, database.details)

    def test_pending_migrations_are_reported_without_mutating_database(self):
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute("CREATE TABLE marker (value TEXT)")
            connection.commit()

        report = build_health_report(
            Settings(bot_token="configured"),
            db_path=self.db_path,
            root_path=self.root,
            secrets_path=self.secrets_path,
        )

        database = next(check for check in report.checks if check.name == "database")
        self.assertEqual("warning", database.status)
        self.assertEqual("001", database.details["pending_migrations"][0])
        with closing(sqlite3.connect(self.db_path)) as connection:
            migration_table = connection.execute(
                "SELECT name FROM sqlite_master WHERE name = 'migrations'"
            ).fetchone()
        self.assertIsNone(migration_table)

    def test_json_cli_contains_no_secret_values(self):
        env_file = self.root / ".env"
        secret = "diagnostic-secret-value"
        env_file.write_text(f"BOT_TOKEN={secret}\n", encoding="utf-8")

        with redirect_stdout(StringIO()) as output:
            result = main(
                [
                    "--env-file",
                    str(env_file),
                    "--db-path",
                    str(self.db_path),
                    "--root-path",
                    str(self.root),
                    "--secrets-path",
                    str(self.secrets_path),
                    "--json",
                ]
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(0, result)
        self.assertTrue(payload["ready"])
        self.assertNotIn(secret, output.getvalue())


if __name__ == "__main__":
    unittest.main()
