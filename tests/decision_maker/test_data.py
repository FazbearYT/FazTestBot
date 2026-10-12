import unittest
from unittest.mock import patch

from modules.decision_maker.data.heroes import (
    ALL_HEROES,
    DOTA2_HEROES,
    HEROES_COUNT,
    get_attribute_name_ru,
    get_hero_attribute,
    get_heroes_by_attribute,
    get_random_hero,
)


class HeroDataTests(unittest.TestCase):
    def test_flat_hero_catalog_is_sorted_and_unique(self):
        expected = sorted({hero for heroes in DOTA2_HEROES.values() for hero in heroes})

        self.assertEqual(expected, ALL_HEROES)
        self.assertEqual(len(expected), HEROES_COUNT)

    def test_attribute_lookup_supports_alias_and_fallback(self):
        self.assertEqual(DOTA2_HEROES["strength"], get_heroes_by_attribute("стр"))
        self.assertIs(ALL_HEROES, get_heroes_by_attribute("missing"))
        self.assertEqual("strength", get_hero_attribute("Axe"))
        self.assertEqual("unknown", get_hero_attribute("Not a hero"))

    def test_attribute_display_name_and_random_choice_are_stable_contracts(self):
        self.assertEqual("💪 Сила", get_attribute_name_ru("strength"))
        self.assertEqual("missing", get_attribute_name_ru("missing"))
        with patch(
            "modules.decision_maker.data.heroes.random.choice",
            return_value="Axe",
        ) as choice:
            self.assertEqual("Axe", get_random_hero())
        choice.assert_called_once_with(ALL_HEROES)


if __name__ == "__main__":
    unittest.main()
