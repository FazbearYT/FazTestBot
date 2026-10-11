"""Repository and module contracts enforced by CI."""

from __future__ import annotations

import re
import subprocess
from collections.abc import Iterable
from pathlib import Path

from scripts.ci.verify_dependencies import DependencyVerificationError, read_exact_pins

MODULES_DIR = "modules"
TESTS_DIR = "tests"
LEGACY_ALLOWLIST = ".ci/legacy-modules-without-tests.txt"
DEPENDENCY_MANIFESTS = ("requirements.txt", "requirements-dev.txt")

FORBIDDEN_PREFIXES = (
    ".graphify/",
    "backups/",
    "database/",
    "downloads/",
    "exports/",
    "graphify-out/",
    "temp/",
)
FORBIDDEN_EXACT_PATHS = {".env", "secrets.py"}
FORBIDDEN_SUFFIXES = (".db", ".key", ".pem", ".sqlite", ".sqlite3")
TEXT_SUFFIXES = {
    ".ini",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}

CONFLICT_MARKER = re.compile(
    r"^(?:<{7}(?: .*)?|={7}|>{7}(?: .*)?)$",
    re.MULTILINE,
)
TELEGRAM_TOKEN = re.compile(r"(?<![A-Za-z0-9_-])\d{8,12}:[A-Za-z0-9_-]{30,}(?![A-Za-z0-9_-])")
ACTION_USE = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)", re.MULTILINE)
FULL_COMMIT_SHA = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")
DIRECT_SQLITE_CONNECT = re.compile(r"\bsqlite3\s*\.\s*connect\s*\(")
SCHEMA_DDL = re.compile(r"\bCREATE\s+TABLE\b", re.IGNORECASE)
BARE_EXCEPT = re.compile(r"^\s*except\s*:\s*$", re.MULTILINE)
DIRECT_PRINT = re.compile(r"\bprint\s*\(")
MOVING_UBUNTU_RUNNER = re.compile(r"^\s*runs-on:\s*ubuntu-latest\s*$", re.MULTILINE)


class ContractError(RuntimeError):
    """One or more repository invariants were violated."""


def discover_modules(root: Path) -> list[str]:
    """Return explicit Python packages below modules/, sorted by name."""
    modules_dir = root / MODULES_DIR
    if not modules_dir.is_dir():
        raise ContractError("modules/ directory is missing")
    return sorted(
        path.name
        for path in modules_dir.iterdir()
        if path.is_dir()
        and not path.name.startswith((".", "__"))
        and (path / "__init__.py").is_file()
    )


def read_legacy_allowlist(root: Path) -> set[str]:
    path = root / LEGACY_ALLOWLIST
    if not path.is_file():
        raise ContractError(f"{LEGACY_ALLOWLIST} is missing")
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def tracked_files(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return [item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def validate_repository(root: Path, paths: Iterable[str] | None = None) -> list[str]:
    """Return every contract violation instead of failing at the first one."""
    root = root.resolve()
    paths = sorted(paths if paths is not None else tracked_files(root))
    errors: list[str] = []

    modules = discover_modules(root)
    allowlist = read_legacy_allowlist(root)
    unknown_allowlisted = sorted(allowlist - set(modules))
    if unknown_allowlisted:
        errors.append(
            "legacy allowlist contains unknown modules: " + ", ".join(unknown_allowlisted)
        )

    for module_name in modules:
        test_dir = root / TESTS_DIR / module_name
        test_files = sorted(test_dir.glob("test_*.py")) if test_dir.is_dir() else []
        if module_name in allowlist:
            if test_files:
                errors.append(f"{module_name}: tests exist; remove it from {LEGACY_ALLOWLIST}")
            continue
        if not (test_dir / "__init__.py").is_file():
            errors.append(f"{module_name}: {TESTS_DIR}/{module_name}/__init__.py is required")
        if not test_files:
            errors.append(f"{module_name}: add at least one {TESTS_DIR}/{module_name}/test_*.py")

    normalized_paths = [path.replace("\\", "/") for path in paths]
    for manifest_name in DEPENDENCY_MANIFESTS:
        manifest = root / manifest_name
        if not manifest.is_file():
            errors.append(f"dependency manifest is missing: {manifest_name}")
            continue
        try:
            read_exact_pins(manifest)
        except (OSError, DependencyVerificationError) as error:
            errors.append(str(error))

    for relative_path in normalized_paths:
        lowered = relative_path.lower()
        if (
            lowered in FORBIDDEN_EXACT_PATHS
            or lowered.startswith(FORBIDDEN_PREFIXES)
            or lowered.endswith(FORBIDDEN_SUFFIXES)
        ):
            errors.append(f"forbidden tracked artifact: {relative_path}")
            continue

        absolute_path = root / relative_path
        if absolute_path.suffix.lower() not in TEXT_SUFFIXES or not absolute_path.is_file():
            continue
        try:
            content = absolute_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"expected UTF-8 text file: {relative_path}")
            continue
        if CONFLICT_MARKER.search(content):
            errors.append(f"unresolved merge marker: {relative_path}")
        if TELEGRAM_TOKEN.search(content):
            errors.append(f"possible Telegram bot token: {relative_path}")
        if lowered.endswith(".py") and lowered.startswith(("core/", "modules/")):
            if relative_path != "core/storage.py" and DIRECT_SQLITE_CONNECT.search(content):
                errors.append(f"direct sqlite3.connect outside core/storage.py: {relative_path}")
            if relative_path != "core/migrations.py" and SCHEMA_DDL.search(content):
                errors.append(f"schema DDL outside core/migrations.py: {relative_path}")
        if lowered.endswith(".py") and lowered.startswith("core/"):
            if BARE_EXCEPT.search(content):
                errors.append(f"bare except in core code: {relative_path}")
            if DIRECT_PRINT.search(content):
                errors.append(f"direct print in core code: {relative_path}")

    for workflow in sorted((root / ".github" / "workflows").glob("*.y*ml")):
        content = workflow.read_text(encoding="utf-8")
        if "pull_request_target:" in content:
            errors.append(f"unsafe pull_request_target trigger: {workflow.relative_to(root)}")
        if MOVING_UBUNTU_RUNNER.search(content):
            errors.append(
                f"moving ubuntu-latest runner: {workflow.relative_to(root)}; pin an OS version"
            )
        for action in ACTION_USE.findall(content):
            if action.startswith("./"):
                continue
            if not FULL_COMMIT_SHA.fullmatch(action):
                errors.append(
                    f"GitHub Action must be pinned to a full commit SHA: {action} "
                    f"in {workflow.relative_to(root)}"
                )

    return errors


def assert_repository_contract(root: Path) -> None:
    errors = validate_repository(root)
    if errors:
        formatted = "\n".join(f"- {error}" for error in errors)
        raise ContractError(f"Repository contract failed:\n{formatted}")
