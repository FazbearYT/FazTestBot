import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from telebot import types

from core.module_base import BaseModule
from core.module_manager import ModuleManager


class FailingModule(BaseModule):
    def __init__(self):
        super().__init__("broken", "Broken", "Broken module", "💥", callback_prefix="bad_")

    def handle_entry(self, bot, call):
        pass

    def handle_callback(self, bot, call):
        pass

    def get_menu_keyboard(self):
        return types.InlineKeyboardMarkup()

    def on_load(self, bot):
        raise RuntimeError("storage is unavailable")


class SnapshotFailingModule(FailingModule):
    def __init__(self):
        super().__init__()
        self.id = "snapshot_broken"
        self.name = "Snapshot Broken"

    def get_admin_snapshot(self):
        raise RuntimeError("must not break dashboard")


class ModuleManagerTests(unittest.TestCase):
    def test_on_load_failure_rolls_back_registration(self):
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

    def test_discovery_ignores_non_package_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            modules_dir = Path(temp_dir) / "modules"
            (modules_dir / "stale" / "__pycache__").mkdir(parents=True)
            manager = ModuleManager(str(modules_dir))

            with redirect_stdout(StringIO()):
                loaded = manager.discover_and_load()

        self.assertEqual(0, loaded)
        self.assertEqual([], manager.get_errors())

    def test_admin_snapshot_failures_are_isolated_and_sanitized(self):
        manager = ModuleManager()
        manager.modules = {"snapshot_broken": SnapshotFailingModule()}
        manager._load_errors = [
            {"module": "unavailable", "error": "secret details", "timestamp": "now"}
        ]

        snapshots = manager.get_admin_snapshots()

        self.assertEqual(["snapshot_broken", "unavailable"], [item.module_id for item in snapshots])
        self.assertTrue(all(item.status == "error" for item in snapshots))
        self.assertNotIn("secret details", repr(snapshots))


if __name__ == "__main__":
    unittest.main()
