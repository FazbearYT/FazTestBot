import unittest

from core.module_base import BaseModule
from core.state import InteractionScope, TransientStateStore


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


if __name__ == "__main__":
    unittest.main()
