# modules/steam_deals/keyboards.py
# Клавиатуры модуля "Steam Deals Tracker"

from telebot import types


def steam_main_menu_keyboard():
    """Главное меню модуля Steam Deals"""
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📜 Мой вишлист", callback_data="steam_wishlist"),
        types.InlineKeyboardButton("🔥 Популярные скидки", callback_data="steam_popular"),
        types.InlineKeyboardButton("🎁 Бесплатно", callback_data="steam_free"),
        types.InlineKeyboardButton("➕ Добавить игру", callback_data="steam_add"),
        types.InlineKeyboardButton("🔙 Назад", callback_data="steam_back_to_modules")
    )
    return kb


def wishlist_keyboard(is_empty: bool = False):
    """Клавиатура для вишлиста"""
    kb = types.InlineKeyboardMarkup(row_width=3)

    if not is_empty:
        kb.add(
            types.InlineKeyboardButton("🔄 Обновить цены", callback_data="steam_wishlist_refresh"),
            types.InlineKeyboardButton("❌ Удалить игру", callback_data="steam_wishlist_delete"),
            types.InlineKeyboardButton("🔙 Назад", callback_data="steam_back_to_menu")
        )
    else:
        kb.add(
            types.InlineKeyboardButton("🔙 Назад", callback_data="steam_back_to_menu")
        )

    return kb


def popular_deals_keyboard():
    """Клавиатура для популярных скидок"""
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🔄 Обновить", callback_data="steam_popular_refresh"),
        types.InlineKeyboardButton("➕ Добавить из списка", callback_data="steam_add_from_popular")
    )
    kb.add(
        types.InlineKeyboardButton("🔙 В меню", callback_data="steam_back_to_menu")
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


def search_results_keyboard(game_id: str):
    """Клавиатура для результатов поиска"""
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✅ Добавить", callback_data=f"steam_add_game_{game_id}"),
        types.InlineKeyboardButton("🔙 Отмена", callback_data="steam_back_to_menu")
    )
    return kb


def confirm_delete_keyboard():
    """Клавиатура для подтверждения удаления"""
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🔙 Отмена", callback_data="steam_wishlist")
    )
    return kb