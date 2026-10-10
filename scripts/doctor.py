"""Validate local configuration without starting the bot or exposing secrets."""

from __future__ import annotations

import argparse
from pathlib import Path

from core.paths import ENV_FILE, SECRETS_FILE
from core.settings import ConfigurationError, load_settings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ENV_FILE)
    args = parser.parse_args()

    try:
        settings = load_settings(env_file=args.env_file)
    except ConfigurationError as error:
        print(f"Configuration is invalid: {error}")
        return 1

    errors = settings.startup_errors()
    if errors:
        for error in errors:
            print(f"Configuration is incomplete: {error}")
        return 1

    print("Configuration is valid for startup.")
    print(f"Administrators configured: {len(settings.admins)}")
    print(f"Automatic backups enabled: {settings.backup_enabled}")
    print(f"Media downloader enabled: {settings.media_downloader_enabled}")
    if SECRETS_FILE.exists():
        print(
            "Warning: legacy secrets.py still exists. Migrate its values to .env, "
            "verify startup, then delete it manually."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
