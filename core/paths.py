"""Central filesystem layout for source and runtime data."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from dotenv import dotenv_values

ROOT_DIR = Path(__file__).parent.parent
ENV_FILE = ROOT_DIR / ".env"


def resolve_data_dir(
    environ: Mapping[str, str] | None = None,
    *,
    root_dir: str | Path = ROOT_DIR,
    env_file: str | Path | None = None,
) -> Path:
    """Resolve persistent runtime storage without changing the process environment."""

    root = Path(root_dir).resolve()
    dotenv_path = Path(env_file) if env_file is not None else root / ".env"
    values = {key: value for key, value in dotenv_values(dotenv_path).items() if value is not None}
    values.update(dict(os.environ if environ is None else environ))
    configured = values.get("FAZTESTBOT_DATA_DIR", "").strip()
    candidate = Path(configured).expanduser() if configured else root / "temp"
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve()


# Persistent and transient runtime data live outside tracked source when configured.
DATA_DIR = resolve_data_dir()
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Compatibility alias retained for modules that still use the historical name.
TEMP_DIR = DATA_DIR

DATABASE_DIR = DATA_DIR / "database"
DATABASE_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_PATH = DATABASE_DIR / "users.db"

DOWNLOADS_DIR = DATA_DIR / "downloads"
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

EXPORTS_DIR = DATA_DIR / "exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

BACKUPS_DIR = DATA_DIR / "backups"
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)

LOGS_DIR = DATA_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

SECRETS_FILE = ROOT_DIR / "secrets.py"
SECRETS_TEMPLATE_FILE = ROOT_DIR / "secrets.template.py"

HISTORY_FILE = ROOT_DIR / "history.txt"
ROADMAP_FILE = ROOT_DIR / "roadmap.txt"
REQUIREMENTS_FILE = ROOT_DIR / "requirements.txt"

MODULES_DIR = ROOT_DIR / "modules"
CORE_DIR = ROOT_DIR / "core"


def get_temp_path(subdir: str | None = None) -> Path:
    """Return the runtime data directory or create one of its subdirectories."""

    if subdir:
        path = DATA_DIR / subdir
        path.mkdir(parents=True, exist_ok=True)
        return path
    return DATA_DIR


def cleanup_temp() -> None:
    """Remove disposable downloads and exports while preserving state and backups."""

    for directory in (DOWNLOADS_DIR, EXPORTS_DIR):
        if not directory.exists():
            continue
        for file in directory.iterdir():
            try:
                if file.is_file():
                    file.unlink()
            except OSError as error:
                from core.observability import event_fields, get_logger

                get_logger(__name__).warning(
                    "failed to remove temporary file %s",
                    file,
                    exc_info=(type(error), error, error.__traceback__),
                    extra=event_fields("filesystem.cleanup_failed", path=str(file)),
                )


__all__ = [
    "BACKUPS_DIR",
    "CORE_DIR",
    "DATABASE_DIR",
    "DATABASE_PATH",
    "DATA_DIR",
    "DOWNLOADS_DIR",
    "ENV_FILE",
    "EXPORTS_DIR",
    "HISTORY_FILE",
    "LOGS_DIR",
    "MODULES_DIR",
    "REQUIREMENTS_FILE",
    "ROADMAP_FILE",
    "ROOT_DIR",
    "SECRETS_FILE",
    "SECRETS_TEMPLATE_FILE",
    "TEMP_DIR",
    "cleanup_temp",
    "get_temp_path",
    "resolve_data_dir",
]
