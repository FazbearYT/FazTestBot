"""Validate release metadata and build a reproducible source archive."""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from core.version import RELEASE_DATE, VERSION

SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


class ReleaseError(RuntimeError):
    """Release metadata or source state is inconsistent."""


@dataclass(frozen=True)
class ReleasePaths:
    root: Path
    changelog: Path
    history: Path

    @classmethod
    def from_root(cls, root: Path) -> ReleasePaths:
        resolved = root.resolve()
        return cls(
            root=resolved,
            changelog=resolved / "CHANGELOG.md",
            history=resolved / "history.txt",
        )


def expected_tag(version: str = VERSION) -> str:
    if not SEMVER.fullmatch(version):
        raise ReleaseError(f"VERSION must be strict SemVer X.Y.Z, got {version!r}")
    return f"v{version}"


def changelog_section(text: str, version: str = VERSION, date: str = RELEASE_DATE) -> str:
    heading = f"## [{version}] - {date}"
    start = text.find(heading)
    if start < 0:
        raise ReleaseError(f"CHANGELOG.md is missing {heading!r}")

    next_heading = text.find("\n## [", start + len(heading))
    section = text[start : next_heading if next_heading >= 0 else len(text)].strip()
    if len(section.splitlines()) < 2:
        raise ReleaseError(f"CHANGELOG.md section for {version} is empty")
    return section + "\n"


def verify_release(root: Path, tag: str | None = None) -> str:
    paths = ReleasePaths.from_root(root)
    release_tag = expected_tag()
    if tag is not None and tag != release_tag:
        raise ReleaseError(f"tag {tag!r} does not match VERSION {VERSION!r}")

    try:
        changelog = paths.changelog.read_text(encoding="utf-8")
        history = paths.history.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ReleaseError(f"required release file is missing: {exc.filename}") from exc

    notes = changelog_section(changelog)
    if not re.search(rf"(?m)^v{re.escape(VERSION)}(?:\s|$)", history):
        raise ReleaseError(f"history.txt is missing v{VERSION}")
    return notes


def _run_git(root: Path, *args: str) -> None:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown git error"
        raise ReleaseError(detail)


def build_release(root: Path, output_dir: Path, ref: str = "HEAD") -> tuple[Path, Path, Path]:
    paths = ReleasePaths.from_root(root)
    notes = verify_release(paths.root)
    tag = expected_tag()
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / f"FazTestBot-{tag}.zip"
    checksum = output_dir / f"FazTestBot-{tag}.zip.sha256"
    notes_file = output_dir / f"FazTestBot-{tag}-notes.md"

    _run_git(paths.root, "rev-parse", "--verify", f"{ref}^{{commit}}")
    _run_git(
        paths.root,
        "archive",
        "--format=zip",
        f"--prefix=FazTestBot-{tag}/",
        f"--output={archive}",
        ref,
    )
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    checksum.write_text(f"{digest}  {archive.name}\n", encoding="ascii", newline="\n")
    notes_file.write_text(notes, encoding="utf-8", newline="\n")
    return archive, checksum, notes_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    verify_parser = subparsers.add_parser("verify", help="validate release metadata")
    verify_parser.add_argument("--tag", help="tag to compare with the canonical version")
    build_parser = subparsers.add_parser("build", help="build release files from a Git ref")
    build_parser.add_argument("--output-dir", type=Path, default=Path("dist"))
    build_parser.add_argument("--ref", default="HEAD")

    args = parser.parse_args(argv)
    try:
        if args.command == "verify":
            verify_release(Path.cwd(), args.tag)
            print(f"Release metadata: {expected_tag()} OK")
        else:
            outputs = build_release(Path.cwd(), args.output_dir, args.ref)
            for output in outputs:
                print(output)
    except ReleaseError as exc:
        print(f"Release validation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
