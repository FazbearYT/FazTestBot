import unittest

from core.exceptions import APIError, APIRateLimitError
from modules.ip_lookup.api_client import (
    IPAPI_ENDPOINT,
    IPINFO_ENDPOINT,
    IPLookupClient,
)


class StubHttpClient:
    def __init__(self, *, payload=None, error=None):
        self.payload = payload
        self.error = error
        self.calls = []

    async def get_json(self, service, url, *, params=None):
        self.calls.append((service, url, params))
        if self.error:
            raise self.error
        return self.payload


class IPLookupClientTests(unittest.IsolatedAsyncioTestCase):
    def test_validation_uses_complete_ipv4_and_ipv6_rules(self):
        client = IPLookupClient()

        self.assertEqual((True, "192.0.2.1"), client.validate_ip(" 192.0.2.1 "))
        self.assertEqual((True, "2001:db8::1"), client.validate_ip("2001:0db8::1"))
        self.assertFalse(client.validate_ip("999.1.1.1")[0])
        self.assertFalse(client.validate_ip("example.com")[0])
        self.assertFalse(client.validate_ip("")[0])

    async def test_ipapi_response_is_normalized(self):
        http = StubHttpClient(
            payload={
                "ip": "192.0.2.1",
                "city": "Test City",
                "country_name": "Test Country",
                "country_code": "TC",
                "latitude": 1.25,
                "longitude": 2.5,
            }
        )
        client = IPLookupClient(http=http, service="ipapi")

        success, info = await client.get_ip_info("192.0.2.1")

        self.assertTrue(success)
        self.assertEqual("Test City", info["city"])
        self.assertEqual("Unknown", info["isp"])
        self.assertEqual(1.25, info["latitude"])
        self.assertEqual("ipapi.co", info["source"])
        self.assertEqual(
            ("ipapi", IPAPI_ENDPOINT.format(ip="192.0.2.1"), None),
            http.calls[0],
        )

    async def test_ipinfo_uses_structured_token_and_parses_coordinates(self):
        secret = "ipinfo-secret-token"
        http = StubHttpClient(
            payload={
                "ip": "2001:db8::1",
                "country": "TC",
                "loc": "1.25,2.50",
                "org": "Example ISP",
            }
        )
        client = IPLookupClient(http=http, service="ipinfo", ipinfo_api_key=secret)

        success, info = await client.get_ip_info("2001:0db8::1")

        self.assertTrue(success)
        service, endpoint, params = http.calls[0]
        self.assertEqual("ipinfo", service)
        self.assertEqual(IPINFO_ENDPOINT.format(ip="2001:db8::1"), endpoint)
        self.assertNotIn(secret, endpoint)
        self.assertEqual({"token": secret}, params)
        self.assertEqual(("1.25", "2.50"), (info["latitude"], info["longitude"]))

    async def test_invalid_provider_payloads_are_safe(self):
        malformed = IPLookupClient(http=StubHttpClient(payload=[]), service="ipapi")
        rejected = IPLookupClient(
            http=StubHttpClient(payload={"error": True, "reason": "raw upstream detail"}),
            service="ipapi",
        )

        malformed_result = await malformed.get_ip_info("192.0.2.1")
        rejected_result = await rejected.get_ip_info("192.0.2.1")

        self.assertFalse(malformed_result[0])
        self.assertFalse(rejected_result[0])
        self.assertNotIn("raw upstream detail", rejected_result[1]["error"])

    async def test_missing_ipinfo_key_falls_back_to_ipapi(self):
        http = StubHttpClient(payload={"ip": "192.0.2.1"})
        client = IPLookupClient(http=http, service="ipinfo", ipinfo_api_key="")

        self.assertTrue((await client.get_ip_info("192.0.2.1"))[0])
        self.assertEqual("ipapi", http.calls[0][0])

    async def test_rate_limit_keeps_specific_safe_message(self):
        client = IPLookupClient(
            http=StubHttpClient(error=APIRateLimitError("ipapi")),
            service="ipapi",
        )

        success, result = await client.get_ip_info("192.0.2.1")

        self.assertFalse(success)
        self.assertIn("лимит", result["error"])

    async def test_error_text_and_token_are_not_logged_or_returned(self):
        secret = "never-log-this-token"
        error = APIError("ipinfo", f"provider leaked {secret}")
        client = IPLookupClient(
            http=StubHttpClient(error=error),
            service="ipinfo",
            ipinfo_api_key=secret,
        )

        with self.assertLogs("faztestbot.modules.ip_lookup.api_client") as captured:
            success, result = await client.get_ip_info("192.0.2.1")

        combined = result["error"] + "\n" + "\n".join(captured.output)
        self.assertFalse(success)
        self.assertNotIn(secret, combined)
        self.assertNotIn("provider leaked", combined)


if __name__ == "__main__":
    unittest.main()
