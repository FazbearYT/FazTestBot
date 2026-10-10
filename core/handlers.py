# core/handlers.py
# Глобальные обработчики для главного меню, навигации, админ-панели и пасхалок


import config
from core.admin import admin_manager
from core.admin_panel import (
    AdminPanelService,
    render_backup_overview,
    render_health,
    render_modules,
    render_overview,
    render_restore_instructions,
    render_search_results,
    render_user_profile,
)
from core.admin_security import (
    AdminConfirmationStore,
    AdminInteractionState,
    has_admin_access,
    is_private_chat,
)
from core.backup import backup_manager
from core.database import DatabaseManager
from core.easter_eggs import EasterEggManager
from core.exceptions import classify_exception, handle_exception
from core.observability import event_fields, get_logger
from core.settings import load_settings

from .keyboards import (
    admin_menu_keyboard,
    admin_observability_keyboard,
    back_to_main_keyboard,
    back_to_modules_keyboard,
    backup_info_keyboard,
    backup_list_keyboard,
    backup_menu_keyboard,
    cleanup_keyboard,
    destructive_confirm_keyboard,
    easter_egg_keyboard,
    export_keyboard,
    main_menu_keyboard,
    modules_menu_keyboard,
    stats_navigation_keyboard,
    user_search_keyboard,
)
from .module_manager import module_manager

logger = get_logger(__name__)

# Инициализация менеджеров
db = DatabaseManager()
admin_mgr = admin_manager

# Инициализация менеджера пасхалок
easter_egg_manager = EasterEggManager(db)

# Состояния пользователей для режимов ввода (поиск, экспорт и т.д.)
user_input_state = AdminInteractionState()
admin_confirmations = AdminConfirmationStore()


