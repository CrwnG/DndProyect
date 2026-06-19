"""Basic shop item catalog.

Minimal consumable and weapon data so the shop subsystem (app/models/shop.py)
is functional. Values are in gold pieces; entries carry a numeric ``value`` key
used for pricing and a ``type`` for filtering. Mechanical stats only.
"""
from typing import Dict, Any

CONSUMABLES: Dict[str, Dict[str, Any]] = {
    "potion_of_healing": {
        "name": "Potion of Healing", "type": "potion", "value": 50,
        "effect": "heal", "healing": "2d4+2",
    },
    "potion_of_greater_healing": {
        "name": "Potion of Greater Healing", "type": "potion", "value": 150,
        "effect": "heal", "healing": "4d4+4",
    },
    "antitoxin": {
        "name": "Antitoxin", "type": "potion", "value": 50,
        "effect": "advantage_poison_saves",
    },
    "potion_of_climbing": {
        "name": "Potion of Climbing", "type": "potion", "value": 75,
        "effect": "climb_speed",
    },
    "alchemists_fire": {
        "name": "Alchemist's Fire", "type": "thrown", "value": 50,
        "damage": "1d4", "damage_type": "fire", "effect": "burning",
    },
    "holy_water": {
        "name": "Holy Water", "type": "thrown", "value": 25,
        "damage": "2d6", "damage_type": "radiant",
    },
}

WEAPONS: Dict[str, Dict[str, Any]] = {
    "dagger": {"name": "Dagger", "type": "weapon", "value": 2,
               "damage": "1d4", "damage_type": "piercing",
               "properties": ["finesse", "light", "thrown"]},
    "mace": {"name": "Mace", "type": "weapon", "value": 5,
             "damage": "1d6", "damage_type": "bludgeoning"},
    "shortsword": {"name": "Shortsword", "type": "weapon", "value": 10,
                   "damage": "1d6", "damage_type": "piercing",
                   "properties": ["finesse", "light"]},
    "longsword": {"name": "Longsword", "type": "weapon", "value": 15,
                  "damage": "1d8", "damage_type": "slashing",
                  "properties": ["versatile"]},
    "greataxe": {"name": "Greataxe", "type": "weapon", "value": 30,
                 "damage": "1d12", "damage_type": "slashing",
                 "properties": ["heavy", "two_handed"]},
    "shortbow": {"name": "Shortbow", "type": "weapon", "value": 25,
                 "damage": "1d6", "damage_type": "piercing",
                 "properties": ["ammunition", "two_handed"]},
    "longbow": {"name": "Longbow", "type": "weapon", "value": 50,
                "damage": "1d8", "damage_type": "piercing",
                "properties": ["ammunition", "heavy", "two_handed"]},
    "quarterstaff": {"name": "Quarterstaff", "type": "weapon", "value": 1,
                     "damage": "1d6", "damage_type": "bludgeoning",
                     "properties": ["versatile"]},
}
