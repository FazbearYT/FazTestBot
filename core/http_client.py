"""Bounded asynchronous HTTP access for external service integrations."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

import aiohttp

from core.exceptions import APIAuthenticationError, APIError, APIRateLimitError
from core.observability import event_fields, get_logger

logger = get_logger(__name__)
TRANSIENT_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})


@dataclass(frozen=True, slots=True)
class HttpPolicy:
    connect_timeout_seconds: float = 3.0
    read_timeout_seconds: float = 7.0
    total_timeout_seconds: float = 10.0
    max_attempts: int = 3
    backoff_seconds: float = 0.25
    max_retry_after_seconds: float = 5.0
    max_response_bytes: int = 1_048_576

    def __post_init__(self) -> None:
        positive = (
            self.connect_timeout_seconds,
            self.read_timeout_seconds,
            self.total_timeout_seconds,
            self.max_attempts,
            self.max_response_bytes,
        )
        if any(value <= 0 for value in positive):
            raise ValueError("HTTP timeout, attempt, and response limits must be positive")
        if self.backoff_seconds < 0 or self.max_retry_after_seconds < 0:
            raise ValueError("HTTP retry delays must not be negative")


class AsyncHttpClient:
    """Execute idempotent GET requests under one explicit resilience policy."""

    def __init__(
        self,
        policy: HttpPolicy | None = None,
        *,
        session_factory: Callable[..., Any] = aiohttp.ClientSession,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self.policy = policy or HttpPolicy()
        self.session_factory = session_factory
        self.sleep = sleep

    async def get_json(
        self,
        service: str,
        url: str,
        *,
        params: Mapping[str, str | int | float] | None = None,
    ) -> Any:
        body, _charset = await self._get_bytes(service, url, params=params)
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise APIError(
                service,
                "invalid JSON response",
                code="API_INVALID_RESPONSE",
                retryable=False,
            ) from error

    async def get_text(
        self,
        service: str,
        url: str,
        *,
        params: Mapping[str, str | int | float] | None = None,
    ) -> str:
        body, charset = await self._get_bytes(service, url, params=params)
        try:
            return body.decode(charset or "utf-8")
        except (LookupError, UnicodeDecodeError) as error:
            raise APIError(
                service,
                "invalid text response",
                code="API_INVALID_RESPONSE",
                retryable=False,
            ) from error

    async def _get_bytes(
        self,
        service: str,
        url: str,
        *,
        params: Mapping[str, str | int | float] | None,
    ) -> tuple[bytes, str | None]:
        timeout = aiohttp.ClientTimeout(
            total=self.policy.total_timeout_seconds,
            connect=self.policy.connect_timeout_seconds,
            sock_read=self.policy.read_timeout_seconds,
        )
        last_error: APIError | None = None
        for attempt in range(1, self.policy.max_attempts + 1):
            retry_after: float | None = None
            try:
                async with self.session_factory(timeout=timeout) as session:
                    async with session.get(url, params=params, allow_redirects=False) as response:
                        if 200 <= response.status < 300:
                            body = await self._read_bounded(response, service)
                            return body, response.charset
                        last_error = self._status_error(service, response)
                        if isinstance(last_error, APIRateLimitError):
                            retry_after = self._retry_after(response.headers)
            except (asyncio.TimeoutError, aiohttp.ClientError) as error:
                last_error = APIError(
                    service,
                    "network request failed",
                    code="API_NETWORK_ERROR",
                    retryable=True,
                )
                last_error.__cause__ = error

            if last_error is None:
                raise RuntimeError("HTTP request ended without a result")
            if not last_error.retryable or attempt >= self.policy.max_attempts:
                raise last_error
            delay = (
                retry_after
                if retry_after is not None
                else self.policy.backoff_seconds * (2 ** (attempt - 1))
            )
            logger.warning(
                "external request will be retried",
                extra=event_fields(
                    "http.retry_scheduled",
                    service=service,
                    attempt=attempt,
                    max_attempts=self.policy.max_attempts,
                    delay_seconds=delay,
                    error_code=last_error.code,
                ),
            )
            await self.sleep(delay)
        raise last_error

    async def _read_bounded(self, response: Any, service: str) -> bytes:
        content_length = response.content_length
        if content_length is not None and content_length > self.policy.max_response_bytes:
            raise APIError(
                service,
                "response exceeded size limit",
                code="API_RESPONSE_TOO_LARGE",
                retryable=False,
            )
        body = bytearray()
        async for chunk in response.content.iter_chunked(65_536):
            body.extend(chunk)
            if len(body) > self.policy.max_response_bytes:
                raise APIError(
                    service,
                    "response exceeded size limit",
                    code="API_RESPONSE_TOO_LARGE",
                    retryable=False,
                )
        return bytes(body)

    @staticmethod
    def _status_error(service: str, response: Any) -> APIError:
        if response.status in {401, 403}:
            return APIAuthenticationError(service)
        if response.status == 429:
            return APIRateLimitError(service)
        return APIError(
            service,
            f"HTTP status {response.status}",
            response.status,
            code="API_HTTP_ERROR",
            retryable=response.status in TRANSIENT_STATUS_CODES,
        )

    def _retry_after(self, headers: Mapping[str, str]) -> float | None:
        value = headers.get("Retry-After")
        if value is None:
            return None
        try:
            seconds = max(0.0, float(value))
        except ValueError:
            return None
        return min(seconds, self.policy.max_retry_after_seconds)


http_client = AsyncHttpClient()

__all__ = ["AsyncHttpClient", "HttpPolicy", "TRANSIENT_STATUS_CODES", "http_client"]
