# modules/decision_maker/data/heroes.py
# Список героев Dota 2 (актуально на февраль 2026)
# Всего: 127 героев
# Источник: cybersport.metaratings.ru

DOTA2_HEROES = {
    # СИЛА (Strength) - 36 героев
    "strength": [
        "Alchemist", "Axe", "Bristleback", "Centaur Warrunner",
        "Chaos Knight", "Clockwerk", "Dawnbreaker", "Doom", "Dragon Knight",
        "Earth Spirit", "Earthshaker", "Elder Titan", "Huskar", "Kunkka",
        "Legion Commander", "Lifestealer", "Largo", "Lycan",
        "Mars", "Night Stalker", "Omniknight", "Ogre Magi", "Phoenix",
        "Primal Beast", "Pudge", "Slardar",
        "Spirit Breaker", "Sven", "Tidehunter", "Timbersaw", "Tiny",
        "Treant Protector", "Tusk", "Underlord", "Undying", "Wraith King"
    ],

    # ЛОВКОСТЬ (Agility) - 34 героя
    "agility": [
        "Anti-Mage", "Bloodseeker", "Bounty Hunter", "Broodmother",
        "Clinkz", "Drow Ranger", "Ember Spirit", "Faceless Void", "Gyrocopter",
        "Hoodwink", "Juggernaut", "Kez", "Lone Druid", "Luna",
        "Medusa", "Meepo", "Mirana", "Monkey King", "Morphling",
        "Naga Siren", "Phantom Assassin", "Phantom Lancer",
        "Razor", "Riki", "Shadow Fiend", "Slark", "Sniper",
        "Spectre","Templar Assassin", "Terrorblade", "Troll Warlord",
        "Ursa", "Vengeful Spirit", "Viper", "Weaver"
    ],

    # ИНТЕЛЛЕКТ (Intelligence) - 34 героя
    "intelligence": [
        "Ancient Apparition", "Crystal Maiden",
        "Dark Willow", "Disruptor", "Chen", "Dark Seer",
        "Enchantress", "Grimstroke", "Invoker", "Jakiro",
        "Keeper of the Light", "Leshrac", "Lich", "Lina", "Lion",
        "Muerta", "Necrophos",  "Oracle", "Outworld Destroyer",
        "Puck", "Pugna", "Queen of Pain", "Ringmaster", "Rubick",
        "Shadow Demon", "Shadow Shaman", "Silencer", "Skywrath Mage",
        "Storm Spirit",  "Tinker", "Warlock",
        "Winter Wyvern", "Witch Doctor", "Zeus"
    ],

    # УНИВЕРСАЛ (Universal) - 23 героя
    "universal": [
        "Abaddon", "Arc Warden", "Bane", "Batrider", "Beastmaster", "Windranger",
        "Brewmaster", "Marci", "Magnus", "Venomancer", "Dazzle", "Nyx Assassin",
        "Nature's Prophet", "Death Prophet", "Snapfire", "Pangolier", "Void Spirit",
        "Enigma", "Visage", "Io", "Sand King","Techies", "Winter Wyvern"
    ]
}

# Плоский список всех героев для случайного выбора
ALL_HEROES = []
for attribute, heroes in DOTA2_HEROES.items():
    ALL_HEROES.extend(heroes)

# Убираем дубликаты (некоторые герои могут быть в нескольких категориях)
ALL_HEROES = list(set(ALL_HEROES))
ALL_HEROES.sort()

HEROES_COUNT = len(ALL_HEROES)


def get_random_hero():
    """Возвращает случайного героя"""
    import random
    return random.choice(ALL_HEROES)


def get_heroes_by_attribute(attribute: str) -> list:
    """
    Возвращает список героев по атрибуту

    :param attribute: "strength", "agility", "intelligence", "universal"
    """
    attr_map = {
        "strength": "strength",
        "agility": "agility",
        "intelligence": "intelligence",
        "universal": "universal",
        "стр": "strength",
        "лов": "agility",
        "инт": "intelligence",
        "универсал": "universal"
    }

    key = attr_map.get(attribute.lower(), attribute.lower())
    return DOTA2_HEROES.get(key, ALL_HEROES)


def get_hero_attribute(hero: str) -> str:
    """Определяет атрибут героя"""
    for attribute, heroes in DOTA2_HEROES.items():
        if hero in heroes:
            return attribute

    return "unknown"


def get_attribute_name_ru(attribute: str) -> str:
    """Возвращает русское название атрибута"""
    names = {
        "strength": "💪 Сила",
        "agility": "🗡️ Ловкость",
        "intelligence": "🧠 Интеллект",
        "universal": "⚡ Универсал"
    }
    return names.get(attribute, attribute)