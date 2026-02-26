# modules/ip_lookup/__init__.py
# Модуль "IP Info Lookup" для FazTestBot
# Версия: 1.0.1
# Дата: 26.02.2026

from core.module_base import BaseModule
from .handlers import IPLookupModule

# Создание экземпляра модуля с соблюдением стандартов v3.5+
ip_lookup_module = IPLookupModule(
    module_id="ip_lookup",
    name="IP Info Lookup",
    description="Информация об IP адресе (страна, город, ISP)",
    icon="🌍",
    version="1.0.3",
    callback_prefix="ip_"
)

__all__ = ['ip_lookup_module']