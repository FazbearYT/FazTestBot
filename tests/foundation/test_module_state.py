import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.module_base import BaseModule
from core.state import InteractionScope, TransientStateStore
from modules.cipher.handlers import CipherModule
from modules.decision_maker.handlers import DecisionMakerModule
from modules.ip_lookup.handlers import IPLookupModule
from modules.media_downloader.handlers import MediaDownloaderModule
from modules.steam_deals.handlers import SteamDealsModule
from modules.url_shortener.handlers import URLShortenerModule


class DummyModule(BaseModule):
    def handle_entry(self, bot, call):
        return None

    def handle_callback(self, bot, call):
        return None

    def get_menu_keyboard(self):
        return None


class ModuleStateTests(unittest.TestCase):
    def setUp(self):
        self.store = TransientStateStore()
        self.module = DummyModule("dummy", "Dummy", "Description", "🧪", state_store=self.store)

    def test_legacy_private_chat_api_remains_compatible(self):
        self.module.set_user_state(10, "mode", "waiting")

        self.assertEqual("waiting", self.module.get_user_state(10, "mode"))
        self.assertEqual({"mode": "waiting"}, self.module.get_user_state(10))
        self.module.cleanup_user_state(10)
        self.assertIsNone(self.module.get_user_state(10, "mode"))

    def test_actor_aware_api_does_not_mix_group_members(self):
        self.module.set_interaction_state(10, -100, "selection", "first")
        self.module.set_interaction_state(20, -100, "selection", "second")

        self.assertEqual("first", self.module.get_interaction_state(10, -100, "selection"))
        self.assertEqual("second", self.module.get_interaction_state(20, -100, "selection"))
        self.assertEqual(2, self.module.get_admin_snapshot().active_state_count)

        self.module.cleanup_interaction_state(10, -100)
        self.assertIsNone(self.store.get(InteractionScope(10, -100), "selection"))

    def test_network_modules_bind_entry_state_to_actor_and_chat(self):
        bot = SimpleNamespace(edit_message_text=lambda **_kwargs: None)
        module_types = (IPLookupModule, MediaDownloaderModule, URLShortenerModule)

        for module_type in module_types:
            with self.subTest(module=module_type.__name__):
                module = module_type("network", "Network", "Description", "🌐", "1.0.0", "net_")
                first = self._callback(actor_id=10, chat_id=-100, message_id=1)
                second = self._callback(actor_id=20, chat_id=-100, message_id=2)

                module.handle_entry(bot, first)
                module.handle_entry(bot, second)

                self.assertEqual(1, module.get_interaction_state(10, -100, "message_id"))
                self.assertEqual(2, module.get_interaction_state(20, -100, "message_id"))
                self.assertEqual(2, module.get_admin_snapshot().active_state_count)

    def test_steam_entry_state_is_isolated_by_actor_in_shared_chat(self):
        bot = SimpleNamespace(edit_message_text=lambda **_kwargs: None)
        module = SteamDealsModule("steam", "Steam", "Description", "🎮", "1.0.0", "steam_")

        module.handle_entry(bot, self._callback(actor_id=10, chat_id=-100, message_id=1))
        module.handle_entry(bot, self._callback(actor_id=20, chat_id=-100, message_id=2))

        self.assertEqual(1, module.get_interaction_state(10, -100, "message_id"))
        self.assertEqual(2, module.get_interaction_state(20, -100, "message_id"))

    def test_steam_personal_wishlist_is_rejected_in_shared_chat(self):
        bot = MagicMock()
        module = SteamDealsModule("steam", "Steam", "Description", "🎮", "1.0.0", "steam_")
        call = self._callback(actor_id=10, chat_id=-100, message_id=1)
        call.id = "callback"
        call.data = "steam_wishlist"
        call.message.chat.type = "group"

        with patch.object(module, "_show_wishlist") as show_wishlist:
            module.handle_callback(bot, call)

        show_wishlist.assert_not_called()
        bot.answer_callback_query.assert_any_call(
            "callback",
            "Личный вишлист доступен только в приватном чате с ботом.",
            show_alert=True,
        )

    def test_steam_wishlist_uses_actor_identity_in_private_chat(self):
        bot = MagicMock()
        module = SteamDealsModule("steam", "Steam", "Description", "🎮", "1.0.0", "steam_")
        call = self._callback(actor_id=10, chat_id=10, message_id=7)
        call.id = "callback"
        call.data = "steam_wishlist"
        call.message.chat.type = "private"

        with patch.object(module, "_show_wishlist") as show_wishlist:
            module.handle_callback(bot, call)

        show_wishlist.assert_called_once_with(bot, 10, 10, 7)

    def test_chat_scoped_legacy_workflows_reject_shared_chats(self):
        module_types = (CipherModule, DecisionMakerModule)

        for module_type in module_types:
            with self.subTest(module=module_type.__name__):
                bot = MagicMock()
                module = module_type("legacy", "Legacy", "Description", "🧪", "1.0.0", "legacy_")
                call = self._callback(
                    actor_id=10,
                    chat_id=-100,
                    message_id=1,
                    chat_type="group",
                )
                call.id = "callback"
                call.data = "legacy_action"

                module.handle_entry(bot, call)
                module.handle_callback(bot, call)

                self.assertEqual(0, module.get_admin_snapshot().active_state_count)
                bot.edit_message_text.assert_not_called()
                self.assertEqual(2, bot.answer_callback_query.call_count)
                for invoked in bot.answer_callback_query.call_args_list:
                    self.assertTrue(invoked.kwargs["show_alert"])

    def test_cipher_escapes_user_text_before_html_rendering(self):
        bot = MagicMock()
        module = CipherModule("cipher", "Cipher", "Description", "🔐", "1.0.0", "cipher_")
        module.set_user_state(10, "message_id", 7)
        module.set_user_state(10, "session_id", "session")
        module.set_user_state(10, "cipher", "morze")
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=10),
            chat=SimpleNamespace(id=10, type="private"),
            message_id=8,
            text="<b>unsafe</b>",
        )

        with patch("modules.cipher.handlers.db.log_cipher_operation"):
            module._process_text_input(message, bot)

        rendered = bot.edit_message_text.call_args.kwargs["text"]
        self.assertIn("&lt;b&gt;unsafe&lt;/b&gt;", rendered)
        self.assertNotIn("<code><b>unsafe</b></code>", rendered)

    def test_decision_list_escapes_user_values_before_html_rendering(self):
        bot = MagicMock()
        module = DecisionMakerModule("decision", "Decision", "Description", "🎲", "1.0.0", "dm_")
        module.set_user_state(10, "message_id", 7)
        module.set_user_state(10, "list_state", "waiting_input")
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=10),
            chat=SimpleNamespace(id=10, type="private"),
            message_id=8,
            text="<b>unsafe</b>, safe",
        )

        with (
            patch.object(module, "_log_action"),
            patch("modules.decision_maker.handlers.random.choice", return_value="<b>unsafe</b>"),
        ):
            module._process_list_input(message, bot)

        rendered = bot.edit_message_text.call_args.kwargs["text"]
        self.assertIn("&lt;b&gt;unsafe&lt;/b&gt;", rendered)
        self.assertNotIn("<b><b>unsafe</b></b>", rendered)

    @staticmethod
    def _callback(*, actor_id, chat_id, message_id, chat_type="private"):
        return SimpleNamespace(
            from_user=SimpleNamespace(id=actor_id),
            message=SimpleNamespace(
                chat=SimpleNamespace(id=chat_id, type=chat_type),
                message_id=message_id,
            ),
        )


if __name__ == "__main__":
    unittest.main()
