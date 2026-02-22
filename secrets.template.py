# secrets.template.py
# Шаблон конфиденциальных данных FazTestBot
# Версия: 4.1
# Дата: 21.02.2026
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

# ====== URL SHORTENER ======
URL_SHORTENER_SERVICE = "tinyurl"  # "tinyurl" или "cuttly"
CUTTLY_API_KEY = ""  # Получите на https://cutt.ly/api

# ====== MEDIA DOWNLOADER ======
MEDIA_DOWNLOADER_ENABLED = True
MAX_DOWNLOAD_SIZE_MB = 50
MAX_DOWNLOADS_PER_USER_PER_DAY = 10

# ====== AI CHAT (для будущих версий) ======
GROQ_API_KEY = ""  # Получите на https://console.groq.com

# ====== DATABASE ======
DATABASE_PATH = "users.db"
BACKUP_DIR = "backups"
DOWNLOADS_DIR = "downloads"

# ====== LOGGING ======
LOG_RETENTION_DAYS = 30
LOG_LEVEL = "INFO"