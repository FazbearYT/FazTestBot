# modules/cipher/ciphers.py
# Логика шифрования для модуля "Шифратор"
import random

from .config import ALPHABET_RU, ALPHABET_EN, LEET_MAP, LEET_REPLACE_CHANCE
from config import ALLOWED_SYMBOLS


def caesar_cipher(text, step, language):
    """Шифрование текста шифром Цезаря"""
    result = ""

    for char in text:
        char_upper = char.upper()
        if language == 'ru' and char_upper in ALPHABET_RU:
            pos = ALPHABET_RU.find(char_upper)
            new_pos = (pos + step) % 33
            encrypted_char = ALPHABET_RU[new_pos]
            result += encrypted_char if char.isupper() else encrypted_char.lower()
        elif language == 'en' and char_upper in ALPHABET_EN:
            pos = ALPHABET_EN.find(char_upper)
            new_pos = (pos + step) % 26
            encrypted_char = ALPHABET_EN[new_pos]
            result += encrypted_char if char.isupper() else encrypted_char.lower()
        else:
            result += char

    return result


def validate_caesar_text(text, language):
    """
    Проверяет, что текст соответствует выбранному языку.
    Разрешает: буквы выбранного алфавита + цифры + пробел + знаки препинания
    Запрещает: буквы другого алфавита
    """
    if language == 'ru':
        for char in text:
            if char.lower() not in "абвгдеёжзийклмнопрстуфхцчшщъыьэюя" and char not in ALLOWED_SYMBOLS:
                if char.lower() in "abcdefghijklmnopqrstuvwxyz":
                    return False, "❌ Текст содержит латинские буквы, но выбран русский язык. Пожалуйста, введите текст кириллицей."
                return False, f"❌ Недопустимый символ: '{char}'"
        return True, ""
    else:  # language == 'en'
        for char in text:
            if char.lower() not in "abcdefghijklmnopqrstuvwxyz" and char not in ALLOWED_SYMBOLS:
                if char.lower() in "абвгдеёжзийклмнопрстуфхцчшщъыьэюя":
                    return False, "❌ Текст содержит кириллические буквы, но выбран английский язык. Пожалуйста, введите текст латиницей."
                return False, f"❌ Недопустимый символ: '{char}'"
        return True, ""

def leet_cipher(text: str, difficulty: str, chance: float = None) -> str:
    """
    Преобразование текста в Leet Speak.

    Каждая подходящая буква заменяется лишь с вероятностью chance —
    получается частичная замена (часть букв остаётся как есть). Если
    chance не передан, берётся вероятность пресета из LEET_REPLACE_CHANCE.
    """
    leet_map = LEET_MAP.get(difficulty, LEET_MAP['light'])
    if chance is None:
        chance = LEET_REPLACE_CHANCE.get(difficulty, 1.0)
    result = []
    for char in text:
        upper_char = char.upper()
        if upper_char in leet_map and random.random() <= chance:
            replacement = leet_map[upper_char]
            if isinstance(replacement, list):
                result.append(random.choice(replacement))
            else:
                result.append(replacement)
        else:
            result.append(char)
    return ''.join(result)