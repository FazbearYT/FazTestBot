# modules/decision_maker/keyboards.py
# Клавиатуры модуля "Decision Maker"

from telebot import types


def decision_maker_menu_keyboard():
    """Меню модуля Decision Maker"""
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🎲 Числа", callback_data="dm_numbers"),
        types.InlineKeyboardButton("📝 Список", callback_data="dm_list"),
        types.InlineKeyboardButton("⚔️ Dota 2", callback_data="dm_dota2"),
        types.InlineKeyboardButton("🪙 Монетка", callback_data="dm_coin")
    )
    kb.add(
        types.InlineKeyboardButton("🔙 Назад", callback_data="dm_back_to_modules")
    )
    return kb


def number_range_keyboard():
    """Клавиатура для выбора диапазона чисел"""
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("1-10", callback_data="dm_range_1_10"),
        types.InlineKeyboardButton("1-100", callback_data="dm_range_1_100"),
        types.InlineKeyboardButton("1-1000", callback_data="dm_range_1_1000"),
        types.InlineKeyboardButton("Свой", callback_data="dm_range_custom")
    )
    kb.add(
        types.InlineKeyboardButton("🔙 Назад", callback_data="dm_back_to_menu")
    )
    return kb


def dota2_hero_keyboard():
    """Клавиатура для выбора героя Dota 2"""
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🎲 Случайный", callback_data="dm_dota2_random"),
        types.InlineKeyboardButton("💪 Сила", callback_data="dm_dota2_strength"),
        types.InlineKeyboardButton("🗡️ Ловкость", callback_data="dm_dota2_agility"),
        types.InlineKeyboardButton("🧠 Интеллект", callback_data="dm_dota2_intel")
    )
    kb.add(
        types.InlineKeyboardButton("🔙 Назад", callback_data="dm_back_to_menu")
    )
    return kb


def coin_flip_keyboard():
    """Клавиатура для подбрасывания монетки"""
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🪙 Подбросить", callback_data="dm_coin_flip"),
        types.InlineKeyboardButton("📊 Статистика", callback_data="dm_coin_stats")
    )
    kb.add(
        types.InlineKeyboardButton("🔙 Назад", callback_data="dm_back_to_menu")
    )
    return kb


def result_keyboard(back_callback: str = "dm_back_to_menu"):
    """Клавиатура результата"""
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🔄 Ещё раз", callback_data="dm_again"),
        types.InlineKeyboardButton("🔙 К меню", callback_data=back_callback)
    )
    return kb


def list_options_keyboard():
    """Клавиатура для выбора из списка"""
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("📝 Ввести список", callback_data="dm_list_input")
    )
    kb.add(
        types.InlineKeyboardButton("🔙 Назад", callback_data="dm_back_to_menu")
    )
    return kb