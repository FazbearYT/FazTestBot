import tempfile
import unittest
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from unittest.mock import patch

from scripts.ci.verify_dependencies import (
    DependencyVerificationError,
    read_exact_pins,
    verify_installed,
)


class DependencyVerificationTests(unittest.TestCase):
    def test_exact_pins_support_extras_and_comments(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "requirements.txt"
            path.write_text(
                "package[feature]==1.2.3  # reason\nother_name==4.5\n",
                encoding="utf-8",
            )

            self.assertEqual(
                {"package": "1.2.3", "other-name": "4.5"},
                read_exact_pins(path),
            )

    def test_non_exact_empty_and_duplicate_manifests_are_rejected(self):
        invalid_contents = (
            "package>=1.0\n",
            "# comments only\n",
            "package==1.0\nPACKAGE==1.0\n",
        )
        for content in invalid_contents:
            with self.subTest(content=content), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "requirements.txt"
                path.write_text(content, encoding="utf-8")

                with self.assertRaises(DependencyVerificationError):
                    read_exact_pins(path)

    def test_installed_versions_report_missing_mismatch_and_conflict(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime.txt"
            development = root / "development.txt"
            runtime.write_text("present==1.0\nmissing==2.0\n", encoding="utf-8")
            development.write_text("present==3.0\n", encoding="utf-8")

            def installed(name: str) -> str:
                if name == "missing":
                    raise PackageNotFoundError(name)
                return "2.0"

            with patch("scripts.ci.verify_dependencies.version", side_effect=installed):
                errors = verify_installed([runtime, development])

        self.assertTrue(any("conflicting pins" in error for error in errors))
        self.assertTrue(any("missing is not installed" in error for error in errors))
        self.assertTrue(any("present==2.0" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
