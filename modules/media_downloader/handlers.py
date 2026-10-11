# modules/media_downloader/handlers.py
# Обработчики модуля "Media Downloader"

from typing import Any

from telebot import types

from core.database import DatabaseManager
from core.exceptions import handle_exception
from core.module_base import BaseModule
from core.observability import event_fields, get_logger

from .keyboards import (
    media_downloader_menu_keyboard,
)

db = DatabaseManager()
logger = get_logger(__name__)


class MediaDownloaderModule(BaseModule):
    """Модуль загрузки медиа - ВРЕМЕННО ОТКЛЮЧЁН"""

    def handle_entry(self, bot: Any, call: Any) -> None:
        """Вход в модуль - ЗАГЛУШКА"""
        actor_id = call.from_user.id
        chat_id = call.message.chat.id
        message_id = call.message.message_id

        self.set_interaction_state(actor_id, chat_id, "message_id", message_id)

        # Создаём клавиатуру с кнопкой возврата
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(types.InlineKeyboardButton("🔙 К списку модулей", callback_data="back_to_modules"))

        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="🚧 <b>Media Downloader</b>\n\n"
            "⚠️ <b>Модуль временно отключён</b>\n\n"
            "К сожалению, модуль загрузки видео находится в разработке.\n"
            "Мы столкнулись с техническими сложностями:\n\n"
            "• Проблемы с pytubefix (Maximum retries exceeded)\n"
            "• Ошибки скачивания adaptive streams\n"
            "• Нестабильная работа YouTube API\n\n"
            "Модуль отправлен в долгий ящик до появления стабильных решений.\n\n"
            "<i>Возвращайтесь позже!</i>",
            reply_markup=kb,
            parse_mode="HTML",
        )

    def handle_callback(self, bot: Any, call: Any) -> None:
        """Обработка колбэков - ЗАГЛУШКА"""
        actor_id = call.from_user.id
        chat_id = call.message.chat.id
        message_id = call.message.message_id

        try:
            bot.answer_callback_query(call.id)

            # Назад к списку модулей
            if call.data == "media_back_to_modules":
                from core.module_manager import module_manager

                modules = module_manager.get_all_modules()

                kb = types.InlineKeyboardMarkup(row_width=1)
                for module in modules:
                    kb.add(
                        types.InlineKeyboardButton(
                            f"{module.icon} {module.name}", callback_data=f"module_{module.id}"
                        )
                    )
                kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_main"))

                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="📦 <b>Доступные модули</b>\n\nВыберите модуль:",
                    reply_markup=kb,
                    parse_mode="HTML",
                )
                self.cleanup_interaction_state(actor_id, chat_id)
                return

            # Назад в меню
            if call.data == "media_back_to_menu":
                # Создаём клавиатуру с кнопкой возврата
                kb = types.InlineKeyboardMarkup(row_width=1)
                kb.add(
                    types.InlineKeyboardButton(
                        "🔙 К списку модулей", callback_data="back_to_modules"
                    )
                )

                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="🚧 <b>Media Downloader</b>\n\n"
                    "⚠️ <b>Модуль временно отключён</b>\n\n"
                    "К сожалению, модуль находится в разработке.\n"
                    "Мы столкнулись с техническими сложностями.\n\n"
                    "<i>Возвращайтесь позже!</i>",
                    reply_markup=kb,
                    parse_mode="HTML",
                )
                return

            # Все остальные кнопки - заглушка
            if (
                call.data in ["media_video", "media_audio", "media_my_downloads"]
                or call.data.startswith("media_quality_")
                or call.data == "media_again"
            ):
                bot.answer_callback_query(call.id, "⚠️ Модуль временно отключён", show_alert=True)
                return

        except Exception as exc:
            handle_exception(
                exc,
                logger,
                event="media.callback_failed",
                context={"actor_id": actor_id, "chat_id": chat_id},
            )
            bot.answer_callback_query(call.id, "Сервис временно недоступен.", show_alert=True)

    def get_menu_keyboard(self) -> types.InlineKeyboardMarkup:
        """Клавиатура меню"""
        return media_downloader_menu_keyboard()

    def _process_url_input(self, message, bot):
        """Обработка ввода URL - ЗАГЛУШКА"""
        chat_id = message.chat.id

        # Создаём клавиатуру с кнопкой возврата
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(types.InlineKeyboardButton("🔙 К списку модулей", callback_data="back_to_modules"))

        bot.send_message(
            chat_id,
            "🚧 <b>Модуль временно отключён</b>\n\n"
            "К сожалению, модуль загрузки видео находится в разработке.\n"
            "Мы столкнулись с техническими сложностями.\n\n"
            "<i>Возвращайтесь позже!</i>",
            reply_markup=kb,
            parse_mode="HTML",
        )

    def _check_download_limit(self, user_id: int) -> bool:
        """Проверка лимита"""
        return False  # Всегда false - модуль отключён

    def _log_download(
        self,
        user_id: int,
        url: str,
        media_type: str,
        platform: str,
        title: str,
        file_path: str,
        file_size: int,
        quality: str,
    ):
        """Логирование"""
        pass  # Не логируем - модуль отключён

    def _get_user_downloads(self, user_id: int) -> list:
        """Получение истории"""
        return []  # Пустой список - модуль отключён

    def on_load(self, bot: Any) -> None:
        """Загрузка модуля"""
        logger.warning(
            "disabled module loaded",
            extra=event_fields("media.module_loaded_disabled", version=self.version),
        )

    def on_unload(self, bot: Any) -> None:
        """Выгрузка модуля"""
        logger.info(
            "module unloaded",
            extra=event_fields("media.module_unloaded", version=self.version),
        )
