import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.handlers import register_global_handlers


class FakeBot:
    def __init__(self):
        self.message_handlers = {}
        self.callback_handlers = {}
        self.edits = []
        self.callback_answers = []

    def message_handler(self, **_filters):
        def decorator(function):
            self.message_handlers[function.__name__] = function
            return function

        return decorator

    def callback_query_handler(self, **_filters):
        def decorator(function):
            self.callback_handlers[function.__name__] = function
            return function

        return decorator

    def edit_message_text(self, **kwargs):
        self.edits.append(kwargs)

    def answer_callback_query(self, callback_id, *args, **kwargs):
        self.callback_answers.append((callback_id, args, kwargs))


def callback(data: str, *, user_id: int = 1, chat_id: int = 1, chat_type: str = "private"):
    user = SimpleNamespace(id=user_id, username="admin", first_name="Admin", last_name=None)
    message = SimpleNamespace(
        chat=SimpleNamespace(id=chat_id, type=chat_type),
        message_id=10,
    )
    return SimpleNamespace(id="callback-id", data=data, from_user=user, message=message)


class AdminHandlerRoutingTests(unittest.TestCase):
    def setUp(self):
        self.bot = FakeBot()
        self.admin = Mock()
        self.admin.is_admin.return_value = True
        self.database = Mock()
        self.backups = Mock()
        self.easter = Mock()
        self.easter.check_blocked_user.return_value = False
        patches = (
            patch("core.handlers.admin_mgr", self.admin),
            patch("core.handlers.db", self.database),
            patch("core.handlers.backup_manager", self.backups),
            patch("core.handlers.easter_egg_manager", self.easter),
        )
        self.addCleanup(lambda: [item.stop() for item in reversed(patches)])
        for item in patches:
            item.start()
        register_global_handlers(self.bot)
        self.handler = self.bot.callback_handlers["handle_admin_callbacks"]

    def test_admin_callback_rejects_group_before_database_activity(self):
        self.handler(callback("admin_emergency", chat_type="group"))

        self.database.create_or_update_user.assert_not_called()
        self.admin.emergency_clear_all.assert_not_called()

    def test_destructive_callback_requires_fresh_single_use_confirmation(self):
        self.handler(callback("admin_emergency"))
        markup = self.bot.edits[-1]["reply_markup"]
        confirm_data = markup.keyboard[0][0].callback_data

        self.handler(callback(confirm_data))
        self.handler(callback(confirm_data))

        self.admin.emergency_clear_all.assert_called_once_with()
        self.assertIn("недействительно", self.bot.edits[-1]["text"])

    def test_legacy_emergency_callback_cannot_execute_action(self):
        self.handler(callback("admin_emergency_confirm"))

        self.admin.emergency_clear_all.assert_not_called()
        self.assertIn("старого подтверждения", self.bot.edits[-1]["text"])

    def test_restore_callback_only_returns_offline_instructions(self):
        self.handler(callback("admin_backup_restore_users_manual_20260101_010101.db"))

        self.backups.restore_backup.assert_not_called()
        self.assertIn("Онлайн-восстановление отключено", self.bot.edits[-1]["text"])


if __name__ == "__main__":
    unittest.main()
