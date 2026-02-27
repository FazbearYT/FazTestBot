# modules/ip_lookup/handlers.py
# Обработчики модуля "IP Info Lookup"

import asyncio
import sqlite3
from datetime import datetime, timedelta
from telebot import types
from typing import Any
from core.module_base import BaseModule
from core.database import DatabaseManager
from .keyboards import (
    ip_lookup_menu_keyboard,
    search_result_keyboard,
    history_keyboard
)
from .api_client import ip_client
from .config import (
    MAX_LOOKUPS_PER_USER_PER_DAY,
    TABLE_NAME
)
import config

db = DatabaseManager()


class IPLookupModule(BaseModule):
    """
    Модуль получения информации об IP адресе.
    """

    def __init__(self, module_id, name, description, icon, version, callback_prefix):
        """Инициализация модуля IP Info Lookup"""
        super().__init__(module_id, name, description, icon, version, callback_prefix)
        self._init_database()

    def _init_database(self):
        """Инициализация таблицы запросов в БД"""
        try:
            conn = sqlite3.connect(config.DATABASE_PATH)
            cursor = conn.cursor()

            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    query TEXT NOT NULL,
                    ip TEXT,
                    city TEXT,
                    country TEXT,
                    isp TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"⚠️ Ошибка инициализации БД: {str(e)}")

    def handle_entry(self, bot: Any, call: Any) -> None:
        """
        ОБЯЗАТЕЛЬНО: Вход в модуль — показ меню.
        """
        chat_id = call.message.chat.id
        message_id = call.message.message_id

        self.set_user_state(chat_id, 'message_id', message_id)

        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="🌍 <b>IP Info Lookup</b>\n\n"
                 "Получение информации об IP адресе:\n"
                 "• Страна и город\n"
                 "• Провайдер (ISP)\n"
                 "• Часовой пояс\n"
                 "• Координаты\n\n"
                 f"Лимит: {MAX_LOOKUPS_PER_USER_PER_DAY} запросов/день\n\n"
                 "Выберите действие:",
            reply_markup=self.get_menu_keyboard(),
            parse_mode="HTML"
        )

    def handle_callback(self, bot: Any, call: Any) -> None:
        """
        ОБЯЗАТЕЛЬНО: Обработка колбэков внутри модуля.
        """
        chat_id = call.message.chat.id
        message_id = call.message.message_id

        try:
            bot.answer_callback_query(call.id)

            # Назад к списку модулей
            if call.data == "ip_back_to_modules":
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
            if call.data == "ip_back_to_menu":
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="🌍 <b>IP Info Lookup</b>\n\nВыберите действие:",
                    reply_markup=ip_lookup_menu_keyboard(),
                    parse_mode="HTML"
                )
                return

            # Поиск IP
            if call.data == "ip_search":
                self.set_user_state(chat_id, 'query_type', 'search')
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="🔍 <b>Поиск IP</b>\n\n"
                         "Отправьте IPv4 или IPv6 адрес:\n"
                         "• IPv4: 8.8.8.8\n"
                         "• IPv6: 2001:4860:4860::8888",
                    reply_markup=None,
                    parse_mode="HTML"
                )
                bot.register_next_step_handler(call.message, self._process_ip_input, bot)
                return

            # История
            if call.data == "ip_history":
                lookups = self._get_user_lookups(chat_id)

                if not lookups:
                    text = "📋 <b>История запросов</b>\n\n"
                    text += "⚠️ У вас пока нет запросов.\n\n"
                    text += "Используйте «🔍 Поиск IP» для первого запроса."
                else:
                    text = "📋 <b>История запросов</b>\n\n"
                    text += f"Всего запросов: {len(lookups)}\n\n"

                    for i, lookup in enumerate(lookups[:10], 1):
                        text += f"{i}. {lookup.get('query', '?')}\n"
                        text += f"   🌍 {lookup.get('city', '?')}, {lookup.get('country', '?')}\n"
                        text += f"   📡 {lookup.get('isp', '?')}\n"
                        text += f"   {lookup.get('created_at', '')[:16]}\n\n"

                    if len(lookups) > 10:
                        text += f"<i>... и ещё {len(lookups) - 10} запросов</i>"

                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=history_keyboard(),
                    parse_mode="HTML"
                )
                return

            # Повторный поиск
            if call.data == "ip_search_again":
                self.set_user_state(chat_id, 'query_type', 'search')
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="🔍 <b>Поиск IP</b>\n\n"
                         "Отправьте IPv4 или IPv6 адрес:",
                    reply_markup=None,
                    parse_mode="HTML"
                )
                bot.register_next_step_handler_by_chat_id(chat_id, self._process_ip_input, bot)
                return

        except Exception as e:
            bot.answer_callback_query(
                call.id,
                f"Ошибка: {str(e)[:60]}",
                show_alert=True
            )

    def get_menu_keyboard(self) -> types.InlineKeyboardMarkup:
        """
        ОБЯЗАТЕЛЬНО: Возвращает клавиатуру меню модуля.
        """
        return ip_lookup_menu_keyboard()

    def _process_ip_input(self, message, bot):
        """Обработка ввода IP адреса"""
        chat_id = message.chat.id
        ip = message.text.strip()

        # Удаляем сообщение пользователя
        try:
            bot.delete_message(chat_id, message.message_id)
        except:
            pass

        message_id = self.get_user_state(chat_id, 'message_id')

        if message_id is None:
            bot.send_message(
                chat_id,
                "⚠️ Сессия устарела. Вернитесь в главное меню.",
                reply_markup=ip_lookup_menu_keyboard()
            )
            return

        # Проверяем лимит
        if not self._check_lookup_limit(chat_id):
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"⚠️ <b>Лимит запросов</b>\n\n"
                     f"Вы достигли лимита ({MAX_LOOKUPS_PER_USER_PER_DAY}/день).\n\n"
                     f"Попробуйте завтра.",
                reply_markup=ip_lookup_menu_keyboard(),
                parse_mode="HTML"
            )
            return

        # Показываем статус
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="⏳ <b>Запрос информации...</b>",
            reply_markup=None,
            parse_mode="HTML"
        )

        # Получаем информацию в асинхронном режиме
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success, info = loop.run_until_complete(ip_client.get_ip_info(ip))
        loop.close()

        if success:
            text = self._format_ip_info(info)
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=search_result_keyboard(ip),
                parse_mode="HTML"
            )

            # Логируем
            self._log_lookup(chat_id, ip, info)
        else:
            error_msg = info.get('error', 'Неизвестная ошибка')

            # Обработка ошибки 429 (rate limit)
            if "429" in error_msg or "rate limit" in error_msg.lower():
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="⚠️ <b>Превышен лимит API</b>\n\n"
                         "Сервис ipapi.co имеет ограничение на количество запросов.\n\n"
                         "Подождите несколько минут и попробуйте снова.\n\n"
                         "Или получите бесплатный API ключ на ipinfo.io и добавьте его в secrets.py",
                    reply_markup=ip_lookup_menu_keyboard(),
                    parse_mode="HTML"
                )
            else:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"❌ <b>Ошибка</b>\n\n{error_msg}",
                    reply_markup=ip_lookup_menu_keyboard(),
                    parse_mode="HTML"
                )

    def _format_ip_info(self, info: dict) -> str:
        """Форматирование информации об IP"""
        text = "🌍 <b>Информация об IP</b>\n\n"
        text += f"📍 <b>IP:</b> <code>{info.get('ip', 'Unknown')}</code>\n"
        text += f"🏙️ <b>Город:</b> {info.get('city', 'Unknown')}\n"
        text += f"📍 <b>Регион:</b> {info.get('region', 'Unknown')}\n"
        text += f"🌐 <b>Страна:</b> {info.get('country', 'Unknown')} ({info.get('country_code', 'Unknown')})\n"

        # Увеличен лимит до 100 символов
        isp = info.get('isp', 'Unknown')
        if len(isp) > 100:
            isp = isp[:100] + "..."
        text += f"📡 <b>Провайдер:</b> {isp}\n"

        text += f"🕐 <b>Часовой пояс:</b> {info.get('timezone', 'Unknown')}\n"
        text += f"📮 <b>Почтовый индекс:</b> {info.get('postal', 'Unknown')}\n"
        text += f"🌐 <b>ASN:</b> {info.get('asn', 'Unknown')}\n"

        lat = info.get('latitude', 'Unknown')
        lon = info.get('longitude', 'Unknown')
        if lat != 'Unknown' and lon != 'Unknown':
            text += f"📍 <b>Координаты:</b> {lat}, {lon}\n"

        text += f"\n📊 <b>Источник:</b> {info.get('source', 'Unknown')}"

        return text

    def _check_lookup_limit(self, user_id: int) -> bool:
        """Проверка лимита запросов"""
        try:
            conn = sqlite3.connect(config.DATABASE_PATH)
            cursor = conn.cursor()
            today = datetime.now().strftime('%Y-%m-%d')

            cursor.execute(f"""
                SELECT COUNT(*) FROM {TABLE_NAME}
                WHERE user_id = ? AND DATE(created_at) = ?
            """, (user_id, today))

            count = cursor.fetchone()[0]
            conn.close()

            return count < MAX_LOOKUPS_PER_USER_PER_DAY
        except:
            return True

    def _log_lookup(self, user_id: int, query: str, info: dict):
        """Логирование запроса"""
        try:
            conn = sqlite3.connect(config.DATABASE_PATH)
            cursor = conn.cursor()

            cursor.execute(f"""
                INSERT INTO {TABLE_NAME} 
                (user_id, query, ip, city, country, isp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                query,
                info.get('ip', query),
                info.get('city', 'Unknown'),
                info.get('country', 'Unknown'),
                info.get('isp', 'Unknown')
            ))

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"⚠️ Ошибка логирования: {str(e)}")

    def _get_user_lookups(self, user_id: int) -> list:
        """Получение истории запросов пользователя"""
        try:
            conn = sqlite3.connect(config.DATABASE_PATH)
            cursor = conn.cursor()

            cursor.execute(f"""
                SELECT query, ip, city, country, isp, created_at
                FROM {TABLE_NAME}
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 50
            """, (user_id,))

            lookups = []
            for row in cursor.fetchall():
                lookups.append({
                    'query': row[0],
                    'ip': row[1],
                    'city': row[2],
                    'country': row[3],
                    'isp': row[4],
                    'created_at': row[5]
                })

            conn.close()
            return lookups
        except:
            return []

    def on_load(self, bot: Any) -> None:
        """Вызывается при загрузке модуля"""
        print(f"🌍 Модуль IP Info Lookup v{self.version} загружен")

    def on_unload(self, bot: Any) -> None:
        """Вызывается при выгрузке модуля"""
        print(f"🌍 Модуль IP Info Lookup v{self.version} выгружен")