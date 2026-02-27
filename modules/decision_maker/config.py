# modules/decision_maker/config.py
# Конфигурация модуля "Decision Maker"

# ====== ЛИМИТЫ ======
MAX_RANDOM_RANGE = 1000000  # Максимальный диапазон для генератора чисел
MAX_LIST_ITEMS = 100  # Максимальное количество элементов в списке
MAX_DAILY_USES = 100  # Лимит использований в день на пользователя

# ====== ТАБЛИЦА В БД ======
TABLE_NAME = "decision_maker_logs"

# ====== НАСТРОЙКИ МОНЕТКИ ======
COIN_SIDES = ["Орёл", "Решка"]

# ====== НАСТРОЙКИ ГЕНЕРАТОРА ЧИСЕЛ ======
DEFAULT_MIN = 1
DEFAULT_MAX = 100