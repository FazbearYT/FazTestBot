# modules/url_shortener/keyboards.py
# Клавиатуры модуля "URL Shortener"
# Версия: 1.0.3
# Дата: 21.02.2026

from telebot import types


def url_shortener_menu_keyboard(show_back_button: bool = True):
    """
    Меню модуля сокращения ссылок

    :param show_back_button: Показывать ли кнопку "Назад" к списку модулей
    """
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🔗 Сократить ссылку", callback_data="url_shorten"),
        types.InlineKeyboardButton("📋 Мои ссылки", callback_data="url_my_links")
    )

    if show_back_button:
        kb.add(
            types.InlineKeyboardButton("🔙 Назад", callback_data="url_back_to_modules")
        )

    return kb


def result_menu_keyboard(shortened_url: str):
    """Клавиатура после сокращения ссылки"""
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🌐 Открыть", url=shortened_url),
        types.InlineKeyboardButton("🔄 Другая ссылка", callback_data="url_again")
    )
    kb.add(
        types.InlineKeyboardButton("🔙 Назад", callback_data="url_back_to_menu")
    )
    return kb


def my_links_keyboard():
    """Клавиатура для меню 'Мои ссылки'"""
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🔗 Сократить ссылку", callback_data="url_shorten"),
        types.InlineKeyboardButton("🔙 Назад", callback_data="url_back_to_menu")
    )
    return kb