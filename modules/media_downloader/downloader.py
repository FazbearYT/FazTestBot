import os
import time
import yt_dlp
from pathlib import Path
from typing import Optional, Dict, Tuple, Callable
from .config import (
    MODULE_TEMP_DIR,
    FFMPEG_PATH,
    VIDEO_QUALITIES,
    AUDIO_QUALITIES,
    MAX_RETRIES
)


class MediaDownloader:
    """Ядро загрузки на основе yt-dlp"""

    def __init__(self):
        self.temp_dir = Path(MODULE_TEMP_DIR)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def get_video_info(self, url: str) -> Optional[Dict]:
        """Получение метаданных без скачивания"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'socket_timeout': 30,
                'retries': 3,
                'ffmpeg_location': str(FFMPEG_PATH) if FFMPEG_PATH.exists() else None,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            if not info:
                return None

            duration = info.get('duration', 0)
            duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "00:00"

            return {
                'title': info.get('title', 'Unknown'),
                'duration': duration,
                'duration_str': duration_str,
                'thumbnail': info.get('thumbnail'),
                'platform': info.get('extractor_key', 'Unknown'),
                'uploader': info.get('uploader', 'Unknown'),
                'filesize': info.get('filesize'),
                'filesize_approx': info.get('filesize_approx'),
                'url': url,
                'id': info.get('id', '')
            }
        except Exception as e:
            print(f"❌ Info error: {str(e)[:100]}")
            return None

    def download_video(self, url: str, quality: str = "720p",
                       progress_callback: Callable = None) -> Tuple[bool, str]:
        """Скачивание видео с конвертацией в MP4"""
        format_str = VIDEO_QUALITIES.get(quality, VIDEO_QUALITIES["720p"])["format"]
        return self._download(url, format_str, "video", progress_callback)

    def download_audio(self, url: str, quality: str = "192",
                       progress_callback: Callable = None) -> Tuple[bool, str]:
        """Скачивание аудио с конвертацией в MP3"""
        format_str = "bestaudio/best"
        return self._download(url, format_str, "audio", progress_callback, audio_quality=quality)

    def _download(self, url: str, format_str: str, media_type: str,
                  progress_callback: Callable, audio_quality: str = None) -> Tuple[bool, str]:
        """Универсальная логика скачивания"""
        max_retries = MAX_RETRIES

        for attempt in range(max_retries):
            try:
                filename = f"{media_type}_{int(time.time())}_%(id)s.%(ext)s"
                output_template = str(self.temp_dir / filename)

                def hook(d):
                    if d['status'] == 'downloading':
                        total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                        downloaded = d.get('downloaded_bytes', 0)
                        if total and progress_callback:
                            pct = int((downloaded / total) * 100)
                            spd = d.get('_speed_str', 'N/A')
                            eta = d.get('_eta_str', 'N/A')
                            progress_callback(pct, f"{pct}% | {spd} | ETA: {eta}")
                    elif d['status'] == 'finished':
                        if progress_callback:
                            progress_callback(95, "Финализация файла...")

                ydl_opts = {
                    'format': format_str,
                    'outtmpl': output_template,
                    'progress_hooks': [hook],
                    'quiet': True,
                    'no_warnings': True,
                    'ffmpeg_location': str(FFMPEG_PATH) if FFMPEG_PATH.exists() else None,
                    'socket_timeout': 30,
                    'retries': 3,
                    'fragment_retries': 3,
                }

                # Постпроцессоры в зависимости от типа
                if media_type == "video":
                    ydl_opts['postprocessors'] = [{
                        'key': 'FFmpegVideoConvertor',
                        'preferedformat': 'mp4',
                    }]
                else:
                    ydl_opts['postprocessors'] = [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': audio_quality or '192',
                    }]

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filepath = ydl.prepare_filename(info)

                    # Корректировка расширения
                    if media_type == "video" and not filepath.endswith('.mp4'):
                        filepath = Path(filepath).with_suffix('.mp4')
                    elif media_type == "audio" and not filepath.endswith('.mp3'):
                        filepath = Path(filepath).with_suffix('.mp3')

                    if filepath and os.path.exists(filepath):
                        return True, filepath
                    return False, "Файл не создан после загрузки"

            except Exception as e:
                error_msg = str(e)
                print(f"❌ Download error (attempt {attempt + 1}): {error_msg[:100]}")

                if attempt < max_retries - 1:
                    time.sleep((attempt + 1) * 3)
                else:
                    return False, f"Ошибка загрузки: {error_msg[:200]}"

        return False, "Не удалось загрузить"

    def cleanup_file(self, filepath: str):
        """Безопасное удаление файла"""
        try:
            if filepath and os.path.exists(filepath):
                os.remove(filepath)
        except Exception:
            pass


# Глобальный экземпляр
downloader = MediaDownloader()