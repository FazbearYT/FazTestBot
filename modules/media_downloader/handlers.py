# modules/media_downloader/handlers.py
# Обработчики модуля "Media Downloader"
# Версия: 1.0.0
# Дата: 22.02.2026

import os
import sqlite3
from datetime import datetime, timedelta
from telebot import types
from typing import Any
from core.module_base import BaseModule
from core.database import DatabaseManager
from .keyboards import (
    media_downloader_menu_keyboard,
    quality_keyboard,
    download_result_keyboard,
    my_downloads_keyboard
)
from .downloader import downloader
from .config import (
    ENABLED,
    MAX_FILE_SIZE_MB,
    MAX_DOWNLOADS_PER_USER_PER_DAY,
    TABLE_NAME,
    SUPPORTED_PLATFORMS
)
import config

# Глобальный экземпляр БД
db = DatabaseManager()


class MediaDownloaderModule(BaseModule):
    """
    Модуль загрузки медиа из YouTube, TikTok, Instagram и других платформ.

    Наследуется от BaseModule и реализует все обязательные методы.
    """

    def __init__(self, module_id, name, description, icon, version, callback_prefix):
        """Инициализация модуля Media Downloader"""
        super().__init__(module_id, name, description, icon, version, callback_prefix)

        # Создаём таблицу в БД при инициализации
        self._init_database()

    def _init_database(self):
        """Инициализация таблицы загрузок в БД"""
        try:
            conn = sqlite3.connect(config.DATABASE_PATH)
            cursor = conn.cursor()

            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    url TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    platform TEXT,
                    title TEXT,
                    file_path TEXT,
                    file_size INTEGER,
                    quality TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"⚠️ Ошибка инициализации БД Media Downloader: {str(e)}")

    def handle_entry(self, bot: Any, call: Any) -> None:
        """
        ОБЯЗАТЕЛЬНО: Вход в модуль — показ меню.

        :param bot: Экземпляр TeleBot
        :param call: Объект CallbackQuery
        """
        chat_id = call.message.chat.id
        message_id = call.message.message_id

        # Инициализируем состояние пользователя
        self.set_user_state(chat_id, 'message_id', message_id)
        self.set_user_state(chat_id, 'media_type', None)
        self.set_user_state(chat_id, 'quality', None)
        self.set_user_state(chat_id, 'url', None)

        # Проверяем, включён ли модуль
        if not ENABLED:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="🚫 <b>Media Downloader</b>\n\n"
                     "Модуль временно отключен администратором.\n\n"
                     "Попробуйте позже.",
                reply_markup=media_downloader_menu_keyboard(),
                parse_mode="HTML"
            )
            return

        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="📥 <b>Media Downloader</b>\n\n"
                 "Загрузка видео и аудио из:\n"
                 "• YouTube\n"
                 "• TikTok\n"
                 "• Instagram\n"
                 "• Twitter/X\n"
                 "• Facebook\n"
                 "• Vimeo\n\n"
                 f"Макс. размер: {MAX_FILE_SIZE_MB}MB\n"
                 f"Лимит: {MAX_DOWNLOADS_PER_USER_PER_DAY} загрузок/день\n\n"
                 "Выберите действие:",
            reply_markup=media_downloader_menu_keyboard(),
            parse_mode="HTML"
        )

    def handle_callback(self, bot: Any, call: Any) -> None:
        """
        ОБЯЗАТЕЛЬНО: Обработка колбэков внутри модуля.

        :param bot: Экземпляр TeleBot
        :param call: Объект CallbackQuery
        """
        chat_id = call.message.chat.id
        message_id = call.message.message_id

        try:
            bot.answer_callback_query(call.id)

            # Проверка: включён ли модуль
            if not ENABLED:
                bot.answer_callback_query(
                    call.id,
                    "Модуль отключен администратором",
                    show_alert=True
                )
                return

            # Назад к списку модулей
            if call.data == "media_back_to_modules":
                # Получаем список всех модулей и показываем их
                from core.module_manager import module_manager
                modules = module_manager.get_all_modules()

                kb = types.InlineKeyboardMarkup(row_width=1)
                for module in modules:
                    kb.add(
                        types.InlineKeyboardButton(
                            f"{module.icon} {module.name}",
                            callback_data=f"module_{module.id}"
                        )
                    )
                kb.add(
                    types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")
                )

                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="📦 <b>Доступные модули</b>\n\nВыберите модуль для работы:",
                    reply_markup=kb,
                    parse_mode="HTML"
                )
                self.cleanup_user_state(chat_id)
                return

            # Назад в меню модуля
            if call.data == "media_back_to_menu":
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="📥 <b>Media Downloader</b>\n\nВыберите действие:",
                    reply_markup=media_downloader_menu_keyboard(),
                    parse_mode="HTML"
                )
                return

            # Загрузка видео
            if call.data == "media_video":
                self.set_user_state(chat_id, 'media_type', 'video')
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="🎬 <b>Загрузка видео</b>\n\n"
                         "Отправьте ссылку на видео:\n"
                         "• YouTube\n"
                         "• TikTok\n"
                         "• Instagram\n"
                         "• Twitter/X\n"
                         "• Facebook\n"
                         "• Vimeo",
                    reply_markup=None,
                    parse_mode="HTML"
                )
                bot.register_next_step_handler(call.message, self._process_url_input, bot)
                return

            # Загрузка аудио
            if call.data == "media_audio":
                self.set_user_state(chat_id, 'media_type', 'audio')
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="🎵 <b>Загрузка аудио</b>\n\n"
                         "Отправьте ссылку на видео (YouTube, TikTok, Vimeo):\n\n"
                         "<i>Будет извлечена только аудиодорожка</i>",
                    reply_markup=None,
                    parse_mode="HTML"
                )
                bot.register_next_step_handler(call.message, self._process_url_input, bot)
                return

            # Мои загрузки
            if call.data == "media_my_downloads":
                downloads = self._get_user_downloads(chat_id)

                if not downloads:
                    text = "📋 <b>Мои загрузки</b>\n\n"
                    text += "⚠️ У вас пока нет загрузок.\n\n"
                    text += "Используйте «🎬 Видео» или «🎵 Аудио» для первой загрузки."
                else:
                    text = "📋 <b>Мои загрузки</b>\n\n"
                    text += f"Всего загрузок: {len(downloads)}\n\n"

                    for i, dl in enumerate(downloads[:10], 1):
                        platform = dl.get('platform', 'Unknown')
                        media_type = "🎬" if dl.get('media_type') == 'video' else "🎵"
                        text += f"{i}. {media_type} {platform}\n"
                        text += f"   {dl.get('title', 'Unknown')[:50]}...\n"
                        text += f"   {dl.get('created_at', '')[:10]}\n\n"

                    if len(downloads) > 10:
                        text += f"<i>... и ещё {len(downloads) - 10} загрузок</i>"

                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=my_downloads_keyboard(),
                    parse_mode="HTML"
                )
                return

            # Выбор качества
            if call.data.startswith("media_quality_"):
                quality = call.data.replace("media_quality_", "")
                media_type = self.get_user_state(chat_id, 'media_type')

                if not media_type:
                    bot.answer_callback_query(
                        call.id,
                        "⚠️ Сначала выберите тип медиа",
                        show_alert=True
                    )
                    return

                self.set_user_state(chat_id, 'quality', quality)

                # После выбора качества запрашиваем URL
                if media_type == 'video':
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=f"🎬 <b>Загрузка видео</b>\n\n"
                             f"Качество: {quality}\n\n"
                             "Отправьте ссылку на видео:",
                        reply_markup=None,
                        parse_mode="HTML"
                    )
                else:
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=f"🎵 <b>Загрузка аудио</b>\n\n"
                             f"Качество: {quality} kbps\n\n"
                             "Отправьте ссылку на видео:",
                        reply_markup=None,
                        parse_mode="HTML"
                    )

                bot.register_next_step_handler_by_chat_id(chat_id, self._process_url_input, bot)
                return

            # Повторная загрузка
            if call.data == "media_again":
                media_type = self.get_user_state(chat_id, 'media_type')

                if media_type == 'video':
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text="🎬 <b>Загрузка видео</b>\n\n"
                             "Отправьте ссылку на видео:",
                        reply_markup=None,
                        parse_mode="HTML"
                    )
                else:
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text="🎵 <b>Загрузка аудио</b>\n\n"
                             "Отправьте ссылку на видео:",
                        reply_markup=None,
                        parse_mode="HTML"
                    )

                bot.register_next_step_handler_by_chat_id(chat_id, self._process_url_input, bot)
                return

        except Exception as e:
            bot.answer_callback_query(
                call.id,
                f"Ошибка: {str(e)[:60]}",
                show_alert=True
            )

    def get_menu_keyboard(self) -> types.InlineKeyboardMarkup:
        """
        ОБЯЗАТЕЛЬНО: Возвращает клавиатуру меню модуля.

        :return: InlineKeyboardMarkup для меню модуля
        """
        return media_downloader_menu_keyboard()

    def _process_url_input(self, message, bot):
        """Обработка ввода URL для загрузки"""
        chat_id = message.chat.id
        url = message.text.strip()

        # Удаляем сообщение пользователя
        try:
            bot.delete_message(chat_id, message.message_id)
        except Exception:
            pass

        # Проверяем состояние
        message_id = self.get_user_state(chat_id, 'message_id')
        media_type = self.get_user_state(chat_id, 'media_type')

        if message_id is None or not media_type:
            bot.send_message(
                chat_id,
                "⚠️ Сессия устарела. Вернитесь в главное меню.",
                reply_markup=media_downloader_menu_keyboard()
            )
            return

        # Проверяем лимит загрузок
        if not self._check_download_limit(chat_id):
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"⚠️ <b>Лимит загрузок</b>\n\n"
                     f"Вы достигли лимита ({MAX_DOWNLOADS_PER_USER_PER_DAY} загрузок/день).\n\n"
                     f"Попробуйте завтра.",
                reply_markup=media_downloader_menu_keyboard(),
                parse_mode="HTML"
            )
            return

        # Получаем информацию о видео
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="⏳ <b>Получение информации...</b>\n\n"
                 "Пожалуйста, подождите.",
            reply_markup=None,
            parse_mode="HTML"
        )

        video_info = downloader.get_video_info(url)

        if not video_info:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="❌ <b>Ошибка</b>\n\n"
                     "Не удалось получить информацию о видео.\n\n"
                     "Проверьте ссылку и попробуйте снова.",
                reply_markup=media_downloader_menu_keyboard(),
                parse_mode="HTML"
            )
            return

        # Проверяем платформу
        platform = video_info.get('platform', 'unknown')
        if platform == 'unknown':
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="❌ <b>Неподдерживаемая платформа</b>\n\n"
                     "Эта платформа не поддерживается.\n\n"
                     "Поддерживаются: YouTube, TikTok, Instagram, Twitter, Facebook, Vimeo",
                reply_markup=media_downloader_menu_keyboard(),
                parse_mode="HTML"
            )
            return

        # Проверяем, поддерживает ли платформа нужный тип медиа
        platform_info = SUPPORTED_PLATFORMS.get(platform, {})
        if media_type == 'audio' and not platform_info.get('audio', False):
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"❌ <b>Аудио не поддерживается</b>\n\n"
                     f"{platform_info.get('name', platform)} не поддерживает загрузку аудио.\n\n"
                     "Попробуйте загрузить видео или выберите другую платформу.",
                reply_markup=media_downloader_menu_keyboard(),
                parse_mode="HTML"
            )
            return

        # Показываем информацию о видео
        duration = video_info.get('duration', 0)
        duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "Unknown"

        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"📥 <b>Информация о видео</b>\n\n"
                 f"🎬 {video_info.get('title', 'Unknown')[:100]}\n"
                 f"📺 Платформа: {video_info.get('platform_name', 'Unknown')}\n"
                 f"👤 Автор: {video_info.get('uploader', 'Unknown')}\n"
                 f"⏱️ Длительность: {duration_str}\n"
                 f"👁️ Просмотров: {video_info.get('view_count', 0):,}\n\n"
                 f"{'🎬' if media_type == 'video' else '🎵'} Тип: {media_type}\n\n"
                 "Начинаю загрузку...",
            reply_markup=None,
            parse_mode="HTML"
        )

        # Загружаем медиа
        quality = self.get_user_state(chat_id, 'quality', '720' if media_type == 'video' else '192')

        if media_type == 'video':
            success, filepath = downloader.download_video(url, quality)
        else:
            success, filepath = downloader.download_audio(url, quality)

        if success and filepath and os.path.exists(filepath):
            # Проверяем размер файла
            file_size = os.path.getsize(filepath)
            file_size_mb = file_size / (1024 * 1024)

            if file_size_mb > MAX_FILE_SIZE_MB:
                downloader.cleanup_file(filepath)
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"❌ <b>Файл слишком большой</b>\n\n"
                         f"Размер: {file_size_mb:.2f}MB\n"
                         f"Максимум: {MAX_FILE_SIZE_MB}MB\n\n"
                         "Попробуйте выбрать меньшее качество.",
                    reply_markup=media_downloader_menu_keyboard(),
                    parse_mode="HTML"
                )
                return

            # Отправляем файл
            try:
                if media_type == 'video':
                    with open(filepath, 'rb') as f:
                        bot.send_video(
                            chat_id,
                            f,
                            caption=f"📥 {video_info.get('title', 'Unknown')[:200]}",
                            timeout=300
                        )
                else:
                    with open(filepath, 'rb') as f:
                        bot.send_audio(
                            chat_id,
                            f,
                            caption=f"📥 {video_info.get('title', 'Unknown')[:200]}",
                            timeout=300
                        )
            except Exception as e:
                print(f"❌ Ошибка отправки файла: {str(e)}")
                bot.send_message(
                    chat_id,
                    f"❌ Ошибка отправки: {str(e)[:200]}"
                )
            finally:
                # Удаляем файл после отправки
                downloader.cleanup_file(filepath)

            # Логируем загрузку
            self._log_download(
                user_id=chat_id,
                url=url,
                media_type=media_type,
                platform=platform,
                title=video_info.get('title', 'Unknown'),
                file_path=filepath,
                file_size=file_size,
                quality=quality
            )

            # Показываем меню
            bot.send_message(
                chat_id,
                "✅ Загрузка завершена!",
                reply_markup=media_downloader_menu_keyboard()
            )
        else:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="❌ <b>Ошибка загрузки</b>\n\n"
                     "Не удалось загрузить медиа.\n\n"
                     "Возможные причины:\n"
                     "• Видео недоступно\n"
                     "• Ограничения платформы\n"
                     "• Проблемы с сетью\n\n"
                     "Попробуйте другую ссылку.",
                reply_markup=media_downloader_menu_keyboard(),
                parse_mode="HTML"
            )

    def _check_download_limit(self, user_id: int) -> bool:
        """Проверка лимита загрузок на пользователя в день"""
        try:
            conn = sqlite3.connect(config.DATABASE_PATH)
            cursor = conn.cursor()

            today = datetime.now().strftime('%Y-%m-%d')

            cursor.execute(f"""
                SELECT COUNT(*) FROM {TABLE_NAME}
                WHERE user_id = ? AND DATE(created_at) = ?
            """, (user_id, today))

            count = cursor.fetchone()[0]
            conn.close()

            return count < MAX_DOWNLOADS_PER_USER_PER_DAY

        except Exception as e:
            print(f"⚠️ Ошибка проверки лимита: {str(e)}")
            return True  # Разрешаем при ошибке

    def _log_download(self, user_id: int, url: str, media_type: str,
                      platform: str, title: str, file_path: str,
                      file_size: int, quality: str):
        """Логирование загрузки в БД"""
        try:
            conn = sqlite3.connect(config.DATABASE_PATH)
            cursor = conn.cursor()

            cursor.execute(f"""
                INSERT INTO {TABLE_NAME} 
                (user_id, url, media_type, platform, title, file_path, file_size, quality)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, url, media_type, platform, title, file_path, file_size, quality))

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"⚠️ Ошибка логирования загрузки: {str(e)}")

    def _get_user_downloads(self, user_id: int) -> list:
        """Получение истории загрузок пользователя"""
        try:
            conn = sqlite3.connect(config.DATABASE_PATH)
            cursor = conn.cursor()

            cursor.execute(f"""
                SELECT url, media_type, platform, title, file_size, quality, created_at
                FROM {TABLE_NAME}
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 50
            """, (user_id,))

            downloads = []
            for row in cursor.fetchall():
                downloads.append({
                    'url': row[0],
                    'media_type': row[1],
                    'platform': row[2],
                    'title': row[3],
                    'file_size': row[4],
                    'quality': row[5],
                    'created_at': row[6]
                })

            conn.close()
            return downloads
        except Exception as e:
            print(f"⚠️ Ошибка получения загрузок: {str(e)}")
            return []

    def on_load(self, bot: Any) -> None:
        """Вызывается при загрузке модуля"""
        if ENABLED:
            print(f"📥 Модуль Media Downloader v{self.version} загружен")
        else:
            print(f"⚠️ Модуль Media Downloader v{self.version} отключен")

    def on_unload(self, bot: Any) -> None:
        """Вызывается при выгрузке модуля"""
        print(f"📥 Модуль Media Downloader v{self.version} выгружен")