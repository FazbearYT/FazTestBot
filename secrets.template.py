# secrets.template.py
# Шаблон конфиденциальных данных FazTestBot
#
# ИНСТРУКЦИЯ:
# 1. Скопируйте этот файл как secrets.py
# 2. Заполните реальными значениями
# 3. Никогда не коммитьте secrets.py в репозиторий!
# 4. secrets.template.py можно коммитить (без реальных ключей)

# ====== TELEGRAM ======
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

# ====== ADMINISTRATION ======
ADMINS = [123456789]  # Замените на ваш user_id
ADMIN_SECRET_CODE = "your_secret_code_here"
ADMIN_SESSION_HOURS = 24

# ====== URL SHORTENER ======
URL_SHORTENER_SERVICE = "tinyurl"  # "tinyurl" или "cuttly"
CUTTLY_API_KEY = ""  # Получите на https://cutt.ly/api

# ====== MEDIA DOWNLOADER ======
MEDIA_DOWNLOADER_ENABLED = False  # ⚠️ ОТКЛЮЧЁН ПО УМОЛЧАНИЮ
MAX_DOWNLOAD_SIZE_MB = 50
MAX_DOWNLOADS_PER_USER_PER_DAY = 10

# ====== IP INFO LOOKUP ======
IP_INFO_API_SERVICE = "ipapi"  # "ipapi" (бесплатно, без ключа) или "ipinfo" (требует ключ)
IPINFO_API_KEY = ""  # Получите на https://ipinfo.io (опционально)

# ====== STEAM DEALS TRACKER ======
CHEAPSHARK_API_KEY = ""  # Получите на https://www.cheapshark.com/api (опционально)

# ====== AI CHAT (для будущих версий) ======
GROQ_API_KEY = ""  # Получите на https://console.groq.com

# ====== DATABASE ======
DATABASE_PATH = "users.db"
BACKUP_DIR = "backups"
DOWNLOADS_DIR = "downloads"

# ====== LOGGING ======
LOG_RETENTION_DAYS = 30
LOG_LEVEL = "INFO"