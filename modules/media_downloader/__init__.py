from core.module_base import BaseModule
from .handlers import MediaDownloaderModule

#Создание экземпляра модуля
media_downloader_module = MediaDownloaderModule(
    module_id="media_downloader",
    name="Media Downloader",
    description="Загрузка видео/аудио из YouTube, TikTok, Instagram и др.",
    icon="📥",
    version="2.0.1",
    callback_prefix="media_"
)

__all__ = ['media_downloader_module']