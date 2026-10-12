import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from modules.decision_maker.handlers import DecisionMakerModule


class DecisionMakerHandlerTests(unittest.TestCase):
    def setUp(self):
        self.module = DecisionMakerModule(
            "decision_maker",
            "Decision Maker",
            "Description",
            "🎲",
            "1.0.0",
            "dm_",
        )

    def test_entry_initializes_private_session_and_renders_menu(self):
        bot = MagicMock()
        call = self._callback(actor_id=10, chat_id=10, message_id=7)

        self.module.handle_entry(bot, call)

        self.assertEqual(7, self.module.get_user_state(10, "message_id"))
        rendered = bot.edit_message_text.call_args.kwargs
        self.assertEqual(10, rendered["chat_id"])
        self.assertEqual(7, rendered["message_id"])
        self.assertEqual("HTML", rendered["parse_mode"])

    def test_entry_rejects_shared_chat_without_creating_state(self):
        bot = MagicMock()
        call = self._callback(actor_id=10, chat_id=-100, message_id=7, chat_type="group")

        self.module.handle_entry(bot, call)

        self.assertEqual(0, self.module.get_admin_snapshot().active_state_count)
        bot.edit_message_text.assert_not_called()
        bot.answer_callback_query.assert_called_once_with(
            "callback",
            "Decision Maker доступен только в приватном чате с ботом.",
            show_alert=True,
        )

    def test_list_choice_escapes_values_and_records_action(self):
        bot = MagicMock()
        self.module.set_user_state(10, "message_id", 7)
        self.module.set_user_state(10, "list_state", "waiting_input")
        message = self._message(text="<b>unsafe</b>, safe")

        with (
            patch.object(self.module, "_log_action") as record,
            patch("modules.decision_maker.handlers.random.choice", return_value="<b>unsafe</b>"),
        ):
            self.module._process_list_input(message, bot)

        rendered = bot.edit_message_text.call_args.kwargs["text"]
        self.assertIn("&lt;b&gt;unsafe&lt;/b&gt;", rendered)
        self.assertNotIn("<b><b>unsafe</b></b>", rendered)
        record.assert_called_once_with(10, "list_choice", "<b>unsafe</b>", "2 items")

    def test_non_text_list_input_is_reported_as_empty_instead_of_crashing(self):
        bot = MagicMock()
        self.module.set_user_state(10, "message_id", 7)
        self.module.set_user_state(10, "list_state", "waiting_input")

        self.module._process_list_input(self._message(text=None), bot)

        rendered = bot.edit_message_text.call_args.kwargs["text"]
        self.assertIn("Список пуст", rendered)

    def test_non_text_custom_range_is_reported_as_invalid_format(self):
        bot = MagicMock()
        self.module.set_user_state(10, "message_id", 7)

        self.module._process_custom_range(self._message(text=None), bot)

        rendered = bot.edit_message_text.call_args.kwargs["text"]
        self.assertIn("Неверный формат", rendered)

    @staticmethod
    def _message(*, text):
        return SimpleNamespace(
            from_user=SimpleNamespace(id=10),
            chat=SimpleNamespace(id=10, type="private"),
            message_id=8,
            text=text,
        )

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
