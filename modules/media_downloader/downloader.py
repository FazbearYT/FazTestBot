# modules/media_downloader/downloader.py
# Загрузчик медиа на основе pytubefix с обработкой ошибок
# Версия: 4.1.1
# Дата: 22.02.2026

import os
import time
import hashlib
import subprocess
from pathlib import Path
from typing import Optional, Dict, Tuple
from .config import DOWNLOADS_DIR


class MediaDownloader:
    """Загрузчик медиа с pytubefix для YouTube"""

    def __init__(self, temp_dir: str = None):
        self.temp_dir = Path(temp_dir or DOWNLOADS_DIR)
        self.temp_dir.mkdir(exist_ok=True)

    def get_video_info(self, url: str) -> Optional[Dict]:
        """Получение информации о видео"""
        try:
            from pytubefix import YouTube

            print(f"🔍 Получение информации о видео...")
            yt = YouTube(url)

            duration = yt.length
            if duration:
                minutes = duration // 60
                seconds = duration % 60
                duration_str = f"{minutes}:{seconds:02d}"
            else:
                duration_str = "Unknown"

            return {
                'title': yt.title,
                'duration': duration,
                'duration_str': duration_str,
                'thumbnail': yt.thumbnail_url,
                'platform': 'youtube',
                'platform_name': 'YouTube',
                'uploader': yt.author,
                'view_count': yt.views,
                'url': url
            }
        except Exception as e:
            print(f"❌ Ошибка получения информации: {str(e)[:100]}")
            return None

    def download_video(self, url: str, quality: str = "360p") -> Tuple[bool, str]:
        """Загрузка видео с повторными попытками"""
        max_retries = 3

        for attempt in range(max_retries):
            try:
                print(f"\n📥 Загрузка видео (качество: {quality})... (попытка {attempt + 1}/{max_retries})")

                from pytubefix import YouTube

                # Создаем YouTube объект
                yt = YouTube(
                    url,
                    on_progress_callback=lambda chunk, remaining: self._on_progress(chunk, remaining)
                )

                # Парсим качество
                quality_map = {
                    "360p": 360,
                    "480p": 480,
                    "720p": 720,
                    "1080p": 1080
                }
                target_height = quality_map.get(quality, 360)

                print(f"🔍 Ищем качество до {target_height}p...")

                # Используем adaptive streams
                return self._download_adaptive_video(yt, target_height)

            except Exception as e:
                error_msg = str(e)
                print(f"❌ Ошибка (попытка {attempt + 1}): {error_msg[:100]}")

                if "Maximum number of retries exceeded" in error_msg:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 10
                        print(f"⏰ Превышено количество повторных попыток загрузки. Ждём {wait_time} сек...")
                        time.sleep(wait_time)
                        continue
                    else:
                        print("❌ Все попытки исчерпаны. Попробуйте другое видео или позже.")
                        return False, "Превышено количество попыток загрузки. YouTube может блокировать запросы."
                elif attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 5
                    print(f"⏰ Повторная попытка через {wait_time} сек...")
                    time.sleep(wait_time)
                else:
                    return False, f"Ошибка загрузки: {error_msg[:200]}"

        return False, "Не удалось загрузить видео"

    def _on_progress(self, chunk, remaining):
        """Callback для отображения прогресса"""
        try:
            if remaining and remaining > 0:
                # Процент загрузки
                pass  # Можно добавить вывод прогресса
        except:
            pass

    def _download_stream_with_retry(self, stream, output_path: str, filename: str, stream_type: str) -> Tuple[
        bool, str]:
        """Скачивание стрима с повторными попытками"""
        max_retries = 3

        for attempt in range(max_retries):
            try:
                print(f"💾 Скачивание {stream_type}... (попытка {attempt + 1}/{max_retries})")

                filepath = stream.download(
                    output_path=output_path,
                    filename=filename
                )

                if filepath and os.path.exists(filepath):
                    file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
                    print(f"✅ {stream_type} загружен: {os.path.basename(filepath)} ({file_size_mb:.1f}MB)")
                    return True, filepath
                else:
                    raise Exception("Файл не создан после скачивания")

            except Exception as e:
                print(f"❌ Ошибка скачивания {stream_type} (попытка {attempt + 1}): {str(e)[:100]}")

                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 5
                    print(f"⏰ Повторная попытка через {wait_time} сек...")
                    time.sleep(wait_time)
                else:
                    return False, f"Ошибка скачивания {stream_type}: {str(e)}"

        return False, f"Не удалось скачать {stream_type}"

    def _download_adaptive_video(self, yt, target_height: int) -> Tuple[bool, str]:
        """Скачивание adaptive video + audio с повторными попытками"""
        try:
            print("📹 Поиск video stream...")
            video_stream = yt.streams.filter(
                type='video',
                file_extension='mp4',
                progressive=False
            ).order_by('resolution').desc().first()

            print("🎵 Поиск audio stream...")
            audio_stream = yt.streams.filter(
                type='audio',
                mime_type='audio/mp4',
                progressive=False
            ).order_by('abr').desc().first()

            if not video_stream:
                print("❌ Не найден video stream")
                return False, "Не найден видео поток"

            if not audio_stream:
                print("❌ Не найден audio stream")
                return False, "Не найден аудио поток"

            video_height = int(video_stream.resolution.replace('p', '')) if video_stream.resolution else 0

            print(f"✅ Найдено:")
            print(f"   📹 Видео: {video_stream.resolution} ({video_stream.filesize / 1024 / 1024:.1f}MB)")
            print(f"   🎵 Аудио: {audio_stream.abr}kbps ({audio_stream.filesize / 1024 / 1024:.1f}MB)")

            # Проверяем что качество видео <= запрошенному
            if video_height > target_height:
                print(f"⚠️ Доступное качество {video_height}p выше запрошенного {target_height}p")
                video_stream = yt.streams.filter(
                    type='video',
                    file_extension='mp4',
                    progressive=False
                ).order_by('resolution').asc().first()

                if video_stream:
                    video_height = int(video_stream.resolution.replace('p', '')) if video_stream.resolution else 0
                    print(f"   Выбрано: {video_stream.resolution}")

            # Генерируем имена файлов
            video_filename = self._generate_filename(yt.watch_url, "video", ".mp4")
            audio_filename = self._generate_filename(yt.watch_url, "audio", ".m4a")

            # Скачиваем видео с повторными попытками
            success, video_path = self._download_stream_with_retry(
                video_stream,
                str(self.temp_dir),
                video_filename.name,
                "видео"
            )

            if not success:
                return False, video_path

            # Скачиваем аудио с повторными попытками
            success, audio_path = self._download_stream_with_retry(
                audio_stream,
                str(self.temp_dir),
                audio_filename.name,
                "аудио"
            )

            if not success:
                # Удаляем видео если аудио не скачалось
                if os.path.exists(video_path):
                    os.remove(video_path)
                return False, audio_path

            # Объединяем через ffmpeg
            output_filename = self._generate_filename(yt.watch_url, "video", ".mp4")
            output_path = str(output_filename)

            print(f"\n🔧 Объединение видео и аудио через ffmpeg...")

            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-i', audio_path,
                '-c', 'copy',
                '-map', '0:v:0',
                '-map', '1:a:0',
                '-shortest',
                '-y',
                output_path
            ]

            try:
                result = subprocess.run(cmd, check=True, capture_output=True, text=True)

                # Удаляем временные файлы
                os.remove(video_path)
                os.remove(audio_path)

                file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
                print(f"✅ Загружено: {os.path.basename(output_path)} ({file_size_mb:.1f}MB)")
                return True, output_path

            except subprocess.CalledProcessError as e:
                print(f"❌ Ошибка ffmpeg: {e}")
                print(f"stderr: {e.stderr}")
                # Удаляем файлы
                if os.path.exists(video_path):
                    os.remove(video_path)
                if os.path.exists(audio_path):
                    os.remove(audio_path)
                return False, f"Ошибка ffmpeg: {e}"

        except Exception as e:
            print(f"❌ Ошибка adaptive загрузки: {str(e)[:100]}")
            import traceback
            traceback.print_exc()
            return False, f"Ошибка: {str(e)}"

    def download_audio(self, url: str, quality: str = "128") -> Tuple[bool, str]:
        """Загрузка аудио"""
        try:
            from pytubefix import YouTube

            print(f"🎵 Загрузка аудио (качество: {quality} kbps)...")

            yt = YouTube(url)

            stream = yt.streams.filter(
                only_audio=True,
                file_extension='mp4'
            ).order_by('abr').desc().first()

            if not stream:
                return False, "Не найдено аудио потоков"

            print(f"🎵 {yt.title[:50]}...")

            filename = self._generate_filename(url, "audio", ".mp3")

            # Скачиваем с повторными попытками
            success, filepath = self._download_stream_with_retry(
                stream,
                str(self.temp_dir),
                filename.name.replace('.mp3', '.mp4'),
                "аудио"
            )

            if success and filepath and os.path.exists(filepath):
                # Переименовываем в mp3
                mp3_path = Path(filepath).with_suffix('.mp3')
                try:
                    os.rename(filepath, mp3_path)
                    print(f"✅ Загружено: {mp3_path.name}")
                    return True, str(mp3_path)
                except:
                    print(f"✅ Загружено: {os.path.basename(filepath)}")
                    return True, filepath
            else:
                return False, filepath

        except Exception as e:
            print(f"❌ Ошибка: {str(e)[:100]}")
            return False, f"Ошибка: {str(e)}"

    def cleanup_file(self, filepath: str):
        """Удаление файла"""
        try:
            if filepath and os.path.exists(filepath):
                os.remove(filepath)
                print(f"🗑️ Удалён файл: {os.path.basename(filepath)}")
        except Exception as e:
            print(f"⚠️ Ошибка удаления: {str(e)}")

    def _generate_filename(self, url: str, media_type: str, ext: str) -> Path:
        """Генерация имени файла"""
        hash_input = f"{url}_{time.time()}_{os.getpid()}"
        hash_value = hashlib.md5(hash_input.encode()).hexdigest()[:10]
        filename = f"media_{media_type}_{hash_value}{ext}"
        return self.temp_dir / filename


# Глобальный экземпляр
downloader = MediaDownloader()