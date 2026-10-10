"""Inline keyboards for Sticker Vault."""

from telebot import types


def sticker_actions_keyboard(token: str) -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("➕ В мой стикерпак", callback_data=f"sv_add_{token}"),
        types.InlineKeyboardButton("📥 Скачать файл", callback_data=f"sv_file_{token}"),
    )
    keyboard.add(types.InlineKeyboardButton("✖️ Отмена", callback_data=f"sv_cancel_{token}"))
    return keyboard


def vault_menu_keyboard(pack_names: list[str]) -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    for part_number, pack_name in enumerate(pack_names, start=1):
        keyboard.add(
            types.InlineKeyboardButton(
                f"🔗 Открыть стикерпак · часть {part_number}",
                url=f"https://t.me/addstickers/{pack_name}",
            )
        )
    keyboard.add(
        types.InlineKeyboardButton("🔄 Обновить", callback_data="sv_refresh"),
        types.InlineKeyboardButton("🔙 К списку модулей", callback_data="back_to_modules"),
    )
    return keyboard


def result_keyboard(pack_name: str) -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        types.InlineKeyboardButton(
            "🔗 Открыть стикерпак",
            url=f"https://t.me/addstickers/{pack_name}",
        ),
        types.InlineKeyboardButton("📦 Sticker Vault", callback_data="sv_refresh"),
    )
    return keyboard
