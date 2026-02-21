# modules/url_shortener/__init__.py
# Модуль "URL Shortener" для FazTestBot
# Версия: 4.0
# Дата: 25.02.2026

from core.module_base import BaseModule
from .handlers import URLShortenerModule

# Создание экземпляра модуля с соблюдением стандартов v3.5+
url_shortener_module = URLShortenerModule(
    module_id="url_shortener",
    name="URL Shortener",
    description="Сокращение ссылок через TinyURL/Cutt.ly",
    icon="🔗",
    version="1.0.0",
    callback_prefix="url_"
)

__all__ = ['url_shortener_module']