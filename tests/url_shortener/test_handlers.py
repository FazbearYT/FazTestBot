import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from modules.url_shortener.handlers import URLShortenerModule


class URLShortenerHandlerTests(unittest.TestCase):
    def setUp(self):
        self.database_factory = MagicMock()
        self.module = URLShortenerModule(
            "url_shortener",
            "URL Shortener",
            "Description",
            "🔗",
            "1.0.0",
            "url_",
            database_factory=self.database_factory,
        )

    def test_entry_does_not_open_database(self):
        bot = MagicMock()

        self.module.handle_entry(bot, self._callback("module_url_shortener"))

        self.database_factory.assert_not_called()
        bot.edit_message_text.assert_called_once()

    def test_private_actions_are_rejected_in_shared_chat_before_side_effects(self):
        for callback_data in ("url_shorten", "url_my_links", "url_again"):
            with self.subTest(callback_data=callback_data):
                bot = MagicMock()
                call = self._callback(callback_data, chat_id=-100, chat_type="group")

                self.module.handle_callback(bot, call)

                bot.answer_callback_query.assert_called_once_with(
                    "callback",
                    self.module._PRIVATE_CHAT_MESSAGE,
                    show_alert=True,
                )
                bot.edit_message_text.assert_not_called()
                bot.register_next_step_handler_by_chat_id.assert_not_called()
                self.database_factory.assert_not_called()

    def test_shorten_registers_chat_scoped_handler_after_private_check(self):
        bot = MagicMock()
        call = self._callback("url_shorten")
        self.module.handle_entry(bot, call)
        bot.reset_mock()

        self.module.handle_callback(bot, call)

        bot.register_next_step_handler_by_chat_id.assert_called_once_with(
            10,
            self.module._process_url_input,
            bot,
        )
        self.assertEqual(7, self.module.get_interaction_state(10, 10, "message_id"))

    def test_successful_result_escapes_html_without_corrupting_button_url(self):
        bot = MagicMock()
        self.module.set_interaction_state(10, 10, "message_id", 7)
        message = self._message("https://example.com/?a=<unsafe>&b=2")
        shortened_url = "https://tinyurl.com/a?x=1&y=2"

        with (
            patch(
                "modules.url_shortener.handlers.url_client.shorten_url",
                new=AsyncMock(return_value=(True, shortened_url)),
            ),
            patch.object(self.module, "_log_url_operation") as log_operation,
        ):
            self.module._process_url_input(message, bot)

        rendered = bot.edit_message_text.call_args.kwargs["text"]
        self.assertIn("&lt;unsafe&gt;&amp;b=2", rendered)
        self.assertIn("x=1&amp;y=2", rendered)
        self.assertNotIn("<unsafe>", rendered)
        log_operation.assert_called_once_with(10, message.text, shortened_url)
        keyboard = bot.edit_message_text.call_args.kwargs["reply_markup"]
        self.assertEqual(shortened_url, keyboard.keyboard[0][0].url)

    def test_non_text_input_is_handled_as_validation_failure(self):
        bot = MagicMock()
        self.module.set_interaction_state(10, 10, "message_id", 7)

        with patch(
            "modules.url_shortener.handlers.url_client.shorten_url",
            new=AsyncMock(return_value=(False, "❌ Ссылка не может быть пустой")),
        ) as shorten_url:
            self.module._process_url_input(self._message(None), bot)

        shorten_url.assert_awaited_once_with("")
        rendered = bot.edit_message_text.call_args.kwargs["text"]
        self.assertIn("Ссылка не может быть пустой", rendered)

    def test_history_escapes_values_loaded_from_storage(self):
        bot = MagicMock()
        call = self._callback("url_my_links")
        unsafe_links = [
            {
                "original_url": "https://example.com/<script>",
                "shortened_url": "https://t.example/a?x=1&y=2",
                "created_at": "2026-10-11<script>",
                "clicks_count": 0,
            }
        ]

        with patch.object(self.module, "_get_user_links", return_value=unsafe_links):
            self.module.handle_callback(bot, call)

        rendered = bot.edit_message_text.call_args.kwargs["text"]
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn("x=1&amp;y=2", rendered)
        self.assertNotIn("<script>", rendered)

    def test_unexpected_failure_does_not_expose_diagnostic_detail(self):
        bot = MagicMock()
        self.module.set_interaction_state(10, 10, "message_id", 7)

        with patch(
            "modules.url_shortener.handlers.url_client.shorten_url",
            new=AsyncMock(side_effect=RuntimeError("private-token-value")),
        ):
            self.module._process_url_input(self._message("https://example.com"), bot)

        rendered = bot.edit_message_text.call_args.kwargs["text"]
        self.assertNotIn("private-token-value", rendered)
        self.assertIn("непредвиденная ошибка", rendered)

    @staticmethod
    def _callback(
        data: str,
        *,
        actor_id: int = 10,
        chat_id: int = 10,
        chat_type: str = "private",
    ) -> SimpleNamespace:
        return SimpleNamespace(
            id="callback",
            data=data,
            from_user=SimpleNamespace(id=actor_id),
            message=SimpleNamespace(
                chat=SimpleNamespace(id=chat_id, type=chat_type),
                message_id=7,
            ),
        )

    @staticmethod
    def _message(text: str | None) -> SimpleNamespace:
        return SimpleNamespace(
            from_user=SimpleNamespace(id=10),
            chat=SimpleNamespace(id=10, type="private"),
            message_id=8,
            text=text,
        )


if __name__ == "__main__":
    unittest.main()
