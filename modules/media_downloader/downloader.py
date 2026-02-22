# modules/media_downloader/downloader.py
# Загрузчик медиа через yt-dlp
# Версия: 1.0.0
# Дата: 22.02.2026

import yt_dlp
import os
from typing import Optional, Dict, Tuple
from pathlib import Path
from .config import DOWNLOADS_DIR, DEFAULT_VIDEO_QUALITY, DEFAULT_AUDIO_QUALITY


class MediaDownloader:
    """Загрузчик медиа из соцсетей через yt-dlp"""

    def __init__(self, temp_dir: str = None):
        self.temp_dir = Path(temp_dir or DOWNLOADS_DIR)
        self.temp_dir.mkdir(exist_ok=True)

    def get_video_info(self, url: str) -> Optional[Dict]:
        """
        Получение информации о видео без загрузки

        :param url: URL видео
        :return: Информация о видео или None
        """
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'skip_download': True
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                # Определяем платформу
                platform = self._detect_platform(url)

                return {
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'thumbnail': info.get('thumbnail', ''),
                    'platform': platform,
                    'platform_name': self._get_platform_name(platform),
                    'uploader': info.get('uploader', 'Unknown'),
                    'view_count': info.get('view_count', 0),
                    'formats': self._get_available_formats(info)
                }
        except Exception as e:
            print(f"❌ Ошибка получения информации: {str(e)}")
            return None

    def download_video(self, url: str, quality: str = "720p") -> Tuple[bool, str]:
        """
        Загрузка видео

        :param url: URL видео
        :param quality: Желаемое качество (360p, 480p, 720p, 1080p)
        :return: (success: bool, filepath: str)
        """
        filename = self._generate_filename(url, "video")

        # Преобразуем качество в формат yt-dlp
        quality_map = {
            "360p": "360",
            "480p": "480",
            "720p": "720",
            "1080p": "1080"
        }
        height = quality_map.get(quality, "720")

        ydl_opts = {
            'format': f'bestvideo[height<={height}]+bestaudio/best[height<={height}]/best',
            'outtmpl': str(filename),
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'merge_output_format': 'mp4'
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # Проверяем существование файла
            if filename.exists():
                return True, str(filename)

            # Проверяем с другими расширениями
            for ext in ['.mp4', '.mkv', '.webm']:
                test_file = Path(str(filename) + ext)
                if test_file.exists():
                    return True, str(test_file)

            return False, ""

        except Exception as e:
            print(f"❌ Ошибка загрузки видео: {str(e)}")
            return False, ""

    def download_audio(self, url: str, quality: str = "192") -> Tuple[bool, str]:
        """
        Загрузка только аудио (mp3)

        :param url: URL видео
        :param quality: Качество аудио (128, 192, 320 kbps)
        :return: (success: bool, filepath: str)
        """
        filename = self._generate_filename(url, "audio")

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': str(filename),
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': quality
            }]
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # Проверяем существование файла
            if filename.exists():
                return True, str(filename)

            # Проверяем с расширением mp3
            mp3_file = Path(str(filename) + '.mp3')
            if mp3_file.exists():
                return True, str(mp3_file)

            return False, ""

        except Exception as e:
            print(f"❌ Ошибка загрузки аудио: {str(e)}")
            return False, ""

    def cleanup_file(self, filepath: str):
        """Удаление временного файла"""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                print(f"🗑️ Удалён временный файл: {filepath}")
        except Exception as e:
            print(f"⚠️ Ошибка удаления файла: {str(e)}")

    def _generate_filename(self, url: str, media_type: str) -> Path:
        """Генерация уникального имени файла"""
        import hashlib
        import time

        # Создаём хэш из URL и времени
        hash_input = f"{url}_{time.time()}"
        hash_value = hashlib.md5(hash_input.encode()).hexdigest()[:10]

        ext = ".mp4" if media_type == "video" else ".mp3"
        filename = f"media_{media_type}_{hash_value}{ext}"

        return self.temp_dir / filename

    def _detect_platform(self, url: str) -> str:
        """Определение платформы по URL"""
        url_lower = url.lower()

        if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
            return 'youtube'
        elif 'tiktok.com' in url_lower:
            return 'tiktok'
        elif 'instagram.com' in url_lower:
            return 'instagram'
        elif 'twitter.com' in url_lower or 'x.com' in url_lower:
            return 'twitter'
        elif 'facebook.com' in url_lower or 'fb.watch' in url_lower:
            return 'facebook'
        elif 'vimeo.com' in url_lower:
            return 'vimeo'
        else:
            return 'unknown'

    def _get_platform_name(self, platform: str) -> str:
        """Получение названия платформы"""
        platforms = {
            'youtube': 'YouTube',
            'tiktok': 'TikTok',
            'instagram': 'Instagram',
            'twitter': 'Twitter/X',
            'facebook': 'Facebook',
            'vimeo': 'Vimeo',
            'unknown': 'Unknown'
        }
        return platforms.get(platform, 'Unknown')

    def _get_available_formats(self, info: dict) -> list:
        """Получение доступных форматов"""
        formats = []
        seen_heights = set()

        for f in info.get('formats', []):
            height = f.get('height')
            if height and height not in seen_heights and f.get('vcodec') != 'none':
                formats.append({
                    'format_id': f.get('format_id'),
                    'height': height,
                    'resolution': f.get('resolution', f'{height}p'),
                    'filesize': f.get('filesize')
                })
                seen_heights.add(height)

        # Сортируем по высоте
        formats.sort(key=lambda x: x['height'], reverse=True)
        return formats[:10]  # Возвращаем первые 10 форматов


# Глобальный экземпляр загрузчика
downloader = MediaDownloader()