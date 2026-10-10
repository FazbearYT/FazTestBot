# core/backup.py
# Система резервного копирования базы данных FazTestBot

import os
import re
from datetime import datetime, timedelta
from pathlib import Path

import config
from core.observability import event_fields, get_logger
from core.paths import BACKUPS_DIR, DATABASE_PATH
from core.storage import SQLiteDatabase

BACKUP_FILENAME_PATTERN = re.compile(r"^users_(?:manual|auto)_\d{8}_\d{6}(?:_\d{6})?\.db$")
logger = get_logger(__name__)


class BackupManager:
    """
    Менеджер резервного копирования базы данных.

    Автоматическое создание бэкапов по расписанию,
    ротация старых файлов, ручное создание бэкапов.
    """

    def __init__(self, backup_dir: str = None, db_path: str = None):
        self.backup_dir = Path(backup_dir or BACKUPS_DIR)
        self.db_path = Path(db_path or DATABASE_PATH)
        self.database = SQLiteDatabase(self.db_path)
        self.retention_count = config.BACKUP_RETENTION_COUNT
        self.retention_days = config.BACKUP_RETENTION_DAYS
        self._ensure_backup_dir()

    def _ensure_backup_dir(self):
        """Создание директории для бэкапов если не существует"""
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)
            logger.info(
                "backup directory created: %s",
                self.backup_dir,
                extra=event_fields("backup.directory_created", path=str(self.backup_dir)),
            )

    def create_backup(self, manual: bool = False, *, rotate: bool = True) -> tuple[bool, str]:
        """
        Создание бэкапа базы данных.

        :param manual: True если бэкап создан вручную пользователем
        :return: (success: bool, message: str)
        """
        try:
            # Проверяем существование БД
            if not os.path.exists(self.db_path):
                return False, "❌ База данных не найдена"

            # Генерируем имя файла бэкапа
            # Microseconds prevent a safety backup created during restore from
            # overwriting the selected backup in the same second.
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            backup_type = "manual" if manual else "auto"
            backup_filename = f"users_{backup_type}_{timestamp}.db"
            backup_path = self.backup_dir / backup_filename

            # SQLite Online Backup API includes committed WAL pages and creates
            # a transactionally consistent snapshot of an active database.
            self.database.backup_to(backup_path)

            # Проверяем успешность копирования
            if os.path.exists(backup_path):
                backup_size = os.path.getsize(backup_path)

                # Ротация старых бэкапов
                if rotate:
                    self._rotate_backups()

                message = (
                    f"✅ Бэкап создан успешно!\n\n"
                    f"📁 Файл: {backup_filename}\n"
                    f"📊 Размер: {self._format_size(backup_size)}\n"
                    f"🕐 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
                )

                logger.info(
                    "backup created: %s",
                    backup_filename,
                    extra=event_fields(
                        "backup.created",
                        backup_type=backup_type,
                        backup_filename=backup_filename,
                        size_bytes=backup_size,
                    ),
                )

                return True, message
            else:
                return False, "❌ Ошибка при создании бэкапа"

        except Exception as e:
            error_msg = f"❌ Исключение при создании бэкапа: {str(e)}"
            logger.exception(
                "backup creation failed",
                extra=event_fields("backup.create_failed", manual=manual),
            )
            return False, error_msg

    def _rotate_backups(self):
        """Удаление старых бэкапов согласно настройкам"""
        try:
            # Получаем список всех бэкапов
            backup_files = []
            for filename in os.listdir(self.backup_dir):
                if filename.startswith("users_") and filename.endswith(".db"):
                    filepath = os.path.join(self.backup_dir, filename)
                    backup_files.append(
                        {
                            "filename": filename,
                            "path": filepath,
                            "mtime": datetime.fromtimestamp(os.path.getmtime(filepath)),
                        }
                    )

            # Сортируем по времени создания (новые первые)
            backup_files.sort(key=lambda x: x["mtime"], reverse=True)

            cutoff_date = datetime.now() - timedelta(days=self.retention_days)
            for index, backup in enumerate(backup_files):
                over_count = index >= self.retention_count
                expired = backup["mtime"] < cutoff_date
                if not (over_count or expired):
                    continue
                try:
                    os.remove(backup["path"])
                    logger.info(
                        "expired backup removed: %s",
                        backup["filename"],
                        extra=event_fields(
                            "backup.rotated",
                            backup_filename=backup["filename"],
                            expired=expired,
                            over_count=over_count,
                        ),
                    )
                except Exception as e:
                    logger.warning(
                        "failed to remove expired backup %s",
                        backup["filename"],
                        exc_info=(type(e), e, e.__traceback__),
                        extra=event_fields(
                            "backup.rotation_delete_failed",
                            backup_filename=backup["filename"],
                        ),
                    )

        except Exception:
            logger.exception(
                "backup rotation failed",
                extra=event_fields("backup.rotation_failed"),
            )

    def _format_size(self, size_bytes: int) -> str:
        """Форматирование размера файла в человекочитаемый вид"""
        for unit in ["Б", "КБ", "МБ", "ГБ"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} ТБ"

    def get_backup_list(self) -> list:
        """
        Получение списка всех бэкапов.

        :return: Список словарей с информацией о бэкапах
        """
        backup_list = []

        try:
            for filename in os.listdir(self.backup_dir):
                if filename.startswith("users_") and filename.endswith(".db"):
                    filepath = os.path.join(self.backup_dir, filename)
                    stat = os.stat(filepath)

                    backup_type = "Ручной" if "_manual_" in filename else "Авто"

                    backup_list.append(
                        {
                            "filename": filename,
                            "path": filepath,
                            "size": stat.st_size,
                            "size_formatted": self._format_size(stat.st_size),
                            "created": datetime.fromtimestamp(stat.st_mtime),
                            "type": backup_type,
                        }
                    )

            # Сортируем по времени (новые первые)
            backup_list.sort(key=lambda x: x["created"], reverse=True)

        except Exception:
            logger.exception(
                "failed to list backups",
                extra=event_fields("backup.list_failed"),
            )

        return backup_list

    def get_backup_stats(self) -> dict:
        """
        Получение статистики по бэкапам.

        :return: Словарь со статистикой
        """
        backup_list = self.get_backup_list()

        total_size = sum(b["size"] for b in backup_list)
        auto_count = sum(1 for b in backup_list if b["type"] == "Авто")
        manual_count = sum(1 for b in backup_list if b["type"] == "Ручной")

        return {
            "total_count": len(backup_list),
            "auto_count": auto_count,
            "manual_count": manual_count,
            "total_size": total_size,
            "total_size_formatted": self._format_size(total_size),
            "newest": backup_list[0]["created"].strftime("%d.%m.%Y %H:%M")
            if backup_list
            else "Нет бэкапов",
            "oldest": backup_list[-1]["created"].strftime("%d.%m.%Y %H:%M")
            if backup_list
            else "Нет бэкапов",
        }

    def delete_backup(self, filename: str) -> tuple[bool, str]:
        """
        Удаление конкретного бэкапа.

        :param filename: Имя файла бэкапа
        :return: (success: bool, message: str)
        """
        try:
            filepath = self._resolve_backup_path(filename)
            if filepath is None:
                return False, "❌ Неверный формат файла бэкапа"

            if not filepath.is_file():
                return False, f"❌ Бэкап не найден: {filename}"

            # Удаляем файл
            filepath.unlink()

            return True, f"✅ Бэкап удалён: {filename}"

        except Exception as e:
            return False, f"❌ Ошибка удаления бэкапа: {str(e)}"

    def restore_backup(self, filename: str) -> tuple[bool, str]:
        """
        Восстановление из бэкапа.

        :param filename: Имя файла бэкапа
        :return: (success: bool, message: str)
        """
        try:
            backup_path = self._resolve_backup_path(filename)
            if backup_path is None:
                return False, "❌ Неверный формат файла бэкапа"

            # Проверяем существование
            if not backup_path.is_file():
                return False, f"❌ Бэкап не найден: {filename}"

            # Never touch the live database when the selected snapshot is invalid.
            SQLiteDatabase(backup_path).validate()

            # Создаём бэкап текущей БД перед восстановлением
            logger.info(
                "creating safety backup before restore",
                extra=event_fields("backup.restore_safety_started", backup_filename=filename),
            )
            safety_created, safety_message = self.create_backup(manual=True, rotate=False)
            if not safety_created:
                return False, f"❌ Защитный бэкап не создан: {safety_message}"

            # SQLite holds a destination write transaction for the online restore.
            self.database.restore_from(backup_path)
            self._rotate_backups()

            logger.info(
                "database restored from backup: %s",
                filename,
                extra=event_fields("backup.restored", backup_filename=filename),
            )

            return True, f"✅ Восстановление выполнено из: {filename}"

        except Exception as e:
            logger.exception(
                "database restore failed",
                extra=event_fields("backup.restore_failed", backup_filename=filename),
            )
            return False, f"❌ Ошибка восстановления: {str(e)}"

    def _resolve_backup_path(self, filename: str) -> Path | None:
        """Resolve a plain generated filename inside the configured directory."""

        if not BACKUP_FILENAME_PATTERN.fullmatch(filename):
            return None
        candidate = (self.backup_dir / filename).resolve()
        if candidate.parent != self.backup_dir.resolve():
            return None
        return candidate


# Глобальный экземпляр менеджера бэкапов
backup_manager = BackupManager()
