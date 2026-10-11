"""External service client for Steam Deals Tracker."""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

from core.exceptions import APIError, classify_exception
from core.http_client import AsyncHttpClient, http_client
from core.observability import event_fields, get_logger
from modules.steam_deals.config import (
    CACHE_TTL_SECONDS,
    CHEAPSHARK_API_KEY,
    CHEAPSHARK_BASE_URL,
    DEALS_CACHE_FILE,
    EXCHANGE_RATE_TTL_SECONDS,
    EXCHANGE_RATE_URL,
    FALLBACK_KZT_RUB,
    MAX_FREE_GAMES_DISPLAY,
    PRICE_ALERT_THRESHOLD,
    STEAM_APPDETAILS_URL,
    STEAM_COUNTRY_CODE,
    STEAM_LANGUAGE,
    STEAM_SEARCH_URL,
)

logger = get_logger(__name__)


class SteamDealsClient:
    """Normalize CheapShark, Steam Store, and exchange-rate responses."""

    def __init__(
        self,
        *,
        http: AsyncHttpClient | None = None,
        cache_path: str | Path = DEALS_CACHE_FILE,
        now: Callable[[], datetime] | None = None,
    ):
        self.http = http or http_client
        self.base_url = CHEAPSHARK_BASE_URL.rstrip("/")
        self.api_key = CHEAPSHARK_API_KEY
        self.cache_path = Path(cache_path)
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._cache_lock = RLock()
        self.cache: dict[str, Any] = {}
        self.cache_timestamp: dict[str, str] = {}
        self.kzt_to_rub = FALLBACK_KZT_RUB
        self._load_cache()

    def _load_cache(self) -> None:
        if not self.cache_path.is_file():
            return
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
            if not isinstance(payload, Mapping):
                raise ValueError("cache root is not an object")
            cached_data = payload.get("data", {})
            timestamps = payload.get("timestamp", {})
            rate = payload.get("kzt_to_rub", FALLBACK_KZT_RUB)
            if not isinstance(cached_data, dict) or not isinstance(timestamps, dict):
                raise ValueError("cache sections are invalid")
            rate = float(rate)
            if rate <= 0:
                raise ValueError("cached rate is invalid")
            with self._cache_lock:
                self.cache = cached_data
                self.cache_timestamp = {
                    str(key): value for key, value in timestamps.items() if isinstance(value, str)
                }
                self.kzt_to_rub = rate
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            with self._cache_lock:
                self.cache = {}
                self.cache_timestamp = {}
                self.kzt_to_rub = FALLBACK_KZT_RUB
            logger.warning(
                "Steam cache could not be loaded",
                extra=event_fields("steam.cache_load_failed"),
            )

    def _save_cache(self) -> None:
        temporary_path: Path | None = None
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            with self._cache_lock:
                payload = {
                    "data": self.cache,
                    "timestamp": self.cache_timestamp,
                    "kzt_to_rub": self.kzt_to_rub,
                }
                descriptor, name = tempfile.mkstemp(
                    prefix=f".{self.cache_path.name}.",
                    suffix=".tmp",
                    dir=self.cache_path.parent,
                )
                temporary_path = Path(name)
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    json.dump(payload, stream, ensure_ascii=False, indent=2)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary_path, self.cache_path)
                temporary_path = None
        except (OSError, TypeError, ValueError):
            logger.warning(
                "Steam cache could not be saved",
                extra=event_fields("steam.cache_save_failed"),
            )
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def _is_cache_valid(self, key: str, ttl: int = CACHE_TTL_SECONDS) -> bool:
        with self._cache_lock:
            timestamp = self.cache_timestamp.get(key)
        if not timestamp:
            return False
        try:
            cached_at = datetime.fromisoformat(timestamp)
            if cached_at.tzinfo is None:
                cached_at = cached_at.replace(tzinfo=timezone.utc)
            age = (self._utc_now() - cached_at.astimezone(timezone.utc)).total_seconds()
        except (TypeError, ValueError):
            return False
        return 0 <= age < ttl

    async def ensure_rate(self) -> float:
        if self._is_cache_valid("fx_rate", EXCHANGE_RATE_TTL_SECONDS):
            return self.kzt_to_rub
        try:
            payload = await self.http.get_json("exchange_rate", EXCHANGE_RATE_URL)
        except APIError as error:
            self._log_api_failure(error, "exchange_rate")
            return self.kzt_to_rub
        rates = payload.get("rates") if isinstance(payload, Mapping) else None
        if isinstance(rates, Mapping):
            try:
                rub = float(rates["RUB"])
                kzt = float(rates["KZT"])
                if rub > 0 and kzt > 0:
                    with self._cache_lock:
                        self.kzt_to_rub = rub / kzt
                        self.cache_timestamp["fx_rate"] = self._utc_now().isoformat()
                    self._save_cache()
            except (KeyError, TypeError, ValueError, ZeroDivisionError):
                pass
        return self.kzt_to_rub

    @staticmethod
    def extract_steam_app_id(url: str) -> str | None:
        for pattern in (
            r"steamcommunity\.com/app/(\d+)",
            r"store\.steampowered\.com/app/(\d+)",
            r"steamdb\.info/app/(\d+)",
        ):
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    async def search_games(self, query: str) -> list[dict[str, Any]]:
        app_id = self.extract_steam_app_id(query)
        if app_id:
            return await self.get_games_by_steam_app_id(app_id)
        payload = await self._get_json(
            "cheapshark",
            f"{self.base_url}/games",
            params={"title": query[:200], "limit": 20},
        )
        if not isinstance(payload, list):
            return []
        return [item for item in payload if isinstance(item, dict) and item.get("steamAppID")][:10]

    async def get_games_by_steam_app_id(self, app_id: str) -> list[dict[str, Any]]:
        if not app_id.isdigit():
            return []
        payload = await self._get_json(
            "cheapshark",
            f"{self.base_url}/games",
            params={"steamAppID": app_id},
        )
        if not isinstance(payload, list):
            return []
        return [item for item in payload if isinstance(item, dict) and item.get("steamAppID")]

    async def get_steam_app_id(self, game_id: str) -> dict[str, Any] | None:
        payload = await self._get_json(
            "cheapshark",
            f"{self.base_url}/games",
            params={"id": game_id[:100]},
        )
        info = payload.get("info") if isinstance(payload, Mapping) else None
        if not isinstance(info, Mapping):
            return None
        steam_app_id = info.get("steamAppID")
        if steam_app_id is not None and not str(steam_app_id).isdigit():
            steam_app_id = None
        return {
            "steam_app_id": str(steam_app_id) if steam_app_id is not None else None,
            "title": info.get("title") if isinstance(info.get("title"), str) else "Unknown",
        }

    async def get_appdetails_price(self, steam_app_id: str) -> dict[str, Any] | None:
        if not steam_app_id.isdigit():
            return None
        payload = await self._get_json(
            "steam",
            STEAM_APPDETAILS_URL,
            params={
                "appids": steam_app_id,
                "cc": STEAM_COUNTRY_CODE,
                "l": STEAM_LANGUAGE,
                "filters": "price_overview",
            },
        )
        if payload is None:
            return None
        app = payload.get(steam_app_id) if isinstance(payload, Mapping) else None
        if not isinstance(app, Mapping) or not app.get("success"):
            return {"price_kzt": 0.0, "discount_percent": 0, "available": False}
        app_data = app.get("data")
        price = app_data.get("price_overview") if isinstance(app_data, Mapping) else None
        if not isinstance(price, Mapping):
            return {"price_kzt": 0.0, "discount_percent": 0, "available": False}
        try:
            final = max(0.0, float(price.get("final", 0)) / 100.0)
            discount = min(100, max(0, int(price.get("discount_percent", 0))))
        except (TypeError, ValueError):
            return None
        return {"price_kzt": final, "discount_percent": discount, "available": True}

    @staticmethod
    def _extract_app_id_from_logo(logo_url: str) -> str | None:
        match = re.search(r"/apps/(\d+)/", logo_url)
        return match.group(1) if match else None

    async def get_free_games(self) -> list[dict[str, Any]]:
        cache_key = "free_games"
        if self._is_cache_valid(cache_key):
            with self._cache_lock:
                cached = self.cache.get(cache_key, [])
                return deepcopy(cached) if isinstance(cached, list) else []
        payload = await self._get_json(
            "steam",
            STEAM_SEARCH_URL,
            params={
                "maxprice": "free",
                "specials": "1",
                "json": "1",
                "cc": STEAM_COUNTRY_CODE,
                "l": STEAM_LANGUAGE,
                "count": "50",
            },
        )
        items = payload.get("items") if isinstance(payload, Mapping) else None
        if not isinstance(items, list):
            return []
        free = []
        for item in items:
            if not isinstance(item, Mapping) or not isinstance(item.get("name"), str):
                continue
            free.append(
                {
                    "name": item["name"],
                    "app_id": self._extract_app_id_from_logo(str(item.get("logo", ""))),
                }
            )
        free = free[:MAX_FREE_GAMES_DISPLAY]
        with self._cache_lock:
            self.cache[cache_key] = deepcopy(free)
            self.cache_timestamp[cache_key] = self._utc_now().isoformat()
        self._save_cache()
        return free

    async def _get_json(
        self,
        service: str,
        endpoint: str,
        *,
        params: Mapping[str, str | int | float] | None = None,
    ) -> Any:
        try:
            return await self.http.get_json(service, endpoint, params=params)
        except APIError as error:
            self._log_api_failure(error, service)
            return None

    @staticmethod
    def _log_api_failure(error: APIError, service: str) -> None:
        disposition = classify_exception(error)
        logger.log(
            disposition.log_level,
            "external Steam integration request failed",
            extra=event_fields(
                "steam.request_failed",
                service=service,
                error_code=disposition.code,
                error_category=disposition.category.value,
                retryable=disposition.retryable,
            ),
        )

    def _utc_now(self) -> datetime:
        value = self._now()
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def format_price_kzt(price_kzt: float) -> str:
        return f"{int(round(price_kzt)):,}₸".replace(",", " ")

    def format_price_rub(self, price_kzt: float) -> str:
        return f"~{int(round(price_kzt * self.kzt_to_rub))}₽"

    @staticmethod
    def format_discount(savings: float) -> str:
        return f"-{int(round(savings))}%"

    @staticmethod
    def check_price_alert(current_price: float, historical_low: float) -> bool:
        if historical_low <= 0:
            return False
        difference = ((current_price - historical_low) / historical_low) * 100
        return difference > PRICE_ALERT_THRESHOLD


steam_client = SteamDealsClient()

__all__ = ["SteamDealsClient", "steam_client"]
