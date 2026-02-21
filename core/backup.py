# core/backup.py
# Система резервного копирования базы данных FazTestBot
# Версия: 3.6
# Дата: 19.02.2026

import os
import shutil
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Tuple
import config


class BackupManager:
    """
    Менеджер резервного копирования базы данных.

    Автоматическое создание бэкапов по расписанию,
    ротация старых файлов, ручное создание бэкапов.
    """

    def __init__(self):
        """Инициализация менеджера бэкапов"""
        self.backup_dir = config.BACKUP_DIR
        self.db_path = config.DATABASE_PATH
        self.retention_count = config.BACKUP_RETENTION_COUNT
        self.retention_days = config.BACKUP_RETENTION_DAYS
        self._ensure_backup_dir()

    def _ensure_backup_dir(self):
        """Создание директории для бэкапов если не существует"""
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)
            print(f"📁 Создана папка для бэкапов: {self.backup_dir}")

    def create_backup(self, manual: bool = False) -> Tuple[bool, str]:
        """
        Создание бэкапа базы данных.

        :param manual: True если бэкап создан вручную пользователем
        :return: (success: bool, message: str)
        """
        try:
            # Проверяем существование БД
            if not os.path.exists(self.db_path):
                return False, "❌ База данных не найдена"

            # Проверяем, не открыта ли БД в данный момент
            try:
                conn = sqlite3.connect(self.db_path)
                conn.execute("SELECT 1")
                conn.close()
            except sqlite3.OperationalError as e:
                return False, f"❌ База данных заблокирована: {str(e)}"

            # Генерируем имя файла бэкапа
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_type = "manual" if manual else "auto"
            backup_filename = f"users_{backup_type}_{timestamp}.db"
            backup_path = os.path.join(self.backup_dir, backup_filename)

            # Копируем файл БД
            shutil.copy2(self.db_path, backup_path)

            # Проверяем успешность копирования
            if os.path.exists(backup_path):
                backup_size = os.path.getsize(backup_path)

                # Ротация старых бэкапов
                self._rotate_backups()

                message = (
                    f"✅ Бэкап создан успешно!\n\n"
                    f"📁 Файл: {backup_filename}\n"
                    f"📊 Размер: {self._format_size(backup_size)}\n"
                    f"🕐 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
                )

                if manual:
                    print(f"💾 Ручной бэкап создан: {backup_filename}")
                else:
                    print(f"💾 Автоматический бэкап создан: {backup_filename}")

                return True, message
            else:
                return False, "❌ Ошибка при создании бэкапа"

        except Exception as e:
            error_msg = f"❌ Исключение при создании бэкапа: {str(e)}"
            print(error_msg)
            return False, error_msg

    def _rotate_backups(self):
        """Удаление старых бэкапов согласно настройкам"""
        try:
            # Получаем список всех бэкапов
            backup_files = []
            for filename in os.listdir(self.backup_dir):
                if filename.startswith("users_") and filename.endswith(".db"):
                    filepath = os.path.join(self.backup_dir, filename)
                    backup_files.append({
                        'filename': filename,
                        'path': filepath,
                        'mtime': datetime.fromtimestamp(os.path.getmtime(filepath))
                    })

            # Сортируем по времени создания (новые первые)
            backup_files.sort(key=lambda x: x['mtime'], reverse=True)

            # Удаляем бэкапы сверх лимита количества
            if len(backup_files) > self.retention_count:
                for backup in backup_files[self.retention_count:]:
                    try:
                        os.remove(backup['path'])
                        print(f"🗑️ Удалён старый бэкап: {backup['filename']}")
                    except Exception as e:
                        print(f"⚠️ Ошибка удаления бэкапа {backup['filename']}: {str(e)}")

            # Удаляем бэкапы старше retention_days
            cutoff_date = datetime.now() - timedelta(days=self.retention_days)
            for backup in backup_files:
                if backup['mtime'] < cutoff_date:
                    try:
                        os.remove(backup['path'])
                        print(f"🗑️ Удалён устаревший бэкап: {backup['filename']}")
                    except Exception as e:
                        print(f"⚠️ Ошибка удаления бэкапа {backup['filename']}: {str(e)}")

        except Exception as e:
            print(f"⚠️ Ошибка ротации бэкапов: {str(e)}")

    def _format_size(self, size_bytes: int) -> str:
        """Форматирование размера файла в человекочитаемый вид"""
        for unit in ['Б', 'КБ', 'МБ', 'ГБ']:
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

                    backup_list.append({
                        'filename': filename,
                        'path': filepath,
                        'size': stat.st_size,
                        'size_formatted': self._format_size(stat.st_size),
                        'created': datetime.fromtimestamp(stat.st_mtime),
                        'type': backup_type
                    })

            # Сортируем по времени (новые первые)
            backup_list.sort(key=lambda x: x['created'], reverse=True)

        except Exception as e:
            print(f"⚠️ Ошибка получения списка бэкапов: {str(e)}")

        return backup_list

    def get_backup_stats(self) -> dict:
        """
        Получение статистики по бэкапам.

        :return: Словарь со статистикой
        """
        backup_list = self.get_backup_list()

        total_size = sum(b['size'] for b in backup_list)
        auto_count = sum(1 for b in backup_list if b['type'] == "Авто")
        manual_count = sum(1 for b in backup_list if b['type'] == "Ручной")

        return {
            'total_count': len(backup_list),
            'auto_count': auto_count,
            'manual_count': manual_count,
            'total_size': total_size,
            'total_size_formatted': self._format_size(total_size),
            'newest': backup_list[0]['created'].strftime('%d.%m.%Y %H:%M') if backup_list else "Нет бэкапов",
            'oldest': backup_list[-1]['created'].strftime('%d.%m.%Y %H:%M') if backup_list else "Нет бэкапов"
        }

    def delete_backup(self, filename: str) -> Tuple[bool, str]:
        """
        Удаление конкретного бэкапа.

        :param filename: Имя файла бэкапа
        :return: (success: bool, message: str)
        """
        try:
            filepath = os.path.join(self.backup_dir, filename)

            # Проверяем существование
            if not os.path.exists(filepath):
                return False, f"❌ Бэкап не найден: {filename}"

            # Проверяем что это действительно файл бэкапа
            if not filename.startswith("users_") or not filename.endswith(".db"):
                return False, "❌ Неверный формат файла бэкапа"

            # Удаляем файл
            os.remove(filepath)

            return True, f"✅ Бэкап удалён: {filename}"

        except Exception as e:
            return False, f"❌ Ошибка удаления бэкапа: {str(e)}"

    def restore_backup(self, filename: str) -> Tuple[bool, str]:
        """
        Восстановление из бэкапа.

        :param filename: Имя файла бэкапа
        :return: (success: bool, message: str)
        """
        try:
            backup_path = os.path.join(self.backup_dir, filename)

            # Проверяем существование
            if not os.path.exists(backup_path):
                return False, f"❌ Бэкап не найден: {filename}"

            # Создаём бэкап текущей БД перед восстановлением
            print("📦 Создание бэкапа текущей БД перед восстановлением...")
            self.create_backup(manual=True)

            # Восстанавливаем из бэкапа
            shutil.copy2(backup_path, self.db_path)

            return True, f"✅ Восстановление выполнено из: {filename}"

        except Exception as e:
            return False, f"❌ Ошибка восстановления: {str(e)}"


# Глобальный экземпляр менеджера бэкапов
backup_manager = BackupManager()