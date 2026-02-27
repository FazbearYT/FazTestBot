# modules/media_downloader/keyboards.py
# Клавиатуры модуля "Media Downloader"

from telebot import types


def media_downloader_menu_keyboard():
    """Меню модуля загрузки медиа"""
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🎬 Видео", callback_data="media_video"),
        types.InlineKeyboardButton("🎵 Аудио", callback_data="media_audio"),
        types.InlineKeyboardButton("📋 Мои загрузки", callback_data="media_my_downloads"),
        types.InlineKeyboardButton("🔙 Назад", callback_data="media_back_to_modules")
    )
    return kb


def quality_keyboard(media_type: str):
    """
    Клавиатура выбора качества

    :param media_type: "video" или "audio"
    """
    kb = types.InlineKeyboardMarkup(row_width=2)

    if media_type == "video":
        kb.add(
            types.InlineKeyboardButton("360p", callback_data="media_quality_360"),
            types.InlineKeyboardButton("480p", callback_data="media_quality_480"),
            types.InlineKeyboardButton("720p", callback_data="media_quality_720"),
            types.InlineKeyboardButton("1080p", callback_data="media_quality_1080")
        )
    else:  # audio
        kb.add(
            types.InlineKeyboardButton("128 kbps", callback_data="media_quality_128"),
            types.InlineKeyboardButton("192 kbps", callback_data="media_quality_192"),
            types.InlineKeyboardButton("320 kbps", callback_data="media_quality_320")
        )

    kb.add(
        types.InlineKeyboardButton("🔙 Отмена", callback_data="media_back_to_menu")
    )
    return kb


def my_downloads_keyboard():
    """Клавиатура для меню 'Мои загрузки'"""
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("📥 Новая загрузка", callback_data="media_video"),
        types.InlineKeyboardButton("🔙 Назад", callback_data="media_back_to_menu")
    )
    return kb