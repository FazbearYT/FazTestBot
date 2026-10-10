# FazTestBot

Modular Telegram bot built with Python, pyTelegramBotAPI, and SQLite.

## Installation

```bash
pip install -r requirements.txt
```

Copy `secrets.template.py` to the ignored `secrets.py`, configure the bot token, and
start the application from the repository root with `python bot.py`.

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
