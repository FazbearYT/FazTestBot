# modules/url_shortener/api_client.py
# API клиент для сервисов сокращения ссылок
# Версия: 1.0.0
# Дата: 25.02.2026

import aiohttp
from typing import Optional, Dict, Tuple
from .config import URL_SHORTENER_SERVICE, CUTTLY_API_KEY, DEFAULT_PROTOCOL


class URLShortenerClient:
    """Клиент для сокращения ссылок через различные API"""

    def __init__(self):
        self.service = URL_SHORTENER_SERVICE
        self.cuttly_api_key = CUTTLY_API_KEY

    def validate_url(self, url: str) -> Tuple[bool, str]:
        """
        Валидация URL перед сокращением.

        :param url: Исходная ссылка
        :return: (is_valid: bool, error_message: str)
        """
        if not url or not url.strip():
            return False, "❌ Ссылка не может быть пустой"

        url = url.strip()

        # Проверка длины
        if len(url) > 2048:
            return False, "❌ Ссылка слишком длинная (макс. 2048 символов)"

        # Добавляем протокол если отсутствует
        has_protocol = any(url.startswith(p) for p in ["http://", "https://"])
        if not has_protocol:
            url = DEFAULT_PROTOCOL + url

        # Проверка формата
        if not url.startswith("http://") and not url.startswith("https://"):
            return False, "❌ Неверный формат ссылки (должен начинаться с http:// или https://)"

        return True, url

    async def shorten_url(self, url: str) -> Tuple[bool, str]:
        """
        Сокращение ссылки через выбранный API.

        :param url: Исходная ссылка
        :return: (success: bool, result: str)
        """
        # Валидация
        is_valid, result = self.validate_url(url)
        if not is_valid:
            return False, result

        url = result

        # Выбор сервиса
        if self.service == "cuttly" and self.cuttly_api_key:
            return await self._shorten_with_cuttly(url)
        else:
            return await self._shorten_with_tinyurl(url)

    async def _shorten_with_tinyurl(self, url: str) -> Tuple[bool, str]:
        """Сокращение через TinyURL API"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        f"http://tinyurl.com/api-create.php?url={url}",
                        timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        shortened_url = await response.text()
                        if shortened_url and shortened_url.startswith("http"):
                            return True, shortened_url
                        else:
                            return False, "❌ Ошибка: получен некорректный ответ от TinyURL"
                    else:
                        return False, f"❌ Ошибка TinyURL: статус {response.status}"
        except asyncio.TimeoutError:
            return False, "❌ Таймаут: TinyURL не отвечает"
        except Exception as e:
            return False, f"❌ Ошибка: {str(e)}"

    async def _shorten_with_cuttly(self, url: str) -> Tuple[bool, str]:
        """Сокращение через Cutt.ly API"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        f"https://cutt.ly/api/api.php?key={self.cuttly_api_key}&short={url}",
                        timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("url", {}).get("status") == 7:
                            shortened_url = data.get("url", {}).get("shortLink", "")
                            if shortened_url:
                                return True, shortened_url
                            else:
                                return False, "❌ Ошибка: пустая ссылка от Cutt.ly"
                        else:
                            status_codes = {
                                0: "Плохая ссылка",
                                1: "Неправильный API ключ",
                                2: "Ссылка уже сокращена",
                                3: "Публичная ссылка",
                                4: "Слишком длинная ссылка",
                                5: "Неправильный формат ссылки",
                                6: "Ссылка не найдена",
                                7: "Успешно"
                            }
                            status = data.get("url", {}).get("status", -1)
                            return False, f"❌ Ошибка Cutt.ly: {status_codes.get(status, 'Неизвестная ошибка')}"
                    else:
                        return False, f"❌ Ошибка Cutt.ly: статус {response.status}"
        except asyncio.TimeoutError:
            return False, "❌ Таймаут: Cutt.ly не отвечает"
        except Exception as e:
            return False, f"❌ Ошибка: {str(e)}"


# Глобальный экземпляр клиента
url_client = URLShortenerClient()