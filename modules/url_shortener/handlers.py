"""Telegram handlers for the URL Shortener module."""

from __future__ import annotations

import asyncio
import html
from collections.abc import Callable
from typing import Any

from telebot import types

from core.database import DatabaseManager
from core.exceptions import handle_exception
from core.module_base import BaseModule
from core.observability import event_fields, get_logger
from modules.url_shortener.api_client import url_client
from modules.url_shortener.keyboards import (
    my_links_keyboard,
    result_menu_keyboard,
    url_shortener_menu_keyboard,
)

logger = get_logger(__name__)


class URLShortenerModule(BaseModule):
    """Shorten URLs and keep a private per-user history."""

    _PRIVATE_CALLBACKS = frozenset({"url_shorten", "url_my_links", "url_again"})
    _PRIVATE_CHAT_MESSAGE = (
        "Сокращение ссылок и личная история доступны только в приватном чате с ботом."
    )

    def __init__(
        self,
        module_id: str,
        name: str,
        description: str,
        icon: str,
        version: str,
        callback_prefix: str,
        *,
        database_factory: Callable[[], DatabaseManager] = DatabaseManager,
    ) -> None:
        super().__init__(module_id, name, description, icon, version, callback_prefix)
        self._database_factory = database_factory
        self._database_manager: DatabaseManager | None = None

    def _database(self) -> DatabaseManager:
        """Create storage only when a history operation actually needs it."""

        if self._database_manager is None:
            self._database_manager = self._database_factory()
        return self._database_manager

    def handle_entry(self, bot: Any, call: Any) -> None:
        """Show the module menu and bind state to the actor and chat."""

        chat_id = call.message.chat.id
        actor_id = call.from_user.id
        message_id = call.message.message_id
        self.set_interaction_state(actor_id, chat_id, "message_id", message_id)
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="🔗 <b>URL Shortener</b>\n\nВыберите действие:",
            reply_markup=url_shortener_menu_keyboard(show_back_button=True),
            parse_mode="HTML",
        )

    def handle_callback(self, bot: Any, call: Any) -> None:
        """Route module callbacks without exposing private history in groups."""

        chat_id = call.message.chat.id
        actor_id = call.from_user.id
        message_id = call.message.message_id
        callback_answered = False

        try:
            if call.data in self._PRIVATE_CALLBACKS and not self.require_private_chat(
                bot,
                call,
                message=self._PRIVATE_CHAT_MESSAGE,
            ):
                return

            if call.data == "url_back_to_modules":
                bot.answer_callback_query(call.id)
                callback_answered = True
                self._show_modules(bot, call)
                self.cleanup_interaction_state(actor_id, chat_id)
            elif call.data == "url_back_to_menu":
                bot.answer_callback_query(call.id)
                callback_answered = True
                self._show_menu(bot, chat_id, message_id)
            elif call.data in {"url_shorten", "url_again"}:
                bot.answer_callback_query(call.id)
                callback_answered = True
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="🔗 <b>URL Shortener</b>\n\nОтправьте ссылку для сокращения:",
                    reply_markup=None,
                    parse_mode="HTML",
                )
                bot.register_next_step_handler_by_chat_id(
                    chat_id,
                    self._process_url_input,
                    bot,
                )
            elif call.data == "url_my_links":
                bot.answer_callback_query(call.id)
                callback_answered = True
                self._show_user_links(bot, actor_id, chat_id, message_id)
            else:
                bot.answer_callback_query(call.id)
                callback_answered = True
        except Exception as error:
            user_message = handle_exception(
                error,
                logger,
                event="url_shortener.callback_failed",
                context={"actor_id": actor_id, "chat_id": chat_id},
            )
            try:
                if callback_answered:
                    bot.send_message(chat_id, user_message)
                else:
                    bot.answer_callback_query(call.id, user_message, show_alert=True)
            except Exception as response_error:
                handle_exception(
                    response_error,
                    logger,
                    event="url_shortener.callback_error_response_failed",
                    context={"actor_id": actor_id, "chat_id": chat_id},
                )

    def get_menu_keyboard(self) -> types.InlineKeyboardMarkup:
        """Return the module menu keyboard used by the global module list."""

        return url_shortener_menu_keyboard(show_back_button=False)

    def _process_url_input(self, message: Any, bot: Any) -> None:
        """Validate, shorten, persist, and render one private-chat URL."""

        chat_id = message.chat.id
        actor_id = message.from_user.id
        if getattr(message.chat, "type", None) != "private":
            bot.send_message(
                chat_id,
                "Эта операция доступна только в приватном чате с ботом.",
            )
            return

        url = (message.text or "").strip()
        try:
            bot.delete_message(chat_id, message.message_id)
        except Exception as error:
            handle_exception(
                error,
                logger,
                event="url_shortener.input_delete_failed",
                context={"actor_id": actor_id, "chat_id": chat_id},
            )

        message_id = self.get_interaction_state(actor_id, chat_id, "message_id")
        if message_id is None:
            from core.keyboards import back_to_main_keyboard

            bot.send_message(
                chat_id,
                "⚠️ Сессия устарела. Вернитесь в главное меню.",
                reply_markup=back_to_main_keyboard(),
            )
            return

        try:
            success, result = asyncio.run(url_client.shorten_url(url))
            if success:
                self._log_url_operation(actor_id, url, result)
                original_display = url if len(url) <= 50 else f"{url[:50]}..."
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=(
                        "🔗 <b>Исходная ссылка:</b>\n"
                        f"<code>{html.escape(original_display)}</code>\n\n"
                        "🔗 <b>Сокращённая ссылка:</b>\n"
                        f"<code>{html.escape(result)}</code>"
                    ),
                    reply_markup=result_menu_keyboard(result),
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
                return

            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=(
                    "❌ <b>Ошибка сокращения:</b>\n\n"
                    f"{html.escape(result)}\n\nПопробуйте другую ссылку."
                ),
                reply_markup=url_shortener_menu_keyboard(show_back_button=True),
                parse_mode="HTML",
            )
        except Exception as error:
            user_message = handle_exception(
                error,
                logger,
                event="url_shortener.input_failed",
                context={"actor_id": actor_id, "chat_id": chat_id},
            )
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"❌ <b>Ошибка при обработке:</b>\n{html.escape(user_message)}",
                reply_markup=url_shortener_menu_keyboard(show_back_button=True),
                parse_mode="HTML",
            )

    def _show_menu(self, bot: Any, chat_id: int, message_id: int) -> None:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="🔗 <b>URL Shortener</b>\n\nВыберите действие:",
            reply_markup=url_shortener_menu_keyboard(show_back_button=True),
            parse_mode="HTML",
        )

    def _show_modules(self, bot: Any, call: Any) -> None:
        from core.keyboards import modules_menu_keyboard
        from core.module_manager import module_manager

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="📦 <b>Доступные модули</b>\n\nВыберите модуль для работы:",
            reply_markup=modules_menu_keyboard(module_manager.get_all_modules()),
            parse_mode="HTML",
        )

    def _show_user_links(
        self,
        bot: Any,
        actor_id: int,
        chat_id: int,
        message_id: int,
    ) -> None:
        links = self._get_user_links(actor_id)
        lines = ["📋 <b>Мои ссылки</b>", ""]
        if not links:
            lines.extend(
                [
                    "⚠️ У вас пока нет сокращённых ссылок.",
                    "",
                    "Используйте «🔗 Сократить ссылку» для создания первой.",
                ]
            )
        else:
            lines.extend([f"Всего ссылок: {len(links)}", ""])
            for index, link in enumerate(links[:10], 1):
                original_url = str(link["original_url"])
                if len(original_url) > 60:
                    original_url = f"{original_url[:60]}..."
                created_at = html.escape(str(link["created_at"])[:10])
                shortened_url = html.escape(str(link["shortened_url"]))
                lines.extend(
                    [
                        f"{index}. {created_at}",
                        f"   Исходная: <code>{html.escape(original_url)}</code>",
                        f"   Сокращённая: <code>{shortened_url}</code>",
                        "",
                    ]
                )
            if len(links) > 10:
                lines.append(f"<i>... и ещё {len(links) - 10} ссылок</i>")

        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="\n".join(lines),
            reply_markup=my_links_keyboard(),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

    def _log_url_operation(
        self,
        user_id: int,
        original_url: str,
        shortened_url: str,
    ) -> None:
        """Persist one successful shortening operation."""

        try:
            with self._database().database.connection(write=True) as connection:
                connection.execute(
                    """
                    INSERT INTO url_shortener_logs (user_id, original_url, shortened_url)
                    VALUES (?, ?, ?)
                    """,
                    (user_id, original_url, shortened_url),
                )
        except Exception as error:
            handle_exception(
                error,
                logger,
                event="url_shortener.history_write_failed",
                context={"actor_id": user_id},
            )

    def _get_user_links(self, user_id: int) -> list[dict[str, Any]]:
        """Return the latest history entries for one Telegram actor."""

        try:
            with self._database().database.connection() as connection:
                rows = connection.execute(
                    """
                    SELECT original_url, shortened_url, created_at, clicks_count
                    FROM url_shortener_logs
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT 50
                    """,
                    (user_id,),
                ).fetchall()
            return [
                {
                    "original_url": row[0],
                    "shortened_url": row[1],
                    "created_at": row[2],
                    "clicks_count": row[3],
                }
                for row in rows
            ]
        except Exception as error:
            handle_exception(
                error,
                logger,
                event="url_shortener.history_read_failed",
                context={"actor_id": user_id},
            )
            return []

    def on_load(self, bot: Any) -> None:
        logger.info(
            "URL Shortener module loaded",
            extra=event_fields("url_shortener.loaded", module_version=self.version),
        )

    def on_unload(self, bot: Any) -> None:
        logger.info(
            "URL Shortener module unloaded",
            extra=event_fields("url_shortener.unloaded", module_version=self.version),
        )
