# modules/steam_deals/config.py
# Конфигурация модуля "Steam Deals Tracker"

import config

# ====== API НАСТРОЙКИ ======
CHEAPSHARK_API_KEY = config.CHEAPSHARK_API_KEY
CHEAPSHARK_BASE_URL = "https://www.cheapshark.com/api/1.0"

# ====== КЭШИРОВАНИЕ ======
CACHE_TTL_SECONDS = 3600  # 1 час для популярных и бесплатных игр
DEALS_CACHE_FILE = "temp/steam_deals_cache.json"

# ====== ЛИМИТЫ ======
MAX_WISHLIST_GAMES = 50  # Максимум игр в вишлисте пользователя
MAX_DEALS_DISPLAY = 20  # Максимум отображаемых сделок
MAX_FREE_GAMES_DISPLAY = 20  # Максимум бесплатных игр

# ====== ТАБЛИЦЫ В БД ======
WISHLIST_TABLE = "steam_wishlist"
CACHE_TABLE = "steam_cache"

# ====== ФИЛЬТРЫ ======
MIN_DISCOUNT_PERCENT = 50  # Минимальная скидка для "Популярных скидок" (%)
PRICE_ALERT_THRESHOLD = 20  # Порог предупреждения если цена выше минимума на X%

# ====== ВАЛЮТА ======
CURRENCY = "RUB"
CURRENCY_SYMBOL = "₽"