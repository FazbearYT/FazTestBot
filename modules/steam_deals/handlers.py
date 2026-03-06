# modules/steam_deals/handlers.py
# Обработчики модуля "Steam Deals Tracker"

import asyncio
import sqlite3
from datetime import datetime, timedelta
from telebot import types
from typing import Any
from core.module_base import BaseModule
from core.database import DatabaseManager
from .keyboards import (
    steam_main_menu_keyboard,
    wishlist_keyboard,
    popular_deals_keyboard,
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
    PRICE_ALERT_THRESHOLD
)
import config

db = DatabaseManager()


class SteamDealsModule(BaseModule):
    """
    Модуль отслеживания скидок на игры в Steam.

    Поддерживает:
    - Вишлист с отслеживанием цен
    - Популярные скидки
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
                    current_price REAL,
                    historical_low REAL,
                    discount_percent REAL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, game_id)
                )
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

        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="🎮 <b>Steam Deals Tracker</b>\n\n"
                 "Отслеживание скидок на игры в Steam:\n\n"
                 "📜 <b>Мой вишлист</b> — отслеживаемые игры\n"
                 "🔥 <b>Популярные скидки</b> — лучшие предложения\n"
                 "🎁 <b>Бесплатно</b> — игры 100% OFF\n"
                 "➕ <b>Добавить игру</b> — поиск и добавление\n\n"
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
                return

            # Популярные скидки
            if call.data == "steam_popular":
                self._show_popular_deals(bot, chat_id, message_id)
                return

            # Обновить популярные
            if call.data == "steam_popular_refresh":
                # Очищаем кэш
                steam_client.cache.pop("popular_deals", None)
                steam_client.cache_timestamp.pop("popular_deals", None)
                steam_client._save_cache()

                self._show_popular_deals(bot, chat_id, message_id)
                return

            # Добавить из популярных
            if call.data == "steam_add_from_popular":
                self.set_user_state(chat_id, 'action', 'add_from_popular')
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="➕ <b>Добавление из списка</b>\n\n"
                         "Введите номер игры из списка для добавления в вишлист:",
                    reply_markup=popular_deals_keyboard(),
                    parse_mode="HTML"
                )
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

                self._show_free_games(bot, chat_id, message_id)
                return

            # Добавить игру
            if call.data == "steam_add":
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
                return

            # Обработка текстового ввода
            if call.data == "steam_handle_input":
                # Этот колбэк обрабатывается в message_handler
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

    def _show_popular_deals(self, bot: Any, chat_id: int, message_id: int):
        """Показ популярных скидок"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            deals = loop.run_until_complete(steam_client.get_popular_deals())
            loop.close()

            if not deals:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="🔥 <b>Популярные скидки</b>\n\n"
                         "⚠️ Нет доступных данных.\n\n"
                         "Попробуйте позже.",
                    reply_markup=popular_deals_keyboard(),
                    parse_mode="HTML"
                )
                return

            # Формируем список
            text = "🔥 <b>Популярные скидки</b>\n\n"
            text += f"Всего: {len(deals)}\n\n"

            for i, deal in enumerate(deals[:20], 1):
                name = deal.get('title', 'Unknown')[:40]
                price = steam_client.format_price(float(deal.get('salePrice', 0)))
                discount = steam_client.format_discount(float(deal.get('savings', 0)) * 100)

                # Проверка на исторический минимум
                alert = ""
                normal_price = float(deal.get('normalPrice', 0))
                sale_price = float(deal.get('salePrice', 0))
                if normal_price > 0 and sale_price > 0:
                    if steam_client.check_price_alert(sale_price, normal_price * 0.5):
                        alert = " ⚠️"

                text += f"{i}. {name} | {price} ({discount}){alert}\n"

            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=popular_deals_keyboard(),
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
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="🎁 <b>Бесплатно (100% OFF)</b>\n\n"
                         "⚠️ Нет доступных данных.\n\n"
                         "Попробуйте позже.",
                    reply_markup=free_games_keyboard(),
                    parse_mode="HTML"
                )
                return

            # Формируем список
            text = "🎁 <b>Бесплатно (100% OFF)</b>\n\n"
            text += f"Всего: {len(games)}\n\n"

            for i, game in enumerate(games[:20], 1):
                name = game.get('title', 'Unknown')[:40]
                text += f"{i}. {name}\n"

            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=free_games_keyboard(),
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

    def _get_user_wishlist(self, user_id: int) -> list:
        """Получение вишлиста пользователя"""
        try:
            conn = sqlite3.connect(config.DATABASE_PATH)
            cursor = conn.cursor()

            cursor.execute(f"""
                SELECT game_id, game_name, current_price, historical_low, discount_percent, added_at
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
                    'added_at': row[5]
                })

            conn.close()
            return wishlist
        except:
            return []

    def _add_game_to_wishlist(self, user_id: int, game_id: str, game_name: str,
                              current_price: float = 0, historical_low: float = 0,
                              discount_percent: float = 0) -> bool:
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
                (user_id, game_id, game_name, current_price, historical_low, discount_percent, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (user_id, game_id, game_name, current_price, historical_low, discount_percent))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"⚠️ Ошибка добавления в вишлист: {str(e)}")
            return False

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