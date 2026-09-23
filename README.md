# FazTestBot

FazTestBot is a personal, modular Telegram bot that collects several small utilities behind one inline-button interface. The current release is **v4.5.0** and is built with Python, [pyTelegramBotAPI](https://github.com/eternnoir/pyTelegramBotAPI), SQLite, `aiohttp`, and APScheduler.

The project is usable in its current form, but it is not a polished public service. It was designed for a small, trusted group of users, stores some submitted content locally, and still contains legacy configuration and an unfinished module. Read [Current limitations](#current-limitations) and [Data and security notes](#data-and-security-notes) before deploying it.

## What the bot includes

| Module | Version | State | Functionality |
| --- | ---: | --- | --- |
| Cipher | 2.7.2 | Working | Morse, numeric, Caesar, QR, and Leet transformations. Leet supports Light, Medium, Hardcore, and a custom replacement probability. |
| Decision Maker | 1.0.4 | Working | Random number generation, random selection from a list, coin flips with statistics, and random Dota 2 heroes by attribute. |
| IP Info Lookup | 1.0.3 | Working | IPv4/IPv6 lookup through `ipapi.co` by default or `ipinfo.io` with a token; keeps a per-user lookup history. |
| URL Shortener | 1.0.0 | Working | URL validation, TinyURL shortening, and per-user link history. Cutt.ly code exists, but its configuration is not currently wired to `secrets.py`. |
| Steam Deals Tracker | 2.0.0 | Working | Personal wishlists, game search, regional Steam prices, locally tracked historical lows, free-game discovery, and price-drop notifications every six hours. |
| Media Downloader | 1.3.1 | Disabled | Present in the module menu, but intentionally implemented as a disabled placeholder because the download pipeline is unstable. |

### Steam pricing model

Game discovery uses CheapShark, while current prices come from Steam `appdetails` for the Kazakhstan store (`cc=kz`). The primary price is therefore displayed in KZT. A RUB value is shown only as an approximate currency conversion and is **not** the Russian Steam store price. Steam does not provide price history here, so the bot records the first observed price and updates its own historical minimum.

## User experience

The regular interface starts with `/start` and is driven by inline keyboards. The main menu contains the module list, help, and bot information. Most module flows edit one Telegram message instead of sending a new message for every step.

Available commands:

| Command | Access | Purpose |
| --- | --- | --- |
| `/start` | Everyone | Open the normal main menu and create/update the local user record. |
| `/auth <secret>` | Anyone who knows the configured secret | Create an in-memory temporary admin session. |
| `/admin` | Configured or temporarily authenticated admins | Open the hidden administration panel. |
| `/my_stats` | Admins | Show the requesting admin's stored cipher statistics. |

The admin panel provides global statistics, user profiles, cipher-log search, CSV/JSON export, log cleanup, database backup management, and emergency data cleanup. Administrative actions are written to an audit table.

## Architecture

```text
Telegram update
    |
    v
bot.py
    |-- core/handlers.py -------- global commands, menus, admin flows
    |-- core/module_manager.py -- discovers modules/* packages
    |-- core/database.py -------- SQLite users and cipher operations
    |-- core/backup.py ---------- scheduled/manual database backups
    `-- modules/<module>/
            |-- __init__.py ----- exports the module instance
            |-- handlers.py ----- module state and Telegram handlers
            |-- keyboards.py ---- inline keyboards
            `-- config.py ------- module-local settings
```

`bot.py` creates the `TeleBot`, registers global handlers, discovers modules, starts the daily backup scheduler, and then enters long polling. `ModuleManager` imports every directory below `modules/`, validates its exported `BaseModule` instance, registers its callback prefix, and invokes its `on_load()` hook. A failure in one module is recorded and printed without intentionally preventing the remaining modules from loading.

Runtime state is split between:

- in-memory dictionaries for active menu/admin sessions;
- SQLite tables for users, histories, statistics, wishlists, and audit records;
- JSON cache for Steam data;
- filesystem backups and temporary exports.

All generated runtime files live below `temp/` and are ignored by Git.

## Repository layout

```text
.
|-- bot.py                    # application entry point
|-- config.py                 # global constants and secrets loading
|-- secrets.template.py       # safe configuration template
|-- requirements.txt          # Python dependencies
|-- core/
|   |-- module_base.py        # module interface
|   |-- module_manager.py     # automatic module discovery
|   |-- handlers.py           # global and admin handlers
|   |-- database.py           # SQLite access
|   |-- admin.py              # authentication, exports, admin queries
|   |-- backup.py             # backup creation, rotation, restore
|   |-- paths.py              # canonical runtime paths
|   `-- ...
|-- modules/
|   |-- cipher/
|   |-- decision_maker/
|   |-- ip_lookup/
|   |-- media_downloader/
|   |-- steam_deals/
|   `-- url_shortener/
|-- history.txt               # detailed historical changelog
`-- roadmap.txt               # legacy roadmap; not a reliable current plan
```

## Requirements

- Python 3.10 or newer is recommended.
- A Telegram bot token created with [BotFather](https://t.me/BotFather).
- Network access to Telegram and the APIs used by the enabled modules.
- SQLite support, which is included with normal CPython installations.
- `ffmpeg` would be required by the unfinished Media Downloader path, but that module is currently disabled.

## Installation

Clone the repository and enter its root directory:

```bash
git clone https://github.com/FazbearYT/FazTestBot.git
cd FazTestBot
```

Create and activate a virtual environment.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the tracked dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Create the private configuration file:

Windows PowerShell:

```powershell
Copy-Item secrets.template.py secrets.py
```

Linux/macOS:

```bash
cp secrets.template.py secrets.py
```

Edit `secrets.py`, replace the placeholder bot token, and configure at least one administrator. The file is ignored by Git and must never be committed.

Start the bot **from the repository root**:

```bash
python bot.py
```

Running from the root matters because module discovery currently uses the relative `modules/` path. On first startup, the bot creates `temp/database/users.db` and the other runtime directories automatically.

## Configuration reference

### Effective `secrets.py` settings

| Setting | Required | Default/template behavior |
| --- | --- | --- |
| `BOT_TOKEN` | Yes | Startup stops while the placeholder value is present. |
| `ADMINS` | Recommended | Telegram numeric user IDs with permanent admin access. |
| `ADMIN_SECRET_CODE` | Recommended | Shared code accepted by `/auth`; choose a long, unique value. |
| `ADMIN_SESSION_HOURS` | No | Temporary admin-session lifetime; sessions are lost on restart. |
| `IP_INFO_API_SERVICE` | No | `ipapi` uses the keyless provider; `ipinfo` uses the token below. |
| `IPINFO_API_KEY` | Only for `ipinfo` | Token for `ipinfo.io`. |
| `CHEAPSHARK_API_KEY` | No | Retained by the Steam module configuration; ordinary CheapShark search is keyless. |
| `MAX_DOWNLOAD_SIZE_MB` | No | Loaded by the disabled downloader. |
| `MAX_DOWNLOADS_PER_USER_PER_DAY` | No | Loaded by the disabled downloader. |
| `LOG_RETENTION_DAYS` | No | Displayed in admin settings; cipher cleanup is currently initialized with a 30-day default in code. |
| `LOG_LEVEL` | No | Loaded but not consistently applied by the current logging code. |
| `GROQ_API_KEY` | No | Reserved for a future module and unused in v4.5.0. |

### Settings currently controlled in source

Some values exposed by `secrets.template.py` are not connected end-to-end in v4.5.0:

- `modules/url_shortener/config.py` hard-codes TinyURL and an empty Cutt.ly key, so the similarly named secret settings do not change the active service.
- `modules/media_downloader/config.py` hard-codes `ENABLED = False`; changing `MEDIA_DOWNLOADER_ENABLED` in `secrets.py` does not enable it.
- Runtime paths come from `core/paths.py`; the `DATABASE_PATH`, `BACKUP_DIR`, and `DOWNLOADS_DIR` entries in the template are not imported by `config.py`.
- Backup scheduling is configured in `config.py` with a default time of `03:00`, seven retained files, and a 30-day age limit.
- Steam region, language, notification interval, and wishlist limits are defined in `modules/steam_deals/config.py`.

These mismatches are documented here so operators do not assume a template value has taken effect when the implementation ignores it.

## Persistence and backups

The canonical paths are created by `core/paths.py`:

| Path | Contents |
| --- | --- |
| `temp/database/users.db` | Users, cipher operations, admin audit records, module histories/statistics, and Steam wishlists. |
| `temp/backups/` | Automatic and manual SQLite database copies. |
| `temp/exports/` | Admin-generated CSV and JSON exports. |
| `temp/downloads/` | Temporary media files for the disabled downloader. |
| `temp/steam_deals_cache.json` | Cached Steam/free-game and exchange-rate data. |

The main scheduler attempts an automatic database backup every day at `03:00`. Rotation keeps no more than seven files and also removes files older than 30 days. Admins can create, inspect, restore, and delete backups from the Telegram panel.

The `temp/` directory is intentionally excluded from version control. Back it up separately if the bot's history and wishlists matter.

## External services

| Service | Used for | Key required |
| --- | --- | --- |
| Telegram Bot API | Bot messages, callbacks, and polling | Yes, bot token |
| `ipapi.co` | Default IP geolocation | No |
| `ipinfo.io` | Optional IP lookup provider | Yes |
| TinyURL | Default link shortening | No |
| Cutt.ly | Alternative shortening implementation | Yes, but config wiring needs repair |
| CheapShark | Steam game discovery | No for the current search calls |
| Steam Store APIs | Regional prices and free-game discovery | No |
| `open.er-api.com` | Approximate KZT-to-RUB conversion | No |

Provider availability, limits, and response formats are outside the bot's control. Most network calls have timeouts and user-facing failure messages, but there is no general retry/circuit-breaker layer.

## Data and security notes

This application should be treated as a personal bot, not a hardened multi-tenant service.

- Cipher operations are stored in SQLite with both the original and transformed text. The data is not encrypted at rest.
- URL and IP histories are also stored locally. Database backups and exports contain sensitive operational data.
- The `/auth` mechanism uses one shared plaintext secret from `secrets.py`. Anyone who obtains it can open a temporary admin session.
- Permanent administrator IDs should be restricted to trusted Telegram accounts.
- Temporary admin sessions exist only in process memory and disappear after restart.
- Do not publish `secrets.py`, `temp/`, database files, exports, or backups.
- If deploying for other people, add an explicit privacy policy, access controls, encrypted secret management, and a review of all retention/deletion behavior first.

## Adding a module

Module discovery is convention-based. To add `modules/example/`:

1. Create a class derived from `core.module_base.BaseModule`.
2. Implement `handle_entry()`, `handle_callback()`, and `get_menu_keyboard()`.
3. Give it a unique `module_id` and a callback prefix that ends in `_`.
4. In `modules/example/__init__.py`, expose an instance named `example_module`.
5. Keep callback data under the module's unique prefix and put module-specific settings in `config.py`.
6. Use `on_load()`/`on_unload()` for optional initialization and cleanup.

Minimal package entry point:

```python
from .handlers import ExampleModule

example_module = ExampleModule(
    module_id="example",
    name="Example",
    description="Example module",
    icon="🧩",
    version="1.0.0",
    callback_prefix="example_",
)
```

No change to `bot.py` is required when the folder name, exported variable, module ID, and callback prefix follow these rules.

## Current limitations

- Media Downloader is disabled and only shows an explanatory placeholder. Its dormant implementation references `pytubefix`, while the tracked dependencies currently list `pytube`; enabling it requires repair and testing rather than a configuration toggle.
- There is no automated test suite or CI workflow in the repository.
- Several handlers catch broad exceptions, which can hide programming errors behind generic Telegram alerts.
- Morse, numeric, and Caesar flows currently provide transformation only, not reverse decoding.
- Some HTML-sensitive input paths still need consistent escaping.
- Configuration is split between `secrets.py`, global `config.py`, and module-local config files, with the mismatches listed above.
- SQLite access is synchronous and opens many short-lived connections; that is acceptable for the intended small deployment but is not designed for high concurrency.
- The legacy `roadmap.txt` contains old target dates and version ideas. It should be read as historical planning, not as the current release contract.

## Troubleshooting

### `BOT_TOKEN` is not configured

Copy `secrets.template.py` to `secrets.py`, replace `YOUR_BOT_TOKEN_HERE`, and restart the process.

### A module does not appear or reports a load error

Run from the repository root, check the startup output, and verify the package exports `<folder_name>_module`. The exported object must inherit `BaseModule`, use a unique ID, and use a unique callback prefix ending in `_`.

### IP lookup always uses `ipapi.co`

Set `IP_INFO_API_SERVICE = "ipinfo"` and provide `IPINFO_API_KEY` in `secrets.py`. Without both, the client deliberately falls back to `ipapi.co`.

### Cutt.ly settings in `secrets.py` have no effect

This is a known v4.5.0 wiring issue. The active values are currently hard-coded in `modules/url_shortener/config.py`.

### Steam RUB prices do not match the Steam store

This is expected. KZT is the real configured Steam regional price; RUB is only an exchange-rate estimate.

### No automatic backup is created

The database must already exist when a backup job runs. Check the process output, `config.py` backup settings, and write permissions for `temp/backups/`.

## Project status

The latest tagged version is **v4.5.0**. Development is currently paused and known issues remain intentionally open for later cleanup. See `history.txt` for the detailed release history and `roadmap.txt` for legacy planning context.

No license file is currently included. Unless the repository owner states otherwise, do not assume permission to redistribute or reuse the code.
