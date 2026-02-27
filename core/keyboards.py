# core/keyboards.py
# Глобальные клавиатуры для главного меню, навигации и админ-панели

from telebot import types


def main_menu_keyboard():
    """Главное меню бота-агрегатора для обычных пользователей"""
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("📦 Модули", callback_data="menu_modules"),
        types.InlineKeyboardButton("❓ Помощь", callback_data="menu_help"),
        types.InlineKeyboardButton("ℹ️ О боте", callback_data="menu_about")
    )
    return kb


def modules_menu_keyboard(modules):
    """
    Меню выбора модулей

    :param modules: список объектов модулей с атрибутами: name, description, callback_prefix
    """
    kb = types.InlineKeyboardMarkup(row_width=1)

    # Добавляем кнопки для каждого модуля
    for module in modules:
        kb.add(
            types.InlineKeyboardButton(
                f"{module.icon} {module.name}",
                callback_data=f"module_{module.id}"
            )
        )

    # Кнопка возврата
    kb.add(
        types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")
    )

    return kb


def back_to_modules_keyboard():
    """Клавиатура для возврата к списку модулей"""
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🔙 К списку модулей", callback_data="back_to_modules")
    )
    return kb


def back_to_main_keyboard():
    """Клавиатура для возврата в главное меню"""
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🏠 В главное меню", callback_data="back_to_main")
    )
    return kb


def stats_navigation_keyboard():
    """Клавиатура навигации для статистики"""
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🔄 Обновить", callback_data="admin_stats_refresh"),
        types.InlineKeyboardButton("🏠 В меню", callback_data="admin_back_to_menu")
    )
    return kb


def admin_menu_keyboard():
    """Главное меню админ-панели"""
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
        types.InlineKeyboardButton("👤 Профиль", callback_data="admin_user_search"),
        types.InlineKeyboardButton("🔍 Поиск", callback_data="admin_search"),
        types.InlineKeyboardButton("💾 Экспорт", callback_data="admin_export"),
        types.InlineKeyboardButton("🧹 Очистка", callback_data="admin_cleanup"),
        types.InlineKeyboardButton("⚙️ Настройки", callback_data="admin_settings"),
        types.InlineKeyboardButton("🗄️ Бэкапы", callback_data="admin_backups"),  # НОВОЕ
        types.InlineKeyboardButton("🚨 Экстренно", callback_data="admin_emergency"),
        types.InlineKeyboardButton("🚪 Выход", callback_data="admin_exit")
    )
    return kb


def user_search_keyboard():
    """Клавиатура для поиска пользователя с отменой"""
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("❌ Отмена поиска", callback_data="admin_cancel_search")
    )
    return kb


def emergency_confirm_keyboard():
    """Клавиатура подтверждения экстренных действий"""
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✅ Да, очистить ВСЁ", callback_data="admin_emergency_confirm"),
        types.InlineKeyboardButton("❌ Отмена", callback_data="admin_back_to_menu")
    )
    return kb


def cleanup_keyboard():
    """Клавиатура для очистки логов"""
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🧹 7 дней", callback_data="admin_cleanup_7"),
        types.InlineKeyboardButton("🧹 30 дней", callback_data="admin_cleanup_30"),
        types.InlineKeyboardButton("🧹 90 дней", callback_data="admin_cleanup_90"),
        types.InlineKeyboardButton("🔙 Назад", callback_data="admin_back_to_menu")
    )
    return kb


def export_keyboard():
    """Клавиатура для экспорта данных"""
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📄 CSV", callback_data="admin_export_csv"),
        types.InlineKeyboardButton("🧾 JSON", callback_data="admin_export_json"),
        types.InlineKeyboardButton("🔙 Назад", callback_data="admin_back_to_menu")
    )
    return kb


def easter_egg_keyboard():
    """Клавиатура скрытого меню пасхалки"""
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("📜 История разработки", callback_data="easter_history"),
        types.InlineKeyboardButton("🔙 Закрыть", callback_data="easter_close")
    )
    return kb


# ====== НОВЫЕ КЛАВИАТУРЫ ДЛЯ ВЕРСИИ 3.6 ======

def backup_menu_keyboard():
    """Клавиатура меню бэкапов"""
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("💾 Создать бэкап", callback_data="admin_backup_create"),
        types.InlineKeyboardButton("📋 Список бэкапов", callback_data="admin_backup_list"),
        types.InlineKeyboardButton("📊 Статистика", callback_data="admin_backup_stats"),
        types.InlineKeyboardButton("🔙 Назад", callback_data="admin_back_to_menu")
    )
    return kb


def backup_list_keyboard(backup_files):
    """
    Клавиатура списка бэкапов с кнопками удаления

    :param backup_files: Список файлов бэкапов
    """
    kb = types.InlineKeyboardMarkup(row_width=1)

    # Добавляем кнопки для каждого бэкапа (максимум 10)
    for i, backup in enumerate(backup_files[:10]):
        kb.add(
            types.InlineKeyboardButton(
                f"📁 {backup['filename']} ({backup['size_formatted']})",
                callback_data=f"admin_backup_info_{backup['filename']}"
            )
        )

    kb.add(
        types.InlineKeyboardButton("🔙 Назад", callback_data="admin_backups")
    )

    return kb


def backup_info_keyboard(filename):
    """
    Клавиатура информации о бэкапе

    :param filename: Имя файла бэкапа
    """
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("⬇️ Восстановить", callback_data=f"admin_backup_restore_{filename}"),
        types.InlineKeyboardButton("🗑️ Удалить", callback_data=f"admin_backup_delete_{filename}"),
        types.InlineKeyboardButton("🔙 Назад", callback_data="admin_backup_list")
    )
    return kb