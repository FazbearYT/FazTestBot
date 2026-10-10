"""Reproduce the blocking CI checks locally from one command."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from scripts.ci.contract import discover_modules


def run(*args: str) -> None:
    print("+", " ".join(args), flush=True)
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    subprocess.run(args, check=True, env=env)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--audit",
        action="store_true",
        help="also query the vulnerability service through pip-audit",
    )
    args = parser.parse_args()
    python = sys.executable

    run(python, "-m", "scripts.ci.check_repository")
    run(
        python,
        "-m",
        "ruff",
        "check",
        "core/backup.py",
        "core/admin_panel.py",
        "core/bootstrap.py",
        "core/database.py",
        "core/exceptions.py",
        "core/health.py",
        "core/migrations.py",
        "core/module_base.py",
        "core/module_manager.py",
        "core/observability.py",
        "core/settings.py",
        "core/storage.py",
        "bot.py",
        "config.py",
        "scripts/doctor.py",
        "scripts/database.py",
        "scripts/ci",
        "tests",
    )
    run(
        python,
        "-m",
        "ruff",
        "format",
        "--check",
        "core/backup.py",
        "core/admin_panel.py",
        "core/bootstrap.py",
        "core/database.py",
        "core/exceptions.py",
        "core/health.py",
        "core/migrations.py",
        "core/module_base.py",
        "core/module_manager.py",
        "core/observability.py",
        "core/settings.py",
        "core/storage.py",
        "bot.py",
        "config.py",
        "scripts/doctor.py",
        "scripts/database.py",
        "scripts/ci",
        "tests",
    )
    run(python, "-m", "compileall", "-q", "core", "modules", "scripts", "tests")
    run(python, "-m", "scripts.ci.application_smoke")
    run(python, "-m", "pip", "check")
    run(
        python,
        "-m",
        "coverage",
        "run",
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests",
        "-p",
        "test_*.py",
        "-v",
    )
    run(python, "-m", "coverage", "report")
    run(python, "-m", "coverage", "xml")

    for module_name in discover_modules(Path.cwd()):
        run(python, "-m", "scripts.ci.run_module_checks", module_name)

    if args.audit:
        run(
            python,
            "-m",
            "pip_audit",
            "--strict",
            "--progress-spinner",
            "off",
            "-r",
            "requirements.txt",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
