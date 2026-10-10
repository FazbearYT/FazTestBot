# Admin Panel

Admin Panel v2 keeps Telegram-specific routing separate from dashboard composition.
`core/admin_panel.py` owns read-only dashboard data and HTML rendering, while every
module can expose a bounded `ModuleAdminSnapshot` through the optional base-module
contract. A broken module snapshot is isolated and shown as degraded instead of
breaking the whole panel.

## Access model

- `/admin`, `/auth`, `/my_stats`, admin callbacks, and follow-up input are accepted
  only in private chats;
- configured `ADMINS` retain direct access; optional code-based sessions expire;
- empty `ADMIN_SECRET_CODE` disables code authentication;
- code comparison is constant-time and repeated failures are temporarily throttled;
- leaving the panel revokes a dynamic session and clears pending input and
  confirmation state.

Search input is bound to both the administrator and the private chat, expires after
five minutes, and is consumed once. Dynamic values are escaped before Telegram HTML
rendering and large result messages are bounded below Telegram's message limit.

## Destructive operations

Emergency clearing, old-log cleanup, and backup deletion require a new opaque
confirmation token. The token is bound to the initiating administrator and chat,
expires after two minutes, and can be consumed only once. Buttons from old messages
cannot replay an action.

Database restore is intentionally unavailable while the bot is running. The panel
shows the selected filename and directs the operator to stop the bot and use:

```bash
python -m scripts.database restore --backup-file <generated-backup-name>
python -m scripts.database check
```

The CLI validates the snapshot, creates a safety backup, restores through SQLite's
Online Backup API, and performs an integrity/schema check before returning success.

## Module contract

The default snapshot contains only module metadata, a health status, a short
summary, and an aggregate active-state count. Modules may add explicitly selected,
non-sensitive `ModuleMetric` values. User identifiers and raw state are not exposed.
Provider failures are sanitized and isolated per module.

This stage does not change which user data is stored, log/export retention, or the
policy for deleting user data. Those decisions remain deferred for separate review.
