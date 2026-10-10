import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from telebot.apihelper import ApiTelegramException

from modules.sticker_vault.config import PACK_CAPACITY
from modules.sticker_vault.models import AddStatus, PendingSticker, StickerPackRecord
from modules.sticker_vault.repository import StickerVaultRepository
from modules.sticker_vault.service import StickerVaultService


def api_error(description: str) -> ApiTelegramException:
    return ApiTelegramException(
        "test",
        None,
        {"ok": False, "error_code": 400, "description": description},
    )


def pending(file_id: str, unique_id: str, sticker_format: str) -> PendingSticker:
    return PendingSticker(
        user_id=123,
        chat_id=123,
        file_id=file_id,
        file_unique_id=unique_id,
        sticker_format=sticker_format,
        emoji="🙂",
    )


class FakeBot:
    def __init__(self):
        self.username = "Faz_Test_Bot"
        self.sets = {}
        self.unique_ids = {}
        self.create_calls = []
        self.add_calls = []
        self.fail_next_add_full = False

    def get_me(self):
        return SimpleNamespace(username=self.username)

    def get_sticker_set(self, name):
        if name not in self.sets:
            raise api_error("Bad Request: STICKERSET_INVALID")
        return self.sets[name]

    def create_new_sticker_set(self, **kwargs):
        self.create_calls.append(kwargs)
        name = kwargs["name"]
        input_sticker = kwargs["stickers"][0]
        self.sets[name] = SimpleNamespace(
            name=name,
            stickers=[self._remote_sticker(input_sticker.sticker)],
        )
        return True

    def add_sticker_to_set(self, **kwargs):
        self.add_calls.append(kwargs)
        if self.fail_next_add_full:
            self.fail_next_add_full = False
            raise api_error("Bad Request: STICKERS_TOO_MUCH")
        input_sticker = kwargs["sticker"]
        self.sets[kwargs["name"]].stickers.append(
            self._remote_sticker(input_sticker.sticker)
        )
        return True

    def _remote_sticker(self, file_id):
        return SimpleNamespace(file_id=file_id, file_unique_id=self.unique_ids[file_id])


class StickerVaultServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.repository = StickerVaultRepository(Path(self.temp_dir.name) / "vault.db")
        self.bot = FakeBot()
        self.service = StickerVaultService(self.bot, self.repository)

    def tearDown(self):
        self.temp_dir.cleanup()

    def add_file(self, file_id: str, unique_id: str, sticker_format: str):
        self.bot.unique_ids[file_id] = unique_id
        return self.service.add(pending(file_id, unique_id, sticker_format), "Fazbear")

    def test_creates_one_mixed_format_pack(self):
        first = self.add_file("static-file", "static-unique", "static")
        second = self.add_file("animated-file", "animated-unique", "animated")
        third = self.add_file("video-file", "video-unique", "video")

        self.assertEqual(AddStatus.CREATED, first.status)
        self.assertEqual(AddStatus.ADDED, second.status)
        self.assertEqual(AddStatus.ADDED, third.status)
        self.assertEqual(first.pack_name, second.pack_name)
        self.assertEqual(first.pack_name, third.pack_name)
        self.assertEqual(1, len(self.bot.create_calls))
        self.assertEqual(2, len(self.bot.add_calls))
        formats = [
            self.bot.create_calls[0]["stickers"][0].format,
            self.bot.add_calls[0]["sticker"].format,
            self.bot.add_calls[1]["sticker"].format,
        ]
        self.assertEqual(["static", "animated", "video"], formats)
        self.assertEqual(["🙂"], self.bot.add_calls[0]["emojis"])

    def test_duplicate_is_detected_from_telegram_state(self):
        first = self.add_file("first-file", "same-unique", "static")
        duplicate = self.add_file("new-file-id", "same-unique", "static")

        self.assertEqual(AddStatus.CREATED, first.status)
        self.assertEqual(AddStatus.DUPLICATE, duplicate.status)
        self.assertEqual(0, len(self.bot.add_calls))

    def test_full_pack_rolls_over_to_next_part(self):
        first_name = self.service.build_pack_name(123, 1)
        self.bot.sets[first_name] = SimpleNamespace(
            name=first_name,
            stickers=[
                SimpleNamespace(file_id=f"f-{index}", file_unique_id=f"u-{index}")
                for index in range(PACK_CAPACITY)
            ],
        )
        self.repository.upsert_pack(
            StickerPackRecord(123, 1, first_name, PACK_CAPACITY)
        )

        result = self.add_file("next-file", "next-unique", "video")

        self.assertEqual(AddStatus.CREATED, result.status)
        self.assertEqual(2, result.part_number)
        self.assertNotEqual(first_name, result.pack_name)
        self.assertEqual("video", self.bot.create_calls[0]["stickers"][0].format)

    def test_existing_pack_is_recovered_when_database_is_empty(self):
        pack_name = self.service.build_pack_name(123, 1)
        self.bot.sets[pack_name] = SimpleNamespace(
            name=pack_name,
            stickers=[SimpleNamespace(file_id="old", file_unique_id="old-unique")],
        )

        result = self.add_file("new", "new-unique", "animated")

        self.assertEqual(AddStatus.ADDED, result.status)
        self.assertEqual(pack_name, result.pack_name)
        self.assertEqual(pack_name, self.repository.list_packs(123)[0].pack_name)

    def test_pack_name_fits_telegram_limit(self):
        service = StickerVaultService(
            self.bot,
            self.repository,
            bot_username="A" + "b" * 31,
        )

        name = service.build_pack_name(9_223_372_036_854_775_807, 999)

        self.assertLessEqual(len(name), 64)
        self.assertRegex(name, r"^[A-Za-z][A-Za-z0-9_]+$")
        self.assertTrue(name.endswith("_by_" + ("a" + "b" * 31)))

    def test_empty_emoji_uses_fallback_in_modern_and_legacy_arguments(self):
        self.bot.unique_ids["first"] = "unique-first"
        first = pending("first", "unique-first", "static")
        first = PendingSticker(**{**first.__dict__, "emoji": ""})
        self.service.add(first, "Fazbear")

        self.bot.unique_ids["second"] = "unique-second"
        second = pending("second", "unique-second", "animated")
        second = PendingSticker(**{**second.__dict__, "emoji": ""})
        self.service.add(second, "Fazbear")

        call = self.bot.add_calls[0]
        self.assertEqual(["🙂"], call["emojis"])
        self.assertEqual(["🙂"], call["sticker"].emoji_list)

    def test_add_race_on_full_pack_rolls_over_once(self):
        first_name = self.service.build_pack_name(123, 1)
        self.bot.sets[first_name] = SimpleNamespace(
            name=first_name,
            stickers=[
                SimpleNamespace(file_id=f"f-{index}", file_unique_id=f"u-{index}")
                for index in range(PACK_CAPACITY - 1)
            ],
        )
        self.repository.upsert_pack(
            StickerPackRecord(123, 1, first_name, PACK_CAPACITY - 1)
        )
        self.bot.fail_next_add_full = True

        result = self.add_file("race-file", "race-unique", "video")

        self.assertEqual(AddStatus.CREATED, result.status)
        self.assertEqual(2, result.part_number)
        self.assertEqual(1, len(self.bot.add_calls))
        self.assertEqual(1, len(self.bot.create_calls))

    def test_rejects_unknown_format_before_calling_telegram(self):
        self.bot.unique_ids["bad"] = "bad-unique"

        with self.assertRaisesRegex(Exception, "формат"):
            self.service.add(pending("bad", "bad-unique", "unknown"), "Fazbear")

        self.assertEqual([], self.bot.create_calls)


if __name__ == "__main__":
    unittest.main()
