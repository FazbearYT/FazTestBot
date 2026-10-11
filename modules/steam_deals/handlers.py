# modules/steam_deals/handlers.py
# Обработчики модуля "Steam Deals Tracker"

import asyncio
import html
from datetime import datetime
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from telebot import types
from telebot.apihelper import ApiTelegramException

from core.database import DatabaseManager
from core.exceptions import handle_exception
from core.module_base import BaseModule
from core.observability import event_fields, get_logger

from .api_client import steam_client
from .config import (
    MAX_WISHLIST_DISPLAY,
    MAX_WISHLIST_GAMES,
    REFRESH_CONCURRENCY,
    STEAM_APP_URL,
    STEAM_NOTIFY_ENABLED,
    STEAM_NOTIFY_INTERVAL_HOURS,
    WISHLIST_TABLE,
)
from .keyboards import (
    add_game_keyboard,
    confirm_delete_keyboard,
    free_games_keyboard,
    steam_main_menu_keyboard,
    wishlist_keyboard,
)

db = DatabaseManager()
logger = get_logger(__name__)


class SteamDealsModule(BaseModule):
    """
    Модуль отслеживания скидок на игры в Steam.

    Поддерживает:
    - Вишлист с отслеживанием цен
    - Бесплатные игры
    - Поиск и добавление игр
    """

    def __init__(self, module_id, name, description, icon, version, callback_prefix):
        """Инициализация модуля Steam Deals Tracker"""
        super().__init__(module_id, name, description, icon, version, callback_prefix)

    def handle_entry(self, bot: Any, call: Any) -> None:
        """Вход в модуль"""
        actor_id = call.from_user.id
        chat_id = call.message.chat.id
        message_id = call.message.message_id

        self.set_interaction_state(actor_id, chat_id, "message_id", message_id)
        # Сбрасываем состояние действия
        self.set_interaction_state(actor_id, chat_id, "action", None)
        self.set_interaction_state(actor_id, chat_id, "search_results", None)

        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="🎮 <b>Steam Deals Tracker</b>\n\n"
            "Отслеживание скидок на игры в Steam:\n\n"
            "📜 <b>Мой вишлист</b> — отслеживаемые игры\n"
            "🎁 <b>Бесплатно</b> — игры 100% OFF\n\n"
            "Выберите действие:",
            reply_markup=self.get_menu_keyboard(),
            parse_mode="HTML",
        )

    def handle_callback(self, bot: Any, call: Any) -> None:
        """Обработка колбэков"""
        actor_id = call.from_user.id
        chat_id = call.message.chat.id
        message_id = call.message.message_id

        try:
            bot.answer_callback_query(call.id)

            # Сбрасываем состояние при любом действии с клавиатурой
            self.set_interaction_state(actor_id, chat_id, "action", None)
            self.set_interaction_state(actor_id, chat_id, "search_results", None)

            # Назад к списку модулей
            if call.data == "steam_back_to_modules":
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

            # Назад в меню модуля
            if call.data == "steam_back_to_menu":
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="🎮 <b>Steam Deals Tracker</b>\n\nВыберите действие:",
                    reply_markup=steam_main_menu_keyboard(),
                    parse_mode="HTML",
                )
                return

            # Мой вишлист
            if call.data == "steam_wishlist":
                if not self._require_private_chat(bot, call):
                    return
                self._show_wishlist(bot, actor_id, chat_id, message_id)
                return

            # Обновить вишлист
            if call.data == "steam_wishlist_refresh":
                if not self._require_private_chat(bot, call):
                    return
                self._show_wishlist(bot, actor_id, chat_id, message_id, force_refresh=True)
                return

            # Удалить игру
            if call.data == "steam_wishlist_delete":
                if not self._require_private_chat(bot, call):
                    return
                self.set_interaction_state(actor_id, chat_id, "action", "delete_game")
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="❌ <b>Удаление игры</b>\n\n"
                    "Введите номер игры для удаления:\n\n"
                    "<i>Пример: 1</i>",
                    reply_markup=confirm_delete_keyboard(),
                    parse_mode="HTML",
                )
                bot.register_next_step_handler_by_chat_id(chat_id, self._handle_delete_input, bot)
                return

            # Добавить игру из вишлиста
            if call.data == "steam_add_from_wishlist":
                if not self._require_private_chat(bot, call):
                    return
                self.set_interaction_state(actor_id, chat_id, "action", "add_game")
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="➕ <b>Добавить игру</b>\n\n"
                    "Введите название игры или ссылку на Steam:\n\n"
                    "<i>Пример: Cyberpunk 2077</i>",
                    reply_markup=add_game_keyboard(),
                    parse_mode="HTML",
                )
                bot.register_next_step_handler_by_chat_id(chat_id, self._handle_add_input, bot)
                return

            # Бесплатные игры
            if call.data == "steam_free":
                self._show_free_games(bot, chat_id, message_id)
                return

            # Обновить бесплатные
            if call.data == "steam_free_refresh":
                steam_client.invalidate_cache("free_games")

                # ИСПРАВЛЕНО: Показываем заново с правильным message_id
                self._try_delete_message(bot, chat_id, message_id)

                # Отправляем новое сообщение
                self._show_free_games(bot, chat_id, None)
                return

        except Exception as exc:
            handle_exception(
                exc,
                logger,
                event="steam.callback_failed",
                context={"actor_id": actor_id, "chat_id": chat_id},
            )
            bot.answer_callback_query(call.id, "Сервис временно недоступен.", show_alert=True)

    @staticmethod
    def _require_private_chat(bot: Any, call: Any) -> bool:
        """Keep personal wishlist conversations out of shared chats."""

        chat = call.message.chat
        if getattr(chat, "type", "private") == "private":
            return True
        bot.answer_callback_query(
            call.id,
            "Личный вишлист доступен только в приватном чате с ботом.",
            show_alert=True,
        )
        return False

    @staticmethod
    def _try_delete_message(bot: Any, chat_id: int, message_id: int) -> None:
        try:
            bot.delete_message(chat_id, message_id)
        except ApiTelegramException as exc:
            logger.info(
                "%s",
                type(exc).__name__,
                extra=event_fields("steam.message_delete_skipped", chat_id=chat_id),
            )

    def get_menu_keyboard(self) -> types.InlineKeyboardMarkup:
        """Клавиатура меню"""
        return steam_main_menu_keyboard()

    def _run_async(self, coro):
        """Запуск асинхронной корутины из синхронного обработчика"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def _safe_edit(self, bot: Any, **kwargs) -> None:
        """
        Редактирование сообщения с игнорированием "message is not modified".

        Telegram отвечает ошибкой 400, если новый текст и клавиатура
        полностью совпадают с текущими. Для кнопки "Обновить" это нормально.
        """
        if kwargs.get("message_id") is None:
            send_kwargs = dict(kwargs)
            send_kwargs.pop("message_id", None)
            chat_id = send_kwargs.pop("chat_id")
            bot.send_message(chat_id, **send_kwargs)
            return
        try:
            bot.edit_message_text(**kwargs)
        except ApiTelegramException as e:
            if "message is not modified" in str(e):
                return
            raise

    def _fetch_price_for_add(self, game: dict):
        """
        Цена игры в Steam (тенге) для добавления в вишлист.

        Исторический минимум стартует с текущей цены и далее снижается
        при обновлениях.

        :param game: Результат поиска CheapShark (содержит steamAppID)
        :return: (current_price_kzt, historical_low_kzt, discount_percent, steam_app_id)
        """
        self._run_async(steam_client.ensure_rate())

        steam_app_id = game.get("steamAppID")
        if not steam_app_id:
            return 0.0, 0.0, 0.0, None

        price = self._run_async(steam_client.get_appdetails_price(steam_app_id))

        if price and price.get("available"):
            current = price["price_kzt"]
            return current, current, price["discount_percent"], steam_app_id

        return 0.0, 0.0, 0.0, steam_app_id

    def _show_wishlist(
        self,
        bot: Any,
        actor_id: int,
        chat_id: int,
        message_id: int,
        force_refresh: bool = False,
    ):
        """Показ вишлиста пользователя"""
        try:
            self._run_async(steam_client.ensure_rate())

            if force_refresh:
                self._refresh_wishlist_prices(actor_id)

            wishlist = self._get_user_wishlist(actor_id)

            if not wishlist:
                self._safe_edit(
                    bot,
                    chat_id=chat_id,
                    message_id=message_id,
                    text="📜 <b>Мой вишлист</b>\n\n"
                    "⚠️ Список пуст.\n\n"
                    "Используйте «➕ Добавить игру» для добавления.",
                    reply_markup=wishlist_keyboard(is_empty=True),
                    parse_mode="HTML",
                )
                return

            # Формируем список
            text = "📜 <b>Мой вишлист</b>\n\n"
            text += f"Всего игр: {len(wishlist)}\n\n"

            for i, game in enumerate(wishlist[:MAX_WISHLIST_DISPLAY], 1):
                name = html.escape(game["game_name"][:40])
                discount = (
                    steam_client.format_discount(game["discount_percent"])
                    if game["discount_percent"]
                    else "0%"
                )

                if game["current_price"]:
                    price_kzt = steam_client.format_price_kzt(game["current_price"])
                    price_rub = steam_client.format_price_rub(game["current_price"])
                    price = f"{price_kzt} ({price_rub})"
                else:
                    price = "N/A"

                low = (
                    steam_client.format_price_kzt(game["historical_low"])
                    if game["historical_low"]
                    else "N/A"
                )

                alert = ""
                if game["current_price"] and game["historical_low"]:
                    if steam_client.check_price_alert(
                        game["current_price"], game["historical_low"]
                    ):
                        alert = " ⚠️"

                text += f"{i}. <b>{name}</b>\n"
                text += f"   💰 {price} · скидка {discount} · 📉 мин: {low}{alert}\n"

            if len(wishlist) > MAX_WISHLIST_DISPLAY:
                text += f"\n<i>... и ещё {len(wishlist) - MAX_WISHLIST_DISPLAY} игр</i>"

            if force_refresh:
                text += f"\n<i>🕐 Обновлено: {datetime.now().strftime('%H:%M:%S')}</i>"

            self._safe_edit(
                bot,
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=wishlist_keyboard(),
                parse_mode="HTML",
            )

        except Exception as exc:
            handle_exception(
                exc,
                logger,
                event="steam.wishlist_render_failed",
                context={"actor_id": actor_id, "chat_id": chat_id},
            )
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="❌ <b>Ошибка</b>\n\nСервис временно недоступен.",
                reply_markup=steam_main_menu_keyboard(),
                parse_mode="HTML",
            )

    def _show_free_games(self, bot: Any, chat_id: int, message_id: int):
        """Показ бесплатных игр"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            games = loop.run_until_complete(steam_client.get_free_games())
            loop.close()

            if not games:
                self._safe_edit(
                    bot,
                    chat_id=chat_id,
                    message_id=message_id,
                    text="🎁 <b>Бесплатно (100% OFF)</b>\n\n"
                    "⚠️ Сейчас нет бесплатных игр.\n\n"
                    f"<i>🕐 Проверено: {datetime.now().strftime('%H:%M:%S')}</i>",
                    reply_markup=free_games_keyboard(),
                    parse_mode="HTML",
                )
                return

            # Формируем список
            text = "🎁 <b>Бесплатно (100% OFF)</b>\n\n"
            text += f"Всего: {len(games)}\n\n"

            for i, game in enumerate(games[:20], 1):
                name = html.escape(game.get("name", "Unknown")[:50])
                app_id = game.get("app_id")
                if app_id:
                    text += f'{i}. <a href="{STEAM_APP_URL}{app_id}">{name}</a>\n'
                else:
                    text += f"{i}. {name}\n"

            text += f"\n<i>🕐 Проверено: {datetime.now().strftime('%H:%M:%S')}</i>"

            self._safe_edit(
                bot,
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=free_games_keyboard(),
                parse_mode="HTML",
                disable_web_page_preview=True,
            )

        except Exception as exc:
            handle_exception(
                exc,
                logger,
                event="steam.free_games_render_failed",
                context={"chat_id": chat_id},
            )
            error_text = "❌ <b>Ошибка</b>\n\nСервис временно недоступен."
            if message_id:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=error_text,
                    reply_markup=steam_main_menu_keyboard(),
                    parse_mode="HTML",
                )
            else:
                bot.send_message(
                    chat_id,
                    text=error_text,
                    reply_markup=steam_main_menu_keyboard(),
                    parse_mode="HTML",
                )

    def _handle_delete_input(self, message, bot):
        """Обработка ввода номера игры для удаления"""
        actor_id = message.from_user.id
        chat_id = message.chat.id

        # Сбрасываем состояние
        self.set_interaction_state(actor_id, chat_id, "action", None)

        # Удаляем сообщение пользователя
        self._try_delete_message(bot, chat_id, message.message_id)

        try:
            game_number = int(message.text.strip())
            message_id = self.get_interaction_state(actor_id, chat_id, "message_id")

            if self._remove_game_from_wishlist(actor_id, game_number):
                if message_id:
                    self._show_wishlist(bot, actor_id, chat_id, message_id)
                else:
                    bot.send_message(
                        chat_id,
                        "✅ Игра удалена из вишлиста!",
                        reply_markup=steam_main_menu_keyboard(),
                    )
            else:
                bot.send_message(
                    chat_id,
                    "❌ Неверный номер игры. Попробуйте снова.",
                    reply_markup=steam_main_menu_keyboard(),
                )
        except ValueError:
            bot.send_message(
                chat_id,
                "❌ Введите корректный номер (число).",
                reply_markup=steam_main_menu_keyboard(),
            )
        except Exception as exc:
            handle_exception(
                exc,
                logger,
                event="steam.wishlist_delete_failed",
                context={"actor_id": actor_id, "chat_id": chat_id},
            )
            bot.send_message(
                chat_id, "❌ Сервис временно недоступен.", reply_markup=steam_main_menu_keyboard()
            )

    def _handle_add_input(self, message, bot):
        """Обработка ввода названия игры"""
        actor_id = message.from_user.id
        chat_id = message.chat.id
        query = message.text.strip()

        # Сбрасываем состояние
        self.set_interaction_state(actor_id, chat_id, "action", None)

        # Удаляем сообщение пользователя
        self._try_delete_message(bot, chat_id, message.message_id)

        message_id = self.get_interaction_state(actor_id, chat_id, "message_id")

        # ИСПРАВЛЕНО: Если message_id None, отправляем новое сообщение-заглушку
        if not message_id:
            temp_msg = bot.send_message(chat_id, "⏳ <b>Поиск игры...</b>", parse_mode="HTML")
            message_id = temp_msg.message_id
            self.set_interaction_state(actor_id, chat_id, "message_id", message_id)

        # Поиск игры
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(steam_client.search_games(query))
        loop.close()

        if not results:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="❌ <b>Игра не найдена</b>\n\n"
                "Попробуйте другой запрос.\n\n"
                f"Запрос: {query[:50]}",
                reply_markup=add_game_keyboard(),
                parse_mode="HTML",
            )
            return

        # Если найдена одна игра
        if len(results) == 1:
            game = results[0]
            game_id = game.get("gameID")
            game_name = game.get("external", game.get("title", "Unknown"))

            current_price, historical_low, discount_percent, steam_app_id = (
                self._fetch_price_for_add(game)
            )

            if current_price:
                price_kzt = steam_client.format_price_kzt(current_price)
                price_rub = steam_client.format_price_rub(current_price)
                price_line = f"{price_kzt} ({price_rub})"
            else:
                price_line = "N/A"

            if self._add_game_to_wishlist(
                actor_id,
                game_id,
                game_name,
                steam_app_id,
                current_price,
                historical_low,
                discount_percent,
            ):
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"✅ <b>Игра добавлена</b>\n\n"
                    f"🎮 {html.escape(game_name)}\n"
                    f"💰 {price_line}\n"
                    f"📉 Скидка: {steam_client.format_discount(discount_percent)}\n\n"
                    "Добавлена в вишлист!",
                    reply_markup=wishlist_keyboard(),
                    parse_mode="HTML",
                )
            else:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="❌ Не удалось добавить игру. Возможно, она уже в вишлисте.",
                    reply_markup=steam_main_menu_keyboard(),
                    parse_mode="HTML",
                )
        else:
            # Показываем список вариантов
            text = "🔍 <b>Найдено несколько игр</b>\n\n"
            text += "Выберите номер игры:\n\n"

            for i, game in enumerate(results[:10], 1):
                # Используем external вместо title
                name = game.get("external", game.get("title", "Unknown"))[:40]
                text += f"{i}. {name}\n"

            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=add_game_keyboard(),
                parse_mode="HTML",
            )

            # Ожидаем выбор пользователя
            self.set_interaction_state(actor_id, chat_id, "action", "select_game")
            self.set_interaction_state(actor_id, chat_id, "search_results", results)
            bot.register_next_step_handler_by_chat_id(chat_id, self._handle_game_selection, bot)

    def _handle_game_selection(self, message, bot):
        """Обработка выбора игры из списка"""
        actor_id = message.from_user.id
        chat_id = message.chat.id

        results = self.get_interaction_state(actor_id, chat_id, "search_results") or []

        # Сбрасываем состояние
        self.set_interaction_state(actor_id, chat_id, "action", None)
        self.set_interaction_state(actor_id, chat_id, "search_results", None)

        # Удаляем сообщение пользователя
        self._try_delete_message(bot, chat_id, message.message_id)

        try:
            game_index = int(message.text.strip()) - 1

            if game_index < 0 or game_index >= len(results):
                bot.send_message(
                    chat_id,
                    "❌ Неверный номер. Попробуйте снова.",
                    reply_markup=steam_main_menu_keyboard(),
                )
                return

            game = results[game_index]
            game_id = game.get("gameID")
            game_name = game.get("external", game.get("title", "Unknown"))

            current_price, historical_low, discount_percent, steam_app_id = (
                self._fetch_price_for_add(game)
            )

            if self._add_game_to_wishlist(
                actor_id,
                game_id,
                game_name,
                steam_app_id,
                current_price,
                historical_low,
                discount_percent,
            ):
                bot.send_message(
                    chat_id,
                    f"✅ Игра '{game_name}' добавлена в вишлист!",
                    reply_markup=steam_main_menu_keyboard(),
                )
            else:
                bot.send_message(
                    chat_id,
                    "❌ Не удалось добавить игру. Возможно, она уже в вишлисте.",
                    reply_markup=steam_main_menu_keyboard(),
                )

        except ValueError:
            bot.send_message(
                chat_id,
                "❌ Введите корректный номер (число).",
                reply_markup=steam_main_menu_keyboard(),
            )
        except Exception as exc:
            handle_exception(
                exc,
                logger,
                event="steam.game_selection_failed",
                context={"actor_id": actor_id, "chat_id": chat_id},
            )
            bot.send_message(
                chat_id, "❌ Сервис временно недоступен.", reply_markup=steam_main_menu_keyboard()
            )

    def _get_user_wishlist(self, user_id: int) -> list:
        """Получение вишлиста пользователя"""
        try:
            with db.database.connection() as connection:
                rows = connection.execute(
                    f"""
                    SELECT game_id, game_name, current_price, historical_low,
                           discount_percent, added_at, steam_app_id
                    FROM {WISHLIST_TABLE}
                    WHERE user_id = ?
                    ORDER BY added_at DESC
                    """,
                    (user_id,),
                ).fetchall()
            wishlist = []
            for row in rows:
                wishlist.append(
                    {
                        "game_id": row[0],
                        "game_name": row[1],
                        "current_price": row[2],
                        "historical_low": row[3],
                        "discount_percent": row[4],
                        "added_at": row[5],
                        "steam_app_id": row[6],
                    }
                )

            return wishlist
        except Exception as exc:
            handle_exception(
                exc,
                logger,
                event="steam.wishlist_read_failed",
                context={"user_id": user_id},
            )
            return []

    def _add_game_to_wishlist(
        self,
        user_id: int,
        game_id: str,
        game_name: str,
        steam_app_id: str = None,
        current_price: float = 0,
        historical_low: float = 0,
        discount_percent: float = 0,
    ) -> bool:
        """Добавление игры в вишлист"""
        try:
            with db.database.connection(write=True) as connection:
                connection.execute("BEGIN IMMEDIATE")
                exists = connection.execute(
                    f"""
                    SELECT 1 FROM {WISHLIST_TABLE}
                    WHERE user_id = ? AND game_id = ?
                    """,
                    (user_id, game_id),
                ).fetchone()
                if exists is None:
                    count = connection.execute(
                        f"SELECT COUNT(*) FROM {WISHLIST_TABLE} WHERE user_id = ?",
                        (user_id,),
                    ).fetchone()[0]
                    if count >= MAX_WISHLIST_GAMES:
                        return False

                connection.execute(
                    f"""
                    INSERT INTO {WISHLIST_TABLE}
                        (user_id, game_id, game_name, steam_app_id, current_price,
                         historical_low, discount_percent, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id, game_id) DO UPDATE SET
                        game_name = excluded.game_name,
                        steam_app_id = excluded.steam_app_id,
                        current_price = excluded.current_price,
                        historical_low = excluded.historical_low,
                        discount_percent = excluded.discount_percent,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        user_id,
                        game_id,
                        game_name,
                        steam_app_id,
                        current_price,
                        historical_low,
                        discount_percent,
                    ),
                )
            return True
        except Exception as exc:
            handle_exception(
                exc,
                logger,
                event="steam.wishlist_write_failed",
                context={"user_id": user_id},
            )
            return False

    def _refresh_wishlist_prices(self, user_id: int) -> None:
        """
        Обновление цен вишлиста из Steam.

        Для каждой игры берётся текущая цена Steam, исторический минимум
        снижается, если текущая цена стала ниже ранее зафиксированной.
        """
        wishlist = self._get_user_wishlist(user_id)
        if not wishlist:
            return

        priced = self._run_async(self._gather_prices(wishlist))

        for game, (steam_app_id, price) in zip(wishlist, priced):
            if not steam_app_id or not price or not price.get("available"):
                continue

            current = price["price_kzt"]
            if current <= 0:
                continue

            previous_low = game["historical_low"] or current
            new_low = min(previous_low, current)

            self._update_game_price(
                user_id, game["game_id"], steam_app_id, current, new_low, price["discount_percent"]
            )

    async def _gather_prices(self, wishlist: list):
        """
        Параллельный сбор цен Steam для всего вишлиста.

        Ограничивается семафором, чтобы не перегружать Steam пачкой запросов.

        :return: список кортежей (steam_app_id, price_dict) в порядке вишлиста
        """
        semaphore = asyncio.Semaphore(REFRESH_CONCURRENCY)

        async def fetch_one(game):
            async with semaphore:
                steam_app_id = game.get("steam_app_id")
                if not steam_app_id:
                    resolved = await steam_client.get_steam_app_id(game["game_id"])
                    steam_app_id = resolved.get("steam_app_id") if resolved else None
                    if not steam_app_id:
                        return None, None
                price = await steam_client.get_appdetails_price(steam_app_id)
                return steam_app_id, price

        return await asyncio.gather(*[fetch_one(game) for game in wishlist])

    def _update_game_price(
        self,
        user_id: int,
        game_id: str,
        steam_app_id: str,
        current_price: float,
        historical_low: float,
        discount_percent: float,
    ) -> None:
        """Обновление цены игры в вишлисте"""
        try:
            with db.database.connection(write=True) as connection:
                connection.execute(
                    f"""
                    UPDATE {WISHLIST_TABLE}
                    SET steam_app_id = ?, current_price = ?, historical_low = ?,
                        discount_percent = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND game_id = ?
                    """,
                    (
                        steam_app_id,
                        current_price,
                        historical_low,
                        discount_percent,
                        user_id,
                        game_id,
                    ),
                )
        except Exception as exc:
            handle_exception(
                exc,
                logger,
                event="steam.wishlist_price_update_failed",
                context={"user_id": user_id},
            )

    def _remove_game_from_wishlist(self, user_id: int, game_index: int) -> bool:
        """Удаление игры из вишлиста по индексу"""
        try:
            if game_index < 1:
                return False
            with db.database.connection(write=True) as connection:
                connection.execute("BEGIN IMMEDIATE")
                game = connection.execute(
                    f"""
                    SELECT game_id FROM {WISHLIST_TABLE}
                    WHERE user_id = ? ORDER BY added_at DESC
                    LIMIT 1 OFFSET ?
                    """,
                    (user_id, game_index - 1),
                ).fetchone()
                if game is None:
                    return False
                cursor = connection.execute(
                    f"""
                    DELETE FROM {WISHLIST_TABLE}
                    WHERE user_id = ? AND game_id = ?
                    """,
                    (user_id, game[0]),
                )
                return cursor.rowcount == 1
        except Exception as exc:
            handle_exception(
                exc,
                logger,
                event="steam.wishlist_delete_failed",
                context={"user_id": user_id},
            )
            return False

    def _get_all_user_ids(self) -> list:
        """Список пользователей, у которых есть игры в вишлисте"""
        try:
            with db.database.connection() as connection:
                rows = connection.execute(
                    f"SELECT DISTINCT user_id FROM {WISHLIST_TABLE}"
                ).fetchall()
            return [row[0] for row in rows]
        except Exception as exc:
            handle_exception(exc, logger, event="steam.wishlist_users_read_failed")
            return []

    def _notify_price_drops(self, bot: Any) -> None:
        """
        Фоновая проверка цен: обновляет вишлисты и шлёт уведомление,
        если текущая цена опустилась ниже ранее зафиксированного минимума.
        """
        self._run_async(steam_client.ensure_rate())

        for user_id in self._get_all_user_ids():
            try:
                wishlist = self._get_user_wishlist(user_id)
                if not wishlist:
                    continue

                priced = self._run_async(self._gather_prices(wishlist))
                drops = []

                for game, (steam_app_id, price) in zip(wishlist, priced):
                    if not steam_app_id or not price or not price.get("available"):
                        continue
                    current = price["price_kzt"]
                    if current <= 0:
                        continue

                    previous_low = game["historical_low"]
                    new_low = min(previous_low, current) if previous_low else current
                    self._update_game_price(
                        user_id,
                        game["game_id"],
                        steam_app_id,
                        current,
                        new_low,
                        price["discount_percent"],
                    )

                    if previous_low and current < previous_low:
                        drops.append((game["game_name"], current))

                if drops:
                    self._send_drop_notification(bot, user_id, drops)
            except Exception as exc:
                handle_exception(
                    exc,
                    logger,
                    event="steam.price_notification_failed",
                    context={"user_id": user_id},
                )

    def _send_drop_notification(self, bot: Any, user_id: int, drops: list) -> None:
        """Отправка уведомления о падении цен"""
        text = "🔥 <b>Цена упала!</b>\n\nНовый минимум в вашем вишлисте:\n\n"
        for name, price_kzt in drops:
            line_name = html.escape(name[:40])
            formatted_kzt = steam_client.format_price_kzt(price_kzt)
            formatted_rub = steam_client.format_price_rub(price_kzt)
            text += f"• <b>{line_name}</b> — {formatted_kzt} ({formatted_rub})\n"

        try:
            bot.send_message(user_id, text, parse_mode="HTML")
        except ApiTelegramException as exc:
            logger.warning(
                "%s",
                type(exc).__name__,
                extra=event_fields("steam.price_notification_undelivered", user_id=user_id),
            )

    def on_load(self, bot: Any) -> None:
        """Загрузка модуля"""
        logger.info(
            "module loaded",
            extra=event_fields("steam.module_loaded", version=self.version),
        )

        if STEAM_NOTIFY_ENABLED:
            self._scheduler = BackgroundScheduler()
            self._scheduler.add_job(
                func=lambda: self._notify_price_drops(bot),
                trigger="interval",
                hours=STEAM_NOTIFY_INTERVAL_HOURS,
                id="steam_price_alerts",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
                misfire_grace_time=900,
            )
            self._scheduler.start()
            logger.info(
                "notification scheduler started",
                extra=event_fields(
                    "steam.scheduler_started",
                    interval_hours=STEAM_NOTIFY_INTERVAL_HOURS,
                ),
            )

    def on_unload(self, bot: Any) -> None:
        """Выгрузка модуля"""
        scheduler = getattr(self, "_scheduler", None)
        if scheduler:
            scheduler.shutdown(wait=False)
            self._scheduler = None
        logger.info(
            "module unloaded",
            extra=event_fields("steam.module_unloaded", version=self.version),
        )
