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

## Validation

```bash
python -m pip install -r requirements-dev.txt
python -m ruff check modules/sticker_vault tests/sticker_vault tests/module_loading
python -m ruff format --check modules/sticker_vault tests/sticker_vault tests/module_loading
python -m compileall -q core modules tests
python -m unittest discover -s tests -p "test_*.py" -v
```

GitHub Actions runs the same checks on pushes to `feature/**`, `develop`, and
`master`, and on pull requests targeting `develop` or `master`.
