# modules/decision_maker/handlers.py
# Обработчики модуля "Decision Maker"
# Версия: 4.3.2

import random
import sqlite3
from datetime import datetime, timedelta
from telebot import types
from typing import Any
from core.module_base import BaseModule
from core.database import DatabaseManager
from .keyboards import (
    decision_maker_menu_keyboard,
    number_range_keyboard,
    dota2_hero_keyboard,
    coin_flip_keyboard,
    result_keyboard,
    list_options_keyboard
)
from .data.heroes import ALL_HEROES, get_random_hero, get_heroes_by_attribute, get_hero_attribute, \
    get_attribute_name_ru, HEROES_COUNT
from .config import (
    MAX_RANDOM_RANGE,
    MAX_LIST_ITEMS,
    MAX_DAILY_USES,
    TABLE_NAME,
    COIN_SIDES,
    DEFAULT_MIN,
    DEFAULT_MAX
)
import config

db = DatabaseManager()


class DecisionMakerModule(BaseModule):
    """
    Модуль для принятия решений.

    Поддерживает:
    - Генератор случайных чисел
    - Выбор из списка
    - Случайный герой Dota 2
    - Подбрасывание монетки
    """

    def __init__(self, module_id, name, description, icon, version, callback_prefix):
        """Инициализация модуля Decision Maker"""
        super().__init__(module_id, name, description, icon, version, callback_prefix)
        self._init_database()

    def _init_database(self):
        """Инициализация таблицы в БД"""
        try:
            conn = sqlite3.connect(config.DATABASE_PATH)
            cursor = conn.cursor()

            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    action_type TEXT NOT NULL,
                    result TEXT,
                    details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Таблица статистики монетки
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS coin_flip_stats (
                    user_id INTEGER PRIMARY KEY,
                    heads_count INTEGER DEFAULT 0,
                    tails_count INTEGER DEFAULT 0,
                    total_count INTEGER DEFAULT 0,
                    last_flip TIMESTAMP
                )
            """)

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"⚠️ Ошибка инициализации БД: {str(e)}")

    def handle_entry(self, bot: Any, call: Any) -> None:
        """Вход в модуль"""
        chat_id = call.message.chat.id
        message_id = call.message.message_id

        self.set_user_state(chat_id, 'message_id', message_id)

        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="🎲 <b>Decision Maker</b>\n\n"
                 "Инструменты для принятия решений:\n\n"
                 "🎲 <b>Генератор чисел</b> — случайное число в диапазоне\n"
                 "📝 <b>Выбор из списка</b> — случайный элемент из вашего списка\n"
                 "⚔️ <b>Dota 2 герои</b> — случайный герой для игры\n"
                 "🪙 <b>Монетка</b> — орёл или решка\n\n"
                 f"Лимит: {MAX_DAILY_USES} использований/день\n\n"
                 "Выберите действие:",
            reply_markup=self.get_menu_keyboard(),
            parse_mode="HTML"
        )

    def handle_callback(self, bot: Any, call: Any) -> None:
        """Обработка колбэков"""
        chat_id = call.message.chat.id
        message_id = call.message.message_id

        try:
            bot.answer_callback_query(call.id)

            # Назад к списку модулей
            if call.data == "dm_back_to_modules":
                from core.module_manager import module_manager
                modules = module_manager.get_all_modules()

                kb = types.InlineKeyboardMarkup(row_width=1)
                for module in modules:
                    kb.add(types.InlineKeyboardButton(
                        f"{module.icon} {module.name}",
                        callback_data=f"module_{module.id}"
                    ))
                kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_main"))

                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="📦 <b>Доступные модули</b>\n\nВыберите модуль:",
                    reply_markup=kb,
                    parse_mode="HTML"
                )
                self.cleanup_user_state(chat_id)
                return

            # Назад в меню модуля
            if call.data == "dm_back_to_menu":
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="🎲 <b>Decision Maker</b>\n\n"
                         "Инструменты для принятия решений:\n\n"
                         "🎲 <b>Генератор чисел</b> — случайное число в диапазоне\n"
                         "📝 <b>Выбор из списка</b> — случайный элемент из вашего списка\n"
                         "⚔️ <b>Dota 2 герои</b> — случайный герой для игры\n"
                         "🪙 <b>Монетка</b> — орёл или решка\n\n"
                         f"Лимит: {MAX_DAILY_USES} использований/день\n\n"
                         "Выберите действие:",
                    reply_markup=decision_maker_menu_keyboard(),
                    parse_mode="HTML"
                )
                return

            # Генератор чисел
            if call.data == "dm_numbers":
                self.set_user_state(chat_id, 'action', 'numbers')
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="🎲 <b>Генератор случайных чисел</b>\n\n"
                         "Выберите диапазон или введите свой:\n\n"
                         "<i>Пример: 1-100</i>",
                    reply_markup=number_range_keyboard(),
                    parse_mode="HTML"
                )
                return

            # Выбор из списка
            if call.data == "dm_list":
                self.set_user_state(chat_id, 'action', 'list')
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="📝 <b>Выбор из списка</b>\n\n"
                         "Для начала работы нажмите кнопку «📝 Ввести список»:\n\n"
                         "Отправьте список вариантов через запятую:\n\n"
                         "<i>Пример: пицца, суши, бургер, салат</i>",
                    reply_markup=list_options_keyboard(),
                    parse_mode="HTML"
                )
                return

            # Dota 2 герои
            if call.data == "dm_dota2":
                self.set_user_state(chat_id, 'action', 'dota2')
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="⚔️ <b>Dota 2 Герои</b>\n\n"
                         f"Всего героев: {HEROES_COUNT}\n\n"
                         "Выберите способ выбора:",
                    reply_markup=dota2_hero_keyboard(),
                    parse_mode="HTML"
                )
                return

            # Монетка
            if call.data == "dm_coin":
                self.set_user_state(chat_id, 'action', 'coin')
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="🪙 <b>Подбрасывание монетки</b>\n\n"
                         "Орёл или Решка?\n\n"
                         "Проверь свою удачу!",
                    reply_markup=coin_flip_keyboard(),
                    parse_mode="HTML"
                )
                return

            # ====== ГЕНЕРАТОР ЧИСЕЛ ======
            if call.data.startswith("dm_range_"):
                if call.data == "dm_range_custom":
                    self.set_user_state(chat_id, 'range_type', 'custom')
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text="🎲 <b>Свой диапазон</b>\n\n"
                             f"Введите диапазон (макс. {MAX_RANDOM_RANGE}):\n\n"
                             "<i>Пример: 50-150</i>",
                        reply_markup=None,
                        parse_mode="HTML"
                    )
                    bot.register_next_step_handler_by_chat_id(chat_id, self._process_custom_range, bot)
                    return

                # Предопределённые диапазоны
                range_map = {
                    "dm_range_1_10": (1, 10),
                    "dm_range_1_100": (1, 100),
                    "dm_range_1_1000": (1, 1000)
                }

                if call.data in range_map:
                    min_val, max_val = range_map[call.data]
                    result = random.randint(min_val, max_val)

                    # Сохраняем для повтора
                    self.set_user_state(chat_id, 'last_action', 'numbers')
                    self.set_user_state(chat_id, 'last_min', min_val)
                    self.set_user_state(chat_id, 'last_max', max_val)

                    self._log_action(chat_id, 'random_number', str(result), f"{min_val}-{max_val}")

                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=f"🎲 <b>Случайное число</b>\n\n"
                             f"Диапазон: {min_val}-{max_val}\n"
                             f"Результат: <b>{result}</b>",
                        reply_markup=result_keyboard("dm_numbers"),
                        parse_mode="HTML"
                    )
                    return

            # ====== DOTA 2 ГЕРОИ ======
            if call.data.startswith("dm_dota2_"):
                if call.data == "dm_dota2_random":
                    hero = get_random_hero()
                    attribute = get_hero_attribute(hero)
                    attribute_name = get_attribute_name_ru(attribute)

                    self.set_user_state(chat_id, 'last_action', 'dota2')
                    self.set_user_state(chat_id, 'last_attribute', None)  # Случайный выбор
                    self._log_action(chat_id, 'dota2_hero', hero, attribute)

                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=f"⚔️ <b>Случайный герой</b>\n\n"
                             f"🦸 <b>{hero}</b>\n"
                             f"Атрибут: {attribute_name}\n\n"
                             f"Всего героев: {HEROES_COUNT}",
                        reply_markup=result_keyboard("dm_dota2"),
                        parse_mode="HTML"
                    )
                    return

                # По атрибуту
                attribute_map = {
                    "dm_dota2_strength": ("strength", "💪 Сила"),
                    "dm_dota2_agility": ("agility", "🗡️ Ловкость"),
                    "dm_dota2_intel": ("intelligence", "🧠 Интеллект"),
                    "dm_dota2_universal": ("universal", "⚡ Универсал")
                }

                if call.data in attribute_map:
                    attr_key, attr_name = attribute_map[call.data]
                    heroes = get_heroes_by_attribute(attr_key)
                    hero = random.choice(heroes)

                    self.set_user_state(chat_id, 'last_action', 'dota2')
                    self.set_user_state(chat_id, 'last_attribute', attr_key)  # Сохраняем атрибут!
                    self._log_action(chat_id, 'dota2_hero', hero, attr_key)

                    # ИСПРАВЛЕНО: Правильный подсчет количества героев в категории
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=f"⚔️ <b>Случайный герой</b>\n\n"
                             f"🦸 <b>{hero}</b>\n"
                             f"Атрибут: {attr_name}\n"
                             f"Всего в категории: {len(heroes)}",  # Правильный подсчет!
                        reply_markup=result_keyboard("dm_dota2"),
                        parse_mode="HTML"
                    )
                    return

            # ====== МОНЕТКА ======
            if call.data == "dm_coin_flip":
                result = random.choice(COIN_SIDES)
                emoji = "🦅" if result == "Орёл" else "🪙"

                self.set_user_state(chat_id, 'last_action', 'coin')
                self._log_action(chat_id, 'coin_flip', result, "")
                self._update_coin_stats(chat_id, result)

                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"🪙 <b>Результат подбрасывания</b>\n\n"
                         f"{emoji} <b>{result}</b>!",
                    reply_markup=result_keyboard("dm_coin"),
                    parse_mode="HTML"
                )
                return

            if call.data == "dm_coin_stats":
                stats = self._get_coin_stats(chat_id)

                if stats:
                    text = f"📊 <b>Статистика монетки</b>\n\n"
                    text += f"Всего подбрасываний: {stats['total']}\n"
                    text += f"🦅 Орёл: {stats['heads']} ({stats['heads_percent']}%)\n"
                    text += f"🪙 Решка: {stats['tails']} ({stats['tails_percent']}%)"
                else:
                    text = "📊 <b>Статистика монетки</b>\n\n"
                    text += "Пока нет подбрасываний.\n\n"
                    text += "Подбросьте монетку!"

                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=coin_flip_keyboard(),
                    parse_mode="HTML"
                )
                return

            # ====== ВВОД СПИСКА ======
            if call.data == "dm_list_input":
                self.set_user_state(chat_id, 'action', 'list')
                self.set_user_state(chat_id, 'list_state', 'waiting_input')

                # Создаем клавиатуру с кнопкой "Назад"
                cancel_kb = types.InlineKeyboardMarkup(row_width=1)
                cancel_kb.add(
                    types.InlineKeyboardButton("🔙 Отмена", callback_data="dm_back_to_menu")
                )

                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="📝 <b>Ввод списка</b>\n\n"
                         "Отправьте варианты через запятую:\n\n"
                         "<i>Пример: пицца, суши, бургер, салат</i>\n\n"
                         "Или нажмите «🔙 Отмена»",
                    reply_markup=cancel_kb,  # ИСПРАВЛЕНО: добавлена клавиатура!
                    parse_mode="HTML"
                )
                bot.register_next_step_handler_by_chat_id(chat_id, self._process_list_input, bot)
                return

            # ====== ПОВТОР ======
            if call.data == "dm_again":
                action = self.get_user_state(chat_id, 'last_action')

                if action == 'numbers':
                    min_val = self.get_user_state(chat_id, 'last_min', 1)
                    max_val = self.get_user_state(chat_id, 'last_max', 100)
                    result = random.randint(min_val, max_val)

                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=f"🎲 <b>Случайное число</b>\n\n"
                             f"Диапазон: {min_val}-{max_val}\n"
                             f"Результат: <b>{result}</b>",
                        reply_markup=result_keyboard("dm_numbers"),
                        parse_mode="HTML"
                    )
                elif action == 'dota2':
                    # Проверяем, был ли выбран атрибут
                    last_attribute = self.get_user_state(chat_id, 'last_attribute')

                    if last_attribute:
                        # Повторяем выбор по тому же атрибуту
                        heroes = get_heroes_by_attribute(last_attribute)
                        hero = random.choice(heroes)
                        attribute_name = get_attribute_name_ru(last_attribute)

                        bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=message_id,
                            text=f"⚔️ <b>Случайный герой</b>\n\n"
                                 f"🦸 <b>{hero}</b>\n"
                                 f"Атрибут: {attribute_name}\n"
                                 f"Всего в категории: {len(heroes)}",
                            reply_markup=result_keyboard("dm_dota2"),
                            parse_mode="HTML"
                        )
                    else:
                        # Случайный герой из всех
                        hero = get_random_hero()
                        attribute = get_hero_attribute(hero)
                        attribute_name = get_attribute_name_ru(attribute)

                        bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=message_id,
                            text=f"⚔️ <b>Случайный герой</b>\n\n"
                                 f"🦸 <b>{hero}</b>\n"
                                 f"Атрибут: {attribute_name}",
                            reply_markup=result_keyboard("dm_dota2"),
                            parse_mode="HTML"
                        )
                elif action == 'coin':
                    result = random.choice(COIN_SIDES)
                    emoji = "🦅" if result == "Орёл" else "🪙"

                    self._update_coin_stats(chat_id, result)

                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=f"🪙 <b>Результат подбрасывания</b>\n\n"
                             f"{emoji} <b>{result}</b>!",
                        reply_markup=result_keyboard("dm_coin"),
                        parse_mode="HTML"
                    )
                elif action == 'list':
                    items = self.get_user_state(chat_id, 'last_list', [])
                    if items:
                        result = random.choice(items)

                        # Формируем сообщение
                        items_text = ", ".join(items[:10])
                        if len(items) > 10:
                            items_text += f" ... и ещё {len(items) - 10}"

                        bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=message_id,
                            text=f"📝 <b>Выбор из списка</b>\n\n"
                                 f"Варианты ({len(items)}): {items_text}\n\n"
                                 f"🎲 <b>Результат:</b>\n"
                                 f"<b>{result}</b>",
                            reply_markup=result_keyboard("dm_list"),
                            parse_mode="HTML"
                        )
                    else:
                        bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=message_id,
                            text="⚠️ Список пуст. Введите новый список.",
                            reply_markup=list_options_keyboard(),
                            parse_mode="HTML"
                        )
                else:
                    bot.answer_callback_query(
                        call.id,
                        "⚠️ Нет предыдущего действия",
                        show_alert=True
                    )
                return

        except Exception as e:
            bot.answer_callback_query(
                call.id,
                f"Ошибка: {str(e)[:60]}",
                show_alert=True
            )

    def get_menu_keyboard(self) -> types.InlineKeyboardMarkup:
        """Клавиатура меню"""
        return decision_maker_menu_keyboard()

    def _process_list_input(self, message, bot):
        """Обработка ввода списка"""
        chat_id = message.chat.id
        text = message.text.strip()

        try:
            # Получаем message_id ДО удаления сообщения
            message_id = self.get_user_state(chat_id, 'message_id')

            # Проверяем состояние
            list_state = self.get_user_state(chat_id, 'list_state')
            if list_state != 'waiting_input':
                if message_id:
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text="⚠️ Сессия устарела. Вернитесь в меню и нажмите «📝 Ввести список»",
                        reply_markup=decision_maker_menu_keyboard(),
                        parse_mode="HTML"
                    )
                else:
                    bot.send_message(
                        chat_id,
                        "⚠️ Сессия устарела. Вернитесь в меню и нажмите «📝 Ввести список»",
                        reply_markup=decision_maker_menu_keyboard(),
                        parse_mode="HTML"
                    )
                return

            # Удаляем сообщение пользователя
            try:
                bot.delete_message(chat_id, message.message_id)
            except:
                pass

            # Парсим список
            items = [item.strip() for item in text.split(',') if item.strip()]

            if not items:
                if message_id:
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text="❌ Список пуст. Отправьте варианты через запятую.\n\n"
                             "<i>Пример: пицца, суши, бургер</i>",
                        reply_markup=list_options_keyboard(),
                        parse_mode="HTML"
                    )
                else:
                    bot.send_message(
                        chat_id,
                        "❌ Список пуст. Отправьте варианты через запятую.\n\n"
                        "<i>Пример: пицца, суши, бургер</i>",
                        reply_markup=list_options_keyboard(),
                        parse_mode="HTML"
                    )
                return

            if len(items) > MAX_LIST_ITEMS:
                if message_id:
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=f"❌ Слишком много элементов (макс. {MAX_LIST_ITEMS}).\n\n"
                             f"Вы отправили: {len(items)}",
                        reply_markup=list_options_keyboard(),
                        parse_mode="HTML"
                    )
                else:
                    bot.send_message(
                        chat_id,
                        f"❌ Слишком много элементов (макс. {MAX_LIST_ITEMS}).\n\n"
                        f"Вы отправили: {len(items)}",
                        reply_markup=list_options_keyboard(),
                        parse_mode="HTML"
                    )
                return

            if len(items) < 2:
                if message_id:
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text="❌ Нужно минимум 2 варианта для выбора.\n\n"
                             f"Вы отправили: {len(items)}",
                        reply_markup=list_options_keyboard(),
                        parse_mode="HTML"
                    )
                else:
                    bot.send_message(
                        chat_id,
                        "❌ Нужно минимум 2 варианта для выбора.\n\n"
                        f"Вы отправили: {len(items)}",
                        reply_markup=list_options_keyboard(),
                        parse_mode="HTML"
                    )
                return

            # Выбираем случайный элемент
            result = random.choice(items)

            # Сохраняем для повтора
            self.set_user_state(chat_id, 'last_action', 'list')
            self.set_user_state(chat_id, 'last_list', items)

            self._log_action(chat_id, 'list_choice', result, f"{len(items)} items")

            # Формируем сообщение
            items_text = ", ".join(items[:10])
            if len(items) > 10:
                items_text += f" ... и ещё {len(items) - 10}"

            if message_id:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"📝 <b>Выбор из списка</b>\n\n"
                         f"Варианты ({len(items)}): {items_text}\n\n"
                         f"🎲 <b>Результат:</b>\n"
                         f"<b>{result}</b>",
                    reply_markup=result_keyboard("dm_list"),
                    parse_mode="HTML"
                )
            else:
                bot.send_message(
                    chat_id,
                    f"📝 <b>Выбор из списка</b>\n\n"
                    f"Варианты ({len(items)}): {items_text}\n\n"
                    f"🎲 <b>Результат:</b>\n"
                    f"<b>{result}</b>",
                    reply_markup=result_keyboard("dm_list"),
                    parse_mode="HTML"
                )

        except Exception as e:
            # Получаем message_id для редактирования
            message_id = self.get_user_state(chat_id, 'message_id')

            if message_id:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"❌ Ошибка: {str(e)[:100]}",
                    reply_markup=list_options_keyboard(),
                    parse_mode="HTML"
                )
            else:
                bot.send_message(
                    chat_id,
                    f"❌ Ошибка: {str(e)[:100]}",
                    reply_markup=list_options_keyboard(),
                    parse_mode="HTML"
                )

    def _process_custom_range(self, message, bot):
        """Обработка пользовательского диапазона"""
        chat_id = message.chat.id

        try:
            # Получаем message_id ДО удаления
            message_id = self.get_user_state(chat_id, 'message_id')

            # Удаляем сообщение пользователя
            try:
                bot.delete_message(chat_id, message.message_id)
            except:
                pass

            # Парсим диапазон
            text = message.text.strip()
            if '-' not in text:
                if message_id:
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text="❌ Неверный формат. Используйте формат: min-max\n\nПример: 50-150",
                        reply_markup=number_range_keyboard(),
                        parse_mode="HTML"
                    )
                else:
                    bot.send_message(
                        chat_id,
                        "❌ Неверный формат. Используйте формат: min-max\n\nПример: 50-150",
                        reply_markup=number_range_keyboard(),
                        parse_mode="HTML"
                    )
                return

            parts = text.split('-')
            min_val = int(parts[0].strip())
            max_val = int(parts[1].strip())

            # Проверки
            if min_val >= max_val:
                if message_id:
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text="❌ Минимальное значение должно быть меньше максимального",
                        reply_markup=number_range_keyboard(),
                        parse_mode="HTML"
                    )
                else:
                    bot.send_message(
                        chat_id,
                        "❌ Минимальное значение должно быть меньше максимального",
                        reply_markup=number_range_keyboard(),
                        parse_mode="HTML"
                    )
                return

            if max_val - min_val > MAX_RANDOM_RANGE:
                if message_id:
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=f"❌ Диапазон слишком большой (макс. {MAX_RANDOM_RANGE})",
                        reply_markup=number_range_keyboard(),
                        parse_mode="HTML"
                    )
                else:
                    bot.send_message(
                        chat_id,
                        f"❌ Диапазон слишком большой (макс. {MAX_RANDOM_RANGE})",
                        reply_markup=number_range_keyboard(),
                        parse_mode="HTML"
                    )
                return

            # Генерируем число
            result = random.randint(min_val, max_val)

            # Сохраняем для повтора
            self.set_user_state(chat_id, 'last_action', 'numbers')
            self.set_user_state(chat_id, 'last_min', min_val)
            self.set_user_state(chat_id, 'last_max', max_val)

            self._log_action(chat_id, 'random_number', str(result), f"{min_val}-{max_val}")

            if message_id:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"🎲 <b>Случайное число</b>\n\n"
                         f"Диапазон: {min_val}-{max_val}\n"
                         f"Результат: <b>{result}</b>",
                    reply_markup=result_keyboard("dm_numbers"),
                    parse_mode="HTML"
                )
            else:
                bot.send_message(
                    chat_id,
                    f"🎲 <b>Случайное число</b>\n\n"
                    f"Диапазон: {min_val}-{max_val}\n"
                    f"Результат: <b>{result}</b>",
                    reply_markup=result_keyboard("dm_numbers"),
                    parse_mode="HTML"
                )

        except ValueError:
            message_id = self.get_user_state(chat_id, 'message_id')
            if message_id:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="❌ Введите корректные числа в формате: min-max",
                    reply_markup=number_range_keyboard(),
                    parse_mode="HTML"
                )
            else:
                bot.send_message(
                    chat_id,
                    "❌ Введите корректные числа в формате: min-max",
                    reply_markup=number_range_keyboard(),
                    parse_mode="HTML"
                )
        except Exception as e:
            message_id = self.get_user_state(chat_id, 'message_id')
            if message_id:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"❌ Ошибка: {str(e)[:100]}",
                    reply_markup=number_range_keyboard(),
                    parse_mode="HTML"
                )
            else:
                bot.send_message(
                    chat_id,
                    f"❌ Ошибка: {str(e)[:100]}",
                    reply_markup=number_range_keyboard(),
                    parse_mode="HTML"
                )

    def _log_action(self, user_id: int, action_type: str, result: str, details: str):
        """Логирование действия"""
        try:
            conn = sqlite3.connect(config.DATABASE_PATH)
            cursor = conn.cursor()

            cursor.execute(f"""
                INSERT INTO {TABLE_NAME} (user_id, action_type, result, details)
                VALUES (?, ?, ?, ?)
            """, (user_id, action_type, result, details[:200]))

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"⚠️ Ошибка логирования: {str(e)}")

    def _update_coin_stats(self, user_id: int, result: str):
        """Обновление статистики монетки"""
        try:
            conn = sqlite3.connect(config.DATABASE_PATH)
            cursor = conn.cursor()

            # Проверяем существует ли запись
            cursor.execute("SELECT user_id FROM coin_flip_stats WHERE user_id = ?", (user_id,))
            exists = cursor.fetchone()

            if exists:
                if result == "Орёл":
                    cursor.execute("""
                        UPDATE coin_flip_stats 
                        SET heads_count = heads_count + 1, 
                            total_count = total_count + 1,
                            last_flip = CURRENT_TIMESTAMP
                        WHERE user_id = ?
                    """, (user_id,))
                else:
                    cursor.execute("""
                        UPDATE coin_flip_stats 
                        SET tails_count = tails_count + 1, 
                            total_count = total_count + 1,
                            last_flip = CURRENT_TIMESTAMP
                        WHERE user_id = ?
                    """, (user_id,))
            else:
                heads = 1 if result == "Орёл" else 0
                tails = 1 if result == "Решка" else 0
                cursor.execute("""
                    INSERT INTO coin_flip_stats (user_id, heads_count, tails_count, total_count, last_flip)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (user_id, heads, tails, 1))

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"⚠️ Ошибка обновления статистики: {str(e)}")

    def _get_coin_stats(self, user_id: int) -> dict:
        """Получение статистики монетки"""
        try:
            conn = sqlite3.connect(config.DATABASE_PATH)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT heads_count, tails_count, total_count
                FROM coin_flip_stats
                WHERE user_id = ?
            """, (user_id,))

            result = cursor.fetchone()
            conn.close()

            if result:
                heads, tails, total = result
                heads_percent = round((heads / total * 100), 1) if total > 0 else 0
                tails_percent = round((tails / total * 100), 1) if total > 0 else 0

                return {
                    'heads': heads,
                    'tails': tails,
                    'total': total,
                    'heads_percent': heads_percent,
                    'tails_percent': tails_percent
                }
            return None
        except:
            return None

    def on_load(self, bot: Any) -> None:
        """Загрузка модуля"""
        print(f"🎲 Модуль Decision Maker v{self.version} загружен")

    def on_unload(self, bot: Any) -> None:
        """Выгрузка модуля"""
        print(f"🎲 Модуль Decision Maker v{self.version} выгружен")