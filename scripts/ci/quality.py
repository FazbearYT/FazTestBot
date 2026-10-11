"""Single source of truth for repository-wide Ruff targets."""

from __future__ import annotations

import argparse
import subprocess
import sys

LINT_TARGETS = (
    "core/admin.py",
    "core/admin_panel.py",
    "core/admin_security.py",
    "core/backup.py",
    "core/bootstrap.py",
    "core/database.py",
    "core/exceptions.py",
    "core/handlers.py",
    "core/health.py",
    "core/http_client.py",
    "core/keyboards.py",
    "core/migrations.py",
    "core/module_base.py",
    "core/module_manager.py",
    "core/observability.py",
    "core/process_lock.py",
    "core/settings.py",
    "core/storage.py",
    "modules/ip_lookup/api_client.py",
    "modules/url_shortener/api_client.py",
    "bot.py",
    "config.py",
    "scripts/doctor.py",
    "scripts/database.py",
    "scripts/ci",
    "tests",
)

# handlers.py remains a large legacy formatting migration. It is linted now, but
# formatting it will be enabled in a dedicated mechanical snapshot.
FORMAT_TARGETS = tuple(target for target in LINT_TARGETS if target != "core/handlers.py")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("check", "format"))
    args = parser.parse_args()
    command = [sys.executable, "-m", "ruff"]
    targets = LINT_TARGETS
    if args.mode == "check":
        command.append("check")
    else:
        command.extend(("format", "--check"))
        targets = FORMAT_TARGETS
    return subprocess.run([*command, *targets], check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
