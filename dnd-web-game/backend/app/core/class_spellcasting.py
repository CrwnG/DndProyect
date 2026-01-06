"""
D&D 5e 2024 Class Spellcasting Configuration.

Provides class-specific spell slot tables, cantrip progression,
spellcasting abilities, and preparation formulas.
"""
from typing import Dict, List, Optional
from app.models.spells import SpellcastingType


# Spellcasting class configurations
SPELLCASTING_CLASSES = {
    "wizard": {
        "ability": "intelligence",
        "type": SpellcastingType.PREPARED,
        "has_spellbook": True,
        "ritual_casting": True,
        "prepared_formula": "int_mod + wizard_level",
        "starts_at_level": 1,
    },
    "cleric": {
        "ability": "wisdom",
        "type": SpellcastingType.PREPARED,
        "ritual_casting": True,
        "prepared_formula": "wis_mod + cleric_level",
        "has_domain_spells": True,
        "starts_at_level": 1,
    },
    "druid": {
        "ability": "wisdom",
        "type": SpellcastingType.PREPARED,
        "ritual_casting": True,
        "prepared_formula": "wis_mod + druid_level",
        "starts_at_level": 1,
    },
    "paladin": {
        "ability": "charisma",
        "type": SpellcastingType.PREPARED,
        "prepared_formula": "cha_mod + half_paladin_level",
        "starts_at_level": 2,
        "half_caster": True,
    },
    "bard": {
        "ability": "charisma",
        "type": SpellcastingType.KNOWN,
        "ritual_casting": True,
        "starts_at_level": 1,
    },
    "sorcerer": {
        "ability": "charisma",
        "type": SpellcastingType.KNOWN,
        "starts_at_level": 1,
    },
    "ranger": {
        "ability": "wisdom",
        "type": SpellcastingType.KNOWN,
        "starts_at_level": 2,
        "half_caster": True,
    },
    "warlock": {
        "ability": "charisma",
        "type": SpellcastingType.PACT_MAGIC,
        "short_rest_recovery": True,
        "starts_at_level": 1,
    },
    "artificer": {
        "ability": "intelligence",
        "type": SpellcastingType.PREPARED,
        "ritual_casting": True,
        "prepared_formula": "int_mod + half_artificer_level",
        "starts_at_level": 1,
        "half_caster": True,
    },
}

# Full caster spell slot progression (Wizard, Cleric, Druid, Bard, Sorcerer)
FULL_CASTER_SLOTS = {
    1: {1: 2},
    2: {1: 3},
    3: {1: 4, 2: 2},
    4: {1: 4, 2: 3},
    5: {1: 4, 2: 3, 3: 2},
    6: {1: 4, 2: 3, 3: 3},
    7: {1: 4, 2: 3, 3: 3, 4: 1},
    8: {1: 4, 2: 3, 3: 3, 4: 2},
    9: {1: 4, 2: 3, 3: 3, 4: 3, 5: 1},
    10: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2},
    11: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1},
    12: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1},
    13: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1},
    14: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1},
    15: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1},
    16: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1},
    17: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1, 9: 1},
    18: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 1, 7: 1, 8: 1, 9: 1},
    19: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 2, 7: 1, 8: 1, 9: 1},
    20: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 2, 7: 2, 8: 1, 9: 1},
}

# Half caster spell slot progression (Paladin, Ranger, Artificer)
HALF_CASTER_SLOTS = {
    1: {},
    2: {1: 2},
    3: {1: 3},
    4: {1: 3},
    5: {1: 4, 2: 2},
    6: {1: 4, 2: 2},
    7: {1: 4, 2: 3},
    8: {1: 4, 2: 3},
    9: {1: 4, 2: 3, 3: 2},
    10: {1: 4, 2: 3, 3: 2},
    11: {1: 4, 2: 3, 3: 3},
    12: {1: 4, 2: 3, 3: 3},
    13: {1: 4, 2: 3, 3: 3, 4: 1},
    14: {1: 4, 2: 3, 3: 3, 4: 1},
    15: {1: 4, 2: 3, 3: 3, 4: 2},
    16: {1: 4, 2: 3, 3: 3, 4: 2},
    17: {1: 4, 2: 3, 3: 3, 4: 3, 5: 1},
    18: {1: 4, 2: 3, 3: 3, 4: 3, 5: 1},
    19: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2},
    20: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2},
}

