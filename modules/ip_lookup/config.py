# modules/ip_lookup/config.py
# Конфигурация модуля "IP Info Lookup"
# Версия: 1.0.0
# Дата: 26.02.2026

import config

# ====== НАСТРОЙКИ API ======
IP_INFO_API_SERVICE = config.IP_INFO_API_SERVICE  # "ipapi" или "ipinfo"
IPINFO_API_KEY = config.IPINFO_API_KEY

# ====== ЛИМИТЫ ======
MAX_LOOKUPS_PER_USER_PER_DAY = 50  # Максимум запросов на пользователя в день
CACHE_TTL_SECONDS = 3600  # Время кэширования результатов (1 час)

# ====== ТАБЛИЦА В БД ======
TABLE_NAME = "ip_lookup_logs"

# ====== ПОДДЕРЖИВАЕМЫЕ ТИПЫ ЗАПРОСОВ ======
SUPPORTED_QUERY_TYPES = [
    "ipv4",      # IPv4 адреса
    "ipv6",      # IPv6 адреса
    "domain"     # Доменные имена (WHOIS)
]