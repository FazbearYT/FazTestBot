# modules/steam_deals/api_client.py
# API клиент для CheapShark (Steam deals)

import aiohttp
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from .config import (
    CHEAPSHARK_BASE_URL,
    CHEAPSHARK_API_KEY,
    CACHE_TTL_SECONDS,
    DEALS_CACHE_FILE,
    MIN_DISCOUNT_PERCENT,
    MAX_DEALS_DISPLAY,
    MAX_FREE_GAMES_DISPLAY
)


class SteamDealsClient:
    """Клиент для получения данных о скидках Steam через CheapShark API"""

    def __init__(self):
        self.base_url = CHEAPSHARK_BASE_URL
        self.api_key = CHEAPSHARK_API_KEY
        self.cache = {}
        self.cache_timestamp = {}
        self._load_cache()

    def _load_cache(self):
        """Загрузка кэша из файла"""
        try:
            if os.path.exists(DEALS_CACHE_FILE):
                with open(DEALS_CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.cache = data.get('data', {})
                    self.cache_timestamp = data.get('timestamp', {})
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
                    'timestamp': self.cache_timestamp
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Ошибка сохранения кэша: {str(e)}")

    def _is_cache_valid(self, key: str) -> bool:
        """Проверка валидности кэша"""
        if key not in self.cache_timestamp:
            return False

        timestamp = self.cache_timestamp[key]
        cache_time = datetime.fromisoformat(timestamp)
        age = datetime.now() - cache_time

        return age.total_seconds() < CACHE_TTL_SECONDS

    async def search_games(self, query: str) -> List[Dict]:
        """
        Поиск игр по названию

        :param query: Название игры для поиска
        :return: Список найденных игр
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        f"{self.base_url}/games",
                        params={"title": query, "limit": 10},
                        timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data[:10]  # Ограничиваем 10 результатами
                    else:
                        return []
        except Exception as e:
            print(f"❌ Ошибка поиска игр: {str(e)}")
            return []

    async def get_game_deals(self, game_id: str) -> List[Dict]:
        """
        Получение сделок для конкретной игры

        :param game_id: ID игры в CheapShark
        :return: Список сделок
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        f"{self.base_url}/deals",
                        params={"id": game_id},
                        timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data
                    else:
                        return []
        except Exception as e:
            print(f"❌ Ошибка получения сделок: {str(e)}")
            return []

    async def get_popular_deals(self) -> List[Dict]:
        """
        Получение популярных скидок

        :return: Список популярных сделок
        """
        cache_key = "popular_deals"

        # Проверяем кэш
        if self._is_cache_valid(cache_key):
            print("📦 Используем кэш для популярных скидок")
            return self.cache[cache_key]

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        f"{self.base_url}/deals",
                        params={
                            "storeID": "1",  # Steam
                            "lowerPrice": "0",
                            "upperPrice": "10000",
                            "pageSize": MAX_DEALS_DISPLAY,
                            "sortBy": "Popularity",
                            "desc": "1"
                        },
                        timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    if response.status == 200:
                        data = await response.json()

                        # Фильтруем по минимальной скидке
                        filtered = [
                            deal for deal in data
                            if float(deal.get('savings', 0)) >= MIN_DISCOUNT_PERCENT
                        ]

                        # Сохраняем в кэш
                        self.cache[cache_key] = filtered[:MAX_DEALS_DISPLAY]
                        self.cache_timestamp[cache_key] = datetime.now().isoformat()
                        self._save_cache()

                        return filtered[:MAX_DEALS_DISPLAY]
                    else:
                        return []
        except Exception as e:
            print(f"❌ Ошибка получения популярных скидок: {str(e)}")
            return []

    async def get_free_games(self) -> List[Dict]:
        """
        Получение бесплатных игр (100% OFF)

        :return: Список бесплатных игр
        """
        cache_key = "free_games"

        # Проверяем кэш
        if self._is_cache_valid(cache_key):
            print("📦 Используем кэш для бесплатных игр")
            return self.cache[cache_key]

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        f"{self.base_url}/deals",
                        params={
                            "storeID": "1",  # Steam
                            "lowerPrice": "0",
                            "upperPrice": "0",
                            "pageSize": MAX_FREE_GAMES_DISPLAY,
                            "sortBy": "Deal Rating",
                            "desc": "1"
                        },
                        timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    if response.status == 200:
                        data = await response.json()

                        # Фильтруем только 100% скидки
                        free = [
                            deal for deal in data
                            if float(deal.get('savings', 0)) >= 99
                        ]

                        # Сохраняем в кэш
                        self.cache[cache_key] = free[:MAX_FREE_GAMES_DISPLAY]
                        self.cache_timestamp[cache_key] = datetime.now().isoformat()
                        self._save_cache()

                        return free[:MAX_FREE_GAMES_DISPLAY]
                    else:
                        return []
        except Exception as e:
            print(f"❌ Ошибка получения бесплатных игр: {str(e)}")
            return []

    async def get_game_details(self, game_id: str) -> Optional[Dict]:
        """
        Получение детальной информации об игре

        :param game_id: ID игры в CheapShark
        :return: Детали игры
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        f"{self.base_url}/games/{game_id}",
                        timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data
                    else:
                        return None
        except Exception as e:
            print(f"❌ Ошибка получения деталей игры: {str(e)}")
            return None

    def format_price(self, price: float) -> str:
        """Форматирование цены"""
        return f"{int(price)}₽"

    def format_discount(self, savings: float) -> str:
        """Форматирование скидки"""
        return f"-{int(savings)}%"

    def check_price_alert(self, current_price: float, historical_low: float) -> bool:
        """
        Проверка предупреждения о цене

        :param current_price: Текущая цена
        :param historical_low: Исторический минимум
        :return: True если цена выше минимума на пороговое значение
        """
        if historical_low <= 0:
            return False

        difference = ((current_price - historical_low) / historical_low) * 100
        return difference > 20  # 20% порог


# Глобальный экземпляр клиента
steam_client = SteamDealsClient()