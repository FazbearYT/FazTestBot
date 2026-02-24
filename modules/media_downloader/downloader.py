# modules/media_downloader/downloader.py
# Загрузчик медиа на основе pytubefix
# Версия: 4.1.1
# Дата: 22.02.2026

import os
import time
import hashlib
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
        """Загрузка видео"""
        try:
            from pytubefix import YouTube

            print(f"\n📥 Загрузка видео (качество: {quality})...")

            yt = YouTube(url)

            # Парсим качество
            quality_map = {
                "360p": 360,
                "480p": 480,
                "720p": 720,
                "1080p": 1080
            }
            max_height = quality_map.get(quality, 360)

            print(f"🔍 Ищем качество до {max_height}p...")

            # Получаем все прогрессивные потоки (видео+аудио вместе)
            progressive_streams = yt.streams.filter(
                progressive=True,
                file_extension='mp4'
            )

            if not progressive_streams:
                print("❌ Не найдено прогрессивных потоков")
                return False, "Не найдено подходящих видео потоков"

            # Выводим доступные качества
            print("📋 Доступные качества:")
            available_streams = []
            for stream in progressive_streams:
                if stream.resolution:
                    height = int(stream.resolution.replace('p', ''))
                    available_streams.append((height, stream))
                    print(f"  - {stream.resolution} ({stream.filesize / 1024 / 1024:.1f}MB)")

            # Сортируем по убыванию
            available_streams.sort(reverse=True)

            # Выбираем ЛУЧШИЙ поток с качеством <= запрошенному
            selected_stream = None
            for height, stream in available_streams:
                if height <= max_height:
                    selected_stream = stream
                    print(f"✅ Выбрано качество: {stream.resolution}")
                    break

            # Если не нашли, берем САМОЕ НИЗКОЕ доступное
            if not selected_stream:
                selected_stream = available_streams[-1][1] if available_streams else None
                print(f"⚠️ Используется доступное качество: {selected_stream.resolution if selected_stream else 'N/A'}")

            if not selected_stream:
                return False, "Не найдено подходящих видео потоков"

            print(f"🎬 {yt.title[:50]}...")

            # Генерируем имя файла
            filename = self._generate_filename(url, "video", ".mp4")

            # Скачиваем
            print(f"💾 Скачивание...")
            filepath = selected_stream.download(
                output_path=str(self.temp_dir),
                filename=filename.name
            )

            if filepath and os.path.exists(filepath):
                file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
                print(f"✅ Загружено: {os.path.basename(filepath)} ({file_size_mb:.1f}MB)")
                return True, filepath
            else:
                print("❌ Файл не создан")
                return False, "Файл не создан"

        except Exception as e:
            print(f"❌ Ошибка: {str(e)[:100]}")
            return False, f"Ошибка: {str(e)}"

    def download_audio(self, url: str, quality: str = "128") -> Tuple[bool, str]:
        """Загрузка аудио"""
        try:
            from pytubefix import YouTube

            print(f"🎵 Загрузка аудио (качество: {quality} kbps)...")

            yt = YouTube(url)

            # Получаем аудио поток
            stream = yt.streams.filter(
                only_audio=True,
                file_extension='mp4'
            ).order_by('abr').desc().first()

            if not stream:
                return False, "Не найдено аудио потоков"

            print(f"🎵 {yt.title[:50]}...")

            # Генерируем имя файла
            filename = self._generate_filename(url, "audio", ".mp3")

            # Скачиваем
            filepath = stream.download(
                output_path=str(self.temp_dir),
                filename=filename.name.replace('.mp3', '.mp4')
            )

            if filepath and os.path.exists(filepath):
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
                return False, "Файл не создан"

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