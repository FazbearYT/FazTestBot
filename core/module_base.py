# core/module_base.py
# Базовый класс для всех модулей FazTestBot
# Версия: 3.5
# Дата: 19.02.2026

from abc import ABC, abstractmethod
from telebot import types
from typing import Optional, Dict, Any


class BaseModule(ABC):
    """
    Абстрактный базовый класс для всех модулей FazTestBot.

    Все модули ДОЛЖНЫ наследоваться от этого класса и реализовывать
    обязательные методы. Это обеспечивает единообразие интерфейса
    и упрощает интеграцию новых модулей.
    """

    def __init__(
            self,
            module_id: str,
            name: str,
            description: str,
            icon: str,
            version: str = "1.0.0",
            callback_prefix: Optional[str] = None
    ):
        """
        Инициализация базового модуля.

        :param module_id: Уникальный идентификатор модуля (латиница, без пробелов)
        :param name: Отображаемое название модуля
        :param description: Краткое описание функционала
        :param icon: Эмодзи для визуального обозначения
        :param version: Версия модуля (семантическое версионирование)
        :param callback_prefix: Префикс для callback_data (по умолчанию module_id_)
        """
        self.id = module_id
        self.name = name
        self.description = description
        self.icon = icon
        self.version = version
        self.callback_prefix = callback_prefix or f"{module_id}_"
        self.user_state: Dict[int, Dict[str, Any]] = {}  # Состояния пользователей {user_id: state}

    @abstractmethod
    def handle_entry(self, bot: Any, call: Any) -> None:
        """
        ОБЯЗАТЕЛЬНО: Вход в модуль.

        Вызывается когда пользователь выбирает модуль из общего меню.
        Должен отображать главное меню модуля с доступными функциями.

        :param bot: Экземпляр TeleBot
        :param call: Объект CallbackQuery
        """
        pass

    @abstractmethod
    def handle_callback(self, bot: Any, call: Any) -> None:
        """
        ОБЯЗАТЕЛЬНО: Обработка колбэков внутри модуля.

        Вызывается при нажатии на любую кнопку с префиксом callback_prefix.
        Должен маршрутизировать запросы к соответствующим обработчикам.

        :param bot: Экземпляр TeleBot
        :param call: Объект CallbackQuery
        """
        pass

    @abstractmethod
    def get_menu_keyboard(self) -> types.InlineKeyboardMarkup:
        """
        ОБЯЗАТЕЛЬНО: Получение клавиатуры меню модуля.

        Возвращает Inline-клавиатуру с основными функциями модуля.

        :return: InlineKeyboardMarkup для меню модуля
        """
        pass

    def cleanup_user_state(self, user_id: int) -> None:
        """
        Очистка состояния пользователя при выходе из модуля.

        :param user_id: ID пользователя в Telegram
        """
        if user_id in self.user_state:
            del self.user_state[user_id]

    def get_user_state(self, user_id: int, key: Optional[str] = None, default: Any = None) -> Any:
        """
        Получение состояния пользователя.

        :param user_id: ID пользователя в Telegram
        :param key: Ключ состояния (если None, возвращается весь dict)
        :param default: Значение по умолчанию если ключ не найден
        :return: Значение состояния или default
        """
        if user_id not in self.user_state:
            self.user_state[user_id] = {}

        if key is None:
            return self.user_state[user_id]

        return self.user_state[user_id].get(key, default)

    def set_user_state(self, user_id: int, key: str, value: Any) -> None:
        """
        Установка значения состояния пользователя.

        :param user_id: ID пользователя в Telegram
        :param key: Ключ состояния
        :param value: Значение для сохранения
        """
        if user_id not in self.user_state:
            self.user_state[user_id] = {}

        self.user_state[user_id][key] = value

    def on_load(self, bot: Any) -> None:
        """
        ОПЦИОНАЛЬНО: Вызывается при загрузке модуля.

        Можно использовать для инициализации, проверки зависимостей,
        создания таблиц в БД и т.д.

        :param bot: Экземпляр TeleBot
        """
        pass

    def on_unload(self, bot: Any) -> None:
        """
        ОПЦИОНАЛЬНО: Вызывается при выгрузке модуля.

        Можно использовать для очистки ресурсов, сохранения состояния и т.д.

        :param bot: Экземпляр TeleBot
        """
        pass

    def validate(self) -> tuple:
        """
        Валидация модуля перед загрузкой.

        :return: (is_valid: bool, error_message: str)
        """
        if not self.id or not isinstance(self.id, str):
            return False, "module_id должен быть непустой строкой"

        if not self.name or not isinstance(self.name, str):
            return False, "name должен быть непустой строкой"

        if not self.icon or not isinstance(self.icon, str):
            return False, "icon должен быть непустой строкой (эмодзи)"

        # Проверка уникальности callback_prefix
        if not self.callback_prefix.endswith("_"):
            return False, "callback_prefix должен заканчиваться на '_'"

        return True, ""

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.id} name={self.name} version={self.version}>"