# modules/steam_deals/api_client.py
# API клиент для CheapShark (Steam deals)

import aiohttp
import json
import os
import re
from datetime import datetime
from typing import Optional, Dict, List
from .config import (
    CHEAPSHARK_BASE_URL,
    CHEAPSHARK_API_KEY,
    CACHE_TTL_SECONDS,
    DEALS_CACHE_FILE,
    MAX_FREE_GAMES_DISPLAY,
    EXCHANGE_RATE_URL,
    EXCHANGE_RATE_TTL_SECONDS,
    FALLBACK_KZT_RUB,
    STEAM_SEARCH_URL,
    STEAM_APPDETAILS_URL,
    STEAM_COUNTRY_CODE,
    STEAM_LANGUAGE
)


class SteamDealsClient:
    """Клиент для получения данных о скидках Steam через CheapShark API"""

    def __init__(self):
        self.base_url = CHEAPSHARK_BASE_URL
        self.api_key = CHEAPSHARK_API_KEY
        self.cache = {}
        self.cache_timestamp = {}
        self.kzt_to_rub = FALLBACK_KZT_RUB
        self._load_cache()

    def _load_cache(self):
        """Загрузка кэша из файла"""
        try:
            if os.path.exists(DEALS_CACHE_FILE):
                with open(DEALS_CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.cache = data.get('data', {})
                    self.cache_timestamp = data.get('timestamp', {})
                    self.kzt_to_rub = data.get('kzt_to_rub', FALLBACK_KZT_RUB)
        except Exception as e:
            print(f"⚠️ Ошибка загрузки кэша: {str(e)}")
            self.cache = {}
            self.cache_timestamp = {}

    def _save_cache(self):
        """Сохранение кэша в файл"""
        try:
            os.makedirs(os.path.dirname(DEALS_CACHE_FILE), exist_ok=True)
            with open(DEALS_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    'data': self.cache,
                    'timestamp': self.cache_timestamp,
                    'kzt_to_rub': self.kzt_to_rub
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Ошибка сохранения кэша: {str(e)}")

    def _is_cache_valid(self, key: str, ttl: int = CACHE_TTL_SECONDS) -> bool:
        """Проверка валидности кэша"""
        if key not in self.cache_timestamp:
            return False

        timestamp = self.cache_timestamp[key]
        cache_time = datetime.fromisoformat(timestamp)
        age = datetime.now() - cache_time

        return age.total_seconds() < ttl

    async def ensure_rate(self) -> float:
        """
        Получение актуального курса тенге->рубль (с кэшированием).

        Курсы берутся относительно доллара, KZT->RUB = RUB / KZT.

        :return: Курс тенге к рублю
        """
        if self._is_cache_valid("fx_rate", EXCHANGE_RATE_TTL_SECONDS):
            return self.kzt_to_rub

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        EXCHANGE_RATE_URL,
                        timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        rates = data.get('rates', {})
                        rub = rates.get('RUB')
                        kzt = rates.get('KZT')
                        if rub and kzt:
                            self.kzt_to_rub = float(rub) / float(kzt)
                            self.cache_timestamp["fx_rate"] = datetime.now().isoformat()
                            self._save_cache()
        except Exception as e:
            print(f"⚠️ Ошибка получения курса валют: {str(e)}")

        return self.kzt_to_rub

    def extract_steam_app_id(self, url: str) -> Optional[str]:
        """
        Извлечение Steam App ID из URL

        :param url: Ссылка на игру в Steam
        :return: App ID или None
        """
        patterns = [
            r'steamcommunity\.com/app/(\d+)',
            r'store\.steampowered\.com/app/(\d+)',
            r'steamdb\.info/app/(\d+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return None

    async def search_games(self, query: str) -> List[Dict]:
        """
        Поиск игр по названию или ссылке Steam.

        Возвращаются только игры, представленные в Steam (steamAppID задан).

        :param query: Название игры или ссылка на Steam
        :return: Список найденных игр
        """
        app_id = self.extract_steam_app_id(query)
        if app_id:
            return await self.get_games_by_steam_app_id(app_id)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        f"{self.base_url}/games",
                        params={"title": query, "limit": 20},
                        timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        steam_games = [g for g in data if g.get('steamAppID')]
                        return steam_games[:10]
                    return []
        except Exception as e:
            print(f"❌ Ошибка поиска игр: {str(e)}")
            return []

    async def get_games_by_steam_app_id(self, app_id: str) -> List[Dict]:
        """
        Поиск игр CheapShark по Steam App ID.

        :param app_id: Steam App ID
        :return: Список найденных игр
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        f"{self.base_url}/games",
                        params={"steamAppID": app_id},
                        timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return [g for g in data if g.get('steamAppID')]
                    return []
        except Exception as e:
            print(f"❌ Ошибка поиска по App ID: {str(e)}")
            return []

    async def get_steam_app_id(self, game_id: str) -> Optional[Dict]:
        """
        Получение Steam App ID и названия по CheapShark gameID.

        :param game_id: CheapShark gameID
        :return: {steam_app_id, title} или None
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        f"{self.base_url}/games",
                        params={"id": game_id},
                        timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        return None

                    data = await response.json()
                    info = data.get('info', {})
                    return {
                        'steam_app_id': info.get('steamAppID'),
                        'title': info.get('title', 'Unknown')
                    }
        except Exception as e:
            print(f"❌ Ошибка получения App ID: {str(e)}")
            return None

    async def get_appdetails_price(self, steam_app_id: str) -> Optional[Dict]:
        """
        Актуальная цена игры в Steam (в тенге) по Steam App ID.

        :param steam_app_id: Steam App ID
        :return: {price_kzt, discount_percent, available} или None
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        STEAM_APPDETAILS_URL,
                        params={
                            "appids": steam_app_id,
                            "cc": STEAM_COUNTRY_CODE,
                            "l": STEAM_LANGUAGE,
                            "filters": "price_overview"
                        },
                        timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        return None

                    data = await response.json(content_type=None)
                    app = data.get(str(steam_app_id), {})

                    if not app.get('success'):
                        return {'price_kzt': 0.0, 'discount_percent': 0, 'available': False}

                    price = (app.get('data') or {}).get('price_overview')
                    if not price:
                        return {'price_kzt': 0.0, 'discount_percent': 0, 'available': False}

                    return {
                        'price_kzt': float(price.get('final', 0)) / 100.0,
                        'discount_percent': int(price.get('discount_percent', 0)),
                        'available': True
                    }
        except Exception as e:
            print(f"❌ Ошибка получения цены Steam: {str(e)}")
            return None

    def _extract_app_id_from_logo(self, logo_url: str) -> Optional[str]:
        """Извлечение Steam App ID из ссылки на обложку"""
        match = re.search(r'/apps/(\d+)/', logo_url)
        return match.group(1) if match else None

    async def get_free_games(self) -> List[Dict]:
        """
        Бесплатные игры напрямую из магазина Steam (с учётом региона).

        CheapShark отдаёт только магазин США и пропускает региональные
        раздачи, поэтому источник — собственный поиск Steam.

        :return: Список словарей {name, app_id}
        """
        cache_key = "free_games"

        if self._is_cache_valid(cache_key):
            print("📦 Используем кэш для бесплатных игр")
            return self.cache[cache_key]

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        STEAM_SEARCH_URL,
                        params={
                            "maxprice": "free",
                            "specials": "1",
                            "json": "1",
                            "cc": STEAM_COUNTRY_CODE,
                            "l": STEAM_LANGUAGE,
                            "count": "50"
                        },
                        timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    if response.status == 200:
                        data = await response.json(content_type=None)

                        free = []
                        for item in data.get('items', []):
                            name = item.get('name')
                            if not name:
                                continue
                            free.append({
                                'name': name,
                                'app_id': self._extract_app_id_from_logo(item.get('logo', ''))
                            })

                        free = free[:MAX_FREE_GAMES_DISPLAY]
                        self.cache[cache_key] = free
                        self.cache_timestamp[cache_key] = datetime.now().isoformat()
                        self._save_cache()

                        return free
                    return []
        except Exception as e:
            print(f"❌ Ошибка получения бесплатных игр: {str(e)}")
            return []

    def format_price_kzt(self, price_kzt: float) -> str:
        """Форматирование основной цены в тенге (9 770₸)"""
        return f"{int(round(price_kzt)):,}₸".replace(",", " ")

    def format_price_rub(self, price_kzt: float) -> str:
        """Примерная цена в рублях по курсу (~1444₽)"""
        rub = price_kzt * self.kzt_to_rub
        return f"~{int(round(rub))}₽"

    def format_discount(self, savings: float) -> str:
        """Форматирование скидки"""
        return f"-{int(round(savings))}%"

    def check_price_alert(self, current_price: float, historical_low: float) -> bool:
        """
        Проверка: текущая цена заметно выше исторического минимума.

        :param current_price: Текущая цена
        :param historical_low: Исторический минимум
        :return: True если цена выше минимума более чем на 20%
        """
        if historical_low <= 0:
            return False

        difference = ((current_price - historical_low) / historical_low) * 100
        return difference > 20


# Глобальный экземпляр клиента
steam_client = SteamDealsClient()
