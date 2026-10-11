"""Clients for the external URL shortening services."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from core.exceptions import APIError, classify_exception
from core.http_client import AsyncHttpClient, http_client
from core.observability import event_fields, get_logger
from modules.url_shortener.config import CUTTLY_API_KEY, DEFAULT_PROTOCOL, URL_SHORTENER_SERVICE

logger = get_logger(__name__)

TINYURL_ENDPOINT = "https://tinyurl.com/api-create.php"
CUTTLY_ENDPOINT = "https://cutt.ly/api/api.php"
CUTTLY_STATUS_MESSAGES = {
    0: "Плохая ссылка",
    1: "Неправильный API ключ",
    2: "Ссылка уже сокращена",
    3: "Публичная ссылка",
    4: "Слишком длинная ссылка",
    5: "Неправильный формат ссылки",
    6: "Ссылка не найдена",
}


class URLShortenerClient:
    """Validate URLs and shorten them through one bounded HTTP client."""

    def __init__(
        self,
        *,
        http: AsyncHttpClient | None = None,
        service: str = URL_SHORTENER_SERVICE,
        cuttly_api_key: str = CUTTLY_API_KEY,
    ):
        self.http = http or http_client
        self.service = service
        self.cuttly_api_key = cuttly_api_key

    def validate_url(self, url: str) -> tuple[bool, str]:
        """Return a normalized HTTP(S) URL or a stable validation message."""

        if not url or not url.strip():
            return False, "❌ Ссылка не может быть пустой"

        normalized = url.strip()
        if len(normalized) > 2048:
            return False, "❌ Ссылка слишком длинная (макс. 2048 символов)"

        if "://" not in normalized:
            normalized = DEFAULT_PROTOCOL + normalized

        try:
            parsed = urlsplit(normalized)
            port = parsed.port
        except ValueError:
            return False, "❌ Неверный формат ссылки (нужен корректный HTTP(S) адрес)"
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or any(character.isspace() for character in parsed.hostname)
            or (port is not None and not 1 <= port <= 65_535)
        ):
            return False, "❌ Неверный формат ссылки (нужен корректный HTTP(S) адрес)"
        if parsed.username or parsed.password:
            return False, "❌ Ссылки с данными авторизации не поддерживаются"

        return True, normalized

    async def shorten_url(self, url: str) -> tuple[bool, str]:
        """Shorten a URL while preserving the module's legacy result contract."""

        is_valid, result = self.validate_url(url)
        if not is_valid:
            return False, result

        if self.service == "cuttly" and self.cuttly_api_key:
            return await self._shorten_with_cuttly(result)
        return await self._shorten_with_tinyurl(result)

    async def _shorten_with_tinyurl(self, url: str) -> tuple[bool, str]:
        try:
            shortened_url = (
                await self.http.get_text(
                    "tinyurl",
                    TINYURL_ENDPOINT,
                    params={"url": url},
                )
            ).strip()
        except APIError as error:
            return self._safe_api_failure(error, "tinyurl")

        if not self._is_http_url(shortened_url):
            return False, "❌ TinyURL вернул некорректный ответ"
        return True, shortened_url

    async def _shorten_with_cuttly(self, url: str) -> tuple[bool, str]:
        try:
            payload = await self.http.get_json(
                "cuttly",
                CUTTLY_ENDPOINT,
                params={"key": self.cuttly_api_key, "short": url},
            )
        except APIError as error:
            return self._safe_api_failure(error, "cuttly")

        response = payload.get("url") if isinstance(payload, Mapping) else None
        if not isinstance(response, Mapping):
            return False, "❌ Cutt.ly вернул некорректный ответ"

        status = response.get("status")
        if status != 7:
            message = CUTTLY_STATUS_MESSAGES.get(status, "Неизвестная ошибка")
            return False, f"❌ Ошибка Cutt.ly: {message}"

        shortened_url = response.get("shortLink")
        if not isinstance(shortened_url, str) or not self._is_http_url(shortened_url):
            return False, "❌ Cutt.ly вернул некорректную ссылку"
        return True, shortened_url

    @staticmethod
    def _is_http_url(value: Any) -> bool:
        if not isinstance(value, str):
            return False
        try:
            parsed = urlsplit(value)
            parsed.port
        except ValueError:
            return False
        return (
            parsed.scheme in {"http", "https"}
            and bool(parsed.hostname)
            and not any(character.isspace() for character in parsed.hostname)
        )

    @staticmethod
    def _safe_api_failure(error: APIError, service: str) -> tuple[bool, str]:
        disposition = classify_exception(error)
        logger.log(
            disposition.log_level,
            "external URL shortening request failed",
            extra=event_fields(
                "url_shortener.request_failed",
                service=service,
                error_code=disposition.code,
                error_category=disposition.category.value,
                retryable=disposition.retryable,
            ),
        )
        return False, disposition.user_message


url_client = URLShortenerClient()

__all__ = [
    "CUTTLY_ENDPOINT",
    "TINYURL_ENDPOINT",
    "URLShortenerClient",
    "url_client",
]
