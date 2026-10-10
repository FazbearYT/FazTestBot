"""FazTestBot application entry point.

Importing this module is intentionally side-effect free. Runtime resources are
created only by :func:`build_runtime` after strict configuration validation.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from core.settings import ConfigurationError, Settings, load_settings


@dataclass(slots=True)
class BotRuntime:
    """Own the resources needed for one bot process."""

    bot: Any
    module_manager: Any
    scheduler: Any | None = None
    loaded_count: int = 0
    _scheduler_started: bool = False
    _stopped: bool = False

    def run(self) -> None:
        """Start background jobs and polling, then always release resources."""

        try:
            if self.scheduler is not None:
                self.scheduler.start()
                self._scheduler_started = True
            self.bot.infinity_polling()
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        """Stop the scheduler and Telegram worker pool exactly once."""

        if self._stopped:
            return
        self._stopped = True
        try:
            if self.scheduler is not None and self._scheduler_started:
                self.scheduler.shutdown(wait=False)
        finally:
            self.bot.stop_bot()


def build_runtime(
    settings: Settings | None = None,
    *,
    bot_factory: Callable[[str], Any] | None = None,
    scheduler_factory: Callable[[], Any] | None = None,
    manager: Any | None = None,
    register_handlers: Callable[[Any], None] | None = None,
    backup_callback: Callable[[], Any] | None = None,
    migrate_database: Callable[[], Any] | None = None,
) -> BotRuntime:
    """Validate configuration and assemble, but do not start, the application."""

    settings = settings or load_settings()
    settings.require_startup_ready()

    if migrate_database is None:
        from core.migrations import DatabaseMigrator

        migrate_database = DatabaseMigrator().apply_migrations
    migrate_database()

    # Heavy imports are deliberately delayed until validation has succeeded.
    if bot_factory is None:
        from telebot import TeleBot

        bot_factory = TeleBot
    if scheduler_factory is None:
        from apscheduler.schedulers.background import BackgroundScheduler

        scheduler_factory = BackgroundScheduler
    if manager is None:
        from core.module_manager import module_manager

        manager = module_manager
    if register_handlers is None:
        from core.handlers import register_global_handlers

        register_handlers = register_global_handlers
    if backup_callback is None:
        from core.backup import backup_manager

        def create_scheduled_backup() -> Any:
            return backup_manager.create_backup(manual=False)

        backup_callback = create_scheduled_backup

    bot = bot_factory(settings.bot_token)
    try:
        register_handlers(bot)
        loaded_count = manager.discover_and_load(bot)

        scheduler = None
        if settings.backup_enabled:
            scheduler = scheduler_factory()
            backup_hour, backup_minute = map(int, settings.backup_time.split(":"))
            scheduler.add_job(
                func=backup_callback,
                trigger="cron",
                hour=backup_hour,
                minute=backup_minute,
                id="daily_backup",
                replace_existing=True,
            )
    except Exception:
        bot.stop_bot()
        raise

    return BotRuntime(
        bot=bot,
        module_manager=manager,
        scheduler=scheduler,
        loaded_count=loaded_count,
    )


def _print_startup_summary(runtime: BotRuntime, settings: Settings) -> None:
    import config
    from core.paths import BACKUPS_DIR, DATABASE_PATH, DOWNLOADS_DIR

    print("\nRegistered modules:")
    for module in runtime.module_manager.get_all_modules():
        print(f"  - {module.icon} {module.name} v{module.version}")

    errors = runtime.module_manager.get_errors()
    if errors:
        print("\nModule loading errors:")
        for error in errors:
            print(f"  - {error['module']}: {error['error']}")

    print("\n" + "=" * 50)
    print(f"FazTestBot v{config.VERSION} started")
    print(f"Update date: {config.LAST_UPDATE_DATE}")
    print(f"Database: {DATABASE_PATH}")
    print(f"Backups: {BACKUPS_DIR} (keep {settings.backup_retention_count} files)")
    print(f"Downloads: {DOWNLOADS_DIR} (max {settings.max_download_size_mb} MB)")
    print(f"Administrators: {len(settings.admins)}")
    print(f"Loaded modules: {runtime.loaded_count}")
    print("=" * 50)
    print("\nPress Ctrl+C to stop.\n")


def main() -> int:
    try:
        settings = load_settings()
        runtime = build_runtime(settings)
    except ConfigurationError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        print("Run `python -m scripts.doctor` for details.", file=sys.stderr)
        return 2
    except Exception as error:
        print(f"Startup failed: {error}", file=sys.stderr)
        return 1

    _print_startup_summary(runtime, settings)
    try:
        runtime.run()
    except KeyboardInterrupt:
        print("\nFazTestBot stopped by user.")
        return 0
    except Exception as error:
        print(f"Runtime failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
