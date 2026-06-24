# modules/steam_deals/config.py
# Конфигурация модуля "Steam Deals Tracker"

import config
from core.paths import TEMP_DIR

# ====== API НАСТРОЙКИ ======
CHEAPSHARK_API_KEY = config.CHEAPSHARK_API_KEY
CHEAPSHARK_BASE_URL = "https://www.cheapshark.com/api/1.0"

# ====== КЭШИРОВАНИЕ ======
CACHE_TTL_SECONDS = 3600  # 1 час для бесплатных игр
DEALS_CACHE_FILE = str(TEMP_DIR / "steam_deals_cache.json")

# ====== КОНВЕРТАЦИЯ ВАЛЮТЫ ======
# Основная цена берётся из Steam в тенге. Рубли показываем примерно по курсу.
EXCHANGE_RATE_URL = "https://open.er-api.com/v6/latest/USD"
EXCHANGE_RATE_TTL_SECONDS = 43200  # 12 часов
FALLBACK_KZT_RUB = 0.15  # Запасной курс тенге->рубль, если API недоступен

# ====== STEAM ======
# Бесплатные игры и цены берём напрямую из магазина Steam (с учётом региона).
STEAM_SEARCH_URL = "https://store.steampowered.com/search/results/"
STEAM_APPDETAILS_URL = "https://store.steampowered.com/api/appdetails"
STEAM_COUNTRY_CODE = "kz"  # Регион магазина (kz, ru, us ...)
STEAM_LANGUAGE = "russian"
STEAM_APP_URL = "https://store.steampowered.com/app/"

# ====== ЛИМИТЫ ======
MAX_WISHLIST_GAMES = 50  # Максимум игр в вишлисте пользователя (хранение)
MAX_WISHLIST_DISPLAY = 25  # Максимум игр в одном сообщении (лимит Telegram 4096)
MAX_FREE_GAMES_DISPLAY = 20  # Максимум бесплатных игр
REFRESH_CONCURRENCY = 8  # Одновременных запросов к Steam при обновлении цен

# ====== ТАБЛИЦЫ В БД ======
WISHLIST_TABLE = "steam_wishlist"

# ====== ФИЛЬТРЫ ======
PRICE_ALERT_THRESHOLD = 20  # Порог предупреждения если цена выше минимума на X%

# ====== УВЕДОМЛЕНИЯ О СКИДКАХ ======
STEAM_NOTIFY_ENABLED = True
STEAM_NOTIFY_INTERVAL_HOURS = 6  # Как часто проверять падение цен

# ====== ВАЛЮТА ======
CURRENCY_SYMBOL = "₸"
