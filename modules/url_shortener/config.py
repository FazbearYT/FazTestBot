# modules/url_shortener/config.py
# Конфигурация модуля "URL Shortener"
# Версия: 1.0.0
# Дата: 25.02.2026

# API сервис для сокращения ссылок
# Варианты: "tinyurl" (без ключа) или "cuttly" (требует API ключ)
URL_SHORTENER_SERVICE = "tinyurl"

# API ключ для Cutt.ly (получить на https://cutt.ly/api)
CUTTLY_API_KEY = ""

# Лимиты
MAX_URLS_PER_USER_PER_DAY = 100  # Максимум ссылок на пользователя в день
MAX_URL_LENGTH = 2048  # Максимальная длина исходной ссылки

# Настройки валидации URL
ALLOWED_PROTOCOLS = ["http://", "https://"]
DEFAULT_PROTOCOL = "https://"

# Таблица в БД для истории ссылок
TABLE_NAME = "url_shortener_logs"