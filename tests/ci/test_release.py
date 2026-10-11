import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.version import RELEASE_DATE, VERSION
from scripts.release import (
    ReleaseError,
    build_release,
    changelog_section,
    expected_tag,
    verify_release,
)


class ReleaseMetadataTests(unittest.TestCase):
    def test_expected_tag_requires_strict_semver(self):
        self.assertEqual(expected_tag("5.0.0"), "v5.0.0")
        for invalid in ("v5.0.0", "5.0", "05.0.0", "5.0.0-rc1"):
            with self.subTest(invalid=invalid), self.assertRaises(ReleaseError):
                expected_tag(invalid)

    def test_changelog_section_stops_before_next_release(self):
        text = "# Changelog\n\n## [5.0.0] - 2026-10-11\n\nNotes.\n\n## [4.5.0] - 2025-01-01\nOld.\n"
        self.assertEqual(
            changelog_section(text, version="5.0.0", date="2026-10-11"),
            "## [5.0.0] - 2026-10-11\n\nNotes.\n",
        )

    def test_verify_rejects_tag_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ReleaseError, "does not match VERSION"):
                verify_release(Path(directory), "v4.5.0")

    def test_verify_requires_matching_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "CHANGELOG.md").write_text(
                f"## [{VERSION}] - {RELEASE_DATE}\n\nNotes.\n", encoding="utf-8"
            )
            (root / "history.txt").write_text("v4.5.0\n", encoding="utf-8")
            with self.assertRaisesRegex(ReleaseError, "history.txt"):
                verify_release(root)


class ReleaseBuildTests(unittest.TestCase):
    def test_build_writes_archive_checksum_and_notes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "CHANGELOG.md").write_text(
                f"## [{VERSION}] - {RELEASE_DATE}\n\nRelease notes.\n", encoding="utf-8"
            )
            (root / "history.txt").write_text(f"v{VERSION} — release\n", encoding="utf-8")
            (root / "tracked.txt").write_text("source\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=CI",
                    "-c",
                    "user.email=ci@example.invalid",
                    "commit",
                    "-qm",
                    "fixture",
                ],
                cwd=root,
                check=True,
            )

            archive, checksum, notes = build_release(root, root / "dist")

            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            self.assertEqual(checksum.read_text(encoding="ascii"), f"{digest}  {archive.name}\n")
            self.assertEqual(
                notes.read_text(encoding="utf-8"),
                f"## [{VERSION}] - {RELEASE_DATE}\n\nRelease notes.\n",
            )

    def test_git_failure_is_reported_as_release_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "CHANGELOG.md").write_text(
                f"## [{VERSION}] - {RELEASE_DATE}\n\nNotes.\n", encoding="utf-8"
            )
            (root / "history.txt").write_text(f"v{VERSION}\n", encoding="utf-8")
            with self.assertRaises(ReleaseError):
                build_release(root, root / "dist")

    def test_build_surfaces_metadata_errors_before_running_git(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("scripts.release._run_git") as run_git:
                with self.assertRaises(ReleaseError):
                    build_release(root, root / "dist")
                run_git.assert_not_called()


if __name__ == "__main__":
    unittest.main()
