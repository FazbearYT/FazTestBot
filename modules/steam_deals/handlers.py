# modules/steam_deals/handlers.py
# Обработчики модуля "Steam Deals Tracker"

import asyncio
from datetime import datetime, timedelta
from telebot import types
from typing import Any
from core.module_base import BaseModule
from core.database import DatabaseManager
from .keyboards import (
    steam_main_menu_keyboard,
    wishlist_keyboard,
    free_games_keyboard,
    add_game_keyboard,
    search_results_keyboard,
    confirm_delete_keyboard
)
from .api_client import steam_client
from .config import (
    MAX_WISHLIST_GAMES,
    WISHLIST_TABLE,
    CURRENCY_SYMBOL,
    PRICE_ALERT_THRESHOLD
)

db = DatabaseManager()


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
        chat_id = call.message.chat.id
        message_id = call.message.message_id

        self.set_user_state(chat_id, 'message_id', message_id)
        # Сбрасываем состояние действия
        self.set_user_state(chat_id, 'action', None)
        self.set_user_state(chat_id, 'search_results', None)

        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="🎮 <b>Steam Deals Tracker</b>\n\n"
                 "Отслеживание скидок на игры в Steam:\n\n"
                 "📜 <b>Мой вишлист</b> — отслеживаемые игры\n"
                 "🎁 <b>Бесплатно</b> — игры 100% OFF\n\n"
                 "Выберите действие:",
            reply_markup=self.get_menu_keyboard(),
            parse_mode="HTML"
        )

    def handle_callback(self, bot: Any, call: Any) -> None:
        """Обработка колбэков"""
        chat_id = call.message.chat.id
        message_id = call.message.message_id

        try:
            bot.answer_callback_query(call.id)

            # Сбрасываем состояние при любом действии с клавиатурой
            self.set_user_state(chat_id, 'action', None)
            self.set_user_state(chat_id, 'search_results', None)

            # Назад к списку модулей
            if call.data == "steam_back_to_modules":
                from core.module_manager import module_manager
                modules = module_manager.get_all_modules()

                kb = types.InlineKeyboardMarkup(row_width=1)
                for module in modules:
                    kb.add(types.InlineKeyboardButton(
                        f"{module.icon} {module.name}",
                        callback_data=f"module_{module.id}"
                    ))
                kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_main"))

                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="📦 <b>Доступные модули</b>\n\nВыберите модуль:",
                    reply_markup=kb,
                    parse_mode="HTML"
                )
                self.cleanup_user_state(chat_id)
                return

            # Назад в меню модуля
            if call.data == "steam_back_to_menu":
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="🎮 <b>Steam Deals Tracker</b>\n\nВыберите действие:",
                    reply_markup=steam_main_menu_keyboard(),
                    parse_mode="HTML"
                )
                return

            # Мой вишлист
            if call.data == "steam_wishlist":
                self._show_wishlist(bot, chat_id, message_id)
                return

            # Обновить вишлист
            if call.data == "steam_wishlist_refresh":
                self._show_wishlist(bot, chat_id, message_id, force_refresh=True)
                return

            # Удалить игру
            if call.data == "steam_wishlist_delete":
                self.set_user_state(chat_id, 'action', 'delete_game')
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="❌ <b>Удаление игры</b>\n\n"
                         "Введите номер игры для удаления:\n\n"
                         "<i>Пример: 1</i>",
                    reply_markup=confirm_delete_keyboard(),
                    parse_mode="HTML"
                )
                bot.register_next_step_handler_by_chat_id(chat_id, self._handle_delete_input, bot)
                return

            # Добавить игру из вишлиста
            if call.data == "steam_add_from_wishlist":
                self.set_user_state(chat_id, 'action', 'add_game')
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="➕ <b>Добавить игру</b>\n\n"
                         "Введите название игры или ссылку на Steam:\n\n"
                         "<i>Пример: Cyberpunk 2077</i>",
                    reply_markup=add_game_keyboard(),
                    parse_mode="HTML"
                )
                bot.register_next_step_handler_by_chat_id(chat_id, self._handle_add_input, bot)
                return

            # Бесплатные игры
            if call.data == "steam_free":
                self._show_free_games(bot, chat_id, message_id)
                return

            # Обновить бесплатные
            if call.data == "steam_free_refresh":
                # Очищаем кэш
                steam_client.cache.pop("free_games", None)
                steam_client.cache_timestamp.pop("free_games", None)
                steam_client._save_cache()

                # ИСПРАВЛЕНО: Показываем заново с правильным message_id
                try:
                    bot.delete_message(chat_id, message_id)
                except:
                    pass

                # Отправляем новое сообщение
                self._show_free_games(bot, chat_id, None)
                return

            # Добавить конкретную игру
            if call.data.startswith("steam_add_game_"):
                game_id = call.data.replace("steam_add_game_", "")
                self._add_game_by_id(bot, chat_id, message_id, game_id)
                return

        except Exception as e:
            bot.answer_callback_query(
                call.id,
                f"Ошибка: {str(e)[:60]}",
                show_alert=True
            )

    def get_menu_keyboard(self) -> types.InlineKeyboardMarkup:
        """Клавиатура меню"""
        return steam_main_menu_keyboard()

    def _show_wishlist(self, bot: Any, chat_id: int, message_id: int, force_refresh: bool = False):
        """Показ вишлиста пользователя"""
        try:
            wishlist = self._get_user_wishlist(chat_id)

            if not wishlist:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="📜 <b>Мой вишлист</b>\n\n"
                         "⚠️ Список пуст.\n\n"
                         "Используйте «➕ Добавить игру» для добавления.",
                    reply_markup=wishlist_keyboard(is_empty=True),
                    parse_mode="HTML"
                )
                return

            # Формируем список
            text = "📜 <b>Мой вишлист</b>\n\n"
            text += f"Всего игр: {len(wishlist)}\n\n"

            for i, game in enumerate(wishlist[:MAX_WISHLIST_GAMES], 1):
                name = game['game_name'][:40]
                price = steam_client.format_price(game['current_price']) if game['current_price'] else "N/A"
                discount = steam_client.format_discount(game['discount_percent']) if game['discount_percent'] else "0%"

                # Проверка на исторический минимум
                alert = ""
                if game['current_price'] and game['historical_low']:
                    if steam_client.check_price_alert(game['current_price'], game['historical_low']):
                        alert = " ⚠️"

                text += f"{i}. {name} | {price} ({discount}){alert}\n"

            if len(wishlist) > MAX_WISHLIST_GAMES:
                text += f"\n<i>... и ещё {len(wishlist) - MAX_WISHLIST_GAMES} игр</i>"

            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=wishlist_keyboard(),
                parse_mode="HTML"
            )

        except Exception as e:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"❌ <b>Ошибка</b>\n\nСервис временно недоступен.\n\n{str(e)[:100]}",
                reply_markup=steam_main_menu_keyboard(),
                parse_mode="HTML"
            )

    def _show_free_games(self, bot: Any, chat_id: int, message_id: int):
        """Показ бесплатных игр"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            games = loop.run_until_complete(steam_client.get_free_games())
            loop.close()

            if not games:
                text = "🎁 <b>Бесплатно (100% OFF)</b>\n\n"
                text += "⚠️ Сейчас нет бесплатных игр.\n\n"
                text += "Загляните позже!"

                if message_id:
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=text,
                        reply_markup=free_games_keyboard(),
                        parse_mode="HTML"
                    )
                else:
                    bot.send_message(
                        chat_id,
                        text=text,
                        reply_markup=free_games_keyboard(),
                        parse_mode="HTML"
                    )
                return

            # Формируем список
            text = "🎁 <b>Бесплатно (100% OFF)</b>\n\n"
            text += f"Всего: {len(games)}\n\n"

            for i, game in enumerate(games[:20], 1):
                # Используем external или title для названия
                name = game.get('external', game.get('title', 'Unknown'))[:50]
                text += f"{i}. {name}\n"

            if message_id:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=free_games_keyboard(),
                    parse_mode="HTML"
                )
            else:
                bot.send_message(
                    chat_id,
                    text=text,
                    reply_markup=free_games_keyboard(),
                    parse_mode="HTML"
                )

        except Exception as e:
            error_text = f"❌ <b>Ошибка</b>\n\nСервис временно недоступен.\n\n{str(e)[:100]}"
            if message_id:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=error_text,
                    reply_markup=steam_main_menu_keyboard(),
                    parse_mode="HTML"
                )
            else:
                bot.send_message(
                    chat_id,
                    text=error_text,
                    reply_markup=steam_main_menu_keyboard(),
                    parse_mode="HTML"
                )

    def _handle_delete_input(self, message, bot):
        """Обработка ввода номера игры для удаления"""
        chat_id = message.chat.id

        # Сбрасываем состояние
        self.set_user_state(chat_id, 'action', None)

        # Удаляем сообщение пользователя
        try:
            bot.delete_message(chat_id, message.message_id)
        except:
            pass

        try:
            game_number = int(message.text.strip())
            message_id = self.get_user_state(chat_id, 'message_id')

            if self._remove_game_from_wishlist(chat_id, game_number):
                if message_id:
                    self._show_wishlist(bot, chat_id, message_id)
                else:
                    bot.send_message(
                        chat_id,
                        "✅ Игра удалена из вишлиста!",
                        reply_markup=steam_main_menu_keyboard()
                    )
            else:
                bot.send_message(
                    chat_id,
                    "❌ Неверный номер игры. Попробуйте снова.",
                    reply_markup=steam_main_menu_keyboard()
                )
        except ValueError:
            bot.send_message(
                chat_id,
                "❌ Введите корректный номер (число).",
                reply_markup=steam_main_menu_keyboard()
            )
        except Exception as e:
            bot.send_message(
                chat_id,
                f"❌ Ошибка: {str(e)[:100]}",
                reply_markup=steam_main_menu_keyboard()
            )

    def _handle_add_input(self, message, bot):
        """Обработка ввода названия игры"""
        chat_id = message.chat.id
        query = message.text.strip()

        # Сбрасываем состояние
        self.set_user_state(chat_id, 'action', None)

        # Удаляем сообщение пользователя
        try:
            bot.delete_message(chat_id, message.message_id)
        except:
            pass

        message_id = self.get_user_state(chat_id, 'message_id')

        # ИСПРАВЛЕНО: Если message_id None, отправляем новое сообщение-заглушку
        if not message_id:
            temp_msg = bot.send_message(
                chat_id,
                "⏳ <b>Поиск игры...</b>",
                parse_mode="HTML"
            )
            message_id = temp_msg.message_id
            self.set_user_state(chat_id, 'message_id', message_id)

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
                parse_mode="HTML"
            )
            return

        # Если найдена одна игра
        if len(results) == 1:
            game = results[0]
            game_id = game.get('gameID')
            # Используем external вместо title
            game_name = game.get('external', game.get('title', 'Unknown'))

            # Добавляем в вишлист
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            deals = loop.run_until_complete(steam_client.get_game_deals(game_id))
            loop.close()

            current_price = 0
            historical_low = 0
            discount_percent = 0

            if deals:
                deal = deals[0]
                current_price = float(deal.get('salePrice', 0))
                historical_low = float(deal.get('lowestPrice', 0))
                discount_percent = float(deal.get('savings', 0)) * 100

            if self._add_game_to_wishlist(chat_id, game_id, game_name, current_price, historical_low, discount_percent):
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"✅ <b>Игра добавлена</b>\n\n"
                         f"🎮 {game_name}\n"
                         f"💰 {steam_client.format_price(current_price)}\n"
                         f"📉 Скидка: {steam_client.format_discount(discount_percent)}\n\n"
                         "Добавлена в вишлист!",
                    reply_markup=wishlist_keyboard(),
                    parse_mode="HTML"
                )
            else:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="❌ Не удалось добавить игру. Возможно, она уже в вишлисте.",
                    reply_markup=steam_main_menu_keyboard(),
                    parse_mode="HTML"
                )
        else:
            # Показываем список вариантов
            text = "🔍 <b>Найдено несколько игр</b>\n\n"
            text += "Выберите номер игры:\n\n"

            for i, game in enumerate(results[:10], 1):
                # Используем external вместо title
                name = game.get('external', game.get('title', 'Unknown'))[:40]
                text += f"{i}. {name}\n"

            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=add_game_keyboard(),
                parse_mode="HTML"
            )

            # Ожидаем выбор пользователя
            self.set_user_state(chat_id, 'action', 'select_game')
            self.set_user_state(chat_id, 'search_results', results)
            bot.register_next_step_handler_by_chat_id(chat_id, self._handle_game_selection, bot)

    def _handle_game_selection(self, message, bot):
        """Обработка выбора игры из списка"""
        chat_id = message.chat.id

        # Сбрасываем состояние
        self.set_user_state(chat_id, 'action', None)
        self.set_user_state(chat_id, 'search_results', None)

        # Удаляем сообщение пользователя
        try:
            bot.delete_message(chat_id, message.message_id)
        except:
            pass

        try:
            game_index = int(message.text.strip()) - 1
            results = self.get_user_state(chat_id, 'search_results', [])

            if game_index < 0 or game_index >= len(results):
                bot.send_message(
                    chat_id,
                    "❌ Неверный номер. Попробуйте снова.",
                    reply_markup=steam_main_menu_keyboard()
                )
                return

            game = results[game_index]
            game_id = game.get('gameID')
            game_name = game.get('external', game.get('title', 'Unknown'))

            # Получаем детали игры
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            deals = loop.run_until_complete(steam_client.get_game_deals(game_id))
            loop.close()

            current_price = 0
            historical_low = 0
            discount_percent = 0

            if deals:
                deal = deals[0]
                current_price = float(deal.get('salePrice', 0))
                historical_low = float(deal.get('lowestPrice', 0))
                discount_percent = float(deal.get('savings', 0)) * 100

            if self._add_game_to_wishlist(chat_id, game_id, game_name, current_price, historical_low, discount_percent):
                bot.send_message(
                    chat_id,
                    f"✅ Игра '{game_name}' добавлена в вишлист!",
                    reply_markup=steam_main_menu_keyboard()
                )
            else:
                bot.send_message(
                    chat_id,
                    "❌ Не удалось добавить игру. Возможно, она уже в вишлисте.",
                    reply_markup=steam_main_menu_keyboard()
                )

        except ValueError:
            bot.send_message(
                chat_id,
                "❌ Введите корректный номер (число).",
                reply_markup=steam_main_menu_keyboard()
            )
        except Exception as e:
            bot.send_message(
                chat_id,
                f"❌ Ошибка: {str(e)[:100]}",
                reply_markup=steam_main_menu_keyboard()
            )

    def _add_game_by_id(self, bot: Any, chat_id: int, message_id: int, game_id: str):
        """Добавление игры по ID"""
        try:
            # Получаем детали игры
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            game_info = loop.run_until_complete(steam_client.get_game_details(game_id))
            loop.close()

            if not game_info:
                bot.answer_callback_query(
                    bot.current_call.id if hasattr(bot, 'current_call') else 0,
                    "❌ Не удалось получить информацию об игре",
                    show_alert=True
                )
                return

            game_name = game_info.get('info', {}).get('title', 'Unknown')

            # Получаем сделки
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            deals = loop.run_until_complete(steam_client.get_game_deals(game_id))
            loop.close()

            current_price = 0
            historical_low = 0
            discount_percent = 0

            if deals:
                deal = deals[0]
                current_price = float(deal.get('salePrice', 0))
                historical_low = float(deal.get('lowestPrice', 0))
                discount_percent = float(deal.get('savings', 0)) * 100

            if self._add_game_to_wishlist(chat_id, game_id, game_name, current_price, historical_low, discount_percent):
                bot.answer_callback_query(
                    bot.current_call.id if hasattr(bot, 'current_call') else 0,
                    f"✅ {game_name} добавлена в вишлист!",
                    show_alert=False
                )
                self._show_wishlist(bot, chat_id, message_id)
            else:
                bot.answer_callback_query(
                    bot.current_call.id if hasattr(bot, 'current_call') else 0,
                    "❌ Игра уже в вишлисте",
                    show_alert=True
                )

        except Exception as e:
            bot.answer_callback_query(
                bot.current_call.id if hasattr(bot, 'current_call') else 0,
                f"❌ Ошибка: {str(e)[:60]}",
                show_alert=True
            )

    def _get_user_wishlist(self, user_id: int) -> list:
        """Получение вишлиста пользователя"""
        try:
            with db.database.connection() as connection:
                rows = connection.execute(
                    f"""
                    SELECT game_id, game_name, current_price, historical_low,
                           discount_percent, added_at
                    FROM {WISHLIST_TABLE}
                    WHERE user_id = ?
                    ORDER BY added_at DESC
                    """,
                    (user_id,),
                ).fetchall()
            wishlist = []
            for row in rows:
                wishlist.append({
                    'game_id': row[0],
                    'game_name': row[1],
                    'current_price': row[2],
                    'historical_low': row[3],
                    'discount_percent': row[4],
                    'added_at': row[5]
                })

            return wishlist
        except Exception:
            return []

    def _add_game_to_wishlist(self, user_id: int, game_id: str, game_name: str,
                              current_price: float = 0, historical_low: float = 0,
                              discount_percent: float = 0) -> bool:
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
                        (user_id, game_id, game_name, current_price,
                         historical_low, discount_percent, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id, game_id) DO UPDATE SET
                        game_name = excluded.game_name,
                        current_price = excluded.current_price,
                        historical_low = excluded.historical_low,
                        discount_percent = excluded.discount_percent,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        user_id,
                        game_id,
                        game_name,
                        current_price,
                        historical_low,
                        discount_percent,
                    ),
                )
            return True
        except Exception as e:
            print(f"⚠️ Ошибка добавления в вишлист: {str(e)}")
            return False

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
        except Exception as e:
            print(f"⚠️ Ошибка удаления из вишлиста: {str(e)}")
            return False

    def on_load(self, bot: Any) -> None:
        """Загрузка модуля"""
        print(f"🎮 Модуль Steam Deals Tracker v{self.version} загружен")

    def on_unload(self, bot: Any) -> None:
        """Выгрузка модуля"""
        print(f"🎮 Модуль Steam Deals Tracker v{self.version} выгружен")
