"""Telegram handlers for the IP Lookup module."""

from __future__ import annotations

import asyncio
import html
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any

from telebot import types

from core.database import DatabaseManager
from core.exceptions import handle_exception
from core.module_base import BaseModule
from core.observability import event_fields, get_logger
from modules.ip_lookup.api_client import ip_client
from modules.ip_lookup.config import MAX_LOOKUPS_PER_USER_PER_DAY, TABLE_NAME
from modules.ip_lookup.keyboards import (
    history_keyboard,
    ip_lookup_menu_keyboard,
    search_result_keyboard,
)

logger = get_logger(__name__)


class IPLookupModule(BaseModule):
    """Resolve IP metadata and keep a private per-user lookup history."""

    _PRIVATE_CALLBACKS = frozenset({"ip_search", "ip_history", "ip_search_again"})
    _PRIVATE_CHAT_MESSAGE = "Поиск IP и личная история доступны только в приватном чате с ботом."

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
            text=(
                "🌍 <b>IP Info Lookup</b>\n\n"
                "Получение информации об IP адресе:\n"
                "• Страна и город\n"
                "• Провайдер (ISP)\n"
                "• Часовой пояс\n"
                "• Координаты\n\n"
                f"Лимит: {MAX_LOOKUPS_PER_USER_PER_DAY} запросов/день\n\n"
                "Выберите действие:"
            ),
            reply_markup=self.get_menu_keyboard(),
            parse_mode="HTML",
        )

    def handle_callback(self, bot: Any, call: Any) -> None:
        """Route callbacks without exposing personal history in shared chats."""

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

            bot.answer_callback_query(call.id)
            callback_answered = True
            if call.data == "ip_back_to_modules":
                self._show_modules(bot, call)
                self.cleanup_interaction_state(actor_id, chat_id)
            elif call.data == "ip_back_to_menu":
                self._show_menu(bot, chat_id, message_id)
            elif call.data in {"ip_search", "ip_search_again"}:
                self.set_interaction_state(actor_id, chat_id, "query_type", "search")
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=(
                        "🔍 <b>Поиск IP</b>\n\n"
                        "Отправьте IPv4 или IPv6 адрес:\n"
                        "• IPv4: 8.8.8.8\n"
                        "• IPv6: 2001:4860:4860::8888"
                    ),
                    reply_markup=None,
                    parse_mode="HTML",
                )
                bot.register_next_step_handler_by_chat_id(
                    chat_id,
                    self._process_ip_input,
                    bot,
                )
            elif call.data == "ip_history":
                self._show_history(bot, actor_id, chat_id, message_id)
        except Exception as error:
            user_message = handle_exception(
                error,
                logger,
                event="ip_lookup.callback_failed",
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
                    event="ip_lookup.callback_error_response_failed",
                    context={"actor_id": actor_id, "chat_id": chat_id},
                )

    def get_menu_keyboard(self) -> types.InlineKeyboardMarkup:
        """Return the module menu keyboard."""

        return ip_lookup_menu_keyboard()

    def _process_ip_input(self, message: Any, bot: Any) -> None:
        """Validate, resolve, persist, and render one private-chat IP query."""

        chat_id = message.chat.id
        actor_id = message.from_user.id
        if getattr(message.chat, "type", None) != "private":
            bot.send_message(
                chat_id,
                "Эта операция доступна только в приватном чате с ботом.",
            )
            return

        query = (message.text or "").strip()
        try:
            bot.delete_message(chat_id, message.message_id)
        except Exception as error:
            handle_exception(
                error,
                logger,
                event="ip_lookup.input_delete_failed",
                context={"actor_id": actor_id, "chat_id": chat_id},
            )

        message_id = self.get_interaction_state(actor_id, chat_id, "message_id")
        if message_id is None:
            bot.send_message(
                chat_id,
                "⚠️ Сессия устарела. Вернитесь в главное меню.",
                reply_markup=ip_lookup_menu_keyboard(),
            )
            return

        try:
            if not self._check_lookup_limit(actor_id):
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=(
                        "⚠️ <b>Лимит запросов</b>\n\n"
                        f"Вы достигли лимита ({MAX_LOOKUPS_PER_USER_PER_DAY}/день).\n\n"
                        "Попробуйте завтра."
                    ),
                    reply_markup=ip_lookup_menu_keyboard(),
                    parse_mode="HTML",
                )
                return

            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="⏳ <b>Запрос информации...</b>",
                reply_markup=None,
                parse_mode="HTML",
            )
            success, info = asyncio.run(ip_client.get_ip_info(query))
            if success:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=self._format_ip_info(info),
                    reply_markup=search_result_keyboard(query),
                    parse_mode="HTML",
                )
                self._log_lookup(actor_id, query, info)
                return

            error_message = str(info.get("error", "❌ Не удалось выполнить запрос"))
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"❌ <b>Ошибка</b>\n\n{html.escape(error_message)}",
                reply_markup=ip_lookup_menu_keyboard(),
                parse_mode="HTML",
            )
        except Exception as error:
            user_message = handle_exception(
                error,
                logger,
                event="ip_lookup.input_failed",
                context={"actor_id": actor_id, "chat_id": chat_id},
            )
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"❌ <b>Ошибка при обработке:</b>\n{html.escape(user_message)}",
                reply_markup=ip_lookup_menu_keyboard(),
                parse_mode="HTML",
            )

    @staticmethod
    def _format_ip_info(info: Mapping[str, Any]) -> str:
        """Return bounded, HTML-safe provider data for Telegram."""

        def safe(key: str) -> str:
            return html.escape(str(info.get(key, "Unknown"))[:60])

        isp = str(info.get("isp", "Unknown"))
        if len(isp) > 100:
            isp = f"{isp[:100]}..."
        lines = [
            "🌍 <b>Информация об IP</b>",
            "",
            f"📍 <b>IP:</b> <code>{safe('ip')}</code>",
            f"🏙️ <b>Город:</b> {safe('city')}",
            f"📍 <b>Регион:</b> {safe('region')}",
            f"🌐 <b>Страна:</b> {safe('country')} ({safe('country_code')})",
            f"📡 <b>Провайдер:</b> {html.escape(isp)}",
            f"🕐 <b>Часовой пояс:</b> {safe('timezone')}",
            f"📮 <b>Почтовый индекс:</b> {safe('postal')}",
            f"🌐 <b>ASN:</b> {safe('asn')}",
        ]
        latitude = info.get("latitude", "Unknown")
        longitude = info.get("longitude", "Unknown")
        if latitude != "Unknown" and longitude != "Unknown":
            lines.append(
                "📍 <b>Координаты:</b> "
                f"{html.escape(str(latitude)[:32])}, {html.escape(str(longitude)[:32])}"
            )
        lines.extend(["", f"📊 <b>Источник:</b> {safe('source')}"])
        return "\n".join(lines)

    def _check_lookup_limit(self, user_id: int) -> bool:
        """Return whether one actor remains below the configured daily limit."""

        today = datetime.now(timezone.utc).date().isoformat()
        with self._database().database.connection() as connection:
            count = connection.execute(
                f"""
                SELECT COUNT(*) FROM {TABLE_NAME}
                WHERE user_id = ? AND DATE(created_at) = ?
                """,
                (user_id, today),
            ).fetchone()[0]
        return count < MAX_LOOKUPS_PER_USER_PER_DAY

    def _log_lookup(self, user_id: int, query: str, info: Mapping[str, Any]) -> None:
        """Persist one successful lookup without interrupting its response."""

        try:
            with self._database().database.connection(write=True) as connection:
                connection.execute(
                    f"""
                    INSERT INTO {TABLE_NAME}
                    (user_id, query, ip, city, country, isp)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        query,
                        info.get("ip", query),
                        info.get("city", "Unknown"),
                        info.get("country", "Unknown"),
                        info.get("isp", "Unknown"),
                    ),
                )
        except Exception as error:
            handle_exception(
                error,
                logger,
                event="ip_lookup.history_write_failed",
                context={"actor_id": user_id},
            )

    def _get_user_lookups(self, user_id: int) -> list[dict[str, Any]]:
        """Return the latest lookup history for one Telegram actor."""

        with self._database().database.connection() as connection:
            rows = connection.execute(
                f"""
                SELECT query, ip, city, country, isp, created_at
                FROM {TABLE_NAME}
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 50
                """,
                (user_id,),
            ).fetchall()
        return [
            {
                "query": row[0],
                "ip": row[1],
                "city": row[2],
                "country": row[3],
                "isp": row[4],
                "created_at": row[5],
            }
            for row in rows
        ]

    def _show_menu(self, bot: Any, chat_id: int, message_id: int) -> None:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="🌍 <b>IP Info Lookup</b>\n\nВыберите действие:",
            reply_markup=ip_lookup_menu_keyboard(),
            parse_mode="HTML",
        )

    def _show_modules(self, bot: Any, call: Any) -> None:
        from core.keyboards import modules_menu_keyboard
        from core.module_manager import module_manager

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="📦 <b>Доступные модули</b>\n\nВыберите модуль:",
            reply_markup=modules_menu_keyboard(module_manager.get_all_modules()),
            parse_mode="HTML",
        )

    def _show_history(
        self,
        bot: Any,
        actor_id: int,
        chat_id: int,
        message_id: int,
    ) -> None:
        lookups = self._get_user_lookups(actor_id)
        lines = ["📋 <b>История запросов</b>", ""]
        if not lookups:
            lines.extend(
                [
                    "⚠️ У вас пока нет запросов.",
                    "",
                    "Используйте «🔍 Поиск IP» для первого запроса.",
                ]
            )
        else:
            lines.extend([f"Всего запросов: {len(lookups)}", ""])
            displayed = 0
            for index, lookup in enumerate(lookups[:10], 1):
                query = html.escape(str(lookup.get("query", "?"))[:60])
                city = html.escape(str(lookup.get("city", "?"))[:60])
                country = html.escape(str(lookup.get("country", "?"))[:60])
                isp = html.escape(str(lookup.get("isp", "?"))[:100])
                created_at = html.escape(str(lookup.get("created_at", ""))[:16])
                entry = [
                    f"{index}. {query}",
                    f"   🌍 {city}, {country}",
                    f"   📡 {isp}",
                    f"   {created_at}",
                    "",
                ]
                if len("\n".join([*lines, *entry])) > 3500:
                    break
                lines.extend(entry)
                displayed += 1
            if len(lookups) > displayed:
                lines.append(f"<i>... и ещё {len(lookups) - displayed} запросов</i>")

        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="\n".join(lines),
            reply_markup=history_keyboard(),
            parse_mode="HTML",
        )

    def on_load(self, bot: Any) -> None:
        logger.info(
            "IP Lookup module loaded",
            extra=event_fields("ip_lookup.loaded", module_version=self.version),
        )

    def on_unload(self, bot: Any) -> None:
        logger.info(
            "IP Lookup module unloaded",
            extra=event_fields("ip_lookup.unloaded", module_version=self.version),
        )