# Warlock Pact Magic slots
WARLOCK_PACT_SLOTS = {
    1: {"slots": 1, "level": 1},
    2: {"slots": 2, "level": 1},
    3: {"slots": 2, "level": 2},
    4: {"slots": 2, "level": 2},
    5: {"slots": 2, "level": 3},
    6: {"slots": 2, "level": 3},
    7: {"slots": 2, "level": 4},
    8: {"slots": 2, "level": 4},
    9: {"slots": 2, "level": 5},
    10: {"slots": 2, "level": 5},
    11: {"slots": 3, "level": 5},
    12: {"slots": 3, "level": 5},
    13: {"slots": 3, "level": 5},
    14: {"slots": 3, "level": 5},
    15: {"slots": 3, "level": 5},
    16: {"slots": 3, "level": 5},
    17: {"slots": 4, "level": 5},
    18: {"slots": 4, "level": 5},
    19: {"slots": 4, "level": 5},
    20: {"slots": 4, "level": 5},
}

# Cantrips known progression
CANTRIPS_KNOWN = {
    "wizard": {1: 3, 4: 4, 10: 5},
    "cleric": {1: 3, 4: 4, 10: 5},
    "druid": {1: 2, 4: 3, 10: 4},
    "bard": {1: 2, 4: 3, 10: 4},
    "sorcerer": {1: 4, 4: 5, 10: 6},
    "warlock": {1: 2, 4: 3, 10: 4},
    "artificer": {1: 2, 10: 3, 14: 4},
}

# Spells known for "known" casters
SPELLS_KNOWN = {
    "bard": {
        1: 4, 2: 5, 3: 6, 4: 7, 5: 8, 6: 9, 7: 10, 8: 11, 9: 12,
        10: 14, 11: 15, 12: 15, 13: 16, 14: 18, 15: 19, 16: 19,
        17: 20, 18: 22, 19: 22, 20: 22
    },
    "sorcerer": {
        1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7, 7: 8, 8: 9, 9: 10,
        10: 11, 11: 12, 12: 12, 13: 13, 14: 13, 15: 14, 16: 14,
        17: 15, 18: 15, 19: 15, 20: 15
    },
    "ranger": {
        2: 2, 3: 3, 4: 3, 5: 4, 6: 4, 7: 5, 8: 5, 9: 6, 10: 6,
        11: 7, 12: 7, 13: 8, 14: 8, 15: 9, 16: 9, 17: 10, 18: 10,
        19: 11, 20: 11
    },
    "warlock": {
        1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7, 7: 8, 8: 9,
        9: 10, 10: 10, 11: 11, 12: 11, 13: 12, 14: 12, 15: 13,
        16: 13, 17: 14, 18: 14, 19: 15, 20: 15
    },
}


def get_spellcasting_ability(class_name: str) -> str:
    """Get the spellcasting ability for a class."""
    config = SPELLCASTING_CLASSES.get(class_name.lower(), {})
    return config.get("ability", "intelligence")


def get_spellcasting_type(class_name: str) -> SpellcastingType:
    """Get the spellcasting type for a class."""
    config = SPELLCASTING_CLASSES.get(class_name.lower(), {})
    return config.get("type", SpellcastingType.PREPARED)


def is_spellcasting_class(class_name: str) -> bool:
    """Check if a class has spellcasting."""
    return class_name.lower() in SPELLCASTING_CLASSES


def get_spellcasting_start_level(class_name: str) -> int:
    """Get the level at which a class gains spellcasting."""
    config = SPELLCASTING_CLASSES.get(class_name.lower(), {})
    return config.get("starts_at_level", 1)


def get_spell_slots_for_level(class_name: str, level: int) -> Dict[int, int]:
    """
    Get spell slots for a class at a given level.

    Returns dict of {spell_level: num_slots}
    """
    class_lower = class_name.lower()

    if class_lower not in SPELLCASTING_CLASSES:
        return {}

    config = SPELLCASTING_CLASSES[class_lower]
    starts_at = config.get("starts_at_level", 1)

    if level < starts_at:
        return {}

    # Warlock uses Pact Magic
    if class_lower == "warlock":
        pact_data = WARLOCK_PACT_SLOTS.get(level, {"slots": 0, "level": 1})
        slot_level = pact_data["level"]
        num_slots = pact_data["slots"]
        return {slot_level: num_slots} if num_slots > 0 else {}

    # Half casters
    if config.get("half_caster"):
        return HALF_CASTER_SLOTS.get(level, {}).copy()

    # Full casters
    return FULL_CASTER_SLOTS.get(level, {}).copy()


