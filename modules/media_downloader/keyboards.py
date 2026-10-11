"""Keyboards for the deliberately disabled Media Downloader module."""

from telebot import types


def media_downloader_menu_keyboard() -> types.InlineKeyboardMarkup:
    """Return only safe navigation while download operations are unavailable."""

    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(types.InlineKeyboardButton("🔙 Назад", callback_data="media_back_to_modules"))
    return keyboard
