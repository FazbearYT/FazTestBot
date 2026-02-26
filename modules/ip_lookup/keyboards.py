# modules/ip_lookup/keyboards.py
# Клавиатуры модуля "IP Info Lookup"
# Версия: 1.0.1
# Дата: 26.02.2026

from telebot import types


def ip_lookup_menu_keyboard():
    """Меню модуля IP Info Lookup"""
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🔍 Поиск IP", callback_data="ip_search"),
        types.InlineKeyboardButton("📋 История", callback_data="ip_history"),
        types.InlineKeyboardButton("🔙 Назад", callback_data="ip_back_to_modules")
    )
    return kb


def search_result_keyboard(ip: str):
    """Клавиатура после получения информации об IP"""
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🔄 Ещё запрос", callback_data="ip_search_again"),
        types.InlineKeyboardButton("🔙 К меню", callback_data="ip_back_to_menu")
    )
    return kb


def history_keyboard():
    """Клавиатура для меню 'История'"""
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🔍 Новый поиск", callback_data="ip_search"),
        types.InlineKeyboardButton("🔙 К меню", callback_data="ip_back_to_menu")
    )
    return kb