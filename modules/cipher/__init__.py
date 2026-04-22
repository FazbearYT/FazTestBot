# modules/cipher/__init__.py
# Модуль "Шифратор" для FazTestBot
# Версия: 3.5 (адаптирован под BaseModule)

from core.module_base import BaseModule
from .handlers import CipherModule

# Создание экземпляра модуля с соблюдением стандартов v3.5
cipher_module = CipherModule(
    module_id="cipher",
    name="Шифратор",
    description="Шифрование текста: Морзе, числовой, Цезарь, QR-код",
    icon="🔐",
    version="2.7.2",  # Наследует версию от v2.6 + интеграция Leet
    callback_prefix="cipher_"
)

__all__ = ['cipher_module']