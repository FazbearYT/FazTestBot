import unittest

from core.exceptions import APIError
from modules.url_shortener.api_client import (
    CUTTLY_ENDPOINT,
    TINYURL_ENDPOINT,
    URLShortenerClient,
)


class StubHttpClient:
    def __init__(self, *, text=None, json=None, error=None):
        self.text = text
        self.json = json
        self.error = error
        self.calls = []

    async def get_text(self, service, url, *, params=None):
        self.calls.append(("text", service, url, params))
        if self.error:
            raise self.error
        return self.text

    async def get_json(self, service, url, *, params=None):
        self.calls.append(("json", service, url, params))
        if self.error:
            raise self.error
        return self.json


class URLShortenerClientTests(unittest.IsolatedAsyncioTestCase):
    def test_validation_normalizes_urls_and_rejects_unsafe_forms(self):
        client = URLShortenerClient()

        self.assertEqual((True, "https://example.com/a"), client.validate_url("example.com/a"))
        self.assertFalse(client.validate_url("ftp://example.com")[0])
        self.assertFalse(client.validate_url("https://user:password@example.com")[0])
        self.assertFalse(client.validate_url("https://")[0])
        self.assertFalse(client.validate_url("https://[")[0])
        self.assertFalse(client.validate_url("https://example.com:invalid")[0])
        self.assertFalse(client.validate_url("https://not valid.example")[0])
        self.assertFalse(client.validate_url(" " * 3)[0])
        self.assertFalse(client.validate_url("https://example.com/" + "x" * 2048)[0])

    async def test_tinyurl_uses_https_and_structured_query_params(self):
        http = StubHttpClient(text="https://tinyurl.com/example\n")
        client = URLShortenerClient(http=http, service="tinyurl")

        result = await client.shorten_url("example.com/path?a=1&b=2")

        self.assertEqual((True, "https://tinyurl.com/example"), result)
        self.assertEqual(
            (
                "text",
                "tinyurl",
                TINYURL_ENDPOINT,
                {"url": "https://example.com/path?a=1&b=2"},
            ),
            http.calls[0],
        )

    async def test_tinyurl_rejects_malformed_success_payload(self):
        client = URLShortenerClient(
            http=StubHttpClient(text="not a URL"),
            service="tinyurl",
        )

        success, message = await client.shorten_url("https://example.com")

        self.assertFalse(success)
        self.assertIn("некорректный", message)

    async def test_cuttly_keeps_api_key_out_of_endpoint(self):
        secret = "secret-api-key"
        http = StubHttpClient(json={"url": {"status": 7, "shortLink": "https://cutt.ly/example"}})
        client = URLShortenerClient(http=http, service="cuttly", cuttly_api_key=secret)

        result = await client.shorten_url("https://example.com")

        self.assertEqual((True, "https://cutt.ly/example"), result)
        _, service, endpoint, params = http.calls[0]
        self.assertEqual("cuttly", service)
        self.assertEqual(CUTTLY_ENDPOINT, endpoint)
        self.assertNotIn(secret, endpoint)
        self.assertEqual(secret, params["key"])
        self.assertEqual("https://example.com", params["short"])

    async def test_cuttly_maps_service_and_invalid_response_errors(self):
        rejected = URLShortenerClient(
            http=StubHttpClient(json={"url": {"status": 5}}),
            service="cuttly",
            cuttly_api_key="key",
        )
        malformed = URLShortenerClient(
            http=StubHttpClient(json=[]),
            service="cuttly",
            cuttly_api_key="key",
        )

        self.assertIn("Неправильный формат", (await rejected.shorten_url("example.com"))[1])
        self.assertIn("некорректный", (await malformed.shorten_url("example.com"))[1])

    async def test_api_failure_never_returns_raw_error_or_secret(self):
        secret = "never-return-this-secret"
        error = APIError("cuttly", f"upstream leaked {secret}")
        client = URLShortenerClient(
            http=StubHttpClient(error=error),
            service="cuttly",
            cuttly_api_key=secret,
        )

        with self.assertLogs("faztestbot.modules.url_shortener.api_client") as captured:
            success, message = await client.shorten_url("https://example.com")

        self.assertFalse(success)
        self.assertNotIn(secret, message)
        self.assertNotIn("upstream leaked", message)
        self.assertIn("Внешний сервис", message)
        self.assertNotIn(secret, "\n".join(captured.output))
        self.assertNotIn("upstream leaked", "\n".join(captured.output))

    async def test_missing_cuttly_key_falls_back_to_tinyurl(self):
        http = StubHttpClient(text="https://tinyurl.com/fallback")
        client = URLShortenerClient(http=http, service="cuttly", cuttly_api_key="")

        self.assertTrue((await client.shorten_url("example.com"))[0])
        self.assertEqual("tinyurl", http.calls[0][1])


if __name__ == "__main__":
    unittest.main()
