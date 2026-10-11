import unittest
from types import SimpleNamespace

from core.module_base import BaseModule
from core.state import InteractionScope, TransientStateStore
from modules.ip_lookup.handlers import IPLookupModule
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
        module_types = (IPLookupModule, URLShortenerModule)

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

    @staticmethod
    def _callback(*, actor_id, chat_id, message_id):
        return SimpleNamespace(
            from_user=SimpleNamespace(id=actor_id),
            message=SimpleNamespace(
                chat=SimpleNamespace(id=chat_id),
                message_id=message_id,
            ),
        )


if __name__ == "__main__":
    unittest.main()
