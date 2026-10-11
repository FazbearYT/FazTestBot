import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from core.database import DatabaseManager
from modules.decision_maker import decision_maker_module
from modules.ip_lookup import ip_lookup_module
from modules.steam_deals import steam_deals_module
from modules.url_shortener import url_shortener_module


class ModuleStorageIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = DatabaseManager(Path(self.temp_dir.name) / "modules.db", retention_days=0)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_url_shortener_history_uses_migrated_schema(self):
        original_database = url_shortener_module._database_manager
        url_shortener_module._database_manager = self.database
        try:
            url_shortener_module._log_url_operation(1, "https://example.com", "https://t.ly/a")
            links = url_shortener_module._get_user_links(1)
        finally:
            url_shortener_module._database_manager = original_database

        self.assertEqual("https://example.com", links[0]["original_url"])
        self.assertEqual("https://t.ly/a", links[0]["shortened_url"])

    def test_ip_lookup_history_uses_migrated_schema(self):
        original_database = ip_lookup_module._database_manager
        ip_lookup_module._database_manager = self.database
        try:
            self.assertTrue(ip_lookup_module._check_lookup_limit(2))
            ip_lookup_module._log_lookup(
                2,
                "8.8.8.8",
                {"ip": "8.8.8.8", "city": "Test", "country": "XX", "isp": "DNS"},
            )
            lookups = ip_lookup_module._get_user_lookups(2)
        finally:
            ip_lookup_module._database_manager = original_database

        self.assertEqual("8.8.8.8", lookups[0]["query"])
        self.assertEqual("DNS", lookups[0]["isp"])

    def test_steam_wishlist_upsert_and_transactional_remove(self):
        with patch("modules.steam_deals.handlers.db", self.database):
            created = steam_deals_module._add_game_to_wishlist(
                3,
                "10",
                "Original",
                steam_app_id="100",
                current_price=100.0,
                historical_low=90.0,
                discount_percent=10.0,
            )
            updated = steam_deals_module._add_game_to_wishlist(
                3,
                "10",
                "Updated",
                steam_app_id="100",
                current_price=80.0,
                historical_low=70.0,
                discount_percent=20.0,
            )
            wishlist = steam_deals_module._get_user_wishlist(3)
            removed = steam_deals_module._remove_game_from_wishlist(3, 1)
            empty = steam_deals_module._get_user_wishlist(3)

        self.assertTrue(created)
        self.assertTrue(updated)
        self.assertEqual(1, len(wishlist))
        self.assertEqual("Updated", wishlist[0]["game_name"])
        self.assertEqual("100", wishlist[0]["steam_app_id"])
        self.assertEqual(80.0, wishlist[0]["current_price"])
        self.assertTrue(removed)
        self.assertEqual([], empty)

    def test_decision_maker_coin_updates_are_atomic(self):
        def flip(result):
            decision_maker_module._update_coin_stats(4, result)

        results = ["Орёл", "Решка"] * 40
        with patch("modules.decision_maker.handlers.db", self.database):
            with ThreadPoolExecutor(max_workers=8) as executor:
                list(executor.map(flip, results))
            stats = decision_maker_module._get_coin_stats(4)
            decision_maker_module._log_action(4, "coin", "Орёл", "test")

        self.assertEqual(40, stats["heads"])
        self.assertEqual(40, stats["tails"])
        self.assertEqual(80, stats["total"])
        with self.database.database.connection() as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM decision_maker_logs WHERE user_id = 4"
            ).fetchone()[0]
        self.assertEqual(1, count)
