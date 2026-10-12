# Changelog

This file records technical changes relevant to maintainers and release operators.
User-visible history remains available in `history.txt`.

## [Unreleased]

### Changed

- Runtime database, backups, logs, downloads, and exports can be placed on durable
  storage with `FAZTESTBOT_DATA_DIR`; readiness checks now inspect free space on
  that configured volume.
- `SIGINT` and `SIGTERM` now trigger the same idempotent shutdown path as normal
  runtime completion, allowing service managers to stop the bot cleanly.
- A local liveness probe now verifies both the published ready status and ownership
  of the single-instance process lock without contacting Telegram.

## [5.0.1] - 2026-10-11

### Fixed

- Non-text Telegram updates no longer crash the Easter egg fallback handler.
- Media Downloader now reports its deliberate disabled state consistently and
  cannot be enabled accidentally through environment configuration.
- URL Shortener now confines personal history and chat-scoped input to private
  chats, escapes rendered URLs, and returns safe errors without import-time
  database initialization.
- IP Lookup now confines searches and history to private chats, escapes all
  provider and stored values, checks its daily quota before network access, and
  avoids import-time database initialization.

### Quality

- Removed the unreachable legacy media download engine and its unused network
  dependencies instead of shipping an unbounded, untested file-processing path.
- Added an isolated Media Downloader test suite and mandatory module-scoped Ruff
  checks, and expanded repository quality coverage to every core Python module.
- Promoted Steam Deals out of the legacy CI exception list; its owned API-client
  tests and the complete module now run under the mandatory module quality gate.
- Promoted URL Shortener out of the legacy CI exception list with handler,
  storage, validation, and bounded external-client regression coverage.
- Promoted IP Lookup out of the legacy CI exception list with handler, storage,
  metering, validation, and bounded external-client regression coverage.
- Pinned every direct Python dependency exactly and made CI verify the installed
  versions in addition to dependency compatibility and vulnerability auditing.
- Pinned GitHub-hosted Linux jobs to Ubuntu 24.04 so a moving runner alias cannot
  silently change the validation or release environment.

### Release engineering

- Standardized GitHub Release titles on the existing `vX.Y.Z` tag convention while
  retaining the auditable `github-actions[bot]` publisher identity.

## [5.0.0] - 2026-10-11

### Changed

- Replaced tracked Python secrets with typed environment configuration, startup
  diagnostics, and explicit runtime bootstrap and shutdown boundaries.
- Introduced versioned SQLite migrations, integrity checks, atomic backups, and
  storage adapters shared by maintained modules.
- Added structured logging, correlation identifiers, secret redaction, health
  snapshots, and an explicit application error taxonomy.
- Reworked the admin panel around authenticated, auditable module snapshots and
  confirmation of destructive operations, with offline restore tooling.
- Centralized bounded HTTP access with timeouts, retries, response limits, and
  safe error reporting for maintained external-service clients.
- Isolated transient interactions by actor and chat. Chat-scoped Telegram flows
  that cannot be isolated safely are now restricted to private chats.
- Reconciled the diverged `master` and `develop` histories while preserving the
  Steam Deals and Leet Speak functionality from both lines.

### Quality

- Added a module-aware GitHub Actions pipeline across Python 3.10 and 3.13,
  repository policy checks, Ruff gates, application smoke tests, branch coverage,
  and dependency vulnerability auditing.
- Added characterization and regression coverage for runtime lifecycle, database
  migrations, admin access, network failure handling, module state, and Telegram
  handler routing.
- Pinned runtime, development, and GitHub Actions dependencies used by blocking
  automation.

### Release engineering

- Established `core.version` as the canonical release metadata source.
- Added a verified, reproducible source-archive build with SHA-256 checksums.
- Added tag-driven GitHub Release publication gated by the complete CI suite and
  by proof that the tagged commit belongs to `master` history.

[5.0.1]: https://github.com/FazbearYT/FazTestBot/compare/v5.0.0...v5.0.1
[5.0.0]: https://github.com/FazbearYT/FazTestBot/compare/v4.5.0...v5.0.0
[Unreleased]: https://github.com/FazbearYT/FazTestBot/compare/v5.0.1...develop
