"""
Utility functions for Foundry VTT export.

Provides ID generation, HTML conversion, and dice parsing utilities.
"""

import hashlib
import re
from typing import Dict, List, Optional, Tuple


def generate_foundry_id(source_id: str, prefix: str = "") -> str:
    """
    Generate a deterministic 16-character ID for Foundry from our source ID.

    Foundry VTT uses 16-character alphanumeric IDs for documents.
    This generates consistent IDs so re-exports produce the same output.

    Args:
        source_id: Our internal ID (e.g., "goblin", "fire_bolt")
        prefix: Optional prefix for namespacing (e.g., "monster_", "spell_")

    Returns:
        16-character hexadecimal ID
    """
    combined = f"{prefix}{source_id}"
    hash_obj = hashlib.md5(combined.encode())
    return hash_obj.hexdigest()[:16]


def convert_to_html(text: str, convert_dice: bool = True) -> str:
    """
    Convert plain text description to HTML with Foundry roll syntax.

    Args:
        text: Plain text description
        convert_dice: If True, convert dice notation to Foundry roll syntax

    Returns:
        HTML-formatted text with Foundry roll syntax
    """
    if not text:
        return ""

    # Escape basic HTML characters
    html = text.replace("&", "&amp;")
    html = html.replace("<", "&lt;")
    html = html.replace(">", "&gt;")

    # Convert line breaks to HTML
    html = html.replace("\n\n", "</p><p>")
    html = html.replace("\n", "<br>")

    if convert_dice:
        # Convert dice notation to Foundry inline rolls
        # Pattern: Match dice like "2d6+4", "1d8", "3d10-2", etc.
        dice_pattern = r'(\d+d\d+(?:[+-]\d+)?)'
        html = re.sub(dice_pattern, r'[[/r \1]]', html)

    # Wrap in paragraph if not already
    if not html.startswith("<p>"):
        html = f"<p>{html}</p>"

    return html


def parse_damage_dice(description: str) -> List[Tuple[str, str]]:
    """
    Parse damage dice and types from an action description.

    Args:
        description: Action description text (e.g., "Hit: 7 (1d8+3) slashing damage")

    Returns:
        List of (dice_formula, damage_type) tuples
    """
    damages = []

    # Pattern: "(XdY+Z) <damage_type> damage" or just "XdY <damage_type> damage"
    pattern = r'(\d+)\s*\((\d+d\d+(?:[+-]\d+)?)\)\s+(\w+)\s+damage'

    for match in re.finditer(pattern, description.lower()):
        avg_damage, dice, damage_type = match.groups()
        damages.append((dice, damage_type))

    # Also check for simpler patterns without average
    simple_pattern = r'(\d+d\d+(?:[+-]\d+)?)\s+(\w+)\s+damage'
    for match in re.finditer(simple_pattern, description.lower()):
        dice, damage_type = match.groups()
        # Avoid duplicates
        if not any(d[0] == dice for d in damages):
            damages.append((dice, damage_type))

    return damages


def parse_attack_bonus(description: str) -> Optional[int]:
    """
    Parse attack bonus from an action description.

    Args:
        description: Action description text (e.g., "Melee Weapon Attack: +5 to hit")

    Returns:
        Attack bonus as integer, or None if not found
    """
    pattern = r'[+-](\d+)\s+to\s+hit'
    match = re.search(pattern, description.lower())
    if match:
        return int(match.group(1))
    return None


def parse_save_dc(description: str) -> Tuple[Optional[int], Optional[str]]:
    """
    Parse saving throw DC and ability from description.

    Args:
        description: Action description text (e.g., "DC 15 Constitution saving throw")

    Returns:
        Tuple of (DC, ability_abbreviation) or (None, None) if not found
    """
    pattern = r'dc\s+(\d+)\s+(strength|dexterity|constitution|intelligence|wisdom|charisma)'
    match = re.search(pattern, description.lower())
    if match:
        dc = int(match.group(1))
        ability_map = {
            "strength": "str",
            "dexterity": "dex",
            "constitution": "con",
            "intelligence": "int",
            "wisdom": "wis",
            "charisma": "cha"
        }
        ability = ability_map.get(match.group(2), "con")
        return dc, ability
    return None, None


