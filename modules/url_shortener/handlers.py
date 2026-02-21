# modules/url_shortener/handlers.py
# Обработчики модуля "URL Shortener"
# Версия: 1.0.4
# Дата: 21.02.2026

import asyncio
import sqlite3
from telebot import types
from typing import Any
from core.module_base import BaseModule
from core.database import DatabaseManager
from .keyboards import (
    url_shortener_menu_keyboard,
    result_menu_keyboard,
    my_links_keyboard
)
from .api_client import url_client
import config

# Глобальный экземпляр БД
db = DatabaseManager()


class URLShortenerModule(BaseModule):
    """
    Модуль сокращения ссылок.

    Наследуется от BaseModule и реализует все обязательные методы.
    Работает по аналогии с модулем шифрования.
    """

    def __init__(self, module_id, name, description, icon, version, callback_prefix):
        """Инициализация модуля URL Shortener"""
        super().__init__(module_id, name, description, icon, version, callback_prefix)

    def handle_entry(self, bot: Any, call: Any) -> None:
        """
        ОБЯЗАТЕЛЬНО: Вход в модуль — показ меню.

        :param bot: Экземпляр TeleBot
        :param call: Объект CallbackQuery
        """
        chat_id = call.message.chat.id
        message_id = call.message.message_id

        # Инициализируем состояние пользователя
        self.set_user_state(chat_id, 'message_id', message_id)

        # Показываем меню с кнопкой "Назад"
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="🔗 <b>URL Shortener</b>\n\nВыберите действие:",
            reply_markup=url_shortener_menu_keyboard(show_back_button=True),
            parse_mode="HTML"
        )

    def handle_callback(self, bot: Any, call: Any) -> None:
        """
        ОБЯЗАТЕЛЬНО: Обработка колбэков внутри модуля.

        :param bot: Экземпляр TeleBot
        :param call: Объект CallbackQuery
        """
        chat_id = call.message.chat.id
        message_id = call.message.message_id

        try:
            bot.answer_callback_query(call.id)

            # Назад к списку модулей (из меню модуля)
            if call.data == "url_back_to_modules":
                # Получаем список всех модулей и показываем их
                from core.module_manager import module_manager
                modules = module_manager.get_all_modules()

                # Создаём клавиатуру со списком модулей
                kb = types.InlineKeyboardMarkup(row_width=1)
                for module in modules:
                    kb.add(
                        types.InlineKeyboardButton(
                            f"{module.icon} {module.name}",
                            callback_data=f"module_{module.id}"
                        )
                    )
                kb.add(
                    types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")
                )

                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="📦 <b>Доступные модули</b>\n\nВыберите модуль для работы:",
                    reply_markup=kb,
                    parse_mode="HTML"
                )
                # Очищаем состояние пользователя
                self.cleanup_user_state(chat_id)
                return

            # Назад в меню модуля (из результата сокращения)
            if call.data == "url_back_to_menu":
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="🔗 <b>URL Shortener</b>\n\nВыберите действие:",
                    reply_markup=url_shortener_menu_keyboard(show_back_button=True),
                    parse_mode="HTML"
                )
                return

            # Сократить ссылку
            if call.data == "url_shorten":
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="🔗 <b>URL Shortener</b>\n\nОтправьте ссылку для сокращения:",
                    reply_markup=None,
                    parse_mode="HTML"
                )
                bot.register_next_step_handler(call.message, self._process_url_input, bot)
                return

            # Мои ссылки
            elif call.data == "url_my_links":
                # Получаем историю ссылок пользователя из БД
                links = self._get_user_links(chat_id)

                if not links:
                    text = "📋 <b>Мои ссылки</b>\n\n"
                    text += "⚠️ У вас пока нет сокращённых ссылок.\n\n"
                    text += "Используйте «🔗 Сократить ссылку» для создания первой."
                else:
                    text = "📋 <b>Мои ссылки</b>\n\n"
                    text += f"Всего ссылок: {len(links)}\n\n"

                    # Показываем последние 10
                    for i, link in enumerate(links[:10], 1):
                        text += f"{i}. {link['created_at'][:10]}\n"
                        # Используем code для предотвращения превью
                        original_url = link['original_url']
                        if len(original_url) > 60:
                            original_url = original_url[:60] + "..."
                        text += f"   Исходная: <code>{original_url}</code>\n"
                        text += f"   Сокращённая: <code>{link['shortened_url']}</code>\n\n"

                    if len(links) > 10:
                        text += f"<i>... и ещё {len(links) - 10} ссылок</i>"

                # Отправляем с отключенным превью ссылок и специальной клавиатурой
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=my_links_keyboard(),  # Специальная клавиатура!
                    parse_mode="HTML",
                    disable_web_page_preview=True  # Отключаем превью!
                )
                return

            # Повторный ввод
            elif call.data == "url_again":
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="🔗 <b>URL Shortener</b>\n\nОтправьте ссылку для сокращения:",
                    reply_markup=None,
                    parse_mode="HTML"
                )
                bot.register_next_step_handler_by_chat_id(chat_id, self._process_url_input, bot)
                return

        except Exception as e:
            bot.answer_callback_query(call.id, f"Ошибка: {str(e)[:60]}", show_alert=True)

    def get_menu_keyboard(self) -> types.InlineKeyboardMarkup:
        """
        ОБЯЗАТЕЛЬНО: Возвращает клавиатуру меню модуля.

        :return: InlineKeyboardMarkup для меню модуля
        """
        return url_shortener_menu_keyboard(show_back_button=False)

    def _process_url_input(self, message, bot):
        """Обработка ввода ссылки для сокращения"""
        chat_id = message.chat.id
        url = message.text.strip()

        # Удаляем сообщение пользователя (приватность)
        try:
            bot.delete_message(chat_id, message.message_id)
        except Exception:
            pass

        # Проверяем состояние
        message_id = self.get_user_state(chat_id, 'message_id')
        if message_id is None:
            from core.keyboards import back_to_main_keyboard
            bot.send_message(
                chat_id,
                "⚠️ Сессия устарела. Вернитесь в главное меню.",
                reply_markup=back_to_main_keyboard()
            )
            return

        try:
            # ИСПРАВЛЕНО: используем asyncio.run() вместо deprecated new_event_loop()
            success, result = asyncio.run(url_client.shorten_url(url))

            if success:
                shortened_url = result

                # Логируем операцию в БД
                self._log_url_operation(chat_id, url, shortened_url)

                # Формируем сообщение с результатом (как в шифраторе)
                original_display = url if len(url) <= 50 else url[:50] + "..."

                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=(
                        f"🔗 <b>Исходная ссылка:</b>\n<code>{original_display}</code>\n\n"
                        f"🔗 <b>Сокращённая ссылка:</b>\n<code>{shortened_url}</code>"
                    ),
                    reply_markup=result_menu_keyboard(shortened_url),
                    parse_mode="HTML",
                    disable_web_page_preview=True  # Отключаем превью!
                )
            else:
                # Ошибка сокращения
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"❌ <b>Ошибка сокращения:</b>\n\n{result}\n\nПопробуйте другую ссылку.",
                    reply_markup=url_shortener_menu_keyboard(show_back_button=True),
                    parse_mode="HTML"
                )

        except Exception as e:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"❌ <b>Ошибка при обработке:</b>\n{str(e)}",
                reply_markup=url_shortener_menu_keyboard(show_back_button=True),
                parse_mode="HTML"
            )

    @staticmethod
    def _log_url_operation(user_id: int, original_url: str, shortened_url: str):
        """Логирование операции сокращения в БД"""
        try:
            conn = sqlite3.connect(config.DATABASE_PATH)
            cursor = conn.cursor()

            # Создаём таблицу если не существует
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS url_shortener_logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    original_url TEXT NOT NULL,
                    shortened_url TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    clicks_count INTEGER DEFAULT 0
                )
            """)

            # Вставляем запись
            cursor.execute("""
                INSERT INTO url_shortener_logs (user_id, original_url, shortened_url)
                VALUES (?, ?, ?)
            """, (user_id, original_url, shortened_url))

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"⚠️ Ошибка логирования URL: {str(e)}")

    @staticmethod
    def _get_user_links(user_id: int) -> list:
        """Получение истории ссылок пользователя из БД"""
        try:
            conn = sqlite3.connect(config.DATABASE_PATH)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT original_url, shortened_url, created_at, clicks_count
                FROM url_shortener_logs
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 50
            """, (user_id,))

            links = []
            for row in cursor.fetchall():
                links.append({
                    'original_url': row[0],
                    'shortened_url': row[1],
                    'created_at': row[2],
                    'clicks_count': row[3]
                })

            conn.close()
            return links
        except Exception as e:
            print(f"⚠️ Ошибка получения ссылок: {str(e)}")
            return []

    def on_load(self, bot: Any) -> None:
        """Вызывается при загрузке модуля"""
        print(f"🔗 Модуль URL Shortener v{self.version} загружен")

    def on_unload(self, bot: Any) -> None:
        """Вызывается при выгрузке модуля"""
        print(f"🔗 Модуль URL Shortener v{self.version} выгружен")