# FazTestBot

Modular Telegram bot built with Python, pyTelegramBotAPI, and SQLite.

## Installation

```bash
python -m pip install -r requirements.txt
```

Copy `secrets.template.py` to the ignored `secrets.py`, configure the bot token,
and start the application from the repository root with `python bot.py`.

## Sticker Vault (experimental)

The `feature/sticker-vault` branch adds an isolated private-chat module that:

- adds separately sent regular stickers to a personal sticker set;
- keeps static, animated, and video stickers in the same regular set;
- prevents duplicates by Telegram `file_unique_id`;
- creates another pack part when the 120-sticker limit is reached;
- exports the original sticker as WEBP, TGS, or WEBM without writing it to disk.

Only generated pack names, part numbers, and last known item counts are persisted
in `temp/database/users.db`. Pending actions remain in memory and expire after 15
minutes. Mask stickers and custom emoji are intentionally outside the MVP scope.

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
