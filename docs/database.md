# Database operations

FazTestBot uses one SQLite database with an ordered migration history. Application
startup validates configuration, creates a consistent backup of an existing database
when migrations are pending, applies each migration in its own transaction, and only
then registers handlers and modules.

## Safety guarantees

- every managed connection enables foreign keys and a five-second busy timeout;
- writable connections commit on success and roll back on exceptions;
- the database uses WAL mode for normal application access;
- schema DDL exists only in `core/migrations.py`;
- CI rejects direct `sqlite3.connect` calls outside `core/storage.py`;
- backups use SQLite's Online Backup API, include committed WAL pages, pass an
  integrity check, and are published by atomic file replacement;
- restore validates the selected snapshot and requires a successful safety backup
  before changing the live database;
- an unknown migration version stops startup instead of letting an older binary
  operate on a newer schema.

The migration and backup work does not change log retention or what user data is
stored. Those decisions remain outside Database v2.

## Offline operator workflow

Run these commands with the bot stopped when validating a real deployment:

```bash
python -m scripts.database check
python -m scripts.database backup
python -m scripts.database migrate
python -m scripts.database check
```

Для восстановления выбранной копии используйте отдельную offline-операцию:

```bash
python -m scripts.database restore --backup-file users_manual_YYYYMMDD_HHMMSS_ffffff.db
python -m scripts.database check
```

`restore` проверяет формат и целостность выбранного файла, создаёт защитную копию
текущей БД и проверяет восстановленную БД. Онлайн-восстановление из Telegram-панели
намеренно отключено. Запущенный бот удерживает межпроцессную блокировку; CLI
откажется восстанавливать БД, пока процесс бота не остановлен.

`migrate` creates another pre-migration backup automatically when changes are
pending. Keep the bot stopped until both the migration and final integrity check
succeed. Do not run these commands against the production database as part of CI.

Backup rotation retains the existing count- and age-based policy. A restore never
rotates away its selected snapshot before use, even when the retention count is one.
