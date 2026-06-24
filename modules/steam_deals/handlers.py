# modules/steam_deals/handlers.py
# Обработчики модуля "Steam Deals Tracker"

import asyncio
import html
import sqlite3
from datetime import datetime, timedelta
from telebot import types
from telebot.apihelper import ApiTelegramException
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
    CACHE_TABLE,
    CURRENCY_SYMBOL,
    PRICE_ALERT_THRESHOLD,
    STEAM_APP_URL
)
import config

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
        self._init_database()

    def _init_database(self):
        """Инициализация таблиц в БД"""
        try:
            conn = sqlite3.connect(config.DATABASE_PATH)
            cursor = conn.cursor()

            # Таблица вишлиста
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {WISHLIST_TABLE} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    game_id TEXT NOT NULL,
                    game_name TEXT NOT NULL,
                    steam_app_id TEXT,
                    current_price REAL,
                    historical_low REAL,
                    discount_percent REAL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, game_id)
                )
            """)

            existing_columns = [row[1] for row in cursor.execute(
                f"PRAGMA table_info({WISHLIST_TABLE})"
            ).fetchall()]
            if "steam_app_id" not in existing_columns:
                cursor.execute(f"ALTER TABLE {WISHLIST_TABLE} ADD COLUMN steam_app_id TEXT")
                # Старые цены хранились в другой валюте (USD), сбрасываем под пересчёт в тенге
                cursor.execute(f"""
                    UPDATE {WISHLIST_TABLE}
                    SET current_price = NULL, historical_low = NULL, discount_percent = NULL
                """)

            # Таблица кэша
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {CACHE_TABLE} (
                    cache_key TEXT PRIMARY KEY,
                    cache_data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"⚠️ Ошибка инициализации БД: {str(e)}")

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

                # Показываем заново с правильным message_id
                self._show_free_games(bot, chat_id, message_id)
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

        steam_app_id = game.get('steamAppID')
        if not steam_app_id:
            return 0.0, 0.0, 0.0, None

        price = self._run_async(steam_client.get_appdetails_price(steam_app_id))

        if price and price.get('available'):
            current = price['price_kzt']
            return current, current, price['discount_percent'], steam_app_id

        return 0.0, 0.0, 0.0, steam_app_id

    def _show_wishlist(self, bot: Any, chat_id: int, message_id: int, force_refresh: bool = False):
        """Показ вишлиста пользователя"""
        try:
            self._run_async(steam_client.ensure_rate())

            if force_refresh:
                self._refresh_wishlist_prices(chat_id)

            wishlist = self._get_user_wishlist(chat_id)

            if not wishlist:
                self._safe_edit(
                    bot,
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
                name = html.escape(game['game_name'][:40])
                discount = steam_client.format_discount(game['discount_percent']) if game['discount_percent'] else "0%"

                if game['current_price']:
                    price = f"{steam_client.format_price_kzt(game['current_price'])} ({steam_client.format_price_rub(game['current_price'])})"
                else:
                    price = "N/A"

                low = steam_client.format_price_kzt(game['historical_low']) if game['historical_low'] else "N/A"

                alert = ""
                if game['current_price'] and game['historical_low']:
                    if steam_client.check_price_alert(game['current_price'], game['historical_low']):
                        alert = " ⚠️"

                text += f"{i}. <b>{name}</b>\n"
                text += f"   💰 {price} · скидка {discount} · 📉 мин: {low}{alert}\n"

            if len(wishlist) > MAX_WISHLIST_GAMES:
                text += f"\n<i>... и ещё {len(wishlist) - MAX_WISHLIST_GAMES} игр</i>"

            if force_refresh:
                text += f"\n<i>🕐 Обновлено: {datetime.now().strftime('%H:%M:%S')}</i>"

            self._safe_edit(
                bot,
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
                self._safe_edit(
                    bot,
                    chat_id=chat_id,
                    message_id=message_id,
                    text="🎁 <b>Бесплатно (100% OFF)</b>\n\n"
                         "⚠️ Сейчас нет бесплатных игр.\n\n"
                         f"<i>🕐 Проверено: {datetime.now().strftime('%H:%M:%S')}</i>",
                    reply_markup=free_games_keyboard(),
                    parse_mode="HTML"
                )
                return

            # Формируем список
            text = "🎁 <b>Бесплатно (100% OFF)</b>\n\n"
            text += f"Всего: {len(games)}\n\n"

            for i, game in enumerate(games[:20], 1):
                name = html.escape(game.get('name', 'Unknown')[:50])
                app_id = game.get('app_id')
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
                disable_web_page_preview=True
            )

        except Exception as e:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"❌ <b>Ошибка</b>\n\nСервис временно недоступен.\n\n{str(e)[:100]}",
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

        # Поиск игры
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(steam_client.search_games(query))
        loop.close()

        if not results:
            if message_id:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="❌ <b>Игра не найдена</b>\n\n"
                         "Попробуйте другой запрос.\n\n"
                         f"Запрос: {query[:50]}",
                    reply_markup=add_game_keyboard(),
                    parse_mode="HTML"
                )
            else:
                bot.send_message(
                    chat_id,
                    "❌ Игра не найдена. Попробуйте другой запрос.",
                    reply_markup=steam_main_menu_keyboard()
                )
            return

        # Если найдена одна игра
        if len(results) == 1:
            game = results[0]
            game_id = game.get('gameID')
            game_name = game.get('external', game.get('title', 'Unknown'))

            current_price, historical_low, discount_percent, steam_app_id = self._fetch_price_for_add(game)

            if current_price:
                price_line = f"{steam_client.format_price_kzt(current_price)} ({steam_client.format_price_rub(current_price)})"
            else:
                price_line = "N/A"

            if self._add_game_to_wishlist(chat_id, game_id, game_name, steam_app_id, current_price, historical_low, discount_percent):
                if message_id:
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=f"✅ <b>Игра добавлена</b>\n\n"
                             f"🎮 {html.escape(game_name)}\n"
                             f"💰 {price_line}\n"
                             f"📉 Скидка: {steam_client.format_discount(discount_percent)}\n\n"
                             "Добавлена в вишлист!",
                        reply_markup=wishlist_keyboard(),
                        parse_mode="HTML"
                    )
                else:
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
        else:
            # Показываем список вариантов
            text = "🔍 <b>Найдено несколько игр</b>\n\n"
            text += "Выберите номер игры:\n\n"

            for i, game in enumerate(results[:10], 1):
                # Используем external вместо title
                name = game.get('external', game.get('title', 'Unknown'))[:40]
                text += f"{i}. {name}\n"

            if message_id:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=add_game_keyboard(),
                    parse_mode="HTML"
                )
            else:
                bot.send_message(
                    chat_id,
                    text,
                    reply_markup=steam_main_menu_keyboard()
                )

            # Ожидаем выбор пользователя
            self.set_user_state(chat_id, 'action', 'select_game')
            self.set_user_state(chat_id, 'search_results', results)
            bot.register_next_step_handler_by_chat_id(chat_id, self._handle_game_selection, bot)

    def _handle_game_selection(self, message, bot):
        """Обработка выбора игры из списка"""
        chat_id = message.chat.id

        results = self.get_user_state(chat_id, 'search_results') or []

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

            current_price, historical_low, discount_percent, steam_app_id = self._fetch_price_for_add(game)

            if self._add_game_to_wishlist(chat_id, game_id, game_name, steam_app_id, current_price, historical_low, discount_percent):
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
            self._run_async(steam_client.ensure_rate())
            info = self._run_async(steam_client.get_steam_app_id(game_id))

            if not info or not info.get('steam_app_id'):
                bot.answer_callback_query(
                    bot.current_call.id if hasattr(bot, 'current_call') else 0,
                    "❌ Не удалось получить информацию об игре",
                    show_alert=True
                )
                return

            game_name = info.get('title', 'Unknown')
            steam_app_id = info['steam_app_id']

            price = self._run_async(steam_client.get_appdetails_price(steam_app_id))

            if price and price.get('available'):
                current_price = price['price_kzt']
                historical_low = current_price
                discount_percent = price['discount_percent']
            else:
                current_price = 0.0
                historical_low = 0.0
                discount_percent = 0.0

            if self._add_game_to_wishlist(chat_id, game_id, game_name, steam_app_id, current_price, historical_low, discount_percent):
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
            conn = sqlite3.connect(config.DATABASE_PATH)
            cursor = conn.cursor()

            cursor.execute(f"""
                SELECT game_id, game_name, current_price, historical_low, discount_percent, added_at, steam_app_id
                FROM {WISHLIST_TABLE}
                WHERE user_id = ?
                ORDER BY added_at DESC
            """, (user_id,))

            wishlist = []
            for row in cursor.fetchall():
                wishlist.append({
                    'game_id': row[0],
                    'game_name': row[1],
                    'current_price': row[2],
                    'historical_low': row[3],
                    'discount_percent': row[4],
                    'added_at': row[5],
                    'steam_app_id': row[6]
                })

            conn.close()
            return wishlist
        except:
            return []

    def _add_game_to_wishlist(self, user_id: int, game_id: str, game_name: str,
                              steam_app_id: str = None, current_price: float = 0,
                              historical_low: float = 0, discount_percent: float = 0) -> bool:
        """Добавление игры в вишлист"""
        try:
            conn = sqlite3.connect(config.DATABASE_PATH)
            cursor = conn.cursor()

            # Проверяем лимит
            cursor.execute(f"SELECT COUNT(*) FROM {WISHLIST_TABLE} WHERE user_id = ?", (user_id,))
            count = cursor.fetchone()[0]

            if count >= MAX_WISHLIST_GAMES:
                conn.close()
                return False

            # Добавляем или обновляем
            cursor.execute(f"""
                INSERT OR REPLACE INTO {WISHLIST_TABLE}
                (user_id, game_id, game_name, steam_app_id, current_price, historical_low, discount_percent, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (user_id, game_id, game_name, steam_app_id, current_price, historical_low, discount_percent))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"⚠️ Ошибка добавления в вишлист: {str(e)}")
            return False

    def _refresh_wishlist_prices(self, user_id: int) -> None:
        """
        Обновление цен вишлиста из Steam.

        Для каждой игры берётся текущая цена Steam, исторический минимум
        снижается, если текущая цена стала ниже ранее зафиксированной.
        """
        wishlist = self._get_user_wishlist(user_id)

        for game in wishlist:
            steam_app_id = game.get('steam_app_id')

            if not steam_app_id:
                resolved = self._run_async(steam_client.get_steam_app_id(game['game_id']))
                steam_app_id = resolved.get('steam_app_id') if resolved else None
                if not steam_app_id:
                    continue

            price = self._run_async(steam_client.get_appdetails_price(steam_app_id))

            if not price or not price.get('available'):
                continue

            current = price['price_kzt']
            if current <= 0:
                continue

            previous_low = game['historical_low'] or current
            new_low = min(previous_low, current)

            self._update_game_price(user_id, game['game_id'], steam_app_id, current, new_low, price['discount_percent'])

    def _update_game_price(self, user_id: int, game_id: str, steam_app_id: str,
                           current_price: float, historical_low: float, discount_percent: float) -> None:
        """Обновление цены игры в вишлисте"""
        try:
            conn = sqlite3.connect(config.DATABASE_PATH)
            cursor = conn.cursor()

            cursor.execute(f"""
                UPDATE {WISHLIST_TABLE}
                SET steam_app_id = ?, current_price = ?, historical_low = ?, discount_percent = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND game_id = ?
            """, (steam_app_id, current_price, historical_low, discount_percent, user_id, game_id))

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"⚠️ Ошибка обновления цены: {str(e)}")

    def _remove_game_from_wishlist(self, user_id: int, game_index: int) -> bool:
        """Удаление игры из вишлиста по индексу"""
        try:
            wishlist = self._get_user_wishlist(user_id)

            if game_index < 1 or game_index > len(wishlist):
                return False

            game = wishlist[game_index - 1]

            conn = sqlite3.connect(config.DATABASE_PATH)
            cursor = conn.cursor()

            cursor.execute(f"""
                DELETE FROM {WISHLIST_TABLE}
                WHERE user_id = ? AND game_id = ?
            """, (user_id, game['game_id']))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"⚠️ Ошибка удаления из вишлиста: {str(e)}")
            return False

    def on_load(self, bot: Any) -> None:
        """Загрузка модуля"""
        print(f"🎮 Модуль Steam Deals Tracker v{self.version} загружен")

    def on_unload(self, bot: Any) -> None:
        """Выгрузка модуля"""
        print(f"🎮 Модуль Steam Deals Tracker v{self.version} выгружен")