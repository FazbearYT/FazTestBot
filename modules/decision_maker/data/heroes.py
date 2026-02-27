# modules/decision_maker/data/heroes.py
# Список героев Dota 2

DOTA2_HEROES = [
    # Сила
    "Axe", "Beastmaster", "Bristleback", "Centaur Warrunner", "Chaos Knight",
    "Clockwerk", "Doom", "Dragon Knight", "Earth Spirit", "Earthshaker",
    "Elder Titan", "Huskar", "Io", "Kunkka", "Legion Commander", "Lifestealer",
    "Lycan", "Magnus", "Marci", "Mars", "Night Stalker", "Omniknight",
    "Phoenix", "Primal Beast", "Pudge", "Sand King", "Slardar", "Snapfire",
    "Spirit Breaker", "Sven", "Tidehunter", "Timbersaw", "Tiny", "Treant Protector",
    "Tusk", "Underlord", "Undying", "Wraith King",

    # Ловкость
    "Anti-Mage", "Arc Warden", "Bloodseeker", "Bounty Hunter", "Broodmother",
    "Clinkz", "Drow Ranger", "Ember Spirit", "Faceless Void", "Gyrocopter",
    "Hoodwink", "Juggernaut", "Lone Druid", "Luna", "Medusa", "Meepo",
    "Mirana", "Monkey King", "Morphling", "Naga Siren", "Nyxx Assassin",
    "Pangolier", "Phantom Assassin", "Phantom Lancer", "Razor", "Riki",
    "Shadow Fiend", "Slark", "Sniper", "Spectre", "Templar Assassin",
    "Terrorblade", "Troll Warlord", "Ursa", "Vengeful Spirit", "Venomancer",
    "Viper", "Weaver",

    # Интеллект
    "Ancient Apparition", "Bane", "Batrider", "Chen", "Crystal Maiden",
    "Dark Seer", "Dark Willow", "Dazzle", "Death Prophet", "Disruptor",
    "Enchantress", "Enigma", "Grimstroke", "Invoker", "Jakiro", "Keeper of the Light",
    "Leshrac", "Lich", "Lina", "Lion", "Nature's Prophet", "Necrophos",
    "Ogre Magi", "Oracle", "Outworld Destroyer", "Puck", "Pugna", "Queen of Pain",
    "Rubick", "Shadow Demon", "Shadow Shaman", "Silencer", "Skywrath Mage",
    "Storm Spirit", "Techies", "Tinker", "Visage", "Void Spirit", "Warlock",
    "Windranger", "Winter Wyvern", "Witch Doctor", "Zeus"
]

# Количество героев
HEROES_COUNT = len(DOTA2_HEROES)


# Получение случайного героя
def get_random_hero():
    """Возвращает случайного героя"""
    import random
    return random.choice(DOTA2_HEROES)


# Получение героя по атрибуту
def get_heroes_by_attribute(attribute: str) -> list:
    """
    Возвращает список героев по атрибуту

    :param attribute: "strength", "agility", "intelligence"
    """
    strength_heroes = [
        "Axe", "Beastmaster", "Bristleback", "Centaur Warrunner", "Chaos Knight",
        "Clockwerk", "Doom", "Dragon Knight", "Earth Spirit", "Earthshaker",
        "Elder Titan", "Huskar", "Io", "Kunkka", "Legion Commander", "Lifestealer",
        "Lycan", "Magnus", "Marci", "Mars", "Night Stalker", "Omniknight",
        "Phoenix", "Primal Beast", "Pudge", "Sand King", "Slardar", "Snapfire",
        "Spirit Breaker", "Sven", "Tidehunter", "Timbersaw", "Tiny", "Treant Protector",
        "Tusk", "Underlord", "Undying", "Wraith King"
    ]

    agility_heroes = [
        "Anti-Mage", "Arc Warden", "Bloodseeker", "Bounty Hunter", "Broodmother",
        "Clinkz", "Drow Ranger", "Ember Spirit", "Faceless Void", "Gyrocopter",
        "Hoodwink", "Juggernaut", "Lone Druid", "Luna", "Medusa", "Meepo",
        "Mirana", "Monkey King", "Morphling", "Naga Siren", "Nyx Assassin",
        "Pangolier", "Phantom Assassin", "Phantom Lancer", "Razor", "Riki",
        "Shadow Fiend", "Slark", "Sniper", "Spectre", "Templar Assassin",
        "Terrorblade", "Troll Warlord", "Ursa", "Vengeful Spirit", "Venomancer",
        "Viper", "Weaver"
    ]

    intel_heroes = [
        "Ancient Apparition", "Bane", "Batrider", "Chen", "Crystal Maiden",
        "Dark Seer", "Dark Willow", "Dazzle", "Death Prophet", "Disruptor",
        "Enchantress", "Enigma", "Grimstroke", "Invoker", "Jakiro", "Keeper of the Light",
        "Leshrac", "Lich", "Lina", "Lion", "Nature's Prophet", "Necrophos",
        "Ogre Magi", "Oracle", "Outworld Destroyer", "Puck", "Pugna", "Queen of Pain",
        "Rubick", "Shadow Demon", "Shadow Shaman", "Silencer", "Skywrath Mage",
        "Storm Spirit", "Techies", "Tinker", "Visage", "Void Spirit", "Warlock",
        "Windranger", "Winter Wyvern", "Witch Doctor", "Zeus"
    ]

    if attribute.lower() == "strength":
        return strength_heroes
    elif attribute.lower() == "agility":
        return agility_heroes
    elif attribute.lower() == "intelligence":
        return intel_heroes
    else:
        return DOTA2_HEROES