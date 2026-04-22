import os
import time
import yt_dlp
from pathlib import Path
from typing import Optional, Dict, Tuple, Callable
from .config import TEMP_DIR, FFMPEG_PATH, VIDEO_QUALITIES, AUDIO_QUALITIES


class MediaDownloader:
    """Загрузчик медиа на основе yt-dlp"""

    def __init__(self):
        self.temp_dir = Path(TEMP_DIR)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def get_video_info(self, url: str) -> Optional[Dict]:
        """Получение информации о видео"""
        try:
            print(f"🔍 Получение информации о видео...")

            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'socket_timeout': 30,
                'retries': 3,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                if not info:
                    return None

                duration = info.get('duration', 0)
                if duration:
                    minutes = duration // 60
                    seconds = duration % 60
                    duration_str = f"{minutes}:{seconds:02d}"
                else:
                    duration_str = "Unknown"

                return {
                    'title': info.get('title', 'Unknown'),
                    'duration': duration,
                    'duration_str': duration_str,
                    'thumbnail': info.get('thumbnail'),
                    'platform': info.get('extractor', 'youtube'),
                    'platform_name': info.get('extractor_key', 'YouTube'),
                    'uploader': info.get('uploader', 'Unknown'),
                    'view_count': info.get('view_count', 0),
                    'url': url,
                    'id': info.get('id', ''),
                }

        except Exception as e:
            print(f"❌ Ошибка получения информации: {str(e)[:100]}")
            return None

    def download_video(self, url: str, quality: str = "720p",
                       progress_callback: Callable = None) -> Tuple[bool, str]:
        """Загрузка видео"""
        max_retries = 3

        for attempt in range(max_retries):
            try:
                print(f"\n📥 Загрузка видео (качество: {quality})... (попытка {attempt + 1}/{max_retries})")

                # Получаем формат из конфига
                format_str = VIDEO_QUALITIES.get(quality, VIDEO_QUALITIES["720p"])["format"]

                # Путь для сохранения
                filename = f"video_{int(time.time())}_%(id)s.%(ext)s"
                output_template = str(self.temp_dir / filename)

                def progress_hook(d):
                    if d['status'] == 'downloading':
                        total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                        downloaded = d.get('downloaded_bytes', 0)

                        if total and progress_callback:
                            percent = int((downloaded / total) * 100)
                            speed = d.get('_speed_str', 'N/A')
                            eta = d.get('_eta_str', 'N/A')
                            progress_callback(percent, f"{percent}% | {speed} | ETA: {eta}")

                    elif d['status'] == 'finished':
                        if progress_callback:
                            progress_callback(90, "Обработка видео...")

                ydl_opts = {
                    'format': format_str,
                    'outtmpl': output_template,
                    'progress_hooks': [progress_hook],
                    'quiet': True,
                    'no_warnings': True,
                    'ffmpeg_location': FFMPEG_PATH if os.path.exists(FFMPEG_PATH) else None,
                    'postprocessors': [{
                        'key': 'FFmpegVideoConvertor',
                        'preferedformat': 'mp4',
                    }],
                    'socket_timeout': 30,
                    'retries': 3,
                    'fragment_retries': 3,
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)

                    # Получаем путь к файлу
                    filepath = ydl.prepare_filename(info)

                    # Меняем расширение на mp4 если нужно
                    if not filepath.endswith('.mp4'):
                        filepath = Path(filepath).with_suffix('.mp4')

                    if filepath and os.path.exists(filepath):
                        file_size = os.path.getsize(filepath)
                        print(f"✅ Видео загружено: {os.path.basename(filepath)} ({file_size / 1024 / 1024:.1f}MB)")
                        return True, filepath
                    else:
                        return False, "Файл не создан после загрузки"

            except Exception as e:
                error_msg = str(e)
                print(f"❌ Ошибка (попытка {attempt + 1}): {error_msg[:100]}")

                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 5
                    print(f"⏰ Повторная попытка через {wait_time} сек...")
                    time.sleep(wait_time)
                else:
                    return False, f"Ошибка загрузки: {error_msg[:200]}"

        return False, "Не удалось загрузить видео"

    def download_audio(self, url: str, quality: str = "192",
                       progress_callback: Callable = None) -> Tuple[bool, str]:
        """Загрузка аудио (MP3)"""
        max_retries = 3

        for attempt in range(max_retries):
            try:
                print(f"\n🎵 Загрузка аудио (качество: {quality} kbps)... (попытка {attempt + 1}/{max_retries})")

                # Путь для сохранения
                filename = f"audio_{int(time.time())}_%(id)s.%(ext)s"
                output_template = str(self.temp_dir / filename)

                def progress_hook(d):
                    if d['status'] == 'downloading':
                        total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                        downloaded = d.get('downloaded_bytes', 0)

                        if total and progress_callback:
                            percent = int((downloaded / total) * 100)
                            speed = d.get('_speed_str', 'N/A')
                            eta = d.get('_eta_str', 'N/A')
                            progress_callback(percent, f"{percent}% | {speed} | ETA: {eta}")

                    elif d['status'] == 'finished':
                        if progress_callback:
                            progress_callback(90, "Конвертация в MP3...")

                ydl_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': output_template,
                    'progress_hooks': [progress_hook],
                    'quiet': True,
                    'no_warnings': True,
                    'ffmpeg_location': FFMPEG_PATH if os.path.exists(FFMPEG_PATH) else None,
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': quality,
                    }],
                    'socket_timeout': 30,
                    'retries': 3,
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)

                    # Получаем путь к файлу
                    filepath = ydl.prepare_filename(info)

                    # Меняем расширение на mp3
                    if not filepath.endswith('.mp3'):
                        filepath = Path(filepath).with_suffix('.mp3')

                    if filepath and os.path.exists(filepath):
                        file_size = os.path.getsize(filepath)
                        print(f"✅ Аудио загружено: {os.path.basename(filepath)} ({file_size / 1024 / 1024:.1f}MB)")
                        return True, filepath
                    else:
                        return False, "Файл не создан после загрузки"

            except Exception as e:
                error_msg = str(e)
                print(f"❌ Ошибка (попытка {attempt + 1}): {error_msg[:100]}")

                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 5
                    print(f"⏰ Повторная попытка через {wait_time} сек...")
                    time.sleep(wait_time)
                else:
                    return False, f"Ошибка загрузки: {error_msg[:200]}"

        return False, "Не удалось загрузить аудио"

    def cleanup_file(self, filepath: str):
        """Удаление файла"""
        try:
            if filepath and os.path.exists(filepath):
                os.remove(filepath)
                print(f"🗑️ Удалён файл: {os.path.basename(filepath)}")
        except Exception as e:
            print(f"⚠️ Ошибка удаления: {str(e)}")


#Глобальный
#экземпляр
downloader = MediaDownloader()