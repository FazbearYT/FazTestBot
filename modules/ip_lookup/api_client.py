"""Bounded clients for external IP information services."""

from __future__ import annotations

from collections.abc import Mapping
from ipaddress import ip_address
from typing import Any

from core.exceptions import APIError, APIRateLimitError, classify_exception
from core.http_client import AsyncHttpClient, http_client
from core.observability import event_fields, get_logger
from modules.ip_lookup.config import IP_INFO_API_SERVICE, IPINFO_API_KEY

logger = get_logger(__name__)

IPAPI_ENDPOINT = "https://ipapi.co/{ip}/json/"
IPINFO_ENDPOINT = "https://ipinfo.io/{ip}/json"
RATE_LIMIT_MESSAGE = "❌ Превышен лимит запросов API. Подождите несколько минут."


class IPLookupClient:
    """Validate IP addresses and normalize provider-specific responses."""

    def __init__(
        self,
        *,
        http: AsyncHttpClient | None = None,
        service: str = IP_INFO_API_SERVICE,
        ipinfo_api_key: str = IPINFO_API_KEY,
    ):
        self.http = http or http_client
        self.service = service
        self.ipinfo_api_key = ipinfo_api_key

    def validate_ip(self, value: str) -> tuple[bool, str]:
        """Return a canonical IPv4/IPv6 address or a stable validation error."""

        if not value or not value.strip():
            return False, "❌ Запрос не может быть пустым"
        try:
            normalized = str(ip_address(value.strip()))
        except ValueError:
            return False, "❌ Неверный формат IP адреса. Поддерживаются только IPv4 и IPv6"
        return True, normalized

    async def get_ip_info(self, value: str) -> tuple[bool, dict[str, Any]]:
        """Fetch normalized information while preserving the legacy result contract."""

        is_valid, result = self.validate_ip(value)
        if not is_valid:
            return False, {"error": result}

        if self.service == "ipinfo" and self.ipinfo_api_key:
            return await self._get_info_ipinfo(result)
        return await self._get_info_ipapi(result)

    async def _get_info_ipapi(self, ip: str) -> tuple[bool, dict[str, Any]]:
        try:
            payload = await self.http.get_json(
                "ipapi",
                IPAPI_ENDPOINT.format(ip=ip),
            )
        except APIError as error:
            return self._safe_api_failure(error, "ipapi")

        if not isinstance(payload, Mapping):
            return False, {"error": "❌ Сервис IP Lookup вернул некорректный ответ"}
        if payload.get("error"):
            return False, {"error": "❌ Сервис IP Lookup отклонил запрос"}

        return True, {
            "ip": self._text(payload.get("ip"), ip),
            "city": self._text(payload.get("city")),
            "region": self._text(payload.get("region")),
            "country": self._text(payload.get("country_name")),
            "country_code": self._text(payload.get("country_code")),
            "isp": self._text(payload.get("org")),
            "timezone": self._text(payload.get("timezone")),
            "latitude": self._value(payload.get("latitude")),
            "longitude": self._value(payload.get("longitude")),
            "postal": self._text(payload.get("postal")),
            "asn": self._text(payload.get("asn")),
            "source": "ipapi.co",
        }

    async def _get_info_ipinfo(self, ip: str) -> tuple[bool, dict[str, Any]]:
        try:
            payload = await self.http.get_json(
                "ipinfo",
                IPINFO_ENDPOINT.format(ip=ip),
                params={"token": self.ipinfo_api_key},
            )
        except APIError as error:
            return self._safe_api_failure(error, "ipinfo")

        if not isinstance(payload, Mapping):
            return False, {"error": "❌ Сервис IP Lookup вернул некорректный ответ"}
        latitude, longitude = self._coordinates(payload.get("loc"))
        country_code = self._text(payload.get("country"))
        return True, {
            "ip": self._text(payload.get("ip"), ip),
            "city": self._text(payload.get("city")),
            "region": self._text(payload.get("region")),
            "country": country_code,
            "country_code": country_code,
            "isp": self._text(payload.get("org")),
            "timezone": self._text(payload.get("timezone")),
            "latitude": latitude,
            "longitude": longitude,
            "postal": self._text(payload.get("postal")),
            "asn": self._text(payload.get("asn")),
            "source": "ipinfo.io",
        }

    @staticmethod
    def _coordinates(value: Any) -> tuple[str, str]:
        if not isinstance(value, str):
            return "Unknown", "Unknown"
        parts = [part.strip() for part in value.split(",")]
        if len(parts) != 2 or not all(parts):
            return "Unknown", "Unknown"
        return parts[0], parts[1]

    @staticmethod
    def _text(value: Any, default: str = "Unknown") -> str:
        return value if isinstance(value, str) and value else default

    @staticmethod
    def _value(value: Any) -> Any:
        return "Unknown" if value is None or isinstance(value, (dict, list)) else value

    @staticmethod
    def _safe_api_failure(error: APIError, service: str) -> tuple[bool, dict[str, Any]]:
        disposition = classify_exception(error)
        logger.log(
            disposition.log_level,
            "external IP lookup request failed",
            extra=event_fields(
                "ip_lookup.request_failed",
                service=service,
                error_code=disposition.code,
                error_category=disposition.category.value,
                retryable=disposition.retryable,
            ),
        )
        message = (
            RATE_LIMIT_MESSAGE if isinstance(error, APIRateLimitError) else disposition.user_message
        )
        return False, {"error": message}


ip_client = IPLookupClient()

__all__ = ["IPAPI_ENDPOINT", "IPINFO_ENDPOINT", "IPLookupClient", "ip_client"]
