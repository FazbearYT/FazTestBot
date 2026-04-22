from telebot import types


def media_menu_keyboard():
    """Главное меню модуля"""
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🎬 Скачать видео", callback_data="media_video"),
        types.InlineKeyboardButton("🎵 Скачать аудио", callback_data="media_audio"),
        types.InlineKeyboardButton("📋 Мои загрузки", callback_data="media_history"),
        types.InlineKeyboardButton("🔙 Назад", callback_data="media_back_to_modules")
    )
    return kb


def quality_keyboard(media_type: str):
    """Клавиатура выбора качества"""
    kb = types.InlineKeyboardMarkup(row_width=2)

    if media_type == "video":
        kb.add(
            types.InlineKeyboardButton("360p", callback_data="media_quality_360p"),
            types.InlineKeyboardButton("480p", callback_data="media_quality_480p"),
            types.InlineKeyboardButton("720p", callback_data="media_quality_720p"),
            types.InlineKeyboardButton("1080p", callback_data="media_quality_1080p")
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


def large_file_keyboard():
    """
    Клавиатура для больших файлов (>50MB)
    """
    kb = types.InlineKeyboardMarkup(row_width=1)

    # Кнопки снижения качества
    kb.add(
        types.InlineKeyboardButton(
            "📥 Скачать в 360p (~15-30MB)",
            callback_data="media_large_file_360p"
        ),
        types.InlineKeyboardButton(
            "📥 Скачать в 480p (~30-50MB)",
            callback_data="media_large_file_480p"
        )
    )

    # Кнопки загрузки на файлообменники
    kb.add(
        types.InlineKeyboardButton(
            "☁️ Загрузить на tmpfiles.org (до 2GB)",
            callback_data="media_upload_tmpfiles"
        ),
        # types.InlineKeyboardButton(
        #     "☁️ Загрузить на gofile.io (без лимита)",
        #     callback_data="media_upload_gofile"
        # )
    )

    # Отмена
    kb.add(
        types.InlineKeyboardButton(
            "❌ Отменить",
            callback_data="media_back_to_menu"
        )
    )

    return kb


def result_keyboard():
    """Клавиатура после успешной загрузки"""
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🔄 Скачать ещё", callback_data="media_again"),
        types.InlineKeyboardButton("🔙 В меню", callback_data="media_back_to_menu")
    )
    return kb


def cancel_keyboard():
    """Клавиатура отмены"""
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🔙 Отмена", callback_data="media_back_to_menu")
    )
    return kb