import asyncio
import unittest
from collections import deque

from core.exceptions import APIAuthenticationError, APIError, APIRateLimitError
from core.http_client import AsyncHttpClient, HttpPolicy


class FakeContent:
    def __init__(self, body: bytes):
        self.body = body

    async def iter_chunked(self, _size):
        yield self.body


class FakeResponse:
    def __init__(self, status=200, body=b"{}", *, headers=None, charset="utf-8"):
        self.status = status
        self.content = FakeContent(body)
        self.content_length = len(body)
        self.headers = headers or {}
        self.charset = charset

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc_info):
        return None


class FakeSession:
    def __init__(self, result, calls):
        self.result = result
        self.calls = calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc_info):
        return None

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class SessionFactory:
    def __init__(self, *results):
        self.results = deque(results)
        self.calls = []
        self.timeouts = []

    def __call__(self, *, timeout):
        self.timeouts.append(timeout)
        return FakeSession(self.results.popleft(), self.calls)


class AsyncHttpClientTests(unittest.IsolatedAsyncioTestCase):
    def policy(self, **overrides):
        values = {
            "max_attempts": 3,
            "backoff_seconds": 0.1,
            "max_retry_after_seconds": 2,
            "max_response_bytes": 100,
        }
        values.update(overrides)
        return HttpPolicy(**values)

    async def test_success_uses_structured_params_and_explicit_timeouts(self):
        factory = SessionFactory(FakeResponse(body=b'{"ok": true}'))
        client = AsyncHttpClient(self.policy(), session_factory=factory)

        result = await client.get_json(
            "service",
            "https://example.test/api",
            params={"token": "secret", "q": "value"},
        )

        self.assertEqual({"ok": True}, result)
        self.assertEqual("https://example.test/api", factory.calls[0][0])
        self.assertEqual("secret", factory.calls[0][1]["params"]["token"])
        timeout = factory.timeouts[0]
        self.assertEqual(3.0, timeout.connect)
        self.assertEqual(7.0, timeout.sock_read)
        self.assertEqual(10.0, timeout.total)

    async def test_transient_error_retries_with_bounded_retry_after(self):
        factory = SessionFactory(
            FakeResponse(status=429, headers={"Retry-After": "30"}),
            FakeResponse(body=b"done"),
        )
        delays = []
        client = AsyncHttpClient(
            self.policy(max_attempts=2),
            session_factory=factory,
            sleep=lambda delay: self._record_delay(delays, delay),
        )

        result = await client.get_text("service", "https://example.test/api")

        self.assertEqual("done", result)
        self.assertEqual([2], delays)
        self.assertEqual(2, len(factory.calls))

    async def test_timeout_is_retried_then_raised_as_safe_api_error(self):
        factory = SessionFactory(asyncio.TimeoutError(), asyncio.TimeoutError())
        client = AsyncHttpClient(
            self.policy(max_attempts=2, backoff_seconds=0),
            session_factory=factory,
            sleep=self._no_sleep,
        )

        with self.assertRaises(APIError) as raised:
            await client.get_json("service", "https://example.test/api")

        self.assertEqual("API_NETWORK_ERROR", raised.exception.code)
        self.assertNotIn("example.test", str(raised.exception))

    async def test_authentication_and_non_transient_errors_are_not_retried(self):
        for status, exception_type in ((401, APIAuthenticationError), (404, APIError)):
            with self.subTest(status=status):
                factory = SessionFactory(FakeResponse(status=status))
                client = AsyncHttpClient(self.policy(), session_factory=factory)
                with self.assertRaises(exception_type):
                    await client.get_json("service", "https://example.test/api")
                self.assertEqual(1, len(factory.calls))

    async def test_rate_limit_after_final_attempt_preserves_typed_error(self):
        factory = SessionFactory(FakeResponse(status=429))
        client = AsyncHttpClient(self.policy(max_attempts=1), session_factory=factory)

        with self.assertRaises(APIRateLimitError):
            await client.get_json("service", "https://example.test/api")

    async def test_invalid_or_oversized_payload_is_rejected(self):
        invalid = AsyncHttpClient(
            self.policy(max_attempts=1),
            session_factory=SessionFactory(FakeResponse(body=b"not-json")),
        )
        oversized = AsyncHttpClient(
            self.policy(max_attempts=1, max_response_bytes=3),
            session_factory=SessionFactory(FakeResponse(body=b"large")),
        )

        with self.assertRaisesRegex(APIError, "invalid JSON"):
            await invalid.get_json("service", "https://example.test/api")
        with self.assertRaisesRegex(APIError, "size limit"):
            await oversized.get_text("service", "https://example.test/api")

    async def _record_delay(self, delays, delay):
        delays.append(delay)

    async def _no_sleep(self, _delay):
        return None


class HttpPolicyTests(unittest.TestCase):
    def test_invalid_limits_are_rejected(self):
        with self.assertRaises(ValueError):
            HttpPolicy(max_attempts=0)
        with self.assertRaises(ValueError):
            HttpPolicy(backoff_seconds=-1)


if __name__ == "__main__":
    unittest.main()
