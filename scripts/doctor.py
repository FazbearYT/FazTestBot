"""Inspect local readiness without starting the bot or exposing secrets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.health import build_health_report
from core.paths import DATABASE_PATH, ENV_FILE, ROOT_DIR, SECRETS_FILE
from core.settings import ConfigurationError, load_settings


def _render_text(report) -> None:
    for check in report.checks:
        print(f"[{check.status.upper()}] {check.name}: {check.summary}")
        if check.name == "configuration" and check.status == "ok":
            print(f"  Administrators configured: {check.details['administrator_count']}")
            print(f"  Automatic backups enabled: {check.details['automatic_backups']}")
            print(f"  Media downloader enabled: {check.details['media_downloader']}")
        elif check.name == "configuration":
            for error in check.details.get("errors", []):
                print(f"  {error}")
        elif check.name == "database":
            print(f"  Schema version: {check.details.get('schema_version', 'unknown')}")
            pending = check.details.get("pending_migrations", [])
            if isinstance(pending, list):
                print(f"  Pending migrations: {', '.join(pending) if pending else 'none'}")
            else:
                print(f"  Pending migrations: {pending}")
    print(f"Readiness: {'ready' if report.ready else 'not ready'}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ENV_FILE)
    parser.add_argument("--db-path", type=Path, default=DATABASE_PATH)
    parser.add_argument("--root-path", type=Path, default=ROOT_DIR, help=argparse.SUPPRESS)
    parser.add_argument("--secrets-path", type=Path, default=SECRETS_FILE, help=argparse.SUPPRESS)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    try:
        settings = load_settings(env_file=args.env_file)
    except ConfigurationError as error:
        if args.as_json:
            print(
                json.dumps(
                    {
                        "ready": False,
                        "checks": [
                            {
                                "name": "configuration",
                                "status": "error",
                                "summary": "configuration could not be parsed",
                                "details": {"error": str(error)},
                            }
                        ],
                    },
                    ensure_ascii=False,
                )
            )
        else:
            print(f"[ERROR] configuration: {error}")
            print("Readiness: not ready")
        return 1

    report = build_health_report(
        settings,
        db_path=args.db_path,
        root_path=args.root_path,
        secrets_path=args.secrets_path,
    )
    if args.as_json:
        print(json.dumps(report.as_dict(), ensure_ascii=False))
    else:
        _render_text(report)
    return 0 if report.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
