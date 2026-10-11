# modules/steam_deals/keyboards.py
# Клавиатуры модуля "Steam Deals Tracker"

from telebot import types


def steam_main_menu_keyboard():
    """Главное меню модуля Steam Deals"""
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📜 Мой вишлист", callback_data="steam_wishlist"),
        types.InlineKeyboardButton("🎁 Бесплатно", callback_data="steam_free"),
        types.InlineKeyboardButton("🔙 Назад", callback_data="steam_back_to_modules")
    )
    return kb


def wishlist_keyboard(is_empty: bool = False):
    """Клавиатура для вишлиста"""
    kb = types.InlineKeyboardMarkup(row_width=2)

    if not is_empty:
        kb.add(
            types.InlineKeyboardButton("🔄 Обновить цены", callback_data="steam_wishlist_refresh"),
            types.InlineKeyboardButton("➕ Добавить игру", callback_data="steam_add_from_wishlist")
        )
        kb.add(
            types.InlineKeyboardButton("❌ Удалить игру", callback_data="steam_wishlist_delete"),
            types.InlineKeyboardButton("🔙 Назад", callback_data="steam_back_to_menu")
        )
    else:
        kb.add(
            types.InlineKeyboardButton("➕ Добавить игру", callback_data="steam_add_from_wishlist"),
            types.InlineKeyboardButton("🔙 Назад", callback_data="steam_back_to_menu")
        )

    return kb


def free_games_keyboard():
    """Клавиатура для бесплатных игр"""
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🔄 Обновить", callback_data="steam_free_refresh")
    )
    kb.add(
        types.InlineKeyboardButton("🔙 В меню", callback_data="steam_back_to_menu")
    )
    return kb


def add_game_keyboard():
    """Клавиатура для добавления игры"""
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🔙 В меню", callback_data="steam_back_to_menu")
    )
    return kb


def confirm_delete_keyboard():
    """Клавиатура для подтверждения удаления"""
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🔙 Отмена", callback_data="steam_wishlist")
    )
    return kb