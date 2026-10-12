import tempfile
import unittest
from pathlib import Path

from core.paths import resolve_data_dir


class RuntimePathTests(unittest.TestCase):
    def test_default_data_directory_is_root_temp(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            resolved = resolve_data_dir({}, root_dir=root, env_file=root / "missing.env")

            self.assertEqual((root / "temp").resolve(), resolved)

    def test_relative_dotenv_path_is_resolved_from_source_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env_file = root / ".env"
            env_file.write_text("FAZTESTBOT_DATA_DIR=runtime/state\n", encoding="utf-8")

            resolved = resolve_data_dir({}, root_dir=root, env_file=env_file)

            self.assertEqual((root / "runtime" / "state").resolve(), resolved)

    def test_process_environment_overrides_dotenv_with_absolute_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            external = root / "external"
            env_file = root / ".env"
            env_file.write_text("FAZTESTBOT_DATA_DIR=from-file\n", encoding="utf-8")

            resolved = resolve_data_dir(
                {"FAZTESTBOT_DATA_DIR": str(external)},
                root_dir=root,
                env_file=env_file,
            )

            self.assertEqual(external.resolve(), resolved)

    def test_blank_process_value_restores_default_instead_of_dotenv_value(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env_file = root / ".env"
            env_file.write_text("FAZTESTBOT_DATA_DIR=from-file\n", encoding="utf-8")

            resolved = resolve_data_dir(
                {"FAZTESTBOT_DATA_DIR": "  "},
                root_dir=root,
                env_file=env_file,
            )

            self.assertEqual((root / "temp").resolve(), resolved)


if __name__ == "__main__":
    unittest.main()
