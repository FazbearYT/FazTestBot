# core/module_base.py
# Базовый класс для всех модулей FazTestBot

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from telebot import types

from core.state import InteractionScope, TransientStateStore


@dataclass(frozen=True, slots=True)
class ModuleMetric:
    """One bounded, non-sensitive aggregate exposed by a module."""

    key: str
    label: str
    value: int | float | str | bool


@dataclass(frozen=True, slots=True)
class ModuleAdminSnapshot:
    """Non-sensitive module state exposed to operational interfaces."""

    module_id: str
    name: str
    icon: str
    version: str
    callback_prefix: str
    status: str
    summary: str
    active_state_count: int
    metrics: tuple[ModuleMetric, ...] = ()


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
        callback_prefix: str | None = None,
        state_store: TransientStateStore | None = None,
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
        self._state_store = state_store or TransientStateStore()

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
        self.cleanup_interaction_state(user_id, user_id)

    def get_user_state(self, user_id: int, key: str | None = None, default: Any = None) -> Any:
        """
        Получение состояния пользователя.

        :param user_id: ID пользователя в Telegram
        :param key: Ключ состояния (если None, возвращается весь dict)
        :param default: Значение по умолчанию если ключ не найден
        :return: Значение состояния или default
        """
        if key is None:
            return self._state_store.get_all(InteractionScope(user_id, user_id))

        return self.get_interaction_state(user_id, user_id, key, default)

    def set_user_state(self, user_id: int, key: str, value: Any) -> None:
        """
        Установка значения состояния пользователя.

        :param user_id: ID пользователя в Telegram
        :param key: Ключ состояния
        :param value: Значение для сохранения
        """
        self.set_interaction_state(user_id, user_id, key, value)

    def get_interaction_state(
        self,
        actor_id: int,
        chat_id: int,
        key: str,
        default: Any = None,
    ) -> Any:
        """Read state isolated by both Telegram actor and chat."""

        return self._state_store.get(InteractionScope(actor_id, chat_id), key, default)

    def set_interaction_state(
        self,
        actor_id: int,
        chat_id: int,
        key: str,
        value: Any,
    ) -> None:
        """Store state isolated by both Telegram actor and chat."""

        self._state_store.set(InteractionScope(actor_id, chat_id), key, value)

    def cleanup_interaction_state(self, actor_id: int, chat_id: int) -> None:
        """Remove all transient state for one actor/chat interaction."""

        self._state_store.clear(InteractionScope(actor_id, chat_id))

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

    def get_admin_snapshot(self) -> ModuleAdminSnapshot:
        """Return the module's safe operational summary for admin tooling."""

        return ModuleAdminSnapshot(
            module_id=self.id,
            name=self.name,
            icon=self.icon,
            version=self.version,
            callback_prefix=self.callback_prefix,
            status="ok",
            summary="module loaded",
            active_state_count=self._state_store.count(),
        )

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
