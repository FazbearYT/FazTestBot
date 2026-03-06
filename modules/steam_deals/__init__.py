# modules/steam_deals/__init__.py
# Модуль "Steam Deals Tracker" для FazTestBot

from core.module_base import BaseModule
from .handlers import SteamDealsModule

# Создание экземпляра модуля с соблюдением стандартов v3.5+
steam_deals_module = SteamDealsModule(
    module_id="steam_deals",
    name="Steam Deals Tracker",
    description="Отслеживание скидок на игры в Steam",
    icon="🎮",
    version="1.0.0",
    callback_prefix="steam_"
)

__all__ = ['steam_deals_module']