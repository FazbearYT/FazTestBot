# modules/media_downloader/config.py
# Конфигурация модуля "Media Downloader"
# Версия: 4.1.1
# Дата: 22.02.2026

import config

# ====== НАСТРОЙКИ ЗАГРУЗКИ ======
ENABLED = config.MEDIA_DOWNLOADER_ENABLED if hasattr(config, 'MEDIA_DOWNLOADER_ENABLED') else True
MAX_FILE_SIZE_MB = config.MAX_DOWNLOAD_SIZE_MB if hasattr(config, 'MAX_DOWNLOAD_SIZE_MB') else 50
MAX_DOWNLOADS_PER_USER_PER_DAY = config.MAX_DOWNLOADS_PER_USER_PER_DAY if hasattr(config, 'MAX_DOWNLOADS_PER_USER_PER_DAY') else 10
DOWNLOADS_DIR = config.DOWNLOADS_DIR if hasattr(config, 'DOWNLOADS_DIR') else "downloads"

# ====== ТАБЛИЦА В БД ======
TABLE_NAME = "media_downloader_logs"