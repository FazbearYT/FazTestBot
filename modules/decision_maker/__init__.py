# modules/decision_maker/__init__.py
# Модуль "Decision Maker" для FazTestBot

from core.module_base import BaseModule
from .handlers import DecisionMakerModule

# Создание экземпляра модуля с соблюдением стандартов v3.5+
decision_maker_module = DecisionMakerModule(
    module_id="decision_maker",
    name="Decision Maker",
    description="Генератор случайных чисел, монетка, Dota 2 герои",
    icon="🎲",
    version="1.0.4",
    callback_prefix="dm_"
)

__all__ = ['decision_maker_module']