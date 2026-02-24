# modules/media_downloader/handlers.py
# Обработчики модуля Media Downloader
# Версия: 4.1.1
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
    my_downloads_keyboard
)
from .downloader import downloader
from .config import (
    ENABLED,
    MAX_FILE_SIZE_MB,
    MAX_DOWNLOADS_PER_USER_PER_DAY,
    TABLE_NAME
)
import config

db = DatabaseManager()


class MediaDownloaderModule(BaseModule):
    """Модуль загрузки медиа"""

    def __init__(self, module_id, name, description, icon, version, callback_prefix):
        super().__init__(module_id, name, description, icon, version, callback_prefix)
        self._init_database()

    def _init_database(self):
        """Инициализация БД"""
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
            print(f"⚠️ Ошибка инициализации БД: {str(e)}")

    def handle_entry(self, bot: Any, call: Any) -> None:
        """Вход в модуль"""
        chat_id = call.message.chat.id
        message_id = call.message.message_id

        self.set_user_state(chat_id, 'message_id', message_id)
        self.set_user_state(chat_id, 'media_type', None)
        self.set_user_state(chat_id, 'quality', None)

        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="📥 <b>Media Downloader</b>\n\n"
                 "Загрузка видео и аудио:\n"
                 "• YouTube\n"
                 "• TikTok, Instagram\n\n"
                 f"Макс. размер: {MAX_FILE_SIZE_MB}MB\n"
                 f"Лимит: {MAX_DOWNLOADS_PER_USER_PER_DAY}/день\n\n"
                 "Выберите действие:",
            reply_markup=media_downloader_menu_keyboard(),
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
                    kb.add(types.InlineKeyboardButton(
                        f"{module.icon} {module.name}",
                        callback_data=f"module_{module.id}"
                    ))
                kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_main"))

                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="📦 <b>Доступные модули</b>\n\nВыберите модуль:",
                    reply_markup=kb,
                    parse_mode="HTML"
                )
                self.cleanup_user_state(chat_id)
                return

            # Назад в меню
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
                self.set_user_state(chat_id, 'quality', None)  # СБРОС качества!
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="🎬 <b>Загрузка видео</b>\n\nВыберите качество:",
                    reply_markup=quality_keyboard("video"),
                    parse_mode="HTML"
                )
                return

            # Загрузка аудио
            if call.data == "media_audio":
                self.set_user_state(chat_id, 'media_type', 'audio')
                self.set_user_state(chat_id, 'quality', None)  # СБРОС качества!
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="🎵 <b>Загрузка аудио</b>\n\nВыберите качество:",
                    reply_markup=quality_keyboard("audio"),
                    parse_mode="HTML"
                )
                return

            # Выбор качества
            if call.data.startswith("media_quality_"):
                quality = call.data.replace("media_quality_", "")
                media_type = self.get_user_state(chat_id, 'media_type')

                # ПРОВЕРКА: выбран ли тип медиа
                if not media_type:
                    bot.answer_callback_query(call.id, "⚠️ Сначала выберите тип", show_alert=True)
                    return

                # СОХРАНЕНИЕ качества
                self.set_user_state(chat_id, 'quality', quality)
                print(f"\n✅ Качество сохранено: {quality} (тип: {media_type})")

                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"📥 <b>Загрузка</b>\n\n"
                         f"Тип: {'Видео' if media_type == 'video' else 'Аудио'}\n"
                         f"Качество: {quality}\n\n"
                         f"Отправьте ссылку:",
                    reply_markup=None,
                    parse_mode="HTML"
                )
                bot.register_next_step_handler_by_chat_id(chat_id, self._process_url_input, bot)
                return

            # Мои загрузки
            if call.data == "media_my_downloads":
                downloads = self._get_user_downloads(chat_id)

                if not downloads:
                    text = "📋 <b>Мои загрузки</b>\n\n⚠️ Пока нет загрузок."
                else:
                    text = f"📋 <b>Мои загрузки</b>\n\nВсего: {len(downloads)}\n\n"
                    for i, dl in enumerate(downloads[:10], 1):
                        icon = "🎬" if dl.get('media_type') == 'video' else "🎵"
                        text += f"{i}. {icon} {dl.get('platform', '?')}\n"
                        text += f"   {dl.get('title', '?')[:50]}...\n\n"

                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=my_downloads_keyboard(),
                    parse_mode="HTML"
                )
                return

            # Повтор
            if call.data == "media_again":
                media_type = self.get_user_state(chat_id, 'media_type')
                quality = self.get_user_state(chat_id, 'quality')

                # Если качество не выбрано, используем дефолтное
                if not quality:
                    quality = '360' if media_type == 'video' else '128'

                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"📥 <b>Загрузка</b>\n\n"
                         f"Качество: {quality}\n\n"
                         f"Отправьте ссылку:",
                    reply_markup=None,
                    parse_mode="HTML"
                )
                bot.register_next_step_handler_by_chat_id(chat_id, self._process_url_input, bot)
                return

        except Exception as e:
            bot.answer_callback_query(call.id, f"Ошибка: {str(e)[:60]}", show_alert=True)

    def get_menu_keyboard(self) -> types.InlineKeyboardMarkup:
        """Клавиатура меню"""
        return media_downloader_menu_keyboard()

    def _process_url_input(self, message, bot):
        """Обработка ввода URL"""
        chat_id = message.chat.id
        url = message.text.strip()

        # Удаляем сообщение пользователя
        try:
            bot.delete_message(chat_id, message.message_id)
        except:
            pass

        message_id = self.get_user_state(chat_id, 'message_id')
        media_type = self.get_user_state(chat_id, 'media_type')
        quality = self.get_user_state(chat_id, 'quality')

        # ПРОВЕРКА: выбрано ли качество
        if not quality:
            quality = '360' if media_type == 'video' else '128'
            print(f"⚠️ Качество не выбрано, используем: {quality}")

        print(f"\n🔍 Параметры загрузки: тип={media_type}, качество={quality}")

        if message_id is None or not media_type:
            bot.send_message(chat_id, "⚠️ Сессия устарела.", reply_markup=media_downloader_menu_keyboard())
            return

        # Проверяем лимит
        if not self._check_download_limit(chat_id):
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"⚠️ <b>Лимит</b>\n\nДостигнут лимит ({MAX_DOWNLOADS_PER_USER_PER_DAY}/день).",
                reply_markup=media_downloader_menu_keyboard(),
                parse_mode="HTML"
            )
            return

        # Показываем статус
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="⏳ <b>Обработка...</b>",
            reply_markup=None,
            parse_mode="HTML"
        )

        # Получаем информацию
        video_info = downloader.get_video_info(url)

        if not video_info:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="❌ <b>Ошибка</b>\n\nНе удалось получить информацию.",
                reply_markup=media_downloader_menu_keyboard(),
                parse_mode="HTML"
            )
            return

        # Показываем информацию
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"📥 <b>Информация</b>\n\n"
                 f"🎬 {video_info.get('title', '?')[:100]}\n"
                 f"⏱️ {video_info.get('duration_str', '?')}\n\n"
                 f"{'🎬' if media_type == 'video' else '🎵'} Загрузка...",
            reply_markup=None,
            parse_mode="HTML"
        )

        # Загружаем
        if media_type == 'video':
            success, filepath = downloader.download_video(url, quality)
        else:
            success, filepath = downloader.download_audio(url, quality)

        if success and filepath and os.path.exists(filepath):
            file_size = os.path.getsize(filepath)
            file_size_mb = file_size / (1024 * 1024)

            if file_size_mb > MAX_FILE_SIZE_MB:
                downloader.cleanup_file(filepath)
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"❌ <b>Файл слишком большой</b>\n\nРазмер: {file_size_mb:.2f}MB\nМаксимум: {MAX_FILE_SIZE_MB}MB",
                    reply_markup=media_downloader_menu_keyboard(),
                    parse_mode="HTML"
                )
                return

            # ==========================================
            # ОТПРАВКА ФАЙЛА (КРИТИЧЕСКИ ВАЖНО!)
            # ==========================================
            print(f"\n{'=' * 50}")
            print(f"📤 ОТПРАВКА ФАЙЛА:")
            print(f"   Путь: {filepath}")
            print(f"   Размер: {file_size_mb:.2f}MB")
            print(f"   Timeout: 300 сек (5 минут)")
            print(f"{'=' * 50}\n")

            try:
                if media_type == 'video':
                    print("🎬 Отправка видео...")
                    with open(filepath, 'rb') as f:
                        bot.send_video(
                            chat_id,
                            f,
                            caption=video_info.get('title', '')[:200],
                            timeout=300  # 5 МИНУТ!
                        )
                else:
                    print("🎵 Отправка аудио...")
                    with open(filepath, 'rb') as f:
                        bot.send_audio(
                            chat_id,
                            f,
                            caption=video_info.get('title', '')[:200],
                            timeout=300  # 5 МИНУТ!
                        )

                print("✅ ФАЙЛ ОТПРАВЛЕН УСПЕШНО!\n")

            except Exception as e:
                print(f"❌ ОШИБКА ОТПРАВКИ: {str(e)}\n")
                print(f"📊 Тип ошибки: {type(e).__name__}")
                bot.send_message(chat_id, f"❌ Ошибка отправки: {str(e)[:200]}")
            finally:
                # ==========================================
                # УДАЛЯЕМ ФАЙЛ ТОЛЬКО ПОСЛЕ ОТПРАВКИ!
                # ==========================================
                print("🗑️ Удаление временного файла...")
                downloader.cleanup_file(filepath)
                print(f"{'=' * 50}\n")

            # Логируем
            self._log_download(
                user_id=chat_id,
                url=url,
                media_type=media_type,
                platform=video_info.get('platform', ''),
                title=video_info.get('title', ''),
                file_path=filepath,
                file_size=file_size,
                quality=quality
            )

            # Показываем результат
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="✅ <b>Готово!</b>\n\nВыберите действие:",
                reply_markup=media_downloader_menu_keyboard(),
                parse_mode="HTML"
            )
        else:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="❌ <b>Ошибка загрузки</b>\n\nПопробуйте другую ссылку.",
                reply_markup=media_downloader_menu_keyboard(),
                parse_mode="HTML"
            )

    def _check_download_limit(self, user_id: int) -> bool:
        """Проверка лимита"""
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
        except:
            return True

    def _log_download(self, user_id: int, url: str, media_type: str, platform: str,
                      title: str, file_path: str, file_size: int, quality: str):
        """Логирование"""
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
            print(f"⚠️ Ошибка логирования: {str(e)}")

    def _get_user_downloads(self, user_id: int) -> list:
        """Получение истории"""
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
        except:
            return []

    def on_load(self, bot: Any) -> None:
        """Загрузка модуля"""
        if ENABLED:
            print(f"📥 Media Downloader v4.1.1 загружен")

    def on_unload(self, bot: Any) -> None:
        """Выгрузка модуля"""
        print(f"📥 Media Downloader выгружен")