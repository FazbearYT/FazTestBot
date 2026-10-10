# core/module_manager.py
# Менеджер модулей с автодискавери

import importlib
import os
from typing import Any

from .module_base import BaseModule, ModuleAdminSnapshot
from .observability import event_fields, get_logger

logger = get_logger(__name__)


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
        self.modules: dict[str, BaseModule] = {}  # {module_id: module_instance}
        self.callback_map: dict[str, str] = {}  # {callback_prefix: module_id}
        self._load_errors: list[dict] = []  # Ошибки загрузки для логирования

    def discover_and_load(self, bot: Any | None = None) -> int:
        """
        Автоматическое обнаружение и загрузка всех модулей.

        :param bot: Экземпляр TeleBot (для on_load)
        :return: Количество успешно загруженных модулей
        """
        loaded_count = 0

        # Сканируем папку modules/
        if not os.path.exists(self.modules_path):
            logger.warning(
                "modules directory not found: %s",
                self.modules_path,
                extra=event_fields("module.discovery_path_missing"),
            )
            return 0

        for item in sorted(os.listdir(self.modules_path)):
            item_path = os.path.join(self.modules_path, item)

            # Пропускаем не-директории и служебные папки
            if not os.path.isdir(item_path):
                continue
            if item.startswith("__") or item.startswith("."):
                continue
            # Ignore stale cache/data directories left after switching branches.
            # A discoverable Python module must be an explicit package.
            if not os.path.isfile(os.path.join(item_path, "__init__.py")):
                continue

            # Пытаемся загрузить модуль
            success = self._load_module(item, bot)
            if success:
                loaded_count += 1

        return loaded_count

    def _load_module(self, module_name: str, bot: Any | None) -> bool:
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
                    # Do not expose a half-loaded module in menus or callback
                    # routing when its startup hook failed.
                    self.modules.pop(module_instance.id, None)
                    self.callback_map.pop(module_instance.callback_prefix, None)
                    self._log_error(module_name, f"Ошибка on_load: {str(e)}", exception=e)
                    return False

            logger.info(
                "module loaded: %s v%s",
                module_instance.name,
                module_instance.version,
                extra=event_fields(
                    "module.loaded",
                    module_id=module_instance.id,
                    module_version=module_instance.version,
                ),
            )
            return True

        except Exception as e:
            self._log_error(module_name, f"Исключение при загрузке: {str(e)}", exception=e)
            return False

    def _log_error(
        self,
        module_name: str,
        error_msg: str,
        *,
        exception: Exception | None = None,
    ):
        """Логирование ошибки загрузки модуля"""
        import datetime

        error = {
            "module": module_name,
            "error": error_msg,
            "timestamp": datetime.datetime.now().isoformat(),
        }
        self._load_errors.append(error)
        exc_info = None
        if exception is not None:
            exc_info = (type(exception), exception, exception.__traceback__)
        logger.error(
            "module %s failed to load: %s",
            module_name,
            error_msg,
            exc_info=exc_info,
            extra=event_fields("module.load_failed", module_id=module_name),
        )

    def get_module_by_id(self, module_id: str) -> BaseModule | None:
        """Получение модуля по ID"""
        return self.modules.get(module_id)

    def get_module_by_callback(self, callback_data: str) -> BaseModule | None:
        """
        Получение модуля по callback_data.

        :param callback_data: Данные колбэка
        :return: Модуль или None
        """
        for prefix, module_id in self.callback_map.items():
            if callback_data.startswith(prefix):
                return self.modules.get(module_id)
        return None

    def get_all_modules(self) -> list[BaseModule]:
        """Получение списка всех загруженных модулей"""
        return list(self.modules.values())

    def get_loaded_count(self) -> int:
        """Получение количества загруженных модулей"""
        return len(self.modules)

    def get_admin_snapshots(self) -> list[ModuleAdminSnapshot]:
        """Return stable, sorted operational summaries for loaded modules."""

        snapshots = []
        for module in self.modules.values():
            try:
                snapshots.append(module.get_admin_snapshot())
            except Exception as error:
                logger.warning(
                    "module %s admin snapshot failed",
                    module.id,
                    exc_info=(type(error), error, error.__traceback__),
                    extra=event_fields("module.admin_snapshot_failed", module_id=module.id),
                )
                snapshots.append(
                    ModuleAdminSnapshot(
                        module_id=module.id,
                        name=module.name,
                        icon=module.icon,
                        version=module.version,
                        callback_prefix=module.callback_prefix,
                        status="error",
                        summary="operational snapshot unavailable",
                        active_state_count=0,
                    )
                )

        loaded_ids = {snapshot.module_id for snapshot in snapshots}
        for failure in self._load_errors:
            module_id = str(failure["module"])
            if module_id in loaded_ids:
                continue
            snapshots.append(
                ModuleAdminSnapshot(
                    module_id=module_id,
                    name=module_id,
                    icon="⚠️",
                    version="unknown",
                    callback_prefix="",
                    status="error",
                    summary="module failed to load",
                    active_state_count=0,
                )
            )
        return sorted(snapshots, key=lambda snapshot: snapshot.module_id)

    def get_errors(self) -> list[dict]:
        """Получение списка ошибок загрузки"""
        return self._load_errors.copy()


# Глобальный экземпляр менеджера модулей
module_manager = ModuleManager()
