import unittest

from modules.sticker_vault.models import PendingLookupStatus, PendingSticker
from modules.sticker_vault.pending import PendingStickerStore


def pending(user_id: int, file_id: str = "file") -> PendingSticker:
    return PendingSticker(user_id, user_id, file_id, f"unique-{file_id}", "static", "🙂")


class PendingStickerStoreTests(unittest.TestCase):
    def test_token_is_single_use_and_bound_to_owner(self):
        now = [10.0]
        store = PendingStickerStore(60, 10, clock=lambda: now[0])
        token = store.put(pending(100))

        forbidden = store.take(token, 200)
        self.assertEqual(PendingLookupStatus.FORBIDDEN, forbidden.status)

        found = store.take(token, 100)
        self.assertEqual(PendingLookupStatus.FOUND, found.status)
        self.assertEqual("file", found.sticker.file_id)
        self.assertEqual(PendingLookupStatus.MISSING, store.take(token, 100).status)

    def test_expired_token_is_removed(self):
        now = [10.0]
        store = PendingStickerStore(5, 10, clock=lambda: now[0])
        token = store.put(pending(100))

        now[0] = 15.0

        self.assertEqual(PendingLookupStatus.MISSING, store.take(token, 100).status)

    def test_oldest_token_is_evicted_at_capacity(self):
        store = PendingStickerStore(60, 2, clock=lambda: 10.0)
        first = store.put(pending(1, "one"))
        second = store.put(pending(2, "two"))
        third = store.put(pending(3, "three"))

        self.assertEqual(PendingLookupStatus.MISSING, store.take(first, 1).status)
        self.assertEqual(PendingLookupStatus.FOUND, store.take(second, 2).status)
        self.assertEqual(PendingLookupStatus.FOUND, store.take(third, 3).status)


if __name__ == "__main__":
    unittest.main()
