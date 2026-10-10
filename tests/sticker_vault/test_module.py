import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from modules.sticker_vault.config import PENDING_ACTION_CACHE_SIZE
from modules.sticker_vault.module import StickerVaultModule
from modules.sticker_vault.pending import PendingStickerStore
from modules.sticker_vault.repository import StickerVaultRepository
from modules.sticker_vault.service import StickerVaultError


class FakeUserDatabase:
    def __init__(self):
        self.calls = []

    def create_or_update_user(self, **kwargs):
        self.calls.append(kwargs)


class FakeBot:
    def __init__(self):
        self.replies = []
        self.edits = []
        self.documents = []
        self.registered = []

    def register_message_handler(self, callback, **kwargs):
        self.registered.append((callback, kwargs))

    def reply_to(self, message, text, **kwargs):
        self.replies.append((message, text, kwargs))

    def edit_message_text(self, **kwargs):
        self.edits.append(kwargs)

    def get_file(self, file_id):
        return SimpleNamespace(file_path=f"stickers/{file_id}.unknown")

    def download_file(self, file_path):
        return b"sticker-bytes"

    def send_document(self, **kwargs):
        self.documents.append(kwargs)

    def get_me(self):
        return SimpleNamespace(username="Faz_Test_Bot")


class FailingService:
    def add(self, sticker, display_name):
        raise StickerVaultError("Повторите через 17 сек.")


def message(sticker, chat_type="private"):
    user = SimpleNamespace(
        id=321,
        username="fazbear",
        first_name="Faz",
        last_name="Bear",
    )
    return SimpleNamespace(
        from_user=user,
        chat=SimpleNamespace(id=321, type=chat_type),
        sticker=sticker,
        message_id=10,
    )


def sticker(**overrides):
    values = {
        "file_id": "file-1",
        "file_unique_id": "unique-1",
        "type": "regular",
        "emoji": "🧸",
        "is_animated": False,
        "is_video": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class StickerVaultModuleTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.repository = StickerVaultRepository(Path(self.temp_dir.name) / "vault.db")
        self.user_db = FakeUserDatabase()
        self.store = PendingStickerStore(900, PENDING_ACTION_CACHE_SIZE)
        self.module = StickerVaultModule(self.repository, self.user_db, self.store)
        self.bot = FakeBot()
        self.module.on_load(self.bot)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_on_load_registers_sticker_only_handler_with_bot_argument(self):
        self.assertEqual(1, len(self.bot.registered))
        _, kwargs = self.bot.registered[0]
        self.assertEqual(["sticker"], kwargs["content_types"])
        self.assertTrue(kwargs["pass_bot"])

    def test_sticker_formats_get_short_owner_bound_callbacks(self):
        for source, expected in (
            (sticker(), "static"),
            (sticker(file_id="a", file_unique_id="ua", is_animated=True), "animated"),
            (sticker(file_id="v", file_unique_id="uv", is_video=True), "video"),
        ):
            self.module._handle_sticker_message(message(source), self.bot)
            keyboard = self.bot.replies[-1][2]["reply_markup"]
            callbacks = [
                button.callback_data for row in keyboard.keyboard for button in row
            ]
            self.assertTrue(
                all(len(value.encode("utf-8")) <= 64 for value in callbacks)
            )
            token = callbacks[0].removeprefix("sv_add_")
            lookup = self.store.take(token, 321)
            self.assertEqual(expected, lookup.sticker.sticker_format)

    def test_group_and_non_regular_stickers_are_rejected(self):
        self.module._handle_sticker_message(message(sticker(), "group"), self.bot)
        self.module._handle_sticker_message(
            message(sticker(type="custom_emoji")), self.bot
        )

        self.assertIn("личном чате", self.bot.replies[0][1])
        self.assertIn("обычные стикеры", self.bot.replies[1][1])
        self.assertEqual(2, len(self.user_db.calls))

    def test_video_export_uses_flag_based_extension_and_memory_buffer(self):
        self.module._handle_sticker_message(message(sticker(is_video=True)), self.bot)
        keyboard = self.bot.replies[-1][2]["reply_markup"]
        file_callback = keyboard.keyboard[0][1].callback_data
        call = SimpleNamespace(
            data=file_callback,
            from_user=message(sticker()).from_user,
            message=SimpleNamespace(chat=SimpleNamespace(id=321), message_id=99),
        )

        self.module.handle_callback(self.bot, call)

        sent = self.bot.documents[0]
        self.assertEqual("sticker_unique-1.webm", sent["visible_file_name"])
        self.assertEqual(b"sticker-bytes", sent["document"].getvalue())
        self.assertIn("sticker_unique-1.webm", self.bot.edits[-1]["text"])

    def test_action_is_single_use_and_bound_to_owner(self):
        self.module._handle_sticker_message(message(sticker()), self.bot)
        callback = self.bot.replies[-1][2]["reply_markup"].keyboard[-1][0].callback_data
        foreign_call = SimpleNamespace(
            data=callback,
            from_user=SimpleNamespace(id=999, first_name="X", last_name=None),
            message=SimpleNamespace(chat=SimpleNamespace(id=321), message_id=99),
        )
        self.module.handle_callback(self.bot, foreign_call)
        self.assertIn("другому пользователю", self.bot.edits[-1]["text"])

        own_call = SimpleNamespace(
            data=callback,
            from_user=message(sticker()).from_user,
            message=SimpleNamespace(chat=SimpleNamespace(id=321), message_id=99),
        )
        self.module.handle_callback(self.bot, own_call)
        self.module.handle_callback(self.bot, own_call)
        self.assertIn("устарело", self.bot.edits[-1]["text"])

    def test_retryable_add_failure_gets_a_fresh_action_token(self):
        self.module._handle_sticker_message(message(sticker()), self.bot)
        old_callback = (
            self.bot.replies[-1][2]["reply_markup"].keyboard[0][0].callback_data
        )
        self.module.service = FailingService()
        call = SimpleNamespace(
            data=old_callback,
            from_user=message(sticker()).from_user,
            message=SimpleNamespace(chat=SimpleNamespace(id=321), message_id=99),
        )

        self.module.handle_callback(self.bot, call)

        edit = self.bot.edits[-1]
        self.assertIn("17", edit["text"])
        new_callback = edit["reply_markup"].keyboard[0][0].callback_data
        self.assertNotEqual(old_callback, new_callback)

    def test_group_entry_does_not_read_or_expose_personal_packs(self):
        class RepositoryThatMustNotBeRead:
            def list_packs(self, user_id):
                raise AssertionError("personal repository was read from a group")

        self.module.repository = RepositoryThatMustNotBeRead()
        call = SimpleNamespace(
            data="module_sticker_vault",
            from_user=message(sticker()).from_user,
            message=SimpleNamespace(
                chat=SimpleNamespace(id=-100123, type="supergroup"), message_id=99
            ),
        )

        self.module.handle_entry(self.bot, call)

        self.assertIn("только в личном чате", self.bot.edits[-1]["text"])
        buttons = [
            button
            for row in self.bot.edits[-1]["reply_markup"].keyboard
            for button in row
        ]
        self.assertTrue(all(button.url is None for button in buttons))


if __name__ == "__main__":
    unittest.main()
