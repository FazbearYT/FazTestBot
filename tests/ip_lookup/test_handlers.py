import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from modules.ip_lookup.handlers import IPLookupModule


class IPLookupHandlerTests(unittest.TestCase):
    def setUp(self):
        self.database_factory = MagicMock()
        self.module = IPLookupModule(
            "ip_lookup",
            "IP Lookup",
            "Description",
            "🌍",
            "1.0.3",
            "ip_",
            database_factory=self.database_factory,
        )

    def test_entry_does_not_open_database(self):
        bot = MagicMock()

        self.module.handle_entry(bot, self._callback("module_ip_lookup"))

        self.database_factory.assert_not_called()
        bot.edit_message_text.assert_called_once()

    def test_private_actions_are_rejected_in_shared_chat_before_side_effects(self):
        for callback_data in ("ip_search", "ip_history", "ip_search_again"):
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

    def test_search_registers_chat_scoped_handler_after_private_check(self):
        bot = MagicMock()
        call = self._callback("ip_search")
        self.module.handle_entry(bot, call)
        bot.reset_mock()

        self.module.handle_callback(bot, call)

        bot.register_next_step_handler_by_chat_id.assert_called_once_with(
            10,
            self.module._process_ip_input,
            bot,
        )
        self.assertEqual("search", self.module.get_interaction_state(10, 10, "query_type"))

    def test_successful_result_escapes_untrusted_provider_fields(self):
        bot = MagicMock()
        self.module.set_interaction_state(10, 10, "message_id", 7)
        info = {
            "ip": "192.0.2.1",
            "city": "<City>",
            "region": "A&B",
            "country": "Country",
            "country_code": "TC",
            "isp": "<script>",
            "timezone": "UTC",
            "postal": "123",
            "asn": "AS1",
            "latitude": "1<2",
            "longitude": "3&4",
            "source": "provider.example",
        }

        with (
            patch.object(self.module, "_check_lookup_limit", return_value=True),
            patch(
                "modules.ip_lookup.handlers.ip_client.get_ip_info",
                new=AsyncMock(return_value=(True, info)),
            ),
            patch.object(self.module, "_log_lookup") as log_lookup,
        ):
            self.module._process_ip_input(self._message("192.0.2.1"), bot)

        rendered = bot.edit_message_text.call_args.kwargs["text"]
        self.assertIn("&lt;City&gt;", rendered)
        self.assertIn("A&amp;B", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn("1&lt;2, 3&amp;4", rendered)
        self.assertNotIn("<script>", rendered)
        log_lookup.assert_called_once_with(10, "192.0.2.1", info)

    def test_provider_output_is_bounded_for_telegram(self):
        info = {
            key: "<" * 5000
            for key in (
                "ip",
                "city",
                "region",
                "country",
                "country_code",
                "isp",
                "timezone",
                "postal",
                "asn",
                "latitude",
                "longitude",
                "source",
            )
        }

        rendered = self.module._format_ip_info(info)

        self.assertLess(len(rendered), 4096)
        self.assertNotIn("<" * 2, rendered)

    def test_non_text_input_is_handled_as_validation_failure(self):
        bot = MagicMock()
        self.module.set_interaction_state(10, 10, "message_id", 7)

        with (
            patch.object(self.module, "_check_lookup_limit", return_value=True),
            patch(
                "modules.ip_lookup.handlers.ip_client.get_ip_info",
                new=AsyncMock(return_value=(False, {"error": "❌ Запрос не может быть пустым"})),
            ) as get_ip_info,
        ):
            self.module._process_ip_input(self._message(None), bot)

        get_ip_info.assert_awaited_once_with("")
        rendered = bot.edit_message_text.call_args.kwargs["text"]
        self.assertIn("Запрос не может быть пустым", rendered)

    def test_history_escapes_values_loaded_from_storage(self):
        bot = MagicMock()
        unsafe_lookups = [
            {
                "query": "<query>",
                "city": "A&B",
                "country": "<country>",
                "isp": "<script>",
                "created_at": "2026-10-11<script>",
            }
        ]

        with patch.object(self.module, "_get_user_lookups", return_value=unsafe_lookups):
            self.module.handle_callback(bot, self._callback("ip_history"))

        rendered = bot.edit_message_text.call_args.kwargs["text"]
        self.assertIn("&lt;query&gt;", rendered)
        self.assertIn("A&amp;B", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertNotIn("<script>", rendered)

    def test_history_storage_failure_is_not_reported_as_empty_history(self):
        bot = MagicMock()

        with patch.object(
            self.module,
            "_get_user_lookups",
            side_effect=RuntimeError("private-storage-detail"),
        ):
            self.module.handle_callback(bot, self._callback("ip_history"))

        bot.edit_message_text.assert_not_called()
        bot.send_message.assert_called_once()
        rendered = bot.send_message.call_args.args[1]
        self.assertNotIn("private-storage-detail", rendered)
        self.assertIn("непредвиденная ошибка", rendered)

    def test_database_failure_prevents_unmetered_external_request(self):
        bot = MagicMock()
        self.module.set_interaction_state(10, 10, "message_id", 7)

        with (
            patch.object(
                self.module,
                "_check_lookup_limit",
                side_effect=RuntimeError("private-storage-detail"),
            ),
            patch(
                "modules.ip_lookup.handlers.ip_client.get_ip_info",
                new=AsyncMock(),
            ) as get_ip_info,
        ):
            self.module._process_ip_input(self._message("192.0.2.1"), bot)

        get_ip_info.assert_not_awaited()
        rendered = bot.edit_message_text.call_args.kwargs["text"]
        self.assertNotIn("private-storage-detail", rendered)
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
