import importlib
import sys
import unittest
from unittest.mock import Mock, patch

from core.settings import ConfigurationError, Settings


class BotRuntimeTests(unittest.TestCase):
    def test_import_does_not_construct_runtime_resources(self):
        with (
            patch("telebot.TeleBot") as telebot_factory,
            patch("apscheduler.schedulers.background.BackgroundScheduler") as scheduler_factory,
        ):
            sys.modules.pop("bot", None)
            importlib.import_module("bot")

        telebot_factory.assert_not_called()
        scheduler_factory.assert_not_called()

    def test_invalid_settings_fail_before_any_factory_is_called(self):
        from bot import build_runtime

        bot_factory = Mock()
        scheduler_factory = Mock()
        migrate_database = Mock()

        with self.assertRaises(ConfigurationError):
            build_runtime(
                Settings(),
                bot_factory=bot_factory,
                scheduler_factory=scheduler_factory,
                migrate_database=migrate_database,
            )

        bot_factory.assert_not_called()
        scheduler_factory.assert_not_called()
        migrate_database.assert_not_called()

    def test_build_registers_handlers_modules_and_cron_without_starting(self):
        from bot import build_runtime

        bot_instance = Mock()
        bot_factory = Mock(return_value=bot_instance)
        scheduler = Mock()
        scheduler_factory = Mock(return_value=scheduler)
        manager = Mock()
        manager.discover_and_load.return_value = 6
        register_handlers = Mock()
        backup_callback = Mock()
        settings = Settings(bot_token="token", backup_time="04:35")

        runtime = build_runtime(
            settings,
            bot_factory=bot_factory,
            scheduler_factory=scheduler_factory,
            manager=manager,
            register_handlers=register_handlers,
            backup_callback=backup_callback,
            migrate_database=Mock(),
        )

        bot_factory.assert_called_once_with("token")
        register_handlers.assert_called_once_with(bot_instance)
        manager.discover_and_load.assert_called_once_with(bot_instance)
        scheduler.add_job.assert_called_once_with(
            func=backup_callback,
            trigger="cron",
            hour=4,
            minute=35,
            id="daily_backup",
            replace_existing=True,
        )
        scheduler.start.assert_not_called()
        self.assertEqual(runtime.loaded_count, 6)

    def test_disabled_backup_does_not_construct_scheduler(self):
        from bot import build_runtime

        scheduler_factory = Mock()
        runtime = build_runtime(
            Settings(bot_token="token", backup_enabled=False),
            bot_factory=Mock(return_value=Mock()),
            scheduler_factory=scheduler_factory,
            manager=Mock(discover_and_load=Mock(return_value=0)),
            register_handlers=Mock(),
            backup_callback=Mock(),
            migrate_database=Mock(),
        )

        scheduler_factory.assert_not_called()
        self.assertIsNone(runtime.scheduler)

    def test_partial_build_failure_stops_constructed_bot(self):
        from bot import build_runtime

        bot_instance = Mock()
        register_handlers = Mock(side_effect=RuntimeError("registration failed"))

        with self.assertRaisesRegex(RuntimeError, "registration failed"):
            build_runtime(
                Settings(bot_token="token"),
                bot_factory=Mock(return_value=bot_instance),
                scheduler_factory=Mock(),
                manager=Mock(),
                register_handlers=register_handlers,
                backup_callback=Mock(),
                migrate_database=Mock(),
            )

        bot_instance.stop_bot.assert_called_once_with()

    def test_migrations_run_before_handlers_and_module_discovery(self):
        from bot import build_runtime

        events = []
        bot_instance = Mock()
        manager = Mock()
        manager.discover_and_load.side_effect = lambda bot: events.append("modules") or 0

        build_runtime(
            Settings(bot_token="token", backup_enabled=False),
            bot_factory=lambda token: events.append("bot") or bot_instance,
            scheduler_factory=Mock(),
            manager=manager,
            register_handlers=lambda bot: events.append("handlers"),
            backup_callback=Mock(),
            migrate_database=lambda: events.append("migrations"),
        )

        self.assertEqual(["migrations", "bot", "handlers", "modules"], events)

    def test_run_stops_scheduler_and_bot_after_polling_failure(self):
        from bot import BotRuntime

        bot_instance = Mock()
        bot_instance.infinity_polling.side_effect = RuntimeError("polling failed")
        scheduler = Mock()
        application_lock = Mock()
        runtime = BotRuntime(
            bot=bot_instance,
            module_manager=Mock(),
            scheduler=scheduler,
            application_lock=application_lock,
        )

        with self.assertRaisesRegex(RuntimeError, "polling failed"):
            runtime.run()

        scheduler.start.assert_called_once_with()
        scheduler.shutdown.assert_called_once_with(wait=False)
        bot_instance.stop_bot.assert_called_once_with()
        application_lock.release.assert_called_once_with()
        runtime.shutdown()
        bot_instance.stop_bot.assert_called_once_with()
        application_lock.release.assert_called_once_with()

    def test_scheduler_start_failure_still_stops_bot(self):
        from bot import BotRuntime

        bot_instance = Mock()
        scheduler = Mock()
        scheduler.start.side_effect = RuntimeError("scheduler failed")
        runtime = BotRuntime(bot=bot_instance, module_manager=Mock(), scheduler=scheduler)

        with self.assertRaisesRegex(RuntimeError, "scheduler failed"):
            runtime.run()

        scheduler.shutdown.assert_not_called()
        bot_instance.infinity_polling.assert_not_called()
        bot_instance.stop_bot.assert_called_once_with()
