# modules/media_downloader/config.py
# Конфигурация модуля "Media Downloader"
# Версия: 4.1.1 - МОДУЛЬ ОТКЛЮЧЁН
# Дата: 22.02.2026

import config

# ====== СТАТУС МОДУЛЯ ======
ENABLED = False  # ⚠️ МОДУЛЬ ОТКЛЮЧЁН

# ====== НАСТРОЙКИ ЗАГРУЗКИ ======
MAX_FILE_SIZE_MB = config.MAX_DOWNLOAD_SIZE_MB
MAX_DOWNLOADS_PER_USER_PER_DAY = config.MAX_DOWNLOADS_PER_USER_PER_DAY
DOWNLOADS_DIR = config.DOWNLOADS_DIR

# ====== ПОДДЕРЖИВАЕМЫЕ ПЛАТФОРМЫ ======
SUPPORTED_PLATFORMS = {
    "youtube": {"video": True, "audio": True, "name": "YouTube"},
    "tiktok": {"video": True, "audio": True, "name": "TikTok"},
    "instagram": {"video": True, "audio": False, "name": "Instagram"},
    "twitter": {"video": True, "audio": False, "name": "Twitter/X"},
    "facebook": {"video": True, "audio": False, "name": "Facebook"},
    "vimeo": {"video": True, "audio": True, "name": "Vimeo"}
}

# ====== КАЧЕСТВО ПО УМОЛЧАНИЮ ======
DEFAULT_VIDEO_QUALITY = "720p"
DEFAULT_AUDIO_QUALITY = "192"

# ====== ТАБЛИЦА В БД ======
TABLE_NAME = "media_downloader_logs"

# ====== ВРЕМЯ ХРАНЕНИЯ ФАЙЛОВ ======
TEMP_FILE_LIFETIME_HOURS = 1