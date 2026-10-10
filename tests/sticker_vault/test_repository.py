import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from modules.sticker_vault.models import StickerPackRecord
from modules.sticker_vault.repository import StickerVaultRepository


class StickerVaultRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.repository = StickerVaultRepository(Path(self.temp_dir.name) / "vault.db")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_upsert_and_list_packs(self):
        self.repository.upsert_pack(StickerPackRecord(42, 2, "pack-2", 4))
        self.repository.upsert_pack(StickerPackRecord(42, 1, "pack-1", 120))
        self.repository.upsert_pack(StickerPackRecord(42, 2, "pack-2", 5))

        records = self.repository.list_packs(42)

        self.assertEqual([1, 2], [record.part_number for record in records])
        self.assertEqual([120, 5], [record.last_known_count for record in records])

    def test_remove_pack_only_affects_selected_user_part(self):
        self.repository.upsert_pack(StickerPackRecord(42, 1, "pack-a", 1))
        self.repository.upsert_pack(StickerPackRecord(43, 1, "pack-b", 2))

        self.repository.remove_pack(42, 1)

        self.assertEqual([], self.repository.list_packs(42))
        self.assertEqual("pack-b", self.repository.list_packs(43)[0].pack_name)


if __name__ == "__main__":
    unittest.main()
