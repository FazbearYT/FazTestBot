"""Compatibility facade for environment-based application configuration.

New code should depend on :mod:`core.settings`. Existing modules can keep using
these constants while configuration is migrated incrementally.
"""

from core.paths import BACKUPS_DIR as BACKUPS_DIR
from core.paths import DATABASE_PATH as DATABASE_PATH
from core.paths import DOWNLOADS_DIR as DOWNLOADS_DIR
from core.paths import EXPORTS_DIR as EXPORTS_DIR
from core.paths import TEMP_DIR as TEMP_DIR
from core.settings import ConfigurationError as ConfigurationError
from core.settings import load_settings

VERSION = "4.5.0"
LAST_UPDATE_DATE = "10.10.2026"
AUTHOR = "@Fazbear_r"

_settings = load_settings()

BOT_TOKEN = _settings.bot_token
ADMINS = list(_settings.admins)
ADMIN_SECRET_CODE = _settings.admin_secret_code
ADMIN_SESSION_HOURS = _settings.admin_session_hours
URL_SHORTENER_SERVICE = _settings.url_shortener_service
CUTTLY_API_KEY = _settings.cuttly_api_key
MEDIA_DOWNLOADER_ENABLED = _settings.media_downloader_enabled
MAX_DOWNLOAD_SIZE_MB = _settings.max_download_size_mb
MAX_DOWNLOADS_PER_USER_PER_DAY = _settings.max_downloads_per_user_per_day
IP_INFO_API_SERVICE = _settings.ip_info_api_service
IPINFO_API_KEY = _settings.ipinfo_api_key
GROQ_API_KEY = _settings.groq_api_key
CHEAPSHARK_API_KEY = _settings.cheapshark_api_key
LOG_RETENTION_DAYS = _settings.log_retention_days
LOG_LEVEL = _settings.log_level
BACKUP_ENABLED = _settings.backup_enabled
BACKUP_TIME = _settings.backup_time
BACKUP_RETENTION_COUNT = _settings.backup_retention_count
BACKUP_RETENTION_DAYS = _settings.backup_retention_days
BLOCKED_USERS = list(_settings.blocked_users)

ALLOWED_SYMBOLS = "0123456789 .,!?;:'\"-()[]{}@#$%&*+=/\\|<>«»„"


def validate_config() -> bool:
    """Return whether the current environment can start the Telegram bot."""

    return not _settings.startup_errors()


def require_valid_config() -> None:
    """Raise a concise error when required runtime settings are missing."""

    _settings.require_startup_ready()


def validate_secrets() -> bool:
    """Deprecated compatibility alias for old callers."""

    return validate_config()
