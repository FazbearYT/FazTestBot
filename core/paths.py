# core/paths.py
# Централизованное управление путями FazTestBot
# Версия: 4.2.2

import os
from pathlib import Path

# Корневая директория бота
ROOT_DIR = Path(__file__).parent.parent

# ====== ВРЕМЕННЫЕ ДАННЫЕ (не в репозитории) ======
TEMP_DIR = ROOT_DIR / "temp"
TEMP_DIR.mkdir(exist_ok=True)

# База данных
DATABASE_DIR = TEMP_DIR / "database"
DATABASE_DIR.mkdir(exist_ok=True)
DATABASE_PATH = DATABASE_DIR / "users.db"

# Загрузки медиа
DOWNLOADS_DIR = TEMP_DIR / "downloads"
DOWNLOADS_DIR.mkdir(exist_ok=True)

# Экспорты из админки
EXPORTS_DIR = TEMP_DIR / "exports"
EXPORTS_DIR.mkdir(exist_ok=True)

# Резервные копии
BACKUPS_DIR = TEMP_DIR / "backups"
BACKUPS_DIR.mkdir(exist_ok=True)

# ====== ФАЙЛЫ КОНФИГУРАЦИИ ======
SECRETS_FILE = ROOT_DIR / "secrets.py"
SECRETS_TEMPLATE_FILE = ROOT_DIR / "secrets.template.py"
ENV_FILE = ROOT_DIR / ".env"

# ====== ДОКУМЕНТАЦИЯ ======
HISTORY_FILE = ROOT_DIR / "history.txt"
ROADMAP_FILE = ROOT_DIR / "roadmap.txt"
REQUIREMENTS_FILE = ROOT_DIR / "requirements.txt"

# ====== МОДУЛИ ======
MODULES_DIR = ROOT_DIR / "modules"
CORE_DIR = ROOT_DIR / "core"


def get_temp_path(subdir: str = None) -> Path:
    """
    Получение пути во временной папке

    :param subdir: Поддиректория (downloads, exports, backups)
    :return: Path объект
    """
    if subdir:
        path = TEMP_DIR / subdir
        path.mkdir(exist_ok=True)
        return path
    return TEMP_DIR


def cleanup_temp():
    """Очистка временных файлов (кроме БД и бэкапов)"""
    import shutil

    dirs_to_clean = [DOWNLOADS_DIR, EXPORTS_DIR]

    for dir_path in dirs_to_clean:
        if dir_path.exists():
            for file in dir_path.iterdir():
                try:
                    if file.is_file():
                        file.unlink()
                except Exception as e:
                    print(f"⚠️ Ошибка очистки {file}: {e}")


# Экспорт всех путей
__all__ = [
    'ROOT_DIR',
    'TEMP_DIR',
    'DATABASE_DIR',
    'DATABASE_PATH',
    'DOWNLOADS_DIR',
    'EXPORTS_DIR',
    'BACKUPS_DIR',
    'SECRETS_FILE',
    'SECRETS_TEMPLATE_FILE',
    'ENV_FILE',
    'HISTORY_FILE',
    'ROADMAP_FILE',
    'REQUIREMENTS_FILE',
    'MODULES_DIR',
    'CORE_DIR',
    'get_temp_path',
    'cleanup_temp'
]