# modules/cipher/handlers.py
# Обработчики модуля "Шифратор" для FazTestBot
# Адаптирован под BaseModule с унифицированным интерфейсом

import qrcode
import os
import uuid
import hashlib
from telebot import types
from typing import Any
from core.module_base import BaseModule
from core.database import DatabaseManager
from .keyboards import (
    cipher_menu_keyboard,
    caesar_language_keyboard,
    result_menu_keyboard
)
from .ciphers import caesar_cipher, validate_caesar_text
from .config import SHIFR

# Глобальный экземпляр БД
db = DatabaseManager()


class CipherModule(BaseModule):
    """
    Модуль шифрования текста.

    Наследуется от BaseModule и реализует все обязательные методы.
    Поддерживает: Азбуку Морзе, Числовой шифр, QR-код, Шифр Цезаря
    """

    def __init__(self, module_id, name, description, icon, version, callback_prefix):
        """Инициализация модуля Шифратор"""
        super().__init__(module_id, name, description, icon, version, callback_prefix)

    def handle_entry(self, bot: Any, call: Any) -> None:
        """
        ОБЯЗАТЕЛЬНО: Вход в модуль — показ меню шифров.

        :param bot: Экземпляр TeleBot
        :param call: Объект CallbackQuery
        """
        chat_id = call.message.chat.id
        message_id = call.message.message_id

        # Генерируем уникальный session_id для группировки операций
        session_id = str(uuid.uuid4())

        # Инициализируем состояние пользователя для модуля
        self.set_user_state(chat_id, 'message_id', message_id)
        self.set_user_state(chat_id, 'session_id', session_id)
        self.set_user_state(chat_id, 'cipher', None)
        self.set_user_state(chat_id, 'step', None)
        self.set_user_state(chat_id, 'language', None)
        self.set_user_state(chat_id, 'qr_message_id', None)

        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="🔐 <b>Шифратор</b>\n\nВыберите тип шифрования:",
            reply_markup=self.get_menu_keyboard(),
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

            # Назад к списку модулей
            if call.data == "cipher_back_to_modules":
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

            # НАЗАД К МЕНЮ ШИФРОВ
            if call.data == "cipher_back_to_menu":
                # УДАЛЯЕМ СООБЩЕНИЕ С QR-КОДОМ, ЕСЛИ ОНО ЕСТЬ
                qr_message_id = self.get_user_state(chat_id, 'qr_message_id')
                if qr_message_id:
                    try:
                        bot.delete_message(chat_id, qr_message_id)
                    except Exception:
                        pass

                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="🔐 <b>Шифратор</b>\n\nВыберите тип шифрования:",
                    reply_markup=self.get_menu_keyboard(),
                    parse_mode="HTML"
                )
                # Сбрасываем параметры шифра Цезаря
                self.set_user_state(chat_id, 'step', None)
                self.set_user_state(chat_id, 'language', None)
                return

            # Проверка состояния пользователя
            if self.get_user_state(chat_id, 'message_id') is None:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="⚠️ Сессия устарела. Вернитесь в главное меню.",
                    reply_markup=self.get_menu_keyboard(),
                    parse_mode="HTML"
                )
                return

            # Выбор шифра: Морзе
            if call.data == "cipher_morze":
                self.set_user_state(chat_id, 'cipher', 'morze')
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="🔤 <b>Азбука Морзе</b>\n\nВведите текст для шифрования:",
                    reply_markup=None,
                    parse_mode="HTML"
                )
                bot.register_next_step_handler(call.message, self._process_text_input, bot)
                return

            # Выбор шифра: Числовой
            if call.data == "cipher_numbers":
                self.set_user_state(chat_id, 'cipher', 'numbers')
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="🔢 <b>Числовой шифр</b>\n\nВведите текст для шифрования:",
                    reply_markup=None,
                    parse_mode="HTML"
                )
                bot.register_next_step_handler(call.message, self._process_text_input, bot)
                return

            # Выбор шифра: QR-код
            if call.data == "cipher_qr":
                self.set_user_state(chat_id, 'cipher', 'qr')
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="📷 <b>QR-код</b>\n\nВведите текст для генерации QR-кода:",
                    reply_markup=None,
                    parse_mode="HTML"
                )
                bot.register_next_step_handler(call.message, self._process_text_input, bot)
                return

            # Выбор шифра: Цезарь
            if call.data == "cipher_caesar":
                self.set_user_state(chat_id, 'cipher', 'caesar')
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="🔄 <b>Шифр Цезаря</b>\n\nВведите шаг шифрования (целое число, например: 3 или -5):",
                    reply_markup=None,
                    parse_mode="HTML"
                )
                bot.register_next_step_handler(call.message, self._caesar_step_input, bot)
                return

            # Язык для Цезаря
            if call.data in ["cipher_lang_ru", "cipher_lang_en"]:
                cipher = self.get_user_state(chat_id, 'cipher')
                if cipher != 'caesar':
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text="⚠️ Сессия устарела. Вернитесь в меню шифров.",
                        reply_markup=self.get_menu_keyboard(),
                        parse_mode="HTML"
                    )
                    return

                lang = 'ru' if call.data == "cipher_lang_ru" else 'en'
                self.set_user_state(chat_id, 'language', lang)

                step = self.get_user_state(chat_id, 'step', 0)
                lang_name = "русский" if lang == 'ru' else "английский"
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"🔤 <b>Шифр Цезаря</b>\nЯзык: {lang_name}\nШаг: {step}\n\nВведите текст для шифрования:",
                    reply_markup=None,
                    parse_mode="HTML"
                )
                bot.register_next_step_handler(call.message, self._process_text_input, bot)
                return

            # Повторный ввод
            if call.data == "cipher_again":
                cipher = self.get_user_state(chat_id, 'cipher')
                titles = {
                    'morze': "🔤 <b>Азбука Морзе</b>\n\nВведите текст для шифрования:",
                    'numbers': "🔢 <b>Числовой шифр</b>\n\nВведите текст для шифрования:",
                    'qr': "📷 <b>QR-код</b>\n\nВведите текст для генерации QR-кода:",
                    'caesar': f"🔤 <b>Шифр Цезаря</b>\nЯзык: {self.get_user_state(chat_id, 'language', '??')}\nШаг: {self.get_user_state(chat_id, 'step', '??')}\n\nВведите текст для шифрования:"
                }

                if cipher == 'caesar':
                    if self.get_user_state(chat_id, 'step') is None or self.get_user_state(chat_id, 'language') is None:
                        bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=message_id,
                            text="⚠️ Неполные параметры Цезаря. Вернитесь в меню шифров.",
                            reply_markup=self.get_menu_keyboard(),
                            parse_mode="HTML"
                        )
                        return

                # Удаляем сообщение с QR-кодом, если оно существует
                if cipher == 'qr':
                    qr_message_id = self.get_user_state(chat_id, 'qr_message_id')
                    if qr_message_id:
                        try:
                            bot.delete_message(chat_id, qr_message_id)
                        except Exception:
                            pass

                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=titles.get(cipher, "🔐 <b>Шифратор</b>\n\nВведите текст:"),
                    reply_markup=None,
                    parse_mode="HTML"
                )
                bot.register_next_step_handler_by_chat_id(chat_id, self._process_text_input, bot)
                return

            # Изменить настройки Цезаря
            if call.data == "cipher_change_settings":
                cipher = self.get_user_state(chat_id, 'cipher')
                if cipher != 'caesar':
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text="⚠️ Сессия устарела. Вернитесь в меню шифров.",
                        reply_markup=self.get_menu_keyboard(),
                        parse_mode="HTML"
                    )
                    return

                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="🔄 <b>Шифр Цезаря</b>\n\nВведите новый шаг шифрования (целое число):",
                    reply_markup=None,
                    parse_mode="HTML"
                )
                bot.register_next_step_handler_by_chat_id(chat_id, self._caesar_step_input, bot)
                return

        except Exception as e:
            bot.answer_callback_query(call.id, f"Ошибка: {str(e)[:60]}", show_alert=True)

    def get_menu_keyboard(self) -> types.InlineKeyboardMarkup:
        """
        ОБЯЗАТЕЛЬНО: Возвращает клавиатуру меню модуля.

        :return: InlineKeyboardMarkup для меню модуля
        """
        return cipher_menu_keyboard()

    def _caesar_step_input(self, message, bot):
        """Обработка ввода шага для шифра Цезаря"""
        chat_id = message.chat.id

        try:
            step = int(message.text.strip())

            cipher = self.get_user_state(chat_id, 'cipher')
            if cipher != 'caesar':
                bot.send_message(
                    chat_id,
                    "⚠️ Сессия устарела. Вернитесь в меню шифров.",
                    reply_markup=self.get_menu_keyboard()
                )
                self.cleanup_user_state(chat_id)
                return

            self.set_user_state(chat_id, 'step', step)

            # Удаляем сообщение пользователя
            try:
                bot.delete_message(chat_id, message.message_id)
            except Exception:
                pass

            # Редактируем сообщение бота
            bot_message_id = self.get_user_state(chat_id, 'message_id')

            bot.edit_message_text(
                chat_id=chat_id,
                message_id=bot_message_id,
                text=f"🔄 <b>Шифр Цезаря</b>\nШаг: {step}\n\nВыберите язык текста:",
                reply_markup=caesar_language_keyboard(),
                parse_mode="HTML"
            )

        except ValueError:
            # Удаляем сообщение пользователя
            try:
                bot.delete_message(chat_id, message.message_id)
            except Exception:
                pass

            bot_message_id = self.get_user_state(chat_id, 'message_id')
            if bot_message_id:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=bot_message_id,
                    text="❌ Некорректный шаг! Введите целое число (например: 3 или -5):",
                    parse_mode="HTML"
                )
                bot.register_next_step_handler_by_chat_id(chat_id, self._caesar_step_input, bot)
            else:
                bot.send_message(
                    chat_id,
                    "⚠️ Сессия устарела. Вернитесь в меню шифров.",
                    reply_markup=self.get_menu_keyboard()
                )

    def _process_text_input(self, message, bot):
        """Обработка ввода текста для шифрования"""
        chat_id = message.chat.id
        text = message.text

        # Удаляем сообщение пользователя
        try:
            bot.delete_message(chat_id, message.message_id)
        except Exception:
            pass

        # Проверяем состояние
        if self.get_user_state(chat_id, 'message_id') is None:
            bot.send_message(
                chat_id,
                "⚠️ Сессия устарела. Вернитесь в главное меню.",
                reply_markup=self.get_menu_keyboard()
            )
            return

        cipher = self.get_user_state(chat_id, 'cipher')
        message_id = self.get_user_state(chat_id, 'message_id')
        session_id = self.get_user_state(chat_id, 'session_id')

        try:
            # Шифрование Морзе
            if cipher == "morze":
                result = ""
                for char in text.lower():
                    if char in SHIFR["morze"]:
                        result += SHIFR["morze"][char] + " "
                    else:
                        result += f"[{char}] "

                # ЛОГИРУЕМ ОПЕРАЦИЮ ПОСЛЕ УСПЕШНОГО ШИФРОВАНИЯ
                db.log_cipher_operation(
                    user_id=chat_id,
                    cipher_type="morze",
                    original_text=text,
                    encrypted_text=result.strip(),
                    session_id=session_id
                )

                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=(
                        f"🔤 <b>Исходный текст:</b>\n<code>{text}</code>\n\n"
                        f"📡 <b>Результат (Морзе):</b>\n<code>{result.strip()}</code>"
                    ),
                    reply_markup=result_menu_keyboard('morze'),
                    parse_mode="HTML"
                )

            # Числовой шифр
            elif cipher == "numbers":
                result = ""
                for char in text.lower():
                    if char in SHIFR["numbers"]:
                        result += SHIFR["numbers"][char] + " "
                    else:
                        result += f"[{char}] "

                # ЛОГИРУЕМ ОПЕРАЦИЮ
                db.log_cipher_operation(
                    user_id=chat_id,
                    cipher_type="numbers",
                    original_text=text,
                    encrypted_text=result.strip(),
                    session_id=session_id
                )

                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=(
                        f"🔤 <b>Исходный текст:</b>\n<code>{text}</code>\n\n"
                        f"🔢 <b>Результат (числа):</b>\n<code>{result.strip()}</code>"
                    ),
                    reply_markup=result_menu_keyboard('numbers'),
                    parse_mode="HTML"
                )

            # QR-код
            elif cipher == "qr":
                # ИСПРАВЛЕНО: используем hashlib вместо hash() для стабильности
                hash_object = hashlib.md5(text.encode())
                filename = f"qr_{chat_id}_{hash_object.hexdigest()}.png"
                try:
                    # Генерация QR-кода
                    img = qrcode.make(text)
                    img.save(filename)

                    # Удаляем исходное сообщение
                    try:
                        bot.delete_message(chat_id, message_id)
                    except Exception:
                        pass

                    # Отправляем QR-код
                    with open(filename, 'rb') as photo:
                        qr_message = bot.send_photo(
                            chat_id,
                            photo,
                            caption=f"🔤 <b>Исходный текст:</b>\n<code>{text}</code>",
                            parse_mode="HTML"
                        )

                    # Сохраняем ID сообщения с QR-кодом
                    self.set_user_state(chat_id, 'qr_message_id', qr_message.message_id)

                    # ЛОГИРУЕМ ОПЕРАЦИЮ (для QR сохраняем текст как результат)
                    db.log_cipher_operation(
                        user_id=chat_id,
                        cipher_type="qr",
                        original_text=text,
                        encrypted_text=text,
                        session_id=session_id
                    )

                    # Отправляем сообщение с результатом
                    result_message = bot.send_message(
                        chat_id,
                        "✅ QR-код сгенерирован!",
                        reply_markup=result_menu_keyboard('qr'),
                        parse_mode="HTML"
                    )

                    # Обновляем message_id для дальнейшей работы
                    self.set_user_state(chat_id, 'message_id', result_message.message_id)

                finally:
                    if os.path.exists(filename):
                        os.remove(filename)

            # Шифр Цезаря
            elif cipher == "caesar":
                step = self.get_user_state(chat_id, 'step')
                lang = self.get_user_state(chat_id, 'language')

                if step is None or lang is None:
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text="⚠️ Неполные параметры. Вернитесь в меню шифров.",
                        reply_markup=self.get_menu_keyboard(),
                        parse_mode="HTML"
                    )
                    self.cleanup_user_state(chat_id)
                    return

                # Проверка алфавита
                is_valid, error_message = validate_caesar_text(text, lang)
                if not is_valid:
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=(
                            f"🔤 <b>Исходный текст:</b>\n<code>{text}</code>\n\n"
                            f"{error_message}\n\n"
                            f"Введите текст заново:"
                        ),
                        reply_markup=None,
                        parse_mode="HTML"
                    )
                    bot.register_next_step_handler_by_chat_id(chat_id, self._process_text_input, bot)
                    return

                result = caesar_cipher(text, step, lang)

                # ЛОГИРУЕМ ОПЕРАЦИЮ
                db.log_cipher_operation(
                    user_id=chat_id,
                    cipher_type="caesar",
                    original_text=text,
                    encrypted_text=result,
                    language=lang,
                    step=step,
                    session_id=session_id
                )

                lang_name = "русский" if lang == 'ru' else "английский"
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=(
                        f"🔤 <b>Исходный текст:</b>\n<code>{text}</code>\n\n"
                        f"🔄 <b>Результат (Цезарь):</b>\n<code>{result}</code>\n\n"
                        f"Язык: {lang_name}\nШаг: {step}"
                    ),
                    reply_markup=result_menu_keyboard('caesar'),
                    parse_mode="HTML"
                )

        except Exception as e:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"❌ Ошибка при обработке: {str(e)}",
                reply_markup=self.get_menu_keyboard(),
                parse_mode="HTML"
            )
            self.cleanup_user_state(chat_id)

    def on_load(self, bot: Any) -> None:
        """
        ОПЦИОНАЛЬНО: Вызывается при загрузке модуля.

        :param bot: Экземпляр TeleBot
        """
        print(f"🔐 Модуль Шифратор v{self.version} загружен")

    def on_unload(self, bot: Any) -> None:
        """
        ОПЦИОНАЛЬНО: Вызывается при выгрузке модуля.

        :param bot: Экземпляр TeleBot
        """
        print(f"🔐 Модуль Шифратор v{self.version} выгружен")