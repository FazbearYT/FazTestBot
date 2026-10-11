import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.settings import ConfigurationError, load_settings


class SettingsTests(unittest.TestCase):
    def load(self, values=None):
        with tempfile.TemporaryDirectory() as directory:
            missing_file = Path(directory) / ".env"
            return load_settings(values or {}, env_file=missing_file)

    def test_safe_defaults_are_importable_without_secrets(self):
        settings = self.load()

        self.assertEqual(settings.bot_token, "")
        self.assertEqual(settings.admins, ())
        self.assertFalse(settings.media_downloader_enabled)
        self.assertEqual(settings.log_level, "INFO")

    def test_environment_values_are_typed(self):
        settings = self.load(
            {
                "BOT_TOKEN": "test-token",
                "ADMINS": "10, 20",
                "MEDIA_DOWNLOADER_ENABLED": "yes",
                "MAX_DOWNLOAD_SIZE_MB": "75",
                "BACKUP_ENABLED": "off",
                "BLOCKED_USERS": "30",
                "LOG_LEVEL": "debug",
            }
        )

        self.assertEqual(settings.admins, (10, 20))
        self.assertTrue(settings.media_downloader_enabled)
        self.assertEqual(settings.max_download_size_mb, 75)
        self.assertFalse(settings.backup_enabled)
        self.assertEqual(settings.blocked_users, (30,))
        self.assertEqual(settings.log_level, "DEBUG")

    def test_process_environment_overrides_dotenv(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text("BOT_TOKEN=file-token\nLOG_LEVEL=WARNING\n", encoding="utf-8")

            settings = load_settings(
                {"BOT_TOKEN": "process-token", "LOG_LEVEL": "ERROR"},
                env_file=env_file,
            )

        self.assertEqual(settings.bot_token, "process-token")
        self.assertEqual(settings.log_level, "ERROR")

    def test_invalid_values_fail_with_setting_name(self):
        invalid_cases = [
            ({"MEDIA_DOWNLOADER_ENABLED": "sometimes"}, "MEDIA_DOWNLOADER_ENABLED"),
            ({"MAX_DOWNLOAD_SIZE_MB": "0"}, "MAX_DOWNLOAD_SIZE_MB"),
            ({"ADMINS": "1,1"}, "ADMINS"),
            ({"BACKUP_TIME": "3am"}, "BACKUP_TIME"),
            ({"IP_INFO_API_SERVICE": "unknown"}, "IP_INFO_API_SERVICE"),
        ]

        for values, expected in invalid_cases:
            with self.subTest(values=values):
                with self.assertRaisesRegex(ConfigurationError, expected):
                    self.load(values)

    def test_startup_validation_requires_token(self):
        settings = self.load()

        with self.assertRaisesRegex(ConfigurationError, "BOT_TOKEN"):
            settings.require_startup_ready()

    def test_selected_services_require_their_api_keys(self):
        cuttly = self.load({"BOT_TOKEN": "token", "URL_SHORTENER_SERVICE": "cuttly"})
        ipinfo = self.load({"BOT_TOKEN": "token", "IP_INFO_API_SERVICE": "ipinfo"})

        self.assertIn("CUTTLY_API_KEY", " ".join(cuttly.startup_errors()))
        self.assertIn("IPINFO_API_KEY", " ".join(ipinfo.startup_errors()))

    def test_disabled_media_backend_cannot_be_enabled_accidentally(self):
        settings = self.load({"MEDIA_DOWNLOADER_ENABLED": "true"})

        self.assertIn("MEDIA_DOWNLOADER_ENABLED=true", " ".join(settings.startup_errors()))

    def test_loading_does_not_mutate_process_environment(self):
        before = dict(os.environ)
        with patch.dict(os.environ, {}, clear=True):
            self.load({"BOT_TOKEN": "not-exported"})
            self.assertNotIn("BOT_TOKEN", os.environ)
        self.assertEqual(dict(os.environ), before)

    def test_secret_values_are_redacted_from_repr(self):
        settings = self.load(
            {
                "BOT_TOKEN": "telegram-secret",
                "ADMIN_SECRET_CODE": "admin-secret",
                "CUTTLY_API_KEY": "cuttly-secret",
                "IPINFO_API_KEY": "ipinfo-secret",
                "GROQ_API_KEY": "groq-secret",
                "CHEAPSHARK_API_KEY": "cheapshark-secret",
                "ADMINS": "1",
            }
        )

        rendered = repr(settings)
        for secret in (
            "telegram-secret",
            "admin-secret",
            "cuttly-secret",
            "ipinfo-secret",
            "groq-secret",
            "cheapshark-secret",
        ):
            self.assertNotIn(secret, rendered)
