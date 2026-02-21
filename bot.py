# bot.py
# FazTestBot v3.6 — Модульный бот-агрегатор с системой бэкапов
# Точка входа — объединяет все модули воедино

import telebot
import config
from apscheduler.schedulers.background import BackgroundScheduler
from core.handlers import register_global_handlers
from core.module_manager import module_manager
from core.backup import backup_manager

# Инициализация бота
bot = telebot.TeleBot(config.BOT_TOKEN)

# Регистрация глобальных обработчиков
register_global_handlers(bot)

# 🔥 АВТОМАТИЧЕСКАЯ ЗАГРУЗКА ВСЕХ МОДУЛЕЙ
print("🔍 Поиск и загрузка модулей...")
loaded_count = module_manager.discover_and_load(bot)
print(f"✅ Загружено модулей: {loaded_count}")

# Вывод списка загруженных модулей
print("\n📦 Зарегистрированные модули:")
for module in module_manager.get_all_modules():
    print(f"   • {module.icon} {module.name} v{module.version}")

# Проверка ошибок загрузки
errors = module_manager.get_errors()
if errors:
    print("\n⚠️ Ошибки загрузки модулей:")
    for error in errors:
        print(f"   • {error['module']}: {error['error']}")

# ====== НАСТРОЙКА АВТОМАТИЧЕСКИХ БЭКАПОВ ======
if config.BACKUP_ENABLED:
    scheduler = BackgroundScheduler()

    # Парсим время бэкапа
    backup_hour, backup_minute = map(int, config.BACKUP_TIME.split(':'))

    # Добавляем задачу на ежедневный бэкап
    scheduler.add_job(
        func=lambda: backup_manager.create_backup(manual=False),
        trigger='cron',
        hour=backup_hour,
        minute=backup_minute,
        id='daily_backup',
        replace_existing=True
    )

    scheduler.start()
    print(f"⏰ Автоматические бэкапы настроены на {config.BACKUP_TIME}")
else:
    print("⚠️ Автоматические бэкапы отключены")

# Запуск бота
if __name__ == "__main__":
    print(f"\n✅ FazTestBot v{config.VERSION} запущен")
    print(f"💾 База данных: {config.DATABASE_PATH}")
    print(f"📅 Дата обновления: {config.LAST_UPDATE_DATE}")
    print(f"🗄️ Бэкапы: {config.BACKUP_DIR} (хранение {config.BACKUP_RETENTION_COUNT} файлов)")
    print("Нажмите Ctrl+C для остановки.\n")
    try:
        bot.infinity_polling()
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен пользователем")