def parse_reach_or_range(description: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Parse weapon reach or range from description.

    Args:
        description: Action description (e.g., "reach 10 ft." or "range 80/320 ft.")

    Returns:
        Tuple of (reach_or_normal_range, long_range) or (None, None) if not found
    """
    # Check for reach
    reach_pattern = r'reach\s+(\d+)\s*ft'
    reach_match = re.search(reach_pattern, description.lower())
    if reach_match:
        return int(reach_match.group(1)), None

    # Check for range
    range_pattern = r'range\s+(\d+)/(\d+)\s*ft'
    range_match = re.search(range_pattern, description.lower())
    if range_match:
        return int(range_match.group(1)), int(range_match.group(2))

    # Single range value
    single_range_pattern = r'range\s+(\d+)\s*ft'
    single_match = re.search(single_range_pattern, description.lower())
    if single_match:
        return int(single_match.group(1)), None

    return None, None


def parse_cr(cr_value) -> float:
    """
    Parse challenge rating to a float.

    Args:
        cr_value: CR as string (e.g., "1/4", "5") or number

    Returns:
        CR as float
    """
    if isinstance(cr_value, (int, float)):
        return float(cr_value)

    if isinstance(cr_value, str):
        cr_map = {
            "0": 0,
            "1/8": 0.125,
            "1/4": 0.25,
            "1/2": 0.5,
        }
        if cr_value in cr_map:
            return cr_map[cr_value]
        try:
            return float(cr_value)
        except ValueError:
            return 0

    return 0


def get_xp_for_cr(cr: float) -> int:
    """
    Get XP value for a challenge rating.

    Args:
        cr: Challenge rating as float

    Returns:
        XP value
    """
    xp_table = {
        0: 10, 0.125: 25, 0.25: 50, 0.5: 100,
        1: 200, 2: 450, 3: 700, 4: 1100, 5: 1800,
        6: 2300, 7: 2900, 8: 3900, 9: 5000, 10: 5900,
        11: 7200, 12: 8400, 13: 10000, 14: 11500, 15: 13000,
        16: 15000, 17: 18000, 18: 20000, 19: 22000, 20: 25000,
        21: 33000, 22: 41000, 23: 50000, 24: 62000, 25: 75000,
        26: 90000, 27: 105000, 28: 120000, 29: 135000, 30: 155000,
    }
    return xp_table.get(cr, 0)


# Foundry VTT size mappings
SIZE_MAP = {
    "tiny": "tiny",
    "small": "sm",
    "medium": "med",
    "large": "lg",
    "huge": "huge",
    "gargantuan": "grg",
}

# Token size scales (grid squares)
TOKEN_SIZE_SCALE = {
    "tiny": 0.5,
    "sm": 0.8,
    "med": 1,
    "lg": 2,
    "huge": 3,
    "grg": 4,
}

# Foundry school abbreviations
SCHOOL_MAP = {
    "abjuration": "abj",
    "conjuration": "con",
    "divination": "div",
    "enchantment": "enc",
    "evocation": "evo",
    "illusion": "ill",
    "necromancy": "nec",
    "transmutation": "trs",
}

# Damage type mappings (our format to Foundry)
DAMAGE_TYPE_MAP = {
    "acid": "acid",
    "bludgeoning": "bludgeoning",
    "cold": "cold",
    "fire": "fire",
    "force": "force",
    "lightning": "lightning",
    "necrotic": "necrotic",
    "piercing": "piercing",
    "poison": "poison",
    "psychic": "psychic",
    "radiant": "radiant",
    "slashing": "slashing",
    "thunder": "thunder",
}
