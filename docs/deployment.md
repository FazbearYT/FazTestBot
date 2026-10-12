# Deployment foundation

FazTestBot is a long-polling, single-instance application. The repository provides
an operating contract and health commands, but intentionally does not deploy to a
host until the production target and its secret store have been selected.

## Runtime contract

- Run exactly one bot process against one SQLite database.
- Keep the source checkout, secrets, and persistent data separate.
- Store `BOT_TOKEN` and optional provider credentials in the host's secret store or
  in an untracked, access-restricted `.env` file.
- Set `FAZTESTBOT_DATA_DIR` to a durable local filesystem path. Do not place the
  SQLite database on a network share and do not mount the same data directory into
  multiple replicas.
- Let the process manager send `SIGTERM` or `SIGINT` and allow a shutdown grace
  period. The bot then stops its scheduler, modules, Telegram worker pool, and
  releases its single-instance lock.

The configured data directory contains the database, backups, logs, downloads,
exports, process lock, and runtime status. Changing `FAZTESTBOT_DATA_DIR` does not
move existing data.

## Installation preflight

Use a dedicated Python virtual environment and install the exact runtime pins:

```bash
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m scripts.doctor
```

`scripts.doctor` validates configuration, the database and migrations, available
space on the configured data volume, and the absence of the legacy `secrets.py`.
It performs no migration, network request, or write to the database.

Before the first production start, explicitly choose one of these database paths:

1. Start fresh and let the application create a new database.
2. Stop the old instance, back up its database, copy it into
   `<FAZTESTBOT_DATA_DIR>/database/users.db`, run `python -m scripts.database
   check`, then start the new instance so controlled migrations can run.

Never copy a live SQLite database file directly. Follow [database.md](database.md)
for backup, inspection, migration, and restore procedures.

## Process-manager health checks

Readiness before startup:

```bash
python -m scripts.doctor --json
```

Liveness after startup:

```bash
python -m scripts.liveness --json
```

The liveness command succeeds only when a structurally valid ready marker exists
and the application lock is currently owned. It does not call Telegram or expose
credentials. A missing marker means the process has not reached polling; a stale
marker means no process owns the lock and the service should be restarted.

The process manager should restart non-zero exits with a bounded delay, retain
logs, start after networking is available, and avoid overlapping instances. Do not
use the readiness command as a recurring liveness probe because it describes
configuration and storage, not whether polling is active.

## Home Windows host

A home PC is suitable for a pilot, not for an availability commitment. Use Task
Scheduler to start at system boot under a dedicated local account, regardless of
interactive logon, with the repository as the working directory and the virtual
environment's `python.exe` running `bot.py`. Configure restart-on-failure and make
sure sleep and hibernation cannot suspend the machine while the bot is expected to
serve users.

Keep the data directory outside replaceable source checkouts. Gaming load is
unlikely to stress the bot itself, but restarts, Windows Update, sleep, unstable
connectivity, and manual shutdowns are real outages. The pilot should therefore
prove backup restore, automatic restart, and liveness monitoring before it is
treated as production.

## Update and rollback boundary

An update procedure should always:

1. Verify a tagged GitHub Release and its checksum.
2. Create and validate a database backup.
3. Stop the old process and confirm liveness is false.
4. Install the release into a new code directory without overwriting persistent
   data or `.env`.
5. Run readiness diagnostics, start the process, and require liveness to become
   true.
6. On failure, stop the candidate, restore the previous code and—only when a
   migration requires it—the matching verified database backup.

Automatic deployment remains deferred until the target can implement these steps,
protect production secrets with an approval-gated GitHub Environment, serialize
deployments, and report a verifiable rollback result.
