import tempfile
import unittest
from pathlib import Path

from scripts.ci.contract import discover_modules, validate_repository

PINNED_ACTION = "actions/checkout@" + "a" * 40


class RepositoryContractTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "modules" / "legacy").mkdir(parents=True)
        (self.root / "modules" / "legacy" / "__init__.py").write_text("", encoding="utf-8")
        (self.root / ".ci").mkdir()
        (self.root / ".ci" / "legacy-modules-without-tests.txt").write_text(
            "legacy\n", encoding="utf-8"
        )
        (self.root / ".github" / "workflows").mkdir(parents=True)
        (self.root / ".github" / "workflows" / "ci.yml").write_text(
            f"steps:\n  - uses: {PINNED_ACTION}\n", encoding="utf-8"
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_clean_grandfathered_repository_passes(self):
        paths = [
            ".ci/legacy-modules-without-tests.txt",
            ".github/workflows/ci.yml",
            "modules/legacy/__init__.py",
        ]

        self.assertEqual([], validate_repository(self.root, paths))

    def test_new_module_requires_matching_tests(self):
        (self.root / "modules" / "new_tool").mkdir()
        (self.root / "modules" / "new_tool" / "__init__.py").write_text("", encoding="utf-8")

        errors = validate_repository(self.root, [])

        self.assertTrue(any("tests/new_tool/__init__.py" in error for error in errors))
        self.assertTrue(any("tests/new_tool/test_*.py" in error for error in errors))

    def test_allowlist_entry_must_be_removed_when_tests_exist(self):
        test_dir = self.root / "tests" / "legacy"
        test_dir.mkdir(parents=True)
        (test_dir / "__init__.py").write_text("", encoding="utf-8")
        (test_dir / "test_service.py").write_text("", encoding="utf-8")

        errors = validate_repository(self.root, [])

        self.assertTrue(any("remove it from" in error for error in errors))

    def test_forbidden_artifacts_tokens_and_conflicts_are_reported(self):
        (self.root / "unsafe.py").write_text(
            "<<<<<<< HEAD\nBOT_TOKEN = '123456789:" + "x" * 35 + "'\n",
            encoding="utf-8",
        )
        paths = ["secrets.py", "graphify-out/data.json", "unsafe.py"]

        errors = validate_repository(self.root, paths)

        self.assertIn("forbidden tracked artifact: secrets.py", errors)
        self.assertIn("forbidden tracked artifact: graphify-out/data.json", errors)
        self.assertIn("unresolved merge marker: unsafe.py", errors)
        self.assertIn("possible Telegram bot token: unsafe.py", errors)

    def test_actions_must_use_full_commit_sha(self):
        workflow = self.root / ".github" / "workflows" / "ci.yml"
        workflow.write_text("steps:\n  - uses: actions/checkout@v7\n", encoding="utf-8")

        errors = validate_repository(self.root, [".github/workflows/ci.yml"])

        self.assertTrue(any("full commit SHA" in error for error in errors))

    def test_long_plaintext_separator_is_not_a_merge_marker(self):
        (self.root / "history.txt").write_text("===========================\n", encoding="utf-8")

        errors = validate_repository(self.root, ["history.txt"])

        self.assertFalse(any("merge marker" in error for error in errors))

    def test_discovery_ignores_directories_without_init_file(self):
        (self.root / "modules" / "stale_cache" / "__pycache__").mkdir(parents=True)

        self.assertEqual(["legacy"], discover_modules(self.root))

    def test_database_access_and_schema_are_centralized(self):
        core_file = self.root / "core" / "unsafe.py"
        core_file.parent.mkdir()
        core_file.write_text("sqlite3.connect('users.db')\n", encoding="utf-8")
        module_file = self.root / "modules" / "legacy" / "schema.py"
        module_file.write_text("SQL = 'CREATE TABLE drift (id INT)'\n", encoding="utf-8")

        errors = validate_repository(
            self.root,
            ["core/unsafe.py", "modules/legacy/schema.py"],
        )

        self.assertIn("direct sqlite3.connect outside core/storage.py: core/unsafe.py", errors)
        self.assertIn("schema DDL outside core/migrations.py: modules/legacy/schema.py", errors)


if __name__ == "__main__":
    unittest.main()
