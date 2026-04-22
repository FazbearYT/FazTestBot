import os
import uuid
import time
from telebot import types
from typing import Any
from core.module_base import BaseModule
from core.database import DatabaseManager
from .keyboards import (
    media_menu_keyboard,
    quality_keyboard,
    result_keyboard,
    cancel_keyboard
)
from .downloader import downloader
from .config import (
    ENABLED,
    MAX_FILE_SIZE_MB,
    MAX_DOWNLOADS_PER_USER_PER_DAY,
    VIDEO_QUALITIES,
    AUDIO_QUALITIES
)
import sqlite3
import config

db = DatabaseManager()


class MediaDownloaderModule(BaseModule):
    """Модуль загрузки медиа на основе yt-dlp"""

    def __init__(self, module_id, name, description, icon, version, callback_prefix):
        super().__init__(module_id, name, description, icon, version, callback_prefix)
        self._init_database()

    def _init_database(self):
        """Инициализация таблицы логов"""
        try:
            conn = sqlite3.connect(config.DATABASE_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS media_downloader_logs (
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
            print(f"⚠️ Ошибка инициализации БД: {str(e)}")

    def handle_entry(self, bot: Any, call: Any) -> None:
        """Вход в модуль"""
        chat_id = call.message.chat.id
        message_id = call.message.message_id

        session_id = str(uuid.uuid4())

        self.set_user_state(chat_id, 'message_id', message_id)
        self.set_user_state(chat_id, 'session_id', session_id)
        self.set_user_state(chat_id, 'media_type', None)
        self.set_user_state(chat_id, 'quality', None)
        self.set_user_state(chat_id, 'url', None)

        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=(
                "📥 <b>Media Downloader</b>\n\n"
                "Загрузка видео и аудио из YouTube, TikTok, Instagram и др.\n\n"
                "Выберите тип медиа:"
            ),
            reply_markup=media_menu_keyboard(),
            parse_mode="HTML"
        )

    def handle_callback(self, bot: Any, call: Any) -> None:
        """Обработка колбэков"""
        chat_id = call.message.chat.id
        message_id = call.message.message_id

        try:
            bot.answer_callback_query(call.id)

            # Назад к списку модулей
            if call.data == "media_back_to_modules":
                from core.module_manager import module_manager
                modules = module_manager.get_all_modules()
                kb = types.InlineKeyboardMarkup(row_width=1)
                for module in modules:
                    kb.add(
                        types.InlineKeyboardButton(f"{module.icon} {module.name}", callback_data=f"module_{module.id}"))
                kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_main"))
                bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                      text="📦 <b>Доступные модули</b>\n\nВыберите модуль:", reply_markup=kb,
                                      parse_mode="HTML")
                self.cleanup_user_state(chat_id)
                return

            # Назад в меню модуля
            if call.data == "media_back_to_menu":
                self.set_user_state(chat_id, 'media_type', None)
                self.set_user_state(chat_id, 'quality', None)
                self.set_user_state(chat_id, 'url', None)
                bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                      text="📥 <b>Media Downloader</b>\n\nВыберите тип медиа:",
                                      reply_markup=media_menu_keyboard(), parse_mode="HTML")
                return

            # Проверка состояния
            if self.get_user_state(chat_id, 'message_id') is None:
                bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                      text="⚠️ Сессия устарела. Вернитесь в главное меню.",
                                      reply_markup=media_menu_keyboard(), parse_mode="HTML")
                return

            # Выбор типа медиа
            if call.data in ["media_video", "media_audio"]:
                media_type = call.data.replace("media_", "")
                self.set_user_state(chat_id, 'media_type', media_type)
                bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                      text=f"📥 <b>Media Downloader</b>\n\nТип: {'🎬 Видео' if media_type == 'video' else '🎵 Аудио'}\n\nВыберите качество:",
                                      reply_markup=quality_keyboard(media_type), parse_mode="HTML")
                return

            # Выбор качества
            if call.data.startswith("media_quality_"):
                quality = call.data.replace("media_quality_", "")
                self.set_user_state(chat_id, 'quality', quality)

                media_type = self.get_user_state(chat_id, 'media_type')
                bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                      text=f"📥 <b>Media Downloader</b>\n\nТип: {'🎬 Видео' if media_type == 'video' else '🎵 Аудио'}\nКачество: {quality}\n\nОтправьте ссылку на видео/аудио:",
                                      reply_markup=cancel_keyboard(), parse_mode="HTML")
                bot.register_next_step_handler(call.message, self._process_url_input, bot)
                return

            # История загрузок
            if call.data == "media_history":
                downloads = self._get_user_downloads(chat_id)
                if not downloads:
                    bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                          text="📋 <b>История загрузок</b>\n\nУ вас пока нет загрузок.",
                                          reply_markup=media_menu_keyboard(), parse_mode="HTML")
                else:
                    text = "📋 <b>История загрузок</b>\n\n"
                    for i, dl in enumerate(downloads[:5], 1):
                        text += f"{i}. {dl['title'][:30]}... ({dl['media_type']})\n"
                    text += "\nИспользуйте «Скачать ещё» для новой загрузки."
                    bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text,
                                          reply_markup=media_menu_keyboard(), parse_mode="HTML")
                return

            # Повторная загрузка
            if call.data == "media_again":
                self.set_user_state(chat_id, 'media_type', None)
                self.set_user_state(chat_id, 'quality', None)
                self.set_user_state(chat_id, 'url', None)
                bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                      text="📥 <b>Media Downloader</b>\n\nВыберите тип медиа:",
                                      reply_markup=media_menu_keyboard(), parse_mode="HTML")
                return

        except Exception as e:
            bot.answer_callback_query(call.id, f"Ошибка: {str(e)[:60]}", show_alert=True)

    def get_menu_keyboard(self) -> types.InlineKeyboardMarkup:
        return media_menu_keyboard()

    def _process_url_input(self, message, bot):
        """Обработка ввода URL"""
        chat_id = message.chat.id
        url = message.text.strip()

        try:
            bot.delete_message(chat_id, message.message_id)
        except Exception:
            pass

        if not url.startswith(('http://', 'https://')):
            bot.send_message(chat_id, "❌ Некорректная ссылка. Отправьте валидный URL.", reply_markup=cancel_keyboard())
            bot.register_next_step_handler_by_chat_id(chat_id, self._process_url_input, bot)
            return

        self.set_user_state(chat_id, 'url', url)
        media_type = self.get_user_state(chat_id, 'media_type')
        quality = self.get_user_state(chat_id, 'quality')

        # Проверка лимита
        if not self._check_download_limit(chat_id):
            bot.edit_message_text(chat_id=chat_id, message_id=self.get_user_state(chat_id, 'message_id'),
                                  text="⚠️ Превышен лимит загрузок на сегодня.", reply_markup=media_menu_keyboard(),
                                  parse_mode="HTML")
            return

        # Начинаем загрузку
        self._start_download(bot, chat_id, url, media_type, quality)

    def _start_download(self, bot: Any, chat_id: int, url: str, media_type: str, quality: str):
        """Начало загрузки"""
        message_id = self.get_user_state(chat_id, 'message_id')

        # Получаем инфо о видео
        info = downloader.get_video_info(url)
        if not info:
            bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                  text="❌ Не удалось получить информацию о видео. Проверьте ссылку.",
                                  reply_markup=media_menu_keyboard(), parse_mode="HTML")
            return

        # Показываем прогресс
        progress_msg = bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                             text=f"📥 Загрузка...\n\n📌 {info['title'][:50]}...\n⏳ Подготовка...",
                                             parse_mode="HTML")

        def progress_callback(percent, text):
            try:
                bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                      text=f"📥 Загрузка...\n\n📌 {info['title'][:50]}...\n⏳ {text}", parse_mode="HTML")
            except Exception:
                pass

        # Загружаем
        if media_type == "video":
            success, filepath = downloader.download_video(url, quality, progress_callback)
        else:
            success, filepath = downloader.download_audio(url, quality, progress_callback)

        if not success:
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"❌ Ошибка загрузки: {filepath}",
                                  reply_markup=media_menu_keyboard(), parse_mode="HTML")
            return

        # Проверяем размер
        #file_size = os.path.getsize(filepath)
        #if file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
            #downloader.cleanup_file(filepath)
            #bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                  #text=f"❌ Файл слишком большой ({file_size / 1024 / 1024:.1f}MB). Максимум: {MAX_FILE_SIZE_MB}MB.",
                                  #reply_markup=media_menu_keyboard(), parse_mode="HTML")
            #return

        # Отправляем файл
        try:
            if media_type == "video":
                with open(filepath, 'rb') as video:
                    bot.send_video(chat_id, video, caption=f"🎬 {info['title']}", parse_mode="HTML")
            else:
                with open(filepath, 'rb') as audio:
                    bot.send_audio(chat_id, audio, caption=f"🎵 {info['title']}", parse_mode="HTML")

            # Логируем
            self._log_download(chat_id, url, media_type, info['platform_name'], info['title'], filepath, file_size,
                               quality)

            # Очищаем файл
            downloader.cleanup_file(filepath)

            # Показываем результат
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="✅ Загрузка завершена!",
                                  reply_markup=result_keyboard(), parse_mode="HTML")

        except Exception as e:
            downloader.cleanup_file(filepath)
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"❌ Ошибка отправки: {str(e)}",
                                  reply_markup=media_menu_keyboard(), parse_mode="HTML")

    def _check_download_limit(self, user_id: int) -> bool:
        """Проверка лимита загрузок"""
        # Здесь можно добавить проверку в БД
        return True

    def _log_download(self, user_id: int, url: str, media_type: str, platform: str, title: str, file_path: str,
                      file_size: int, quality: str):
        """Логирование загрузки"""
        try:
            conn = sqlite3.connect(config.DATABASE_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO media_downloader_logs (user_id, url, media_type, platform, title, file_path, file_size, quality)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, url, media_type, platform, title, file_path, file_size, quality))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"⚠️ Ошибка логирования: {str(e)}")

    def _get_user_downloads(self, user_id: int) -> list:
        """Получение истории загрузок"""
        try:
            conn = sqlite3.connect(config.DATABASE_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT title, media_type, created_at FROM media_downloader_logs WHERE user_id = ? ORDER BY created_at DESC LIMIT 5",
                (user_id,))
            rows = cursor.fetchall()
            conn.close()
            return [{"title": row[0], "media_type": row[1], "created_at": row[2]} for row in rows]
        except Exception as e:
            print(f"⚠️ Ошибка получения истории: {str(e)}")
            return []

    def on_load(self, bot: Any) -> None:
        print(f"📥 Модуль Media Downloader v{self.version} загружен")

    def on_unload(self, bot: Any) -> None:
        print(f"📥 Модуль Media Downloader v{self.version} выгружен")