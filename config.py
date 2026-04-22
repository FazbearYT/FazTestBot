# config.py
# Конфигурация FazTestBot
# Модульный бот-агрегатор с безопасным хранением секретов

# ====== ИМПОРТ ПУТЕЙ ======
from core.paths import DATABASE_PATH, DOWNLOADS_DIR, BACKUPS_DIR, TEMP_DIR, EXPORTS_DIR

# ====== ВЕРСИЯ БОТА (ЕДИНЫЙ ИСТОЧНИК) ======
VERSION = "pre 4.4.2"
LAST_UPDATE_DATE = "22.04.2026"
AUTHOR = "@Fazbear_r"

# ====== ЗАГРУЗКА СЕКРЕТОВ ======
try:
    from secrets import (
        BOT_TOKEN,
        ADMINS,
        ADMIN_SECRET_CODE,
        ADMIN_SESSION_HOURS,
        URL_SHORTENER_SERVICE,
        CUTTLY_API_KEY,
        MEDIA_DOWNLOADER_ENABLED,
        MAX_DOWNLOAD_SIZE_MB,
        MAX_DOWNLOADS_PER_USER_PER_DAY,
        IP_INFO_API_SERVICE,
        IPINFO_API_KEY,
        GROQ_API_KEY,
        CHEAPSHARK_API_KEY,
        LOG_RETENTION_DAYS,
        LOG_LEVEL
    )
except ImportError:
    print("⚠️ WARNING: secrets.py not found! Using fallback values.")
    BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
    ADMINS = [123456789]
    ADMIN_SECRET_CODE = "фазбер"
    ADMIN_SESSION_HOURS = 24
    URL_SHORTENER_SERVICE = "tinyurl"
    CUTTLY_API_KEY = ""
    MEDIA_DOWNLOADER_ENABLED = False
    MAX_DOWNLOAD_SIZE_MB = 50
    MAX_DOWNLOADS_PER_USER_PER_DAY = 10
    IP_INFO_API_SERVICE = "ipapi"
    IPINFO_API_KEY = ""
    GROQ_API_KEY = ""
    CHEAPSHARK_API_KEY = ""
    LOG_RETENTION_DAYS = 30
    LOG_LEVEL = "INFO"

# ====== НАСТРОЙКИ РЕЗЕРВНОГО КОПИРОВАНИЯ ======
BACKUP_ENABLED = True
BACKUP_TIME = "03:00"
BACKUP_RETENTION_COUNT = 7
BACKUP_RETENTION_DAYS = 30

# ====== НАСТРОЙКИ БЛОКИРОВКИ ======
BLOCKED_USERS = []

# ====== ГЛОБАЛЬНЫЕ НАСТРОЙКИ ======
ALLOWED_SYMBOLS = "0123456789 .,!?;:'\"-()[]{}@#$%&*+=/\\|<>«»„"


# ====== ПРОВЕРКА СЕКРЕТОВ ======
def validate_secrets():
    """Проверка наличия необходимых секретов"""
    errors = []

    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        errors.append("❌ BOT_TOKEN не настроен в secrets.py")

    if errors:
        print("\n⚠️ ОШИБКИ КОНФИГУРАЦИИ:")
        for error in errors:
            print(error)
        print("\n📝 Скопируйте secrets.template.py в secrets.py и заполните значения!\n")
        return False

    print("✅ Все секреты настроены корректно")
    return True