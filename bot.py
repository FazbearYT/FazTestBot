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
    application_lock: Any | None = None
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
            try:
                shutdown_modules = getattr(self.module_manager, "shutdown", None)
                if callable(shutdown_modules):
                    shutdown_modules(self.bot)
            finally:
                try:
                    self.bot.stop_bot()
                finally:
                    if self.application_lock is not None:
                        self.application_lock.release()


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
        from core.bootstrap import migrate_database_safely

        migrate_database = migrate_database_safely
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
        try:
            shutdown_modules = getattr(manager, "shutdown", None)
            if callable(shutdown_modules):
                shutdown_modules(bot)
        finally:
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
    from core.observability import event_fields, get_logger
    from core.paths import BACKUPS_DIR, DATABASE_PATH, DOWNLOADS_DIR

    startup_logger = get_logger("runtime")
    for module in runtime.module_manager.get_all_modules():
        startup_logger.info(
            "module registered: %s v%s",
            module.name,
            module.version,
            extra=event_fields(
                "module.registered",
                module_id=module.id,
                module_version=module.version,
            ),
        )

    errors = runtime.module_manager.get_errors()
    startup_logger.info(
        "FazTestBot v%s started with %s modules",
        config.VERSION,
        runtime.loaded_count,
        extra=event_fields(
            "application.started",
            version=config.VERSION,
            update_date=config.LAST_UPDATE_DATE,
            database_path=str(DATABASE_PATH),
            backup_path=str(BACKUPS_DIR),
            download_path=str(DOWNLOADS_DIR),
            backup_retention_count=settings.backup_retention_count,
            max_download_size_mb=settings.max_download_size_mb,
            administrator_count=len(settings.admins),
            loaded_module_count=runtime.loaded_count,
            module_error_count=len(errors),
        ),
    )


def main() -> int:
    application_lock = None
    try:
        settings = load_settings()
        from core.observability import configure_logging, event_fields, get_logger
        from core.process_lock import ApplicationLock

        configure_logging(
            level=settings.log_level,
            retention_days=settings.log_retention_days,
        )
        runtime_logger = get_logger("runtime")
        application_lock = ApplicationLock()
        application_lock.acquire()
        runtime = build_runtime(settings)
        runtime.application_lock = application_lock
    except ConfigurationError as error:
        if application_lock is not None:
            application_lock.release()
        print(f"Configuration error: {error}", file=sys.stderr)
        print("Run `python -m scripts.doctor` for details.", file=sys.stderr)
        return 2
    except Exception as error:
        if application_lock is not None:
            application_lock.release()
        if "runtime_logger" in locals():
            runtime_logger.exception(
                "application startup failed",
                extra=event_fields("application.startup_failed"),
            )
        else:
            print(f"Startup failed: {error}", file=sys.stderr)
        return 1

    try:
        _print_startup_summary(runtime, settings)
        from core.runtime_status import RuntimeStatus
        from core.signals import ShutdownSignalHandlers
        from core.version import VERSION

        with RuntimeStatus(VERSION, runtime.loaded_count):
            with ShutdownSignalHandlers(runtime.shutdown) as shutdown_signals:
                runtime.run()
    except KeyboardInterrupt:
        runtime.shutdown()
        runtime_logger.info(
            "FazTestBot stopped by operator",
            extra=event_fields("application.stopped", reason="keyboard_interrupt"),
        )
        return 0
    except Exception:
        runtime.shutdown()
        runtime_logger.exception(
            "application runtime failed",
            extra=event_fields("application.runtime_failed"),
        )
        return 1
    if shutdown_signals.received is not None:
        runtime_logger.info(
            "FazTestBot stopped by process signal",
            extra=event_fields(
                "application.stopped",
                reason="process_signal",
                signal=shutdown_signals.received.name,
            ),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
