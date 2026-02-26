# modules/ip_lookup/api_client.py
# API клиент для сервисов IP Info
# Версия: 1.0.1
# Дата: 26.02.2026

import aiohttp
from typing import Optional, Dict, Tuple
from .config import IP_INFO_API_SERVICE, IPINFO_API_KEY


class IPLookupClient:
    """Клиент для получения информации об IP адресе"""

    def __init__(self):
        self.service = IP_INFO_API_SERVICE
        self.ipinfo_api_key = IPINFO_API_KEY

    def validate_ip(self, ip: str) -> Tuple[bool, str]:
        """
        Валидация IP адреса (только IPv4 и IPv6)
        """
        if not ip or not ip.strip():
            return False, "❌ Запрос не может быть пустым"

        ip = ip.strip()

        # Проверка на IPv4
        import re
        ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        if re.match(ipv4_pattern, ip):
            # Проверка диапазонов октетов
            octets = ip.split('.')
            for octet in octets:
                if int(octet) > 255:
                    return False, "❌ Неверный IPv4 адрес"
            return True, ip

        # Проверка на IPv6 (упрощённая)
        ipv6_pattern = r'^([0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}$'
        if re.match(ipv6_pattern, ip):
            return True, ip

        return False, "❌ Неверный формат IP адреса. Поддерживаются только IPv4 и IPv6"

    async def get_ip_info(self, ip: str) -> Tuple[bool, Dict]:
        """
        Получение информации об IP
        """
        # Валидация
        is_valid, result = self.validate_ip(ip)
        if not is_valid:
            return False, {"error": result}

        ip = result

        # Выбор сервиса
        if self.service == "ipinfo" and self.ipinfo_api_key:
            return await self._get_info_ipinfo(ip)
        else:
            return await self._get_info_ipapi(ip)

    async def _get_info_ipapi(self, ip: str) -> Tuple[bool, Dict]:
        """Получение информации через ipapi.co (бесплатно, без ключа)"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        f"https://ipapi.co/{ip}/json/",
                        timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()

                        if data.get('error'):
                            return False, {"error": data.get('reason', 'Неизвестная ошибка')}

                        return True, {
                            "ip": data.get('ip', ip),
                            "city": data.get('city', 'Unknown'),
                            "region": data.get('region', 'Unknown'),
                            "country": data.get('country_name', 'Unknown'),
                            "country_code": data.get('country_code', 'Unknown'),
                            "isp": data.get('org', 'Unknown'),
                            "timezone": data.get('timezone', 'Unknown'),
                            "latitude": data.get('latitude', 'Unknown'),
                            "longitude": data.get('longitude', 'Unknown'),
                            "postal": data.get('postal', 'Unknown'),
                            "asn": data.get('asn', 'Unknown'),
                            "source": "ipapi.co"
                        }
                    elif response.status == 429:
                        return False, {"error": "❌ Превышен лимит запросов API (429). Подождите несколько минут."}
                    else:
                        return False, {"error": f"Ошибка API: статус {response.status}"}
        except asyncio.TimeoutError:
            return False, {"error": "❌ Таймаут: сервис не отвечает"}
        except Exception as e:
            return False, {"error": f"❌ Ошибка: {str(e)}"}

    async def _get_info_ipinfo(self, ip: str) -> Tuple[bool, Dict]:
        """Получение информации через ipinfo.io (требует API ключ)"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        f"https://ipinfo.io/{ip}/json?token={self.ipinfo_api_key}",
                        timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()

                        return True, {
                            "ip": data.get('ip', ip),
                            "city": data.get('city', 'Unknown'),
                            "region": data.get('region', 'Unknown'),
                            "country": data.get('country', 'Unknown'),
                            "country_code": data.get('country', 'Unknown'),
                            "isp": data.get('org', 'Unknown'),
                            "timezone": data.get('timezone', 'Unknown'),
                            "latitude": data.get('loc', '').split(',')[0] if data.get('loc') else 'Unknown',
                            "longitude": data.get('loc', '').split(',')[1] if data.get('loc') else 'Unknown',
                            "postal": data.get('postal', 'Unknown'),
                            "asn": data.get('asn', 'Unknown'),
                            "source": "ipinfo.io"
                        }
                    elif response.status == 429:
                        return False, {"error": "❌ Превышен лимит запросов API (429). Подождите несколько минут."}
                    else:
                        return False, {"error": f"Ошибка API: статус {response.status}"}
        except asyncio.TimeoutError:
            return False, {"error": "❌ Таймаут: сервис не отвечает"}
        except Exception as e:
            return False, {"error": f"❌ Ошибка: {str(e)}"}


# Глобальный экземпляр клиента
ip_client = IPLookupClient()