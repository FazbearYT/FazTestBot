import os
from core.paths import TEMP_DIR, DOWNLOADS_DIR, ROOT_DIR

#====== СТАТУС МОДУЛЯ ======
ENABLED = True  # ✅ МОДУЛЬ ВКЛЮЧЁН

#====== ПУТИ ======
# Временная папка модуля для загрузок
MODULE_TEMP_DIR = TEMP_DIR / "media_downloader"
MODULE_TEMP_DIR.mkdir(exist_ok=True)

# Путь к FFmpeg (предполагается, что он лежит в assets/ffmpeg/bin/)
ASSETS_DIR = ROOT_DIR / "assets"
FFMPEG_DIR = ASSETS_DIR / "ffmpeg" / "bin"
FFMPEG_DIR.mkdir(exist_ok=True)

FFMPEG_PATH = FFMPEG_DIR / ("ffmpeg.exe" if os.name == 'nt' else 'ffmpeg')
FFPROBE_PATH = FFMPEG_DIR / ("ffprobe.exe" if os.name == 'nt' else 'ffprobe')

# Проверка наличия ffmpeg
if not FFMPEG_PATH.exists():
    print(f"⚠️ FFmpeg не найден: {FFMPEG_PATH}")
    print("   Скачайте с: https://www.gyan.dev/ffmpeg/builds/")
    print(f"   И распакуйте в: {FFMPEG_DIR}")

#====== НАСТРОЙКИ ЗАГРУЗКИ ======
MAX_FILE_SIZE_MB = 50  # Лимит Telegram Bot API (50 МБ)
MAX_DOWNLOADS_PER_USER_PER_DAY = 10
DEFAULT_VIDEO_QUALITY = "720p"
DEFAULT_AUDIO_QUALITY = "192"

#====== ПОДДЕРЖИВАЕМЫЕ ПЛАТФОРМЫ ======
SUPPORTED_PLATFORMS = {
    "youtube": {"name": "YouTube", "video": True, "audio": True},
    "tiktok": {"name": "TikTok", "video": True, "audio": False},
    "instagram": {"name": "Instagram", "video": True, "audio": False},
    "twitter": {"name": "Twitter/X", "video": True, "audio": False},
    "facebook": {"name": "Facebook", "video": True, "audio": False},
    "vimeo": {"name": "Vimeo", "video": True, "audio": True},
    "vk": {"name": "VK", "video": True, "audio": False},
    "rutube": {"name": "RuTube", "video": True, "audio": False},
}

#====== КАЧЕСТВО (yt-dlp форматы) ======
VIDEO_QUALITIES = {
    "360p": {"height": 360, "format": "bestvideo[height<=360]+bestaudio/best[height<=360]"},
    "480p": {"height": 480, "format": "bestvideo[height<=480]+bestaudio/best[height<=480]"},
    "720p": {"height": 720, "format": "bestvideo[height<=720]+bestaudio/best[height<=720]"},
    "1080p": {"height": 1080, "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]"},
}

AUDIO_QUALITIES = {
    "128": "128",
    "192": "192",
    "320": "320",
}

#====== ТАЙМАУТЫ И ПОВТОРЫ ======
DOWNLOAD_TIMEOUT = 300  # 5 минут
MAX_RETRIES = 3

#====== БАЗА ДАННЫХ ======
TABLE_NAME = "media_downloader_logs"