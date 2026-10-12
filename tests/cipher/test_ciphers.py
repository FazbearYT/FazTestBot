import unittest
from unittest.mock import patch

from modules.cipher.ciphers import caesar_cipher, leet_cipher, validate_caesar_text


class CipherFunctionsTests(unittest.TestCase):
    def test_caesar_wraps_each_alphabet_and_preserves_case_and_symbols(self):
        self.assertEqual("Bcd-A", caesar_cipher("Abc-Z", 1, "en"))
        self.assertEqual("Бвг-А", caesar_cipher("Абв-Я", 1, "ru"))

    def test_caesar_supports_negative_and_oversized_steps(self):
        self.assertEqual("Zab", caesar_cipher("Abc", -1, "en"))
        self.assertEqual("Bcd", caesar_cipher("Abc", 27, "en"))

    def test_validation_rejects_letters_from_the_other_alphabet(self):
        valid_ru, ru_error = validate_caesar_text("тест English", "ru")
        valid_en, en_error = validate_caesar_text("test Русский", "en")

        self.assertFalse(valid_ru)
        self.assertIn("латинские буквы", ru_error)
        self.assertFalse(valid_en)
        self.assertIn("кириллические буквы", en_error)

    def test_validation_accepts_configured_symbols(self):
        self.assertEqual((True, ""), validate_caesar_text("Text <42>!", "en"))
        self.assertEqual((True, ""), validate_caesar_text("Текст <42>!", "ru"))

    def test_leet_uses_requested_density_and_preserves_unselected_text(self):
        with patch("modules.cipher.ciphers.random.random", side_effect=[0.1, 0.9]):
            result = leet_cipher("AZ!", "light", chance=0.5)

        self.assertEqual("4Z!", result)

    def test_leet_selects_one_variant_for_multi_value_mapping(self):
        with (
            patch("modules.cipher.ciphers.random.random", return_value=0.0),
            patch("modules.cipher.ciphers.random.choice", return_value="@") as choice,
        ):
            result = leet_cipher("A", "medium", chance=1.0)

        self.assertEqual("@", result)
        choice.assert_called_once_with(["4", "@"])


if __name__ == "__main__":
    unittest.main()