def register_global_handlers(bot):
    """Регистрация глобальных обработчиков с поддержкой пасхалок и блокировки"""

    admin_panel = AdminPanelService(admin_mgr, module_manager, load_settings())

    @bot.message_handler(commands=['start'])
    def send_welcome(message):
        """Обработчик команды /start — проверка блокировки и пасхалок"""
        # Проверяем, не заблокирован ли пользователь
        if easter_egg_manager.check_blocked_user(message.from_user.id):
            return  # Полностью игнорируем заблокированного пользователя

        # Логируем пользователя
        db.create_or_update_user(
            user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )

        # ВСЕГДА показываем обычное меню (даже для админов)
        bot.send_message(
            message.chat.id,
            "🏠 <b>Главное меню</b>\n\n"
            "Добро пожаловать в FazTestBot — модульный бот-агрегатор!\n"
            "Выберите действие ниже:",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML"
        )

    @bot.message_handler(commands=['admin'])
    def show_admin_panel(message):
        """Команда /admin — показывает админ-панель ТОЛЬКО для аутентифицированных пользователей"""
        # Проверяем, не заблокирован ли пользователь
        if easter_egg_manager.check_blocked_user(message.from_user.id):
            return  # Полностью игнорируем заблокированного пользователя
        if not is_private_chat(message):
            return

        db.create_or_update_user(
            user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )

        if admin_mgr.is_admin(message.from_user.id):
            bot.send_message(
                message.chat.id,
                "👑 <b>Админ-панель</b>\n\nДобро пожаловать в панель управления FazTestBot!",
                reply_markup=admin_menu_keyboard(),
                parse_mode="HTML"
            )
            admin_mgr.log_admin_action(message.from_user.id, "open_admin_panel", None)
        else:
            bot.send_message(
                message.chat.id,
                "Я не понимаю эту команду. Используйте меню для навигации.",
                reply_markup=main_menu_keyboard()
            )

    @bot.message_handler(commands=['auth'])
    def authenticate_admin(message):
        """Команда /auth — аутентификация через кодовое слово (получение статуса админа)"""
        # Проверяем, не заблокирован ли пользователь
        if easter_egg_manager.check_blocked_user(message.from_user.id):
            return  # Полностью игнорируем заблокированного пользователя
        if not is_private_chat(message):
            return

        db.create_or_update_user(
            user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )

        # Разделяем команду и аргументы
        command_parts = message.text.split(' ', 1)
        if len(command_parts) > 1:
            code = command_parts[1].strip()
        else:
            code = ""

        if admin_mgr.authenticate_by_code(message.from_user.id, code):
            bot.send_message(
                message.chat.id,
                f"✅ Успешная аутентификация!\n\n"
                f"Вам предоставлен статус администратора на {config.ADMIN_SESSION_HOURS} часов.\n"
                f"Для доступа к админ-панели используйте команду /admin",
                reply_markup=main_menu_keyboard(),
                parse_mode="HTML"
            )
            admin_mgr.log_admin_action(message.from_user.id, "auth_by_code", None)
        else:
            bot.send_message(
                message.chat.id,
                "Я не понимаю эту команду. Используйте меню для навигации.",
                reply_markup=main_menu_keyboard()
            )

    @bot.message_handler(commands=['my_stats'])
    def show_my_stats(message):
        """Команда /my_stats — доступна ТОЛЬКО аутентифицированным администраторам"""
        # Проверяем, не заблокирован ли пользователь
        if easter_egg_manager.check_blocked_user(message.from_user.id):
            return  # Полностью игнорируем заблокированного пользователя
        if not is_private_chat(message):
            return

        db.create_or_update_user(
            user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )

        if admin_mgr.is_admin(message.from_user.id):
            show_admin_stats(bot, message)
        else:
            bot.send_message(
                message.chat.id,
                "Я не понимаю эту команду. Используйте меню для навигации.",
                reply_markup=main_menu_keyboard()
            )

    def show_admin_stats(bot_instance, message):
        """Показывает подробную статистику администратору"""
        stats = db.get_user_cipher_stats(message.from_user.id)

        total = stats['total_operations']
        dist = stats['cipher_distribution']

        text = "📊 <b>Ваша статистика шифрования</b>\n\n"
        text += f"Всего операций: <b>{total}</b>\n"
        text += (
            f"Сегодня: <b>{stats['today_ops']}</b> | "
            f"Неделя: <b>{stats['week_ops']}</b> | "
            f"Месяц: <b>{stats['month_ops']}</b>\n\n"
        )

        if total > 0:
            text += "┌──────────────────────────────┐\n"
            text += "│ Тип шифра      │ Кол-во │ %  │\n"
            text += "├──────────────────────────────┤\n"

            total_count = sum(dist.values())
            for cipher, count in sorted(dist.items(), key=lambda x: x[1], reverse=True):
                percent = (count / total_count * 100) if total_count > 0 else 0
                cipher_name = {
                    "morze": "Азбука Морзе",
                    "numbers": "Числовой",
                    "caesar": "Цезарь",
                    "qr": "QR-код"
                }.get(cipher, cipher)
                text += f"│ {cipher_name:<14} │ {count:<6} │ {percent:>4.1f}%│\n"

            text += "└──────────────────────────────┘\n\n"
        else:
            text += "⚠️ Пока нет операций шифрования\n\n"

        text += "<b>Последние операции:</b>\n"
        if stats['last_operations']:
            for i, op in enumerate(stats['last_operations'], 1):
                ts = op['timestamp']
                time_str = ts.split()[1][:5]  # Только часы:минуты

                cipher_name = {
                    "morze": "Морзе",
                    "numbers": "Числа",
                    "caesar": f"Цезарь (шаг {op['step']})",
                    "qr": "QR"
                }.get(op['cipher_type'], op['cipher_type'])

                text += f"{i}. [{time_str}] {cipher_name}:\n"
                text += f"   «{op['original_text']}» → «{op['encrypted_text']}»\n"
        else:
            text += "Нет последних операций"

        bot_instance.send_message(
            message.chat.id,
            text,
            reply_markup=stats_navigation_keyboard(),
            parse_mode="HTML"
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("easter_"))
    def handle_easter_egg_callbacks(call):
        """Обработка колбэков пасхалки"""
        # Проверяем, не заблокирован ли пользователь
        if easter_egg_manager.check_blocked_user(call.from_user.id):
            return  # Полностью игнорируем заблокированного пользователя

        chat_id = call.message.chat.id
        message_id = call.message.message_id

        try:
            bot.answer_callback_query(call.id)

            # Показать историю разработки (ОТПРАВКА ФАЙЛОМ)
            if call.data == "easter_history":
                history_file_path = easter_egg_manager.get_dev_history_file_path()

                # Отправляем файл history.txt как документ
                with open(history_file_path, 'rb') as f:
                    bot.send_document(
                        chat_id,
                        f,
                        caption=(
                            "📜 <b>История разработки FazTestBot</b>\n\n"
                            "Полная история всех версий бота."
                        ),
                        parse_mode="HTML"
                    )

                # Удаляем сообщение с меню пасхалки
                try:
                    bot.delete_message(chat_id, message_id)
                except Exception as error:
                    logger.debug(
                        "easter egg menu message was already unavailable",
                        exc_info=(type(error), error, error.__traceback__),
                        extra=event_fields("telegram.message_delete_failed"),
                    )

                # Отправляем новое сообщение с главным меню
                bot.send_message(
                    chat_id,
                    "🏠 <b>Главное меню</b>\n\n"
                    "Добро пожаловать в FazTestBot — модульный бот-агрегатор!\n"
                    "Выберите действие ниже:",
                    reply_markup=main_menu_keyboard(),
                    parse_mode="HTML"
                )

                # ⚠️ ВАЖНО: НЕТ СБРОСА СОСТОЯНИЯ
                # last_completed сохраняется, КД 24 часа продолжается

            # Закрыть пасхалку
            elif call.data == "easter_close":
                # ⚠️ ВАЖНО: НЕТ СБРОСА СОСТОЯНИЯ
                # last_completed сохраняется, КД 24 часа продолжается

                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="🏠 <b>Главное меню</b>\n\n"
                         "Добро пожаловать в FazTestBot — модульный бот-агрегатор!\n"
                         "Выберите действие ниже:",
                    reply_markup=main_menu_keyboard(),
                    parse_mode="HTML"
                )

        except Exception as e:
            user_message = handle_exception(
                e,
                logger,
                event="handler.easter_egg_failed",
            )
            bot.answer_callback_query(
                call.id,
                user_message[:200],
                show_alert=True
            )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
    def handle_admin_callbacks(call):
        """Обработка колбэков админ-панели"""
        # Проверяем, не заблокирован ли пользователь
        if easter_egg_manager.check_blocked_user(call.from_user.id):
            return  # Полностью игнорируем заблокированного пользователя

        chat_id = call.message.chat.id
        message_id = call.message.message_id

        # Reject group chats and expired sessions before recording or doing any work.
        if not has_admin_access(call, admin_mgr):
            bot.answer_callback_query(call.id, "Операция не поддерживается", show_alert=False)
            return

        # Логируем активность
        db.create_or_update_user(
            user_id=call.from_user.id,
            username=call.from_user.username,
            first_name=call.from_user.first_name,
            last_name=call.from_user.last_name
        )

        try:
            bot.answer_callback_query(call.id)

            # ====== СУЩЕСТВУЮЩИЕ ФУНКЦИИ АДМИН-ПАНЕЛИ ======

            # Главное админ-меню
            if call.data == "admin_stats":
                text = render_overview(admin_panel.get_dashboard())

                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=admin_observability_keyboard(),
                    parse_mode="HTML"
                )

            elif call.data == "admin_modules":
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=render_modules(admin_panel.get_dashboard()),
                    reply_markup=admin_observability_keyboard(),
                    parse_mode="HTML"
                )

            elif call.data == "admin_health":
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=render_health(admin_panel.get_dashboard()),
                    reply_markup=admin_observability_keyboard(),
                    parse_mode="HTML"
                )

            # Поиск пользователя
            elif call.data == "admin_user_search":
                # Устанавливаем состояние пользователя для поиска
                user_input_state.begin(
                    call.from_user.id,
                    chat_id,
                    "search_user",
                    message_id,
                )

                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="👑 <b>Админ-панель — Поиск пользователя</b>\n\n"
                         "Введите ID пользователя для просмотра профиля:",
                    reply_markup=user_search_keyboard(),
                    parse_mode="HTML"
                )

            # Отмена поиска
            elif call.data == "admin_cancel_search":
                # Удаляем состояние поиска
                user_input_state.clear(call.from_user.id, chat_id)

                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=(
                        "👑 <b>Админ-панель</b>\n\n"
                        "Добро пожаловать в панель управления FazTestBot!"
                    ),
                    reply_markup=admin_menu_keyboard(),
                    parse_mode="HTML"
                )

            # Поиск по логам
            elif call.data == "admin_search":
                # Устанавливаем состояние пользователя для поиска по логам
                user_input_state.begin(
                    call.from_user.id,
                    chat_id,
                    "search_logs",
                    message_id,
                )

                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="👑 <b>Админ-панель — Поиск по логам</b>\n\n"
                         "Введите ключевое слово для поиска в операциях шифрования:",
                    reply_markup=user_search_keyboard(),
                    parse_mode="HTML"
                )

            # Экспорт данных
            elif call.data == "admin_export":
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="👑 <b>Админ-панель — Экспорт данных</b>\n\n"
                         "Выберите формат экспорта:",
                    reply_markup=export_keyboard(),
                    parse_mode="HTML"
                )

            # Очистка логов
            elif call.data == "admin_cleanup":
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="👑 <b>Админ-панель — Очистка логов</b>\n\n"
                         "Выберите период для очистки старых записей:",
                    reply_markup=cleanup_keyboard(),
                    parse_mode="HTML"
                )

            # Настройки
            elif call.data == "admin_settings":
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="👑 <b>Админ-панель — Настройки</b>\n\n"
                         "Текущие параметры:\n"
                         f"• Автоочистка логов: {config.LOG_RETENTION_DAYS} дней\n"
                         f"• Длительность сессии админа: {config.ADMIN_SESSION_HOURS} часов\n\n"
                         "<i>Настройки можно изменить в файле .env</i>",
                    reply_markup=user_search_keyboard(),
                    parse_mode="HTML"
                )

            # Экстренные действия
            elif call.data == "admin_emergency":
                token = admin_confirmations.issue(
                    call.from_user.id,
                    chat_id,
                    "emergency_clear",
                )
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="⚠️ <b>ЭКСТРЕННЫЕ ДЕЙСТВИЯ</b>\n\n"
                         "Эта операция <b>НЕОБРАТИМА</b>:\n"
                         "• Удалит ВСЕ операции шифрования\n"
                         "• Удалит всех пользователей (кроме админов)\n\n"
                         "Вы уверены, что хотите продолжить?",
                    reply_markup=destructive_confirm_keyboard(token, "✅ Да, очистить ВСЁ"),
                    parse_mode="HTML"
                )

            # Старые сообщения не должны повторно запускать опасную операцию.
            elif call.data == "admin_emergency_confirm":
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="⚠️ Срок старого подтверждения истёк. Откройте действие заново.",
                    reply_markup=admin_menu_keyboard(),
                    parse_mode="HTML"
                )

            # Очистка логов за период
            elif call.data.startswith("admin_cleanup_"):
                days = int(call.data.replace("admin_cleanup_", ""))
                if days not in {7, 30, 90}:
                    raise ValueError("unsupported cleanup period")
                token = admin_confirmations.issue(
                    call.from_user.id,
                    chat_id,
                    "cleanup_logs",
                    str(days),
                )
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=(
                        "⚠️ <b>Подтверждение очистки</b>\n\n"
                        f"Будут удалены записи старше {days} дней. Продолжить?"
                    ),
                    reply_markup=destructive_confirm_keyboard(token),
                    parse_mode="HTML"
                )

            elif call.data.startswith("admin_confirm_"):
                token = call.data.removeprefix("admin_confirm_")
                confirmation = admin_confirmations.consume(
                    token,
                    call.from_user.id,
                    chat_id,
                )
                if confirmation is None:
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text="⚠️ Подтверждение недействительно или истекло.",
                        reply_markup=admin_menu_keyboard(),
                    )
                elif confirmation.action == "emergency_clear":
                    ops_deleted, users_deleted = admin_mgr.emergency_clear_all()
                    admin_mgr.log_admin_action(
                        call.from_user.id,
                        "emergency_clear",
                        None,
                        f"Deleted {ops_deleted} ops, {users_deleted} users",
                    )
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=(
                            "🚨 <b>Экстренная очистка выполнена</b>\n\n"
                            f"Удалено операций: {ops_deleted}\n"
                            f"Удалено пользователей: {users_deleted}\n\n"
                            "Бот готов к работе."
                        ),
                        reply_markup=admin_menu_keyboard(),
                        parse_mode="HTML",
                    )
                elif confirmation.action == "cleanup_logs":
                    days = int(confirmation.payload)
                    deleted = admin_mgr.cleanup_logs(days)
                    admin_mgr.log_admin_action(
                        call.from_user.id,
                        "cleanup_logs",
                        None,
                        f"{days} days, {deleted} records",
                    )
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=(
                            "🧹 <b>Очистка завершена</b>\n\n"
                            f"Удалено записей старше {days} дней: <b>{deleted}</b>"
                        ),
                        reply_markup=admin_menu_keyboard(),
                        parse_mode="HTML",
                    )
                elif confirmation.action == "delete_backup":
                    success, result_message = backup_manager.delete_backup(
                        confirmation.payload
                    )
                    backup_files = backup_manager.get_backup_list()
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=(
                            "🗄️ <b>Админ-панель — Бэкапы</b>\n\n"
                            f"{result_message}\n\nНайдено бэкапов: {len(backup_files)}"
                        ),
                        reply_markup=(
                            backup_list_keyboard(backup_files)
                            if backup_files
                            else backup_menu_keyboard()
                        ),
                        parse_mode="HTML",
                    )
                else:
                    raise ValueError("unsupported admin confirmation action")

            # Экспорт в CSV
            elif call.data == "admin_export_csv":
                try:
                    filename = admin_mgr.export_to_csv()
                    admin_mgr.log_admin_action(call.from_user.id, "export_csv", None)

                    with open(filename, 'rb') as f:
                        bot.send_document(
                            chat_id,
                            f,
                            caption="✅ Экспорт в CSV завершён",
                            reply_to_message_id=message_id
                        )

                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=(
                            "👑 <b>Админ-панель</b>\n\n"
                            "Экспорт данных завершён. Файл отправлен выше."
                        ),
                        reply_markup=admin_menu_keyboard(),
                        parse_mode="HTML"
                    )
                except Exception as e:
                    user_message = handle_exception(
                        e,
                        logger,
                        event="admin.export_failed",
                        context={"export_format": "csv"},
                    )
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=user_message,
                        reply_markup=admin_menu_keyboard(),
                        parse_mode="HTML"
                    )

            # Экспорт в JSON
            elif call.data == "admin_export_json":
                try:
                    filename = admin_mgr.export_to_json()
                    admin_mgr.log_admin_action(call.from_user.id, "export_json", None)

                    with open(filename, 'rb') as f:
                        bot.send_document(
                            chat_id,
                            f,
                            caption="✅ Экспорт в JSON завершён",
                            reply_to_message_id=message_id
                        )

                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=(
                            "👑 <b>Админ-панель</b>\n\n"
                            "Экспорт данных завершён. Файл отправлен выше."
                        ),
                        reply_markup=admin_menu_keyboard(),
                        parse_mode="HTML"
                    )
                except Exception as e:
                    user_message = handle_exception(
                        e,
                        logger,
                        event="admin.export_failed",
                        context={"export_format": "json"},
                    )
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=user_message,
                        reply_markup=admin_menu_keyboard(),
                        parse_mode="HTML"
                    )

            # Обновление статистики
            elif call.data == "admin_stats_refresh":
                text = render_overview(admin_panel.get_dashboard())

                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=admin_observability_keyboard(),
                    parse_mode="HTML"
                )

            # Возврат в главное админ-меню
            elif call.data == "admin_back_to_menu":
                # Удаляем состояние ввода, если оно существует
                user_input_state.clear(call.from_user.id, chat_id)
                admin_confirmations.clear(call.from_user.id)

                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=(
                        "👑 <b>Админ-панель</b>\n\n"
                        "Добро пожаловать в панель управления FazTestBot!"
                    ),
                    reply_markup=admin_menu_keyboard(),
                    parse_mode="HTML"
                )

            # Выход из админ-панели
            elif call.data == "admin_exit":
                user_input_state.clear(call.from_user.id)
                admin_confirmations.clear(call.from_user.id)
                admin_mgr.revoke_session(call.from_user.id)
                # Показываем обычное меню
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="🏠 <b>Главное меню</b>\n\n"
                         "Добро пожаловать в FazTestBot — модульный бот-агрегатор!\n"
                         "Выберите действие ниже:",
                    reply_markup=main_menu_keyboard(),
                    parse_mode="HTML"
                )

            # ====== НОВЫЕ ФУНКЦИИ ВЕРСИИ 3.6 - БЭКАПЫ ======

            # Меню бэкапов
            elif call.data == "admin_backups":
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=render_backup_overview(admin_panel.settings),
                    reply_markup=backup_menu_keyboard(),
                    parse_mode="HTML"
                )

            # Создание бэкапа
            elif call.data == "admin_backup_create":
                bot.answer_callback_query(call.id, "⏳ Создание бэкапа...")
                success, message = backup_manager.create_backup(manual=True)

                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"🗄️ <b>Админ-панель — Бэкапы</b>\n\n{message}",
                    reply_markup=backup_menu_keyboard(),
                    parse_mode="HTML"
                )

            # Список бэкапов
            elif call.data == "admin_backup_list":
                backup_files = backup_manager.get_backup_list()

                if not backup_files:
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text="🗄️ <b>Админ-панель — Бэкапы</b>\n\n"
                             "⚠️ Бэкапы не найдены.\n\n"
                             "Создайте первый бэкап вручную.",
                        reply_markup=backup_menu_keyboard(),
                        parse_mode="HTML"
                    )
                else:
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=f"🗄️ <b>Админ-панель — Бэкапы</b>\n\n"
                             f"Найдено бэкапов: {len(backup_files)}\n\n"
                             f"Выберите бэкап для управления:",
                        reply_markup=backup_list_keyboard(backup_files),
                        parse_mode="HTML"
                    )

            # Статистика бэкапов
            elif call.data == "admin_backup_stats":
                stats = backup_manager.get_backup_stats()

                text = "🗄️ <b>Админ-панель — Статистика бэкапов</b>\n\n"
                text += f"📊 Всего бэкапов: {stats['total_count']}\n"
                text += f"🤖 Автоматических: {stats['auto_count']}\n"
                text += f"👤 Ручных: {stats['manual_count']}\n"
                text += f"💾 Общий размер: {stats['total_size_formatted']}\n"
                text += f"📅 Последний: {stats['newest']}\n"
                text += f"📅 Старейший: {stats['oldest']}\n"

                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=backup_menu_keyboard(),
                    parse_mode="HTML"
                )

            # Информация о бэкапе
            elif call.data.startswith("admin_backup_info_"):
                filename = call.data.replace("admin_backup_info_", "")

                backup_files = backup_manager.get_backup_list()
                backup = next((b for b in backup_files if b['filename'] == filename), None)

                if backup:
                    text = "🗄️ <b>Информация о бэкапе</b>\n\n"
                    text += f"📁 Файл: {backup['filename']}\n"
                    text += f"📊 Размер: {backup['size_formatted']}\n"
                    text += f"🕐 Создан: {backup['created'].strftime('%d.%m.%Y %H:%M')}\n"
                    text += f"🏷️ Тип: {backup['type']}\n\n"
                    text += "Выберите действие:"

                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=text,
                        reply_markup=backup_info_keyboard(filename),
                        parse_mode="HTML"
                    )
                else:
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text="❌ Бэкап не найден.",
                        reply_markup=backup_menu_keyboard(),
                        parse_mode="HTML"
                    )

            # Удаление бэкапа
            elif call.data.startswith("admin_backup_delete_"):
                filename = call.data.replace("admin_backup_delete_", "")
                token = admin_confirmations.issue(
                    call.from_user.id,
                    chat_id,
                    "delete_backup",
                    filename,
                )
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="⚠️ <b>Удалить выбранный бэкап?</b>\n\nДействие необратимо.",
                    reply_markup=destructive_confirm_keyboard(token, "🗑️ Удалить"),
                    parse_mode="HTML",
                )

            # Восстановление из бэкапа
            elif call.data.startswith("admin_backup_restore_"):
                filename = call.data.replace("admin_backup_restore_", "")
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=render_restore_instructions(filename),
                    reply_markup=backup_menu_keyboard(),
                    parse_mode="HTML"
                )

        except Exception as e:
            disposition = classify_exception(e)
            user_message = handle_exception(
                e,
                logger,
                event="admin.callback_failed",
            )
            bot.answer_callback_query(
                call.id,
                user_message[:200],
                show_alert=True
            )
            admin_mgr.log_admin_action(call.from_user.id, "error", None, disposition.code)

    def handle_user_search_input(message, bot_instance):
        """Обработка ввода ID пользователя для поиска (с проверкой состояния)"""
        if not has_admin_access(message, admin_mgr):
            user_input_state.clear(message.from_user.id)
            return
        search_state = user_input_state.consume(
            message.from_user.id,
            message.chat.id,
            "search_user",
        )
        if search_state is None:
            # Не в режиме поиска — игнорируем или показываем обычное меню
            bot_instance.send_message(
                message.chat.id,
                "Я не понимаю эту команду. Используйте меню для навигации.",
                reply_markup=main_menu_keyboard()
            )
            return

        db.create_or_update_user(
            user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )

        try:
            user_id = int(message.text.strip())
            profile = admin_mgr.get_user_profile(user_id)

            if profile:
                text = render_user_profile(user_id, profile)

                bot_instance.send_message(
                    message.chat.id,
                    text,
                    reply_markup=user_search_keyboard(),
                    parse_mode="HTML"
                )
            else:
                bot_instance.send_message(
                    message.chat.id,
                    f"⚠️ Пользователь с ID {user_id} не найден.",
                    reply_markup=user_search_keyboard(),
                    parse_mode="HTML"
                )

        except ValueError:
            bot_instance.send_message(
                message.chat.id,
                "❌ Некорректный ID. Введите целое число.",
                reply_markup=user_search_keyboard(),
                parse_mode="HTML"
            )

    def handle_search_input(message, bot_instance):
        """Обработка ввода для поиска по логам (с проверкой состояния)"""
        if not has_admin_access(message, admin_mgr):
            user_input_state.clear(message.from_user.id)
            return
        search_state = user_input_state.consume(
            message.from_user.id,
            message.chat.id,
            "search_logs",
        )
        if search_state is None:
            # Не в режиме поиска — игнорируем или показываем обычное меню
            bot_instance.send_message(
                message.chat.id,
                "Я не понимаю эту команду. Используйте меню для навигации.",
                reply_markup=main_menu_keyboard()
            )
            return

        db.create_or_update_user(
            user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )

        query = message.text.strip()
        results = admin_mgr.search_operations(query)
        bot_instance.send_message(
            message.chat.id,
            render_search_results(query, results),
            reply_markup=user_search_keyboard(),
            parse_mode="HTML"
        )

    @bot.callback_query_handler(func=lambda call: True)
    def handle_global_callbacks(call):
        """Глобальный обработчик колбэков — маршрутизация к модулям с логированием"""
        # Проверяем, не заблокирован ли пользователь
        if easter_egg_manager.check_blocked_user(call.from_user.id):
            return  # Полностью игнорируем заблокированного пользователя

        chat_id = call.message.chat.id
        message_id = call.message.message_id

        # Логируем активность пользователя при любом колбэке
        db.create_or_update_user(
            user_id=call.from_user.id,
            username=call.from_user.username,
            first_name=call.from_user.first_name,
            last_name=call.from_user.last_name
        )

        # Проверяем, не является ли колбэк админ-колбэком (уже обработан выше)
        if call.data.startswith("admin_"):
            return  # Уже обработан в handle_admin_callbacks

        # Проверяем, не является ли колбэк пасхалки (уже обработан выше)
        if call.data.startswith("easter_"):
            return  # Уже обработан в handle_easter_egg_callbacks

        try:
            bot.answer_callback_query(call.id)

            # Главное меню → Модули
            if call.data == "menu_modules":
                modules = module_manager.get_all_modules()
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="📦 <b>Доступные модули</b>\n\nВыберите модуль для работы:",
                    reply_markup=modules_menu_keyboard(modules),
                    parse_mode="HTML"
                )

            # Главное меню → Помощь
            elif call.data == "menu_help":
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=(
                        "❓ <b>Помощь</b>\n\n"
                        "FazTestBot — модульный бот-агрегатор.\n\n"
                        "<b>Как работать с ботом:</b>\n"
                        "• Нажмите «📦 Модули» для выбора функционала\n"
                        "• Каждый модуль работает независимо\n"
                        "• Используйте кнопки навигации для возврата"
                    ),
                    reply_markup=back_to_main_keyboard(),
                    parse_mode="HTML"
                )

            # Главное меню → О боте
            elif call.data == "menu_about":
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=(
                        f"ℹ️ <b>О боте</b>\n\n"
                        f"FazTestBot v{config.VERSION}\n"
                        f"Дата обновления: {config.LAST_UPDATE_DATE}\n"
                        f"Автор: {config.AUTHOR}\n\n"
                        "Модульный бот-агрегатор для объединения функциональных инструментов."
                    ),
                    reply_markup=back_to_main_keyboard(),
                    parse_mode="HTML"
                )

            # Назад в главное меню
            elif call.data == "back_to_main":
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="🏠 <b>Главное меню</b>\n\n"
                         "Добро пожаловать в FazTestBot — модульный бот-агрегатор!\n"
                         "Выберите действие ниже:",
                    reply_markup=main_menu_keyboard(),
                    parse_mode="HTML"
                )

            # Назад к списку модулей
            elif call.data == "back_to_modules":
                modules = module_manager.get_all_modules()
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="📦 <b>Доступные модули</b>\n\nВыберите модуль для работы:",
                    reply_markup=modules_menu_keyboard(modules),
                    parse_mode="HTML"
                )

            # Выбор модуля
            elif call.data.startswith("module_"):
                module_id = call.data.replace("module_", "")
                module = module_manager.get_module_by_id(module_id)

                if module:
                    # Логируем использование модуля
                    db.increment_module_stat(call.from_user.id, module_id)

                    # Передаём управление модулю через его обработчик
                    if hasattr(module, 'handle_entry'):
                        module.handle_entry(bot, call)
                    else:
                        bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=message_id,
                            text=f"⚠️ Модуль «{module.name}» временно недоступен.",
                            reply_markup=back_to_modules_keyboard(),
                            parse_mode="HTML"
                        )
                else:
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text="⚠️ Модуль не найден. Вернитесь в главное меню.",
                        reply_markup=back_to_main_keyboard(),
                        parse_mode="HTML"
                    )

            # Маршрутизация колбэков к модулям
            else:
                module = module_manager.get_module_by_callback(call.data)
                if module and hasattr(module, 'handle_callback'):
                    # Для колбэков внутри модуля логируем активность (но не инкрементируем счётчик)
                    module.handle_callback(bot, call)
                else:
                    # Неизвестный колбэк — возвращаем в главное меню
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text="⚠️ Неизвестная команда. Вернитесь в главное меню.",
                        reply_markup=back_to_main_keyboard(),
                        parse_mode="HTML"
                    )

        except Exception as e:
            user_message = handle_exception(
                e,
                logger,
                event="handler.callback_failed",
            )
            bot.answer_callback_query(
                call.id,
                user_message[:200],
                show_alert=True
            )

    @bot.message_handler(func=lambda message: True)
    def handle_unknown_commands(message):
        """
        Обработка неизвестных команд и сообщений.
        ВКЛЮЧАЯ проверку на блокировку и пасхалки.
        """
        # Проверяем, не заблокирован ли пользователь
        if easter_egg_manager.check_blocked_user(message.from_user.id):
            return  # Полностью игнорируем заблокированного пользователя

        # Логируем пользователя
        db.create_or_update_user(
            user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )

        # Проверяем, находится ли пользователь в режиме поиска
        admin_state = user_input_state.peek(message.from_user.id, message.chat.id)
        if admin_state is not None:
            mode = admin_state.mode

            if mode == 'search_user':
                handle_user_search_input(message, bot)
                return
            elif mode == 'search_logs':
                handle_search_input(message, bot)
                return

        # Проверяем на пасхалку-головоломку
        easter_result = easter_egg_manager.process_easter_egg_message(
            message.from_user.id,
            message.text
        )

        # Обработка результатов пасхалки
        if easter_result['activated']:
            # Пасхалка активирована! Показываем скрытое меню
            bot.send_message(
                message.chat.id,
                "🎉 <b>Поздравляем!</b>\n\n"
                "Вы нашли секретное меню разработки!\n"
                "Здесь вы можете посмотреть полную историю создания бота.",
                reply_markup=easter_egg_keyboard(),
                parse_mode="HTML"
            )
            return

        elif easter_result['step_success']:
            # Успешный ввод шага — показываем сообщение с прогрессом
            if easter_result.get('response'):
                bot.send_message(
                    message.chat.id,
                    easter_result['response']
                )
            return

        elif easter_result.get('cooldown'):
            # На кулдауне — стандартный ответ бота (ничего не отправляем)
            pass

        # ЕДИНЫЙ ОТВЕТ ДЛЯ ВСЕХ ПОЛЬЗОВАТЕЛЕЙ (включая админов)
        # При неправильном вводе или кулдауне
        bot.send_message(
            message.chat.id,
            "Я не понимаю эту команду. Используйте меню для навигации.",
            reply_markup=main_menu_keyboard()
        )
