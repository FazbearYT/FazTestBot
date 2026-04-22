import os
import sqlite3
import uuid
from telebot import types
from typing import Any
from core.module_base import BaseModule
from core.database import DatabaseManager
from .keyboards import (
    media_menu_keyboard,
    quality_keyboard,
    result_keyboard,
    cancel_keyboard,
    large_file_keyboard
)
from .downloader import downloader
from .config import (
    ENABLED,
    MAX_FILE_SIZE_MB,
    TABLE_NAME
)
import config

db = DatabaseManager()


class MediaDownloaderModule(BaseModule):
    """Модуль загрузки медиа с поддержкой больших файлов"""

    def __init__(self, module_id, name, description, icon, version, callback_prefix):
        super().__init__(module_id, name, description, icon, version, callback_prefix)

    def handle_entry(self, bot: Any, call: Any) -> None:
        chat_id = call.message.chat.id
        message_id = call.message.message_id

        session_id = str(uuid.uuid4())
        self.set_user_state(chat_id, 'message_id', message_id)
        self.set_user_state(chat_id, 'session_id', session_id)
        self.set_user_state(chat_id, 'media_type', None)
        self.set_user_state(chat_id, 'quality', None)
        self.set_user_state(chat_id, 'url', None)
        self.set_user_state(chat_id, 'pending_info', None)

        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="📥 <b>Media Downloader</b>\n\nЗагрузка видео и аудио.\nМакс. размер отправки: 50MB.\n\nВыберите тип:",
            reply_markup=media_menu_keyboard(),
            parse_mode="HTML"
        )

    def handle_callback(self, bot: Any, call: Any) -> None:
        chat_id = call.message.chat.id
        message_id = call.message.message_id

        try:
            bot.answer_callback_query(call.id)

            # Навигация назад
            if call.data == "media_back_to_modules":
                from core.module_manager import module_manager
                modules = module_manager.get_all_modules()
                kb = types.InlineKeyboardMarkup(row_width=1)
                for m in modules:
                    kb.add(types.InlineKeyboardButton(f"{m.icon} {m.name}", callback_data=f"module_{m.id}"))
                kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_main"))
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="📦 <b>Модули</b>\n\nВыберите:",
                                      reply_markup=kb, parse_mode="HTML")
                self.cleanup_user_state(chat_id)
                return

            if call.data == "media_back_to_menu":
                self._reset_state(chat_id)
                bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                      text="📥 <b>Media Downloader</b>\n\nВыберите тип:",
                                      reply_markup=media_menu_keyboard(), parse_mode="HTML")
                return

            if self.get_user_state(chat_id, 'message_id') is None:
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="⚠️ Сессия устарела.",
                                      reply_markup=media_menu_keyboard(), parse_mode="HTML")
                return

            # Выбор типа медиа
            if call.data in ["media_video", "media_audio"]:
                media_type = call.data.replace("media_", "")
                self.set_user_state(chat_id, 'media_type', media_type)
                bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                      text=f"📥 <b>Media Downloader</b>\n\nТип: {'🎬 Видео' if media_type == 'video' else '🎵 Аудио'}\n\nКачество:",
                                      reply_markup=quality_keyboard(media_type), parse_mode="HTML")
                return

            # Выбор качества
            if call.data.startswith("media_quality_"):
                quality = call.data.replace("media_quality_", "")
                self.set_user_state(chat_id, 'quality', quality)
                bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                      text="📥 <b>Media Downloader</b>\n\nОтправьте ссылку:",
                                      reply_markup=cancel_keyboard(), parse_mode="HTML")
                bot.register_next_step_handler(call.message, self._process_url_input, bot)
                return

            # Повторная загрузка (сброс)
            if call.data == "media_again":
                self._reset_state(chat_id)
                bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                      text="📥 <b>Media Downloader</b>\n\nВыберите тип:",
                                      reply_markup=media_menu_keyboard(), parse_mode="HTML")
                return

            # ===== ОБРАБОТКА БОЛЬШИХ ФАЙЛОВ =====
            if call.data == "media_large_file_360p":
                self._handle_large_file_action(bot, chat_id, message_id, "360p")
                return
            if call.data == "media_large_file_480p":
                self._handle_large_file_action(bot, chat_id, message_id, "480p")
                return
            if call.data == "media_upload_tmpfiles":
                self._handle_upload(bot, chat_id, message_id, "tmpfiles")
                return

        except Exception as e:
            bot.answer_callback_query(call.id, f"Ошибка: {str(e)[:60]}", show_alert=True)

    def get_menu_keyboard(self) -> types.InlineKeyboardMarkup:
        return media_menu_keyboard()

    def _process_url_input(self, message, bot):
        chat_id = message.chat.id
        url = message.text.strip()
        try:
            bot.delete_message(chat_id, message.message_id)
        except:
            pass

        if not url.startswith(('http://', 'https://')):
            bot.send_message(chat_id, "❌ Некорректная ссылка.", reply_markup=cancel_keyboard())
            bot.register_next_step_handler_by_chat_id(chat_id, self._process_url_input, bot)
            return

        self.set_user_state(chat_id, 'url', url)
        self._start_download(bot, chat_id, url, self.get_user_state(chat_id, 'media_type'),
                             self.get_user_state(chat_id, 'quality'))

    def _start_download(self, bot: Any, chat_id: int, url: str, media_type: str, quality: str):
        """Единая точка входа: инфо → проверка размера → загрузка → отправка/меню"""
        message_id = self.get_user_state(chat_id, 'message_id')
        info = downloader.get_video_info(url)

        if not info:
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="❌ Не удалось получить данные о видео.",
                                  reply_markup=media_menu_keyboard(), parse_mode="HTML")
            return

        # 1. Проверка размера ДО скачивания (если известен из метаданных)
        est_size = info.get('filesize') or info.get('filesize_approx')
        if est_size and est_size > MAX_FILE_SIZE_MB * 1024 * 1024:
            self._show_large_file_menu(bot, chat_id, message_id, url, media_type, quality, info, est_size)
            return

        # 2. Скачивание
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"⏳ Загрузка...\n📌 {info['title'][:100]}...",
                              parse_mode="HTML")

        success, filepath = downloader.download_video(url,
                                                      quality) if media_type == "video" else downloader.download_audio(
            url, quality)
        if not success:
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"❌ Ошибка: {filepath}",
                                  reply_markup=media_menu_keyboard(), parse_mode="HTML")
            return

        # 3. Проверка размера ПОСЛЕ скачивания (фактический вес)
        actual_size = os.path.getsize(filepath)
        if actual_size > MAX_FILE_SIZE_MB * 1024 * 1024:
            downloader.cleanup_file(filepath)
            self._show_large_file_menu(bot, chat_id, message_id, url, media_type, quality, info, actual_size)
            return

        # 4. Файл в норме → отправка в Telegram
        self._send_to_telegram(bot, chat_id, message_id, filepath, media_type, info, quality)

    def _show_large_file_menu(self, bot, chat_id, message_id, url, media_type, quality, info, size_bytes):
        """Показывает меню выбора при превышении лимита"""
        size_mb = size_bytes / 1024 / 1024
        self.set_user_state(chat_id, 'pending_info', {
            'url': url, 'media_type': media_type, 'quality': quality, 'info': info
        })

        bot.edit_message_text(
            chat_id=chat_id, message_id=message_id,
            text=(
                f"📥 <b>Media Downloader</b>\n\n"
                f"⚠️ <b>Файл слишком большой для отправки!</b>\n\n"
                f"📌 {info['title'][:100]}...\n"
                f"📊 Размер: <b>{size_mb:.1f}MB</b> (Лимит: {MAX_FILE_SIZE_MB}MB)\n\n"
                f"Выберите действие:"
            ),
            reply_markup=large_file_keyboard(),
            parse_mode="HTML"
        )

    def _handle_large_file_action(self, bot, chat_id, message_id, new_quality):
        """Перезапуск загрузки с пониженным качеством"""
        pending = self.get_user_state(chat_id, 'pending_info')
        if not pending:
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="⚠️ Сессия устарела.",
                                  reply_markup=media_menu_keyboard(), parse_mode="HTML")
            return

        self.set_user_state(chat_id, 'pending_info', None)
        self._start_download(bot, chat_id, pending['url'], pending['media_type'], new_quality)

    def _handle_upload(self, bot, chat_id, message_id, service):
        """Загрузка на внешний хостинг"""
        pending = self.get_user_state(chat_id, 'pending_info')
        if not pending:
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="⚠️ Сессия устарела.",
                                  reply_markup=media_menu_keyboard(), parse_mode="HTML")
            return

        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"⏳ Загрузка на {service}...",
                              parse_mode="HTML")

        # Скачиваем заново (файл был удалён после проверки размера)
        success, filepath = downloader.download_video(pending['url'], pending['quality']) if pending[
                                                                                                 'media_type'] == "video" else downloader.download_audio(
            pending['url'], pending['quality'])
        if not success:
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"❌ Ошибка скачивания: {filepath}",
                                  reply_markup=media_menu_keyboard(), parse_mode="HTML")
            return

        # Аплоад
        if service == "tmpfiles":
            ok, link = self._upload_tmpfiles(filepath)

        downloader.cleanup_file(filepath)

        if ok:
            bot.send_message(
                chat_id,
                f"✅ <b>Файл загружен!</b>\n\n🔗 <a href='{link}'>Скачать</a>\n\n<i>Хранится временно. Не делитесь ссылкой публично.</i>",
                reply_markup=result_keyboard(),
                parse_mode="HTML"
            )
            db.log_media_download(chat_id, pending['url'], pending['media_type'], pending['info']['platform'],
                                  pending['info']['title'], "cloud", 0, pending['quality'])
        else:
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"❌ Ошибка аплоада: {link}",
                                  reply_markup=media_menu_keyboard(), parse_mode="HTML")

    def _send_to_telegram(self, bot, chat_id, message_id, filepath, media_type, info, quality):
        """Отправка файла в Telegram + новое сообщение с меню + логирование + очистка"""
        try:
            # 1. Отправляем файл (видео или аудио)
            if media_type == "video":
                with open(filepath, 'rb') as f:
                    bot.send_video(
                        chat_id,
                        f,
                        caption=f"🎬 {info['title'][:200]}",
                        parse_mode="HTML"
                    )
            else:  # audio
                with open(filepath, 'rb') as f:
                    bot.send_audio(
                        chat_id,
                        f,
                        caption=f"🎵 {info['title'][:200]}",
                        parse_mode="HTML"
                    )

            # 2. Логируем загрузку
            fsize = os.path.getsize(filepath)
            db.log_media_download(
                chat_id,
                info['url'],
                media_type,
                info['platform'],
                info['title'],
                str(filepath),  # ✅ ИСПРАВЛЕНО: преобразуем Path в строку
                fsize,
                quality
            )

            # 3. Очищаем временный файл
            downloader.cleanup_file(filepath)

            # 4. ⭐ ОТПРАВЛЯЕМ НОВОЕ сообщение с меню продолжения
            continuation_text = (
                f"✅ <b>Файл готов!</b>\n\n"
                f"📁 {info['title'][:100]}{'...' if len(info['title']) > 100 else ''}\n"
                f"🎚️ Качество: {quality}\n\n"
                f"Что хотите сделать дальше?"
            )

            result_message = bot.send_message(
                chat_id,
                continuation_text,
                reply_markup=result_keyboard(),
                parse_mode="HTML"
            )

            # 5. ⭐ Сохраняем message_id НОВОГО сообщения для работы кнопок!
            self.set_user_state(chat_id, 'message_id', result_message.message_id)

        except Exception as e:
            downloader.cleanup_file(filepath)
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"❌ Ошибка отправки: {str(e)[:200]}",
                reply_markup=media_menu_keyboard(),
                parse_mode="HTML"
            )

    def _upload_tmpfiles(self, filepath: str) -> tuple:
        """Загрузка на tmpfiles.org"""
        try:
            print(f"📤 Загрузка на tmpfiles.org: {os.path.basename(filepath)}")

            with open(filepath, 'rb') as f:
                files = {'file': f}
                response = requests.post(
                    'https://tmpfiles.org/api/v1/upload',
                    files=files,
                    timeout=300
                )

            print(f"📥 Ответ tmpfiles: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print(f"✅ Данные ответа: {data}")

                if data.get('status') == 'success':
                    url = data['data']['url']
                    download_url = url.replace('/dl/', '/download/')
                    print(f"✅ Загружено на tmpfiles: {download_url}")
                    return True, download_url
                else:
                    error_msg = data.get('data', {}).get('error', 'Неизвестная ошибка')
                    print(f"❌ Ошибка tmpfiles: {error_msg}")
                    return False, f"Ошибка сервиса: {error_msg}"
            else:
                print(f"❌ HTTP ошибка: {response.status_code} - {response.text[:200]}")
                return False, f"HTTP {response.status_code}"

        except requests.exceptions.Timeout:
            print("❌ Превышено время ожидания tmpfiles")
            return False, "Превышено время ожидания"
        except requests.exceptions.RequestException as e:
            print(f"❌ Ошибка соединения с tmpfiles: {str(e)}")
            return False, f"Ошибка сети: {str(e)[:100]}"
        except Exception as e:
            print(f"❌ Неожиданная ошибка tmpfiles: {str(e)}")
            import traceback
            traceback.print_exc()
            return False, f"Ошибка: {str(e)[:100]}"

    def _log_download(self, user_id, url, mtype, platform, title, fpath, fsize, quality):
        try:
            conn = sqlite3.connect(config.DATABASE_PATH)
            conn.execute(
                f"INSERT INTO {TABLE_NAME} (user_id, url, media_type, platform, title, file_path, file_size, quality) VALUES (?,?,?,?,?,?,?,?)",
                (user_id, url, mtype, platform, title, str(fpath), fsize, quality))  # ✅ Преобразуем в строку
            conn.commit()
            conn.close()
        except:
            pass

    def _reset_state(self, chat_id):
        self.set_user_state(chat_id, 'media_type', None)
        self.set_user_state(chat_id, 'quality', None)
        self.set_user_state(chat_id, 'url', None)
        self.set_user_state(chat_id, 'pending_info', None)

    def on_load(self, bot: Any) -> None:
        print(f"📥 Media Downloader v{self.version} loaded")

    def on_unload(self, bot: Any) -> None:
        print(f"📥 Media Downloader unloaded")