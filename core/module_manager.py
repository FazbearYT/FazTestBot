# core/module_manager.py
# Менеджер модулей с автодискавери

import os
import importlib
from typing import Dict, List, Optional, Any
from .module_base import BaseModule


class ModuleManager:
    """
    Менеджер модулей с автоматическим обнаружением.

    Автоматически сканирует папку modules/ и загружает все валидные модули.
    Не требует ручной регистрации в bot.py.
    """

    def __init__(self, modules_path: str = "modules"):
        """
        Инициализация менеджера модулей.

        :param modules_path: Путь к папке с модулями
        """
        self.modules_path = modules_path
        self.modules: Dict[str, BaseModule] = {}  # {module_id: module_instance}
        self.callback_map: Dict[str, str] = {}  # {callback_prefix: module_id}
        self._load_errors: List[Dict] = []  # Ошибки загрузки для логирования

    def discover_and_load(self, bot: Optional[Any] = None) -> int:
        """
        Автоматическое обнаружение и загрузка всех модулей.

        :param bot: Экземпляр TeleBot (для on_load)
        :return: Количество успешно загруженных модулей
        """
        loaded_count = 0

        # Сканируем папку modules/
        if not os.path.exists(self.modules_path):
            print(f"⚠️ Папка модулей не найдена: {self.modules_path}")
            return 0

        for item in os.listdir(self.modules_path):
            item_path = os.path.join(self.modules_path, item)

            # Пропускаем не-директории и служебные папки
            if not os.path.isdir(item_path):
                continue
            if item.startswith("__") or item.startswith("."):
                continue

            # Пытаемся загрузить модуль
            success = self._load_module(item, bot)
            if success:
                loaded_count += 1

        return loaded_count

    def _load_module(self, module_name: str, bot: Optional[Any]) -> bool:
        """
        Загрузка отдельного модуля по имени папки.

        :param module_name: Имя папки модуля
        :param bot: Экземпляр TeleBot
        :return: True если успешно загружен
        """
        try:
            # Импортируем __init__.py модуля
            module_path = f"{self.modules_path}.{module_name}"
            init_module = importlib.import_module(module_path)

            # Ищем переменную {module_name}_module
            module_var_name = f"{module_name}_module"
            if not hasattr(init_module, module_var_name):
                error_msg = f"Модуль {module_name} не содержит переменную {module_var_name}"
                self._log_error(module_name, error_msg)
                return False

            module_instance = getattr(init_module, module_var_name)

            # Проверяем наследование от BaseModule
            if not isinstance(module_instance, BaseModule):
                error_msg = f"Модуль {module_name} не наследуется от BaseModule"
                self._log_error(module_name, error_msg)
                return False

            # Валидация модуля
            is_valid, error_msg = module_instance.validate()
            if not is_valid:
                self._log_error(module_name, f"Валидация не пройдена: {error_msg}")
                return False

            # Проверка уникальности module_id
            if module_instance.id in self.modules:
                error_msg = f"Дубликат module_id: {module_instance.id}"
                self._log_error(module_name, error_msg)
                return False

            # Проверка уникальности callback_prefix
            if module_instance.callback_prefix in self.callback_map:
                error_msg = f"Дубликат callback_prefix: {module_instance.callback_prefix}"
                self._log_error(module_name, error_msg)
                return False

            # Регистрация модуля
            self.modules[module_instance.id] = module_instance
            self.callback_map[module_instance.callback_prefix] = module_instance.id

            # Вызываем on_load если есть bot
            if bot:
                try:
                    module_instance.on_load(bot)
                except Exception as e:
                    self._log_error(module_name, f"Ошибка on_load: {str(e)}")

            print(f"✅ Модуль загружен: {module_instance.icon} {module_instance.name} v{module_instance.version}")
            return True

        except Exception as e:
            self._log_error(module_name, f"Исключение при загрузке: {str(e)}")
            return False

    def _log_error(self, module_name: str, error_msg: str):
        """Логирование ошибки загрузки модуля"""
        import datetime
        error = {
            "module": module_name,
            "error": error_msg,
            "timestamp": datetime.datetime.now().isoformat()
        }
        self._load_errors.append(error)
        print(f"❌ Ошибка загрузки модуля {module_name}: {error_msg}")

    def get_module_by_id(self, module_id: str) -> Optional[BaseModule]:
        """Получение модуля по ID"""
        return self.modules.get(module_id)

    def get_module_by_callback(self, callback_data: str) -> Optional[BaseModule]:
        """
        Получение модуля по callback_data.

        :param callback_data: Данные колбэка
        :return: Модуль или None
        """
        for prefix, module_id in self.callback_map.items():
            if callback_data.startswith(prefix):
                return self.modules.get(module_id)
        return None

    def get_all_modules(self) -> List[BaseModule]:
        """Получение списка всех загруженных модулей"""
        return list(self.modules.values())

    def get_loaded_count(self) -> int:
        """Получение количества загруженных модулей"""
        return len(self.modules)

    def get_errors(self) -> List[Dict]:
        """Получение списка ошибок загрузки"""
        return self._load_errors.copy()


# Глобальный экземпляр менеджера модулей
module_manager = ModuleManager()