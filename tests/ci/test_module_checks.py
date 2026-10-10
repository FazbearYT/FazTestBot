import tempfile
import unittest
from pathlib import Path
from unittest.mock import call, patch

from scripts.ci.run_module_checks import run_quality


class ModuleQualityTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / ".ci").mkdir()

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("scripts.ci.run_module_checks.subprocess.run")
    def test_new_module_runs_scoped_lint_and_format(self, run):
        (self.root / ".ci" / "legacy-modules-without-tests.txt").write_text("", encoding="utf-8")

        run_quality(self.root, "new_tool")

        self.assertEqual(2, run.call_count)
        self.assertEqual(
            [
                call(
                    [
                        unittest.mock.ANY,
                        "-m",
                        "ruff",
                        "check",
                        "modules/new_tool",
                        "tests/new_tool",
                    ],
                    cwd=self.root,
                    check=True,
                ),
                call(
                    [
                        unittest.mock.ANY,
                        "-m",
                        "ruff",
                        "format",
                        "--check",
                        "modules/new_tool",
                        "tests/new_tool",
                    ],
                    cwd=self.root,
                    check=True,
                ),
            ],
            run.call_args_list,
        )

    @patch("scripts.ci.run_module_checks.subprocess.run")
    def test_legacy_module_defers_scoped_quality_gate(self, run):
        (self.root / ".ci" / "legacy-modules-without-tests.txt").write_text(
            "legacy\n", encoding="utf-8"
        )

        run_quality(self.root, "legacy")

        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
