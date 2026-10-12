# FazTestBot

Modular Telegram bot built with Python, pyTelegramBotAPI, and SQLite.

## Installation

```bash
pip install -r requirements.txt
```

Copy `.env.example` to the ignored `.env`, configure `BOT_TOKEN`, and validate the
environment before startup:

```bash
python -m scripts.doctor
python bot.py
```

Process environment variables override values from `.env`. Secret values are never
stored in tracked Python files or printed by the diagnostic command.

Runtime state defaults to the ignored `temp/` directory. Set
`FAZTESTBOT_DATA_DIR` to place the database, backups, logs, downloads, and exports
on persistent storage outside the source checkout. Relative paths are resolved from
the repository root. Changing this setting does not move existing data; follow the
database backup and restore procedure when relocating an installation.

For an existing installation, copy the values from the legacy ignored `secrets.py`
to `.env`. After `python -m scripts.doctor` succeeds and the bot starts correctly,
delete `secrets.py`; leaving it in the repository root shadows Python's standard
library module with the same name.

## Development

The repository has a module-aware CI pipeline. Install development tools and run the
same blocking checks locally:

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m scripts.ci.run_all
```

New modules must include their own tests. See [CONTRIBUTING.md](CONTRIBUTING.md) for
the contract and [docs/ci.md](docs/ci.md) for pipeline architecture and branch
protection recommendations.

Database migration, integrity-check, and backup procedures are documented in
[docs/database.md](docs/database.md).

Runtime logging, redaction, correlation, and incident-diagnostics conventions are
documented in [docs/observability.md](docs/observability.md).

Admin access boundaries, module snapshots, destructive confirmations, and offline
restore are documented in [docs/admin-panel.md](docs/admin-panel.md).

External HTTP resilience and transient interaction-state conventions are documented
in [docs/networking.md](docs/networking.md).

## Releases

The application version is declared once in `core/version.py`. Release metadata,
source archives, checksums, and tag publication are validated automatically. See
[CHANGELOG.md](CHANGELOG.md) for technical changes and [docs/releases.md](docs/releases.md)
for the promotion procedure from `develop` to `master`.
