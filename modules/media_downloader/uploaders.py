import requests
import os
from typing import Tuple, Optional


class FileUploader:
    """Загрузка файлов на различные файлообменники"""

    @staticmethod
    def upload_to_tmpfiles(filepath: str) -> Tuple[bool, str]:
        """
        Загрузка на tmpfiles.org
        :return: (success, download_url or error_message)
        """
        try:
            with open(filepath, 'rb') as f:
                files = {'file': f}
                response = requests.post(
                    'https://tmpfiles.org/api/v1/upload',
                    files=files,
                    timeout=300
                )

            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    # Заменяем /dl/ на /download/ для прямой ссылки
                    url = data['data']['url']
                    download_url = url.replace('/dl/', '/download/')
                    return True, download_url

            return False, f"Ошибка API: {response.status_code}"

        except requests.exceptions.RequestException as e:
            return False, f"Ошибка загрузки: {str(e)}"
        except Exception as e:
            return False, f"Неизвестная ошибка: {str(e)}"

    @staticmethod
    def upload_to_gofile(filepath: str) -> Tuple[bool, str]:
        """
        Загрузка на gofile.io
        :return: (success, download_url or error_message)
        """
        try:
            # Сначала получаем токен сервера
            server_res = requests.get('https://api.gofile.io/getServer').json()
            if server_res['status'] != 'ok':
                return False, "Не удалось получить сервер"

            server = server_res['data']['server']

            # Загружаем файл
            with open(filepath, 'rb') as f:
                files = {'file': f}
                response = requests.post(
                    f'https://{server}.gofile.io/uploadFile',
                    files=files,
                    timeout=300
                )

            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'ok':
                    download_url = f"https://gofile.io/d/{data['data']['code']}"
                    return True, download_url

            return False, f"Ошибка API: {response.status_code}"

        except Exception as e:
            return False, f"Ошибка загрузки: {str(e)}"

    @staticmethod
    def upload_to_fileio(filepath: str) -> Tuple[bool, str]:
        """
        Загрузка на file.io (файл удаляется после 1 скачивания)
        :return: (success, download_url or error_message)
        """
        try:
            with open(filepath, 'rb') as f:
                response = requests.post(
                    'https://file.io',
                    files={'file': f},
                    timeout=300
                )

            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    return True, data['link']

            return False, f"Ошибка API: {response.status_code}"

        except Exception as e:
            return False, f"Ошибка загрузки: {str(e)}"


# Глобальный экземпляр
uploader = FileUploader()