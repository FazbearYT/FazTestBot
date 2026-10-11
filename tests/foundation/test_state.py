import threading
import unittest

from core.state import InteractionScope, TransientStateStore


class ManualClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class TransientStateStoreTests(unittest.TestCase):
    def setUp(self):
        self.clock = ManualClock()
        self.store = TransientStateStore(
            ttl_seconds=10,
            max_entries=2,
            clock=self.clock,
        )

    def test_state_is_isolated_by_actor_and_chat(self):
        first = InteractionScope(actor_id=1, chat_id=100)
        second_actor = InteractionScope(actor_id=2, chat_id=100)
        second_chat = InteractionScope(actor_id=1, chat_id=200)

        self.store.set(first, "mode", "first")
        self.store.set(second_actor, "mode", "second")

        self.assertEqual("first", self.store.get(first, "mode"))
        self.assertEqual("second", self.store.get(second_actor, "mode"))
        self.assertIsNone(self.store.get(second_chat, "mode"))

    def test_expiration_is_sliding_and_pruned_from_count(self):
        scope = InteractionScope(1, 1)
        self.store.set(scope, "mode", "waiting")
        self.clock.now = 9
        self.assertEqual("waiting", self.store.get(scope, "mode"))
        self.clock.now = 18
        self.assertEqual(1, self.store.count())
        self.clock.now = 19

        self.assertIsNone(self.store.get(scope, "mode"))
        self.assertEqual(0, self.store.count())

    def test_oldest_state_is_evicted_at_capacity(self):
        first = InteractionScope(1, 1)
        second = InteractionScope(2, 2)
        third = InteractionScope(3, 3)
        self.store.set(first, "value", 1)
        self.clock.now = 1
        self.store.set(second, "value", 2)
        self.clock.now = 2
        self.store.set(third, "value", 3)

        self.assertIsNone(self.store.get(first, "value"))
        self.assertEqual(2, self.store.get(second, "value"))
        self.assertEqual(3, self.store.get(third, "value"))

    def test_get_all_is_a_copy_and_clear_is_idempotent(self):
        scope = InteractionScope(1, 1)
        self.store.set(scope, "items", [1])

        snapshot = self.store.get_all(scope)
        snapshot["new"] = "outside"

        self.assertIsNone(self.store.get(scope, "new"))
        self.assertTrue(self.store.clear(scope))
        self.assertFalse(self.store.clear(scope))

    def test_concurrent_writes_keep_all_fields(self):
        scope = InteractionScope(1, 1)
        barrier = threading.Barrier(8)

        def write(index):
            barrier.wait()
            self.store.set(scope, f"key-{index}", index)

        threads = [threading.Thread(target=write, args=(index,)) for index in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(8, len(self.store.get_all(scope)))

    def test_invalid_limits_are_rejected(self):
        with self.assertRaises(ValueError):
            TransientStateStore(ttl_seconds=0)
        with self.assertRaises(ValueError):
            TransientStateStore(max_entries=0)


if __name__ == "__main__":
    unittest.main()
