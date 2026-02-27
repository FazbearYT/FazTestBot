# core/utils.py
# Общие утилиты FazTestBot

import logging
from datetime import datetime
from typing import Optional, Any
from pathlib import Path


# ====== ЛОГИРОВАНИЕ ======
def setup_logger(name: str, level: str = "INFO") -> logging.Logger:
    """
    Настройка логгера для модуля

    :param name: Имя логгера (обычно __name__)
    :param level: Уровень логирования
    :return: Logger объект
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


# ====== ВАЛИДАЦИЯ ======
def validate_string(value: Any, max_length: int = 4096, allow_empty: bool = False) -> bool:
    """
    Валидация строки

    :param value: Значение для проверки
    :param max_length: Максимальная длина
    :param allow_empty: Разрешить пустую строку
    :return: True если валидно
    """
    if not isinstance(value, str):
        return False

    if not allow_empty and not value.strip():
        return False

    if len(value) > max_length:
        return False

    return True


def validate_integer(value: Any, min_value: int = None, max_value: int = None) -> bool:
    """
    Валидация целого числа

    :param value: Значение для проверки
    :param min_value: Минимальное значение
    :param max_value: Максимальное значение
    :return: True если валидно
    """
    try:
        int_value = int(value)

        if min_value is not None and int_value < min_value:
            return False

        if max_value is not None and int_value > max_value:
            return False

        return True
    except (ValueError, TypeError):
        return False


# ====== ФОРМАТИРОВАНИЕ ======
def format_file_size(size_bytes: int) -> str:
    """
    Форматирование размера файла

    :param size_bytes: Размер в байтах
    :return: Человекочитаемый размер
    """
    for unit in ['Б', 'КБ', 'МБ', 'ГБ', 'ТБ']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} ПБ"


def format_datetime(dt: datetime, format_str: str = "%d.%m.%Y %H:%M") -> str:
    """
    Форматирование даты и времени

    :param dt: datetime объект
    :param format_str: Формат строки
    :return: Форматированная строка
    """
    return dt.strftime(format_str)


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Сокращение текста

    :param text: Исходный текст
    :param max_length: Максимальная длина
    :param suffix: Суффикс для сокращения
    :return: Сокращённый текст
    """
    if len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix


# ====== БЕЗОПАСНОСТЬ ======
def sanitize_filename(filename: str) -> str:
    """
    Очистка имени файла от опасных символов

    :param filename: Исходное имя файла
    :return: Безопасное имя файла
    """
    import re

    # Удаляем опасные символы
    safe_name = re.sub(r'[<>:"/\\|?*]', '_', filename)

    # Удаляем control characters
    safe_name = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', safe_name)

    # Ограничиваем длину
    safe_name = safe_name[:255]

    return safe_name.strip()


def sanitize_input(text: str, allowed_chars: str = None) -> str:
    """
    Очистка пользовательского ввода

    :param text: Исходный текст
    :param allowed_chars: Разрешённые символы (None = все)
    :return: Очищенный текст
    """
    if not text:
        return ""

    if allowed_chars:
        return ''.join(c for c in text if c in allowed_chars)

    # Удаляем потенциально опасные последовательности
    dangerous = ['<script', 'javascript:', 'data:', 'vbscript:']
    text_lower = text.lower()

    for danger in dangerous:
        if danger in text_lower:
            text = text.replace(danger, '')

    return text


# ====== ВРЕМЯ ======
def get_timestamp() -> str:
    """Получение текущей метки времени"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def get_date() -> str:
    """Получение текущей даты"""
    return datetime.now().strftime("%d.%m.%Y")


# Экспорт всех функций
__all__ = [
    'setup_logger',
    'validate_string',
    'validate_integer',
    'format_file_size',
    'format_datetime',
    'truncate_text',
    'sanitize_filename',
    'sanitize_input',
    'get_timestamp',
    'get_date'
]