# modules/cipher/keyboards.py
# Клавиатуры модуля "Шифратор"

from telebot import types


def cipher_menu_keyboard():
    """Меню выбора шифра"""
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("📡 Азбука Морзе", callback_data="cipher_morze"),
        types.InlineKeyboardButton("🔢 Числовой шифр", callback_data="cipher_numbers"),
        types.InlineKeyboardButton("💀 Leet спик", callback_data="cipher_leet"),
        types.InlineKeyboardButton("📷 QR-код", callback_data="cipher_qr"),
        types.InlineKeyboardButton("🔄 Шифр Цезаря", callback_data="cipher_caesar"),
        types.InlineKeyboardButton("🔙 Назад", callback_data="cipher_back_to_modules")
    )
    return kb

def leet_difficulty_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🟢 Light", callback_data="cipher_leet_light"),
        types.InlineKeyboardButton("🟡 Medium", callback_data="cipher_leet_medium"),
        types.InlineKeyboardButton("🔴 Hardcore", callback_data="cipher_leet_hardcore"),
        types.InlineKeyboardButton("⚙️ Детальная настройка", callback_data="cipher_leetadv"),
        types.InlineKeyboardButton("ℹ️ О шифре Leet", callback_data="cipher_leetinfo"),
        types.InlineKeyboardButton("🔙 Отмена", callback_data="cipher_back_to_menu")
    )
    return kb

def leet_advanced_keyboard():
    """Детальная настройка: выбор словаря, вероятность задаётся вручную"""
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🟢 Словарь Light", callback_data="cipher_ladv_light"),
        types.InlineKeyboardButton("🟡 Словарь Medium", callback_data="cipher_ladv_medium"),
        types.InlineKeyboardButton("🔴 Словарь Hardcore", callback_data="cipher_ladv_hardcore"),
        types.InlineKeyboardButton("🔙 Назад", callback_data="cipher_leet")
    )
    return kb


def caesar_language_keyboard():
    """Выбор языка для шифра Цезаря"""
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🇷🇺 Русский", callback_data="cipher_lang_ru"),
        types.InlineKeyboardButton("🇬🇧 Английский", callback_data="cipher_lang_en"),
        types.InlineKeyboardButton("🔙 Отмена", callback_data="cipher_back_to_menu")
    )
    return kb


def result_menu_keyboard(cipher_type):
    """Меню после получения результата"""
    kb = types.InlineKeyboardMarkup(row_width=2)

    if cipher_type == "caesar":
        kb.add(
            types.InlineKeyboardButton("🔄 Другой текст", callback_data="cipher_again"),
            types.InlineKeyboardButton("⚙️ Изменить настройки", callback_data="cipher_caesar_change_settings"),
            types.InlineKeyboardButton("🔙 К шифрам", callback_data="cipher_back_to_menu")
        )
    elif cipher_type == "leet":
        kb.add(
            types.InlineKeyboardButton("🔄 Другой текст", callback_data="cipher_again"),
            types.InlineKeyboardButton("⚙️ Изменить настройки", callback_data="cipher_leets_change_settings"),
            types.InlineKeyboardButton("🔙 К шифрам", callback_data="cipher_back_to_menu")
        )
    else:
        kb.add(
            types.InlineKeyboardButton("🔄 Другой текст", callback_data="cipher_again"),
            types.InlineKeyboardButton("🔙 К шифрам", callback_data="cipher_back_to_menu")
        )
    return kb