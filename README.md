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

For an existing installation, copy the values from the legacy ignored `secrets.py`
to `.env`. After `python -m scripts.doctor` succeeds and the bot starts correctly,
delete `secrets.py`; leaving it in the repository root shadows Python's standard
library module with the same name.

## Development

The repository has a module-aware CI pipeline. Install development tools and run the
same blocking checks locally:

```bash
python -m pip install -r requirements-dev.txt
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
