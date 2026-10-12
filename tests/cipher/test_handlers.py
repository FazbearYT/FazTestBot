import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from modules.cipher.handlers import CipherModule


class CipherHandlerTests(unittest.TestCase):
    def setUp(self):
        self.module = CipherModule(
            "cipher",
            "Cipher",
            "Description",
            "🔐",
            "1.0.0",
            "cipher_",
        )

    def test_entry_initializes_private_session_and_renders_menu(self):
        bot = MagicMock()
        call = self._callback(actor_id=10, chat_id=10, message_id=7)

        with patch("modules.cipher.handlers.uuid.uuid4", return_value="session-id"):
            self.module.handle_entry(bot, call)

        self.assertEqual(7, self.module.get_user_state(10, "message_id"))
        self.assertEqual("session-id", self.module.get_user_state(10, "session_id"))
        self.assertIsNone(self.module.get_user_state(10, "cipher"))
        rendered = bot.edit_message_text.call_args.kwargs
        self.assertEqual(10, rendered["chat_id"])
        self.assertEqual(7, rendered["message_id"])
        self.assertEqual("HTML", rendered["parse_mode"])

    def test_entry_rejects_shared_chat_without_creating_state(self):
        bot = MagicMock()
        call = self._callback(actor_id=10, chat_id=-100, message_id=7, chat_type="group")
        call.id = "callback"

        self.module.handle_entry(bot, call)

        self.assertEqual(0, self.module.get_admin_snapshot().active_state_count)
        bot.edit_message_text.assert_not_called()
        bot.answer_callback_query.assert_called_once_with(
            "callback",
            "Шифратор доступен только в приватном чате с ботом.",
            show_alert=True,
        )

    def test_morse_result_escapes_user_text_and_records_operation(self):
        bot = MagicMock()
        self.module.set_user_state(10, "message_id", 7)
        self.module.set_user_state(10, "session_id", "session")
        self.module.set_user_state(10, "cipher", "morze")
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=10),
            chat=SimpleNamespace(id=10, type="private"),
            message_id=8,
            text="<b>A</b>",
        )

        with patch("modules.cipher.handlers.db.log_cipher_operation") as record:
            self.module._process_text_input(message, bot)

        rendered = bot.edit_message_text.call_args.kwargs["text"]
        self.assertIn("&lt;b&gt;A&lt;/b&gt;", rendered)
        self.assertNotIn("<code><b>A</b></code>", rendered)
        record.assert_called_once()

    @staticmethod
    def _callback(*, actor_id, chat_id, message_id, chat_type="private"):
        return SimpleNamespace(
            id="callback",
            from_user=SimpleNamespace(id=actor_id),
            message=SimpleNamespace(
                chat=SimpleNamespace(id=chat_id, type=chat_type),
                message_id=message_id,
            ),
        )


if __name__ == "__main__":
    unittest.main()