def get_max_prepared_spells(class_name: str, level: int, ability_mod: int) -> int:
    """
    Calculate max number of prepared spells for a class.

    For known casters, returns the number of known spells instead.
    """
    class_lower = class_name.lower()

    if class_lower not in SPELLCASTING_CLASSES:
        return 0

    config = SPELLCASTING_CLASSES[class_lower]
    starts_at = config.get("starts_at_level", 1)

    if level < starts_at:
        return 0

    # Known casters use spells known table
    spell_type = config.get("type")
    if spell_type in [SpellcastingType.KNOWN, SpellcastingType.PACT_MAGIC]:
        known_table = SPELLS_KNOWN.get(class_lower, {})
        for lvl in range(level, 0, -1):
            if lvl in known_table:
                return known_table[lvl]
        return 0

    # Prepared casters use formulas
    formula = config.get("prepared_formula", "")

    if "half" in formula:
        # Half level + ability mod
        return max(1, (level // 2) + ability_mod)
    else:
        # Full level + ability mod
        return max(1, level + ability_mod)


def get_cantrips_known(class_name: str, level: int) -> int:
    """Get number of cantrips known at a given level."""
    class_lower = class_name.lower()

    if class_lower not in CANTRIPS_KNOWN:
        return 0

    cantrip_table = CANTRIPS_KNOWN[class_lower]
    known = 0

    for req_level, count in sorted(cantrip_table.items()):
        if level >= req_level:
            known = count

    return known


def get_max_spell_level(class_name: str, level: int) -> int:
    """Get the maximum spell level a class can cast at a given level."""
    slots = get_spell_slots_for_level(class_name, level)
    if not slots:
        return 0
    return max(slots.keys())


def can_ritual_cast(class_name: str) -> bool:
    """Check if a class can cast ritual spells."""
    config = SPELLCASTING_CLASSES.get(class_name.lower(), {})
    return config.get("ritual_casting", False)


def has_spellbook(class_name: str) -> bool:
    """Check if a class uses a spellbook."""
    config = SPELLCASTING_CLASSES.get(class_name.lower(), {})
    return config.get("has_spellbook", False)


def get_warlock_pact_slots(level: int) -> Dict[str, int]:
    """Get Warlock's pact magic slot info."""
    pact_data = WARLOCK_PACT_SLOTS.get(level, {"slots": 0, "level": 1})
    return {
        "slots": pact_data["slots"],
        "slot_level": pact_data["level"]
    }


def get_spellcasting_summary(class_name: str, level: int, ability_mod: int) -> Dict:
    """
    Get a complete spellcasting summary for a class at a level.

    Returns dict with all spellcasting info.
    """
    class_lower = class_name.lower()

    if not is_spellcasting_class(class_lower):
        return {"has_spellcasting": False}

    config = SPELLCASTING_CLASSES[class_lower]
    starts_at = config.get("starts_at_level", 1)

    if level < starts_at:
        return {
            "has_spellcasting": True,
            "unlocks_at": starts_at,
            "ability": config.get("ability"),
        }

    prof_bonus = 2 + ((level - 1) // 4)

    return {
        "has_spellcasting": True,
        "ability": config.get("ability"),
        "spell_save_dc": 8 + prof_bonus + ability_mod,
        "spell_attack_bonus": prof_bonus + ability_mod,
        "type": config.get("type", SpellcastingType.PREPARED).value,
        "spell_slots": get_spell_slots_for_level(class_lower, level),
        "cantrips_known": get_cantrips_known(class_lower, level),
        "max_prepared": get_max_prepared_spells(class_lower, level, ability_mod),
        "max_spell_level": get_max_spell_level(class_lower, level),
        "ritual_casting": config.get("ritual_casting", False),
        "has_spellbook": config.get("has_spellbook", False),
    }


# =============================================================================
# MULTICLASS SPELLCASTING
# =============================================================================

# Multiclass spellcaster categories
FULL_CASTER_CLASSES = {"wizard", "cleric", "druid", "bard", "sorcerer"}
HALF_CASTER_CLASSES = {"paladin", "ranger", "artificer"}
THIRD_CASTER_SUBCLASSES = {
    "fighter": ["eldritch_knight"],
    "rogue": ["arcane_trickster"],
}


def get_caster_level_contribution(class_name: str, class_level: int, subclass: Optional[str] = None) -> float:
    """
    Get the caster level contribution for a class.

    D&D 5e 2024 Multiclass Spellcasting Rules:
    - Full casters: add class level
    - Half casters: add class level / 2 (round down)
    - Third casters (Eldritch Knight, Arcane Trickster): add class level / 3 (round down)
    - Warlocks: 0 (Pact Magic is separate)

    Args:
        class_name: The class name
        class_level: Levels in this class
        subclass: Optional subclass name

    Returns:
        Caster level contribution (can be fractional for calculation, but will be floored)
    """
    class_lower = class_name.lower()

    # Warlocks use Pact Magic, not regular spell slots
    if class_lower == "warlock":
        return 0

    # Check if not a spellcasting class
    if class_lower not in SPELLCASTING_CLASSES:
        # Check for third-caster subclass (Eldritch Knight, Arcane Trickster)
        if class_lower in THIRD_CASTER_SUBCLASSES:
            subclass_lower = (subclass or "").lower().replace(" ", "_").replace("-", "_")
            if subclass_lower in THIRD_CASTER_SUBCLASSES[class_lower]:
                # Third casters contribute 1/3 of their level, but only from level 3+
                if class_level >= 3:
                    return class_level / 3
        return 0

    config = SPELLCASTING_CLASSES[class_lower]
    starts_at = config.get("starts_at_level", 1)

    # Class hasn't unlocked spellcasting yet
    if class_level < starts_at:
        return 0

    # Full casters
    if class_lower in FULL_CASTER_CLASSES:
        return class_level

    # Half casters
    if config.get("half_caster") or class_lower in HALF_CASTER_CLASSES:
        return class_level / 2

    # Default: treat as full caster if it has spellcasting
    return class_level


def get_multiclass_caster_level(class_levels: Dict[str, int], subclasses: Optional[Dict[str, str]] = None) -> int:
    """
    Calculate the combined caster level for a multiclass character.

    This is used to determine spell slots from the multiclass spellcaster table.
    Warlock Pact Magic is NOT included - it's tracked separately.

    Args:
        class_levels: Dict of class_name -> level
        subclasses: Optional dict of class_name -> subclass_name

    Returns:
        Combined caster level (rounded down)
    """
    subclasses = subclasses or {}
    total_contribution = 0

    for class_name, level in class_levels.items():
        subclass = subclasses.get(class_name.lower())
        contribution = get_caster_level_contribution(class_name, level, subclass)
        total_contribution += contribution

    return int(total_contribution)


def get_multiclass_spell_slots(class_levels: Dict[str, int], subclasses: Optional[Dict[str, str]] = None) -> Dict[int, int]:
    """
    Get spell slots for a multiclass character.

    Uses the Multiclass Spellcaster table from D&D 5e 2024.
    Warlock Pact Magic slots are separate.

    Args:
        class_levels: Dict of class_name -> level
        subclasses: Optional dict of class_name -> subclass_name

    Returns:
        Dict of {spell_level: num_slots}
    """
    caster_level = get_multiclass_caster_level(class_levels, subclasses)

    if caster_level == 0:
        return {}

    # Use the full caster table with the combined caster level
    return FULL_CASTER_SLOTS.get(caster_level, {}).copy()


def get_multiclass_pact_magic(class_levels: Dict[str, int]) -> Dict[str, int]:
    """
    Get Warlock Pact Magic slots (separate from multiclass spell slots).

    Args:
        class_levels: Dict of class_name -> level

    Returns:
        Dict with slots, slot_level, or empty if no Warlock levels
    """
    warlock_level = class_levels.get("warlock", 0)
    if warlock_level == 0:
        return {}

    return get_warlock_pact_slots(warlock_level)


def get_multiclass_spellcasting_summary(
    class_levels: Dict[str, int],
    ability_scores: Dict[str, int],
    subclasses: Optional[Dict[str, str]] = None,
    total_level: Optional[int] = None
) -> Dict:
    """
    Get a complete multiclass spellcasting summary.

    Args:
        class_levels: Dict of class_name -> level
        ability_scores: Dict of ability_name -> score
        subclasses: Optional dict of class_name -> subclass
        total_level: Optional total character level (for proficiency)

    Returns:
        Comprehensive spellcasting info for multiclass character
    """
    subclasses = subclasses or {}

    if total_level is None:
        total_level = sum(class_levels.values())

    prof_bonus = 2 + ((total_level - 1) // 4)

    # Get combined caster level and slots
    caster_level = get_multiclass_caster_level(class_levels, subclasses)
    spell_slots = get_multiclass_spell_slots(class_levels, subclasses)

    # Get Pact Magic separately
    pact_magic = get_multiclass_pact_magic(class_levels)

    # Determine spellcasting abilities for each class
    spellcasting_abilities = {}
    cantrips_by_class = {}
    max_prepared_by_class = {}

    for class_name, level in class_levels.items():
        class_lower = class_name.lower()

        if is_spellcasting_class(class_lower):
            config = SPELLCASTING_CLASSES[class_lower]
            ability = config.get("ability", "intelligence")
            spellcasting_abilities[class_name] = ability

            # Get ability modifier
            ability_score = ability_scores.get(ability, 10)
            ability_mod = (ability_score - 10) // 2

            # Cantrips known (per class, not combined)
            cantrips = get_cantrips_known(class_lower, level)
            if cantrips > 0:
                cantrips_by_class[class_name] = cantrips

            # Prepared spells (per class for prepared casters)
            max_prep = get_max_prepared_spells(class_lower, level, ability_mod)
            if max_prep > 0:
                max_prepared_by_class[class_name] = max_prep

    # Check for third-caster subclasses
    for class_name, level in class_levels.items():
        class_lower = class_name.lower()
        subclass = subclasses.get(class_lower, "")

        if class_lower in THIRD_CASTER_SUBCLASSES:
            subclass_lower = subclass.lower().replace(" ", "_").replace("-", "_")
            if subclass_lower in THIRD_CASTER_SUBCLASSES[class_lower]:
                # Third caster has INT as spellcasting ability
                spellcasting_abilities[class_name] = "intelligence"

    has_spellcasting = caster_level > 0 or bool(pact_magic)

    result = {
        "has_spellcasting": has_spellcasting,
        "is_multiclass": len(class_levels) > 1,
        "caster_level": caster_level,
        "spell_slots": spell_slots,
        "max_spell_level": max(spell_slots.keys()) if spell_slots else 0,
        "spellcasting_abilities": spellcasting_abilities,
        "cantrips_by_class": cantrips_by_class,
        "total_cantrips": sum(cantrips_by_class.values()),
        "max_prepared_by_class": max_prepared_by_class,
        "proficiency_bonus": prof_bonus,
    }

    # Add Pact Magic if Warlock levels
    if pact_magic:
        result["pact_magic"] = pact_magic
        result["has_pact_magic"] = True
    else:
        result["has_pact_magic"] = False

    # Calculate spell save DCs and attack bonuses for each class
    spell_dcs = {}
    spell_attacks = {}
    for class_name, ability in spellcasting_abilities.items():
        ability_score = ability_scores.get(ability, 10)
        ability_mod = (ability_score - 10) // 2
        spell_dcs[class_name] = 8 + prof_bonus + ability_mod
        spell_attacks[class_name] = prof_bonus + ability_mod

    result["spell_save_dcs"] = spell_dcs
    result["spell_attack_bonuses"] = spell_attacks

    return result


def can_cast_spell_level(
    class_levels: Dict[str, int],
    spell_level: int,
    subclasses: Optional[Dict[str, str]] = None
) -> bool:
    """
    Check if a multiclass character can cast spells of a given level.

    Note: This checks slot availability, not spell knowledge!

    Args:
        class_levels: Dict of class_name -> level
        spell_level: The spell level to check
        subclasses: Optional dict of class_name -> subclass

    Returns:
        True if the character has slots of this level
    """
    # Check multiclass spell slots
    slots = get_multiclass_spell_slots(class_levels, subclasses)
    if spell_level in slots and slots[spell_level] > 0:
        return True

    # Check Pact Magic
    pact = get_multiclass_pact_magic(class_levels)
    if pact and pact.get("slot_level", 0) >= spell_level:
        return True

    return False


def get_max_learnable_spell_level(
    class_name: str,
    class_level: int,
    subclass: Optional[str] = None
) -> int:
    """
    Get the maximum spell level a class can learn/prepare at a given class level.

    This is different from slot level - you learn spells based on your
    individual class level, not your combined caster level.

    Args:
        class_name: The class name
        class_level: Levels in this specific class
        subclass: Optional subclass name

    Returns:
        Maximum spell level that can be learned/prepared
    """
    class_lower = class_name.lower()

    # Non-spellcasting classes
    if class_lower not in SPELLCASTING_CLASSES:
        # Check third-caster subclass
        if class_lower in THIRD_CASTER_SUBCLASSES:
            subclass_lower = (subclass or "").lower().replace(" ", "_").replace("-", "_")
            if subclass_lower in THIRD_CASTER_SUBCLASSES[class_lower]:
                # Third casters learn spells at: 3rd=1st, 7th=2nd, 13th=3rd, 19th=4th
                if class_level >= 19:
                    return 4
                elif class_level >= 13:
                    return 3
                elif class_level >= 7:
                    return 2
                elif class_level >= 3:
                    return 1
        return 0

    # Get single-class spell slots and find max level
    slots = get_spell_slots_for_level(class_lower, class_level)
    if not slots:
        return 0

    return max(slots.keys())
