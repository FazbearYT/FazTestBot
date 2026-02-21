# core/easter_eggs.py
# Логика пасхалок и секретных функций
# Дата обновления: 18.02.2026

from datetime import datetime, timedelta
from typing import Optional, Dict
import os


class EasterEggManager:
    """Менеджер пасхалок и головоломок"""

    def __init__(self, db_manager):
        self.db = db_manager
        # Последовательность активации головоломки
        self.puzzle_sequence = ["Bot", "history", "open"]
        # Время сброса пасхалки (24 часа)
        self.reset_hours = 24

    def check_blocked_user(self, user_id: int) -> bool:
        """Проверка, заблокирован ли пользователь"""
        from config import BLOCKED_USERS
        return user_id in BLOCKED_USERS

    def process_easter_egg_message(self, user_id: int, message_text: str) -> Dict:
        """
        Обработка сообщения на предмет пасхалки-головоломки

        :return: Словарь с результатом:
            - 'activated': bool (пасхалка активирована)
            - 'step_success': bool (успешный ввод шага)
            - 'step': int (текущий шаг 0-3)
            - 'response': str (ответ для пользователя)
        """
        # Проверяем состояние пользователя
        user_state = self.db.get_user_easter_egg_state(user_id)

        if user_state is None:
            # Создаём новое состояние
            user_state = {
                'current_step': 0,
                'last_completed': None,
                'started_at': datetime.now()
            }

        # ⚠️ ПРОВЕРКА КУЛДАУНА ПЕРЕД ОБРАБОТКОЙ ШАГОВ
        if user_state.get('last_completed'):
            last_time = datetime.fromisoformat(user_state['last_completed'])
            if datetime.now() - last_time < timedelta(hours=self.reset_hours):
                # Пасхалка на cooldown — возвращаем стандартный ответ
                # Никакой обработки шагов, прогресс не начинается
                return {
                    'activated': False,
                    'step_success': False,
                    'step': user_state['current_step'],
                    'cooldown': True,
                    'response': None  # None = стандартный ответ бота
                }

        current_step = user_state.get('current_step', 0)
        message_text = message_text.strip()

        # Проверяем соответствие последовательности
        if current_step < len(self.puzzle_sequence):
            expected_message = self.puzzle_sequence[current_step]

            if message_text == expected_message:
                # Правильное сообщение на текущем шаге
                new_step = current_step + 1
                user_state['current_step'] = new_step

                # Сохраняем состояние
                self.db.update_user_easter_egg_state(user_id, user_state)

                if new_step == len(self.puzzle_sequence):
                    # ⚠️ ГОЛОВОЛОМКА ЗАВЕРШЕНА — УСТАНАВЛИВАЕМ КУЛДАУН
                    user_state['last_completed'] = datetime.now().isoformat()
                    self.db.update_user_easter_egg_state(user_id, user_state)
                    return {
                        'activated': True,
                        'step_success': True,
                        'step': new_step,
                        'cooldown': False,
                        'response': "🎉 Поздравляем! Вы нашли секретное меню!"
                    }
                else:
                    # Переход на следующий шаг — успешный ввод
                    return {
                        'activated': False,
                        'step_success': True,
                        'step': new_step,
                        'cooldown': False,
                        'response': f"Успешный ввод ✅ ({new_step}/{len(self.puzzle_sequence)})"
                    }
            else:
                # Неправильное сообщение — сбрасываем ТОЛЬКО текущий прогресс шагов
                # last_completed НЕ трогается!
                user_state['current_step'] = 0
                self.db.update_user_easter_egg_state(user_id, user_state)
                # Возвращаем None для стандартного ответа бота
                return {
                    'activated': False,
                    'step_success': False,
                    'step': 0,
                    'cooldown': False,
                    'response': None  # None = стандартный ответ бота
                }

        # Если дошли сюда — возвращаем стандартный ответ
        return {
            'activated': False,
            'step_success': False,
            'step': current_step,
            'cooldown': False,
            'response': None
        }

    def get_dev_history(self) -> str:
        """Чтение истории разработки из файла"""
        try:
            history_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'history.txt')
            with open(history_file, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"❌ Ошибка чтения истории: {str(e)}"

    def get_dev_history_file_path(self) -> str:
        """Получение пути к файлу history.txt"""
        return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'history.txt')


# Глобальный экземпляр (будет инициализирован в handlers.py)
easter_egg_manager = None