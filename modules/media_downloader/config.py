import os
import config as bot_config

#====== СТАТУС МОДУЛЯ ======
ENABLED = True  # ✅ МОДУЛЬ ВКЛЮЧЁН

#====== ПУТИ ======
MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(MODULE_DIR, '..', '..'))
TEMP_DIR = os.path.join(PROJECT_ROOT, 'temp', 'downloads')
ASSETS_DIR = os.path.join(PROJECT_ROOT, 'assets', 'ffmpeg', 'bin')

#Создаём папки если не существуют
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(ASSETS_DIR, exist_ok=True)

#====== FFmpeg ======
FFMPEG_PATH = os.path.join(ASSETS_DIR, 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')
FFPROBE_PATH = os.path.join(ASSETS_DIR, 'ffprobe.exe' if os.name == 'nt' else 'ffprobe')

#Проверка наличия ffmpeg
if not os.path.exists(FFMPEG_PATH):
    print(f"⚠️ FFmpeg не найден: {FFMPEG_PATH}")
    print("   Скачайте с: https://www.gyan.dev/ffmpeg/builds/")
    print(f"   И распакуйте в: {ASSETS_DIR}")

#====== НАСТРОЙКИ ЗАГРУЗКИ ======
MAX_FILE_SIZE_MB = getattr(bot_config, 'MAX_DOWNLOAD_SIZE_MB', 50)
MAX_DOWNLOADS_PER_USER_PER_DAY = getattr(bot_config, 'MAX_DOWNLOADS_PER_USER_PER_DAY', 10)
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

#====== КАЧЕСТВО ======
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

#====== ТАЙМАУТЫ ======
DOWNLOAD_TIMEOUT = 300  # 5 минут
MAX_RETRIES = 3