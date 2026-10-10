from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from telebot import types

from core.module_base import BaseModule
from core.module_manager import ModuleManager


class FailingModule(BaseModule):
    def __init__(self):
        super().__init__(
            "broken", "Broken", "Broken module", "💥", callback_prefix="bad_"
        )

    def handle_entry(self, bot, call):
        pass

    def handle_callback(self, bot, call):
        pass

    def get_menu_keyboard(self):
        return types.InlineKeyboardMarkup()

    def on_load(self, bot):
        raise RuntimeError("storage is unavailable")


class ModuleManagerTests(TestCase):
    def test_on_load_failure_rolls_back_module_registration(self):
        manager = ModuleManager()
        imported = SimpleNamespace(bad_module=FailingModule())

        with (
            patch("core.module_manager.importlib.import_module", return_value=imported),
            redirect_stdout(StringIO()),
        ):
            loaded = manager._load_module("bad", object())

        self.assertFalse(loaded)
        self.assertEqual({}, manager.modules)
        self.assertEqual({}, manager.callback_map)
        self.assertEqual(1, len(manager.get_errors()))
