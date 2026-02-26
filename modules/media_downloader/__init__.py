# modules/media_downloader/__init__.py
# Модуль "Media Downloader" для FazTestBot
# Версия: 4.1.1
# Дата: 22.02.2026

from core.module_base import BaseModule
from .handlers import MediaDownloaderModule

# Создание экземпляра модуля
media_downloader_module = MediaDownloaderModule(
    module_id="media_downloader",
    name="Media Downloader",
    description="Загрузка видео/аудио из YouTube, TikTok, Instagram",
    icon="📥",
    version="1.3.1",
    callback_prefix="media_"
)

__all__ = ['media_downloader_module']