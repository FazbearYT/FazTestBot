import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.exceptions import APIError
from modules.steam_deals.api_client import SteamDealsClient
from modules.steam_deals.config import (
    CHEAPSHARK_BASE_URL,
    EXCHANGE_RATE_URL,
    FALLBACK_KZT_RUB,
    STEAM_APPDETAILS_URL,
    STEAM_SEARCH_URL,
)


class StubHttpClient:
    def __init__(self, *results):
        self.results = list(results)
        self.calls = []

    async def get_json(self, service, endpoint, *, params=None):
        self.calls.append((service, endpoint, params))
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class SteamDealsClientTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache_path = Path(self.temp_dir.name) / "steam-cache.json"
        self.now = datetime(2026, 10, 11, tzinfo=timezone.utc)

    def tearDown(self):
        self.temp_dir.cleanup()

    def client(self, http=None):
        return SteamDealsClient(
            http=http or StubHttpClient(),
            cache_path=self.cache_path,
            now=lambda: self.now,
        )

    def test_corrupt_cache_falls_back_without_exposing_contents(self):
        secret = "never-log-cache-secret"
        self.cache_path.write_text(f"not-json {secret}", encoding="utf-8")

        with self.assertLogs("faztestbot.modules.steam_deals.api_client") as captured:
            client = self.client()

        self.assertEqual({}, client.cache)
        self.assertEqual(FALLBACK_KZT_RUB, client.kzt_to_rub)
        self.assertNotIn(secret, "\n".join(captured.output))

    def test_cache_save_is_atomic_and_reloadable(self):
        client = self.client()
        client.cache["free_games"] = [{"name": "Game", "app_id": "10"}]
        client.cache_timestamp["free_games"] = self.now.isoformat()
        client._save_cache()

        reloaded = self.client()

        self.assertEqual(client.cache, reloaded.cache)
        self.assertEqual([], list(self.cache_path.parent.glob("*.tmp")))
        self.assertIsInstance(json.loads(self.cache_path.read_text(encoding="utf-8")), dict)

    def test_invalid_and_expired_cache_timestamps_are_rejected(self):
        client = self.client()
        client.cache_timestamp["bad"] = "not-a-date"
        client.cache_timestamp["old"] = (self.now - timedelta(hours=2)).isoformat()
        client.cache_timestamp["future"] = (self.now + timedelta(seconds=1)).isoformat()

        self.assertFalse(client._is_cache_valid("bad"))
        self.assertFalse(client._is_cache_valid("old"))
        self.assertFalse(client._is_cache_valid("future"))

    async def test_search_uses_games_endpoint_and_filters_non_steam_results(self):
        http = StubHttpClient(
            [
                {"gameID": "1", "steamAppID": "10"},
                {"gameID": "2", "steamAppID": None},
                "invalid",
            ]
        )
        client = self.client(http)

        result = await client.search_games("Example")

        self.assertEqual([{"gameID": "1", "steamAppID": "10"}], result)
        self.assertEqual(
            ("cheapshark", f"{CHEAPSHARK_BASE_URL}/games", {"title": "Example", "limit": 20}),
            http.calls[0],
        )

    async def test_steam_price_is_normalized_and_validated(self):
        http = StubHttpClient(
            {
                "10": {
                    "success": True,
                    "data": {"price_overview": {"final": 977000, "discount_percent": 25}},
                }
            }
        )
        client = self.client(http)

        result = await client.get_appdetails_price("10")

        self.assertEqual(
            {"price_kzt": 9770.0, "discount_percent": 25, "available": True},
            result,
        )
        self.assertEqual(STEAM_APPDETAILS_URL, http.calls[0][1])
        self.assertEqual("10", http.calls[0][2]["appids"])
        self.assertIsNone(await client.get_appdetails_price("not-an-id"))

    async def test_free_games_are_cached_and_returned_as_copies(self):
        http = StubHttpClient(
            {
                "items": [
                    {
                        "name": "Free Game",
                        "logo": "https://cdn.example/apps/123/header.jpg",
                    }
                ]
            }
        )
        client = self.client(http)

        first = await client.get_free_games()
        first[0]["name"] = "mutated"
        second = await client.get_free_games()

        self.assertEqual("Free Game", second[0]["name"])
        self.assertEqual(1, len(http.calls))
        self.assertEqual(STEAM_SEARCH_URL, http.calls[0][1])

    async def test_exchange_rate_is_cached_and_network_errors_are_sanitized(self):
        secret = "never-log-provider-secret"
        success_http = StubHttpClient({"rates": {"RUB": 90, "KZT": 450}})
        client = self.client(success_http)

        self.assertEqual(0.2, await client.ensure_rate())
        self.assertEqual(0.2, await client.ensure_rate())
        self.assertEqual(EXCHANGE_RATE_URL, success_http.calls[0][1])
        self.assertEqual(1, len(success_http.calls))

        failing = self.client(StubHttpClient(APIError("steam", f"leaked {secret}")))
        with self.assertLogs("faztestbot.modules.steam_deals.api_client") as captured:
            result = await failing.get_appdetails_price("10")

        self.assertIsNone(result)
        self.assertNotIn(secret, "\n".join(captured.output))

    def test_extracts_only_numeric_app_ids(self):
        client = self.client()

        self.assertEqual(
            "123",
            client.extract_steam_app_id("https://store.steampowered.com/app/123/name"),
        )
        self.assertIsNone(client.extract_steam_app_id("https://example.com/app/123"))


if __name__ == "__main__":
    unittest.main()
