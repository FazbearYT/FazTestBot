import unittest
from copy import deepcopy
from datetime import datetime

from core.easter_eggs import EasterEggManager


class FakeEasterEggStorage:
    def __init__(self, state=None):
        self.state = deepcopy(state)
        self.updates = []

    def get_user_easter_egg_state(self, user_id):
        return deepcopy(self.state)

    def update_user_easter_egg_state(self, user_id, state):
        self.state = deepcopy(state)
        self.updates.append((user_id, deepcopy(state)))


class EasterEggManagerTests(unittest.TestCase):
    def test_non_text_message_is_treated_as_wrong_input_without_crashing(self):
        storage = FakeEasterEggStorage({"current_step": 1, "last_completed": None})
        manager = EasterEggManager(storage)

        result = manager.process_easter_egg_message(7, None)

        self.assertFalse(result["activated"])
        self.assertFalse(result["step_success"])
        self.assertEqual(result["step"], 0)
        self.assertEqual(storage.state["current_step"], 0)

    def test_wrong_step_resets_only_current_progress(self):
        storage = FakeEasterEggStorage({"current_step": 2, "last_completed": None})
        manager = EasterEggManager(storage)

        result = manager.process_easter_egg_message(7, "unexpected")

        self.assertEqual(result["step"], 0)
        self.assertIsNone(storage.state["last_completed"])

    def test_complete_sequence_activates_and_records_cooldown(self):
        storage = FakeEasterEggStorage()
        manager = EasterEggManager(storage)

        first = manager.process_easter_egg_message(7, " Bot ")
        second = manager.process_easter_egg_message(7, "history")
        final = manager.process_easter_egg_message(7, "open")

        self.assertTrue(first["step_success"])
        self.assertTrue(second["step_success"])
        self.assertTrue(final["activated"])
        self.assertEqual(final["step"], 3)
        self.assertIsNotNone(storage.state["last_completed"])
        datetime.fromisoformat(storage.state["last_completed"])

    def test_active_cooldown_does_not_restart_or_write_progress(self):
        completed = datetime.now().isoformat()
        storage = FakeEasterEggStorage({"current_step": 3, "last_completed": completed})
        manager = EasterEggManager(storage)

        result = manager.process_easter_egg_message(7, "Bot")

        self.assertTrue(result["cooldown"])
        self.assertEqual(result["step"], 3)
        self.assertEqual(storage.updates, [])


if __name__ == "__main__":
    unittest.main()
