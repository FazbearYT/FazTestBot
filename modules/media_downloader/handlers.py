"""Deliberately disabled Media Downloader Telegram integration."""

from typing import Any

from telebot import types

from core.exceptions import handle_exception
from core.module_base import BaseModule, ModuleAdminSnapshot
from core.observability import event_fields, get_logger

from .keyboards import media_downloader_menu_keyboard

logger = get_logger(__name__)

DISABLED_MESSAGE = (
    "🚧 <b>Media Downloader</b>\n\n"
    "⚠️ <b>Модуль временно отключён</b>\n\n"
    "Загрузка медиа недоступна, пока её сетевой и файловый контур не будет "
    "переработан и проверен.\n\n"
    "<i>Возвращайтесь позже!</i>"
)


class MediaDownloaderModule(BaseModule):
    """Expose an honest placeholder without initializing download machinery."""

    def handle_entry(self, bot: Any, call: Any) -> None:
        actor_id = call.from_user.id
        chat_id = call.message.chat.id
        message_id = call.message.message_id
        self.set_interaction_state(actor_id, chat_id, "message_id", message_id)

        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=DISABLED_MESSAGE,
            reply_markup=self.get_menu_keyboard(),
            parse_mode="HTML",
        )

    def handle_callback(self, bot: Any, call: Any) -> None:
        actor_id = call.from_user.id
        chat_id = call.message.chat.id
        message_id = call.message.message_id

        try:
            if call.data == "media_back_to_modules":
                bot.answer_callback_query(call.id)
                self._show_module_list(bot, chat_id, message_id)
                self.cleanup_interaction_state(actor_id, chat_id)
                return

            bot.answer_callback_query(call.id, "⚠️ Модуль временно отключён", show_alert=True)
        except Exception as exc:
            handle_exception(
                exc,
                logger,
                event="media.callback_failed",
                context={"actor_id": actor_id, "chat_id": chat_id},
            )
            bot.answer_callback_query(call.id, "Сервис временно недоступен.", show_alert=True)

    @staticmethod
    def _show_module_list(bot: Any, chat_id: int, message_id: int) -> None:
        from core.module_manager import module_manager

        keyboard = types.InlineKeyboardMarkup(row_width=1)
        for module in module_manager.get_all_modules():
            keyboard.add(
                types.InlineKeyboardButton(
                    f"{module.icon} {module.name}", callback_data=f"module_{module.id}"
                )
            )
        keyboard.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_main"))
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="📦 <b>Доступные модули</b>\n\nВыберите модуль:",
            reply_markup=keyboard,
            parse_mode="HTML",
        )

    def get_menu_keyboard(self) -> types.InlineKeyboardMarkup:
        return media_downloader_menu_keyboard()

    def on_load(self, bot: Any) -> None:
        logger.warning(
            "disabled module loaded",
            extra=event_fields("media.module_loaded_disabled", version=self.version),
        )

    def on_unload(self, bot: Any) -> None:
        logger.info(
            "module unloaded",
            extra=event_fields("media.module_unloaded", version=self.version),
        )

    def get_admin_snapshot(self) -> ModuleAdminSnapshot:
        """Expose the deliberate disabled state to operators."""

        return ModuleAdminSnapshot(
            module_id=self.id,
            name=self.name,
            icon=self.icon,
            version=self.version,
            callback_prefix=self.callback_prefix,
            status="disabled",
            summary="media download backend is not enabled",
            active_state_count=self._state_store.count(),
        )
