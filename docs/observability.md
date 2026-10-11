# Observability

FazTestBot writes human-readable runtime events to stderr and structured events to
`temp/logs/faztestbot.jsonl`. Runtime artifacts under `temp/` are ignored by Git.

## Event format

Each file line is a UTF-8 JSON object with these baseline fields:

- `timestamp`: timezone-aware UTC timestamp;
- `level`: standard Python logging level;
- `logger`: application component below the `faztestbot` namespace;
- `message`: concise operator-facing description;
- `event`: stable machine-readable event name when the caller provides one;
- `operation_id`: non-personal correlation identifier inside an operation context.

Additional fields describe an event without embedding Telegram messages, user IDs,
chat IDs, API payloads, or credentials. Known Telegram-token and named-secret forms
are redacted from messages, structured string fields, and exception tracebacks.

## Rotation and configuration

The active JSONL file rotates at UTC midnight. `LOG_RETENTION_DAYS` controls the
number of daily rotated files and keeps its existing default of 30. `LOG_LEVEL`
controls both console and file severity. This implementation does not change what
user data the application stores or the separately deferred data-retention policy.

Use `core.observability.get_logger(__name__)` and attach a stable event name with
`extra=event_fields("component.action", ...)`. Field names must not collide with
standard `LogRecord` attributes. Use `logger.exception(...)` only inside an active
exception handler so the diagnostic traceback is retained.

`core.exceptions` classifies failures as `user`, `transient`, `system`, or
`critical`. The classification determines log severity and whether retry is safe.
`handle_exception` records a stable error code and returns a localized safe message;
generic exception details are never sent to Telegram, and user-input exception text
is not copied into diagnostic logs.

## Incident workflow

1. Record the UTC time and the relevant `operation_id` shown in the JSONL log.
2. Run `python -m scripts.doctor` for read-only configuration, database, legacy-file,
   and disk checks without printing secrets. Use `--json` for machine-readable output.
3. Run `python -m scripts.database check` when the incident may involve persistence.
4. Preserve only the minimum relevant log excerpt; review it before sharing.
5. Never commit files from `temp/`, real `.env` files, databases, or log exports.
