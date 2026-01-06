"""
D&D 5e Rules Engine.

Handles core game mechanics:
- Attack resolution (roll vs AC)
- Damage calculation
- Ability score modifiers
- Armor class calculation
- Saving throws
- Proficiency bonuses
"""
from dataclasses import dataclass
from typing import Optional, List
from enum import Enum

from app.core.dice import roll_d20, roll_damage, D20Result, DamageResult


class DamageType(Enum):
    """Damage types in D&D 5e."""
    SLASHING = "slashing"
    PIERCING = "piercing"
    BLUDGEONING = "bludgeoning"
    FIRE = "fire"
    COLD = "cold"
    LIGHTNING = "lightning"
    THUNDER = "thunder"
    ACID = "acid"
    POISON = "poison"
    NECROTIC = "necrotic"
    RADIANT = "radiant"
    FORCE = "force"
    PSYCHIC = "psychic"


class AbilityScore(Enum):
    """The six ability scores."""
    STRENGTH = "strength"
    DEXTERITY = "dexterity"
    CONSTITUTION = "constitution"
    INTELLIGENCE = "intelligence"
    WISDOM = "wisdom"
    CHARISMA = "charisma"


@dataclass
class AttackResult:
    """Complete result of an attack roll."""
    hit: bool
    critical_hit: bool
    critical_miss: bool
    attack_roll: D20Result
    target_ac: int
    damage: Optional[DamageResult] = None
    damage_type: Optional[DamageType] = None

    @property
    def total_damage(self) -> int:
        """Get total damage dealt (0 if miss)."""
        if self.hit and self.damage:
            return self.damage.total
        return 0


@dataclass
class SavingThrowResult:
    """Result of a saving throw."""
    success: bool
    roll: D20Result
    dc: int
    half_damage_on_save: bool = False


def calculate_ability_modifier(score: int) -> int:
    """
    Calculate ability modifier from ability score.

    The modifier is (score - 10) // 2.
    Examples: 10 -> +0, 14 -> +2, 8 -> -1, 20 -> +5

    Args:
        score: Ability score (typically 1-20, can be higher with magic)

    Returns:
        Ability modifier (can be negative)
    """
    return (score - 10) // 2


def calculate_proficiency_bonus(level: int) -> int:
    """
    Calculate proficiency bonus from character level.

    Level 1-4: +2
    Level 5-8: +3
    Level 9-12: +4
    Level 13-16: +5
    Level 17-20: +6

    Args:
        level: Character level (1-20)

    Returns:
        Proficiency bonus
    """
    if level < 1:
        return 2
    return 2 + (level - 1) // 4


def calculate_ac(
    base_ac: int = 10,
    dex_modifier: int = 0,
    armor_bonus: int = 0,
    shield_bonus: int = 0,
    other_bonuses: int = 0,
    max_dex_bonus: Optional[int] = None
) -> int:
    """
    Calculate Armor Class.

    Args:
        base_ac: Base AC (10 for unarmored, or armor's base AC)
        dex_modifier: Character's DEX modifier
        armor_bonus: Bonus from armor type (if not using base_ac)
        shield_bonus: Bonus from shield (typically +2)
        other_bonuses: Other AC bonuses (magic items, spells, etc.)
        max_dex_bonus: Maximum DEX bonus allowed by armor (None = unlimited)

    Returns:
        Total Armor Class
    """
    # Apply max DEX bonus if armor limits it
    effective_dex = dex_modifier
    if max_dex_bonus is not None:
        effective_dex = min(dex_modifier, max_dex_bonus)

    return base_ac + effective_dex + armor_bonus + shield_bonus + other_bonuses


def resolve_attack(
    attack_bonus: int,
    target_ac: int,
    damage_dice: str,
    damage_modifier: int = 0,
    damage_type: DamageType = DamageType.SLASHING,
    advantage: bool = False,
    disadvantage: bool = False,
    attacker_is_player: bool = True,
    crit_range: int = 20,
    auto_crit: bool = False
) -> AttackResult:
    """
    Resolve a complete attack action.

    Args:
        attack_bonus: Total attack bonus (ability + proficiency + other)
        target_ac: Target's Armor Class
        damage_dice: Damage dice notation (e.g., "1d8", "2d6")
        damage_modifier: Bonus damage (usually ability modifier)
        damage_type: Type of damage dealt
        advantage: Attack with advantage
        disadvantage: Attack with disadvantage
        attacker_is_player: True if attacker is a player (for 2024 crit rules)
        crit_range: Minimum roll for critical hit (default 20, Champion gets 19 or 18)
        auto_crit: Auto-critical on hit (e.g., Assassinate against surprised targets)

    Returns:
        Complete AttackResult with hit/miss and damage
    """
    # Roll the attack
    attack_roll = roll_d20(
        modifier=attack_bonus,
        advantage=advantage,
        disadvantage=disadvantage
    )

    # Check for critical hit (natural 20 always hits, or expanded crit range for Champion)
    is_crit_roll = attack_roll.natural_20 or (attack_roll.base_roll >= crit_range and crit_range < 20)
    if is_crit_roll:
        # 2024 Rule: Only PLAYERS deal extra damage on critical hits
        # Monsters still hit on nat 20, but deal normal damage
        from app.core.rules_config import is_player_only_crits

        is_full_crit = True
        if is_player_only_crits() and not attacker_is_player:
            # Monster nat 20: hits but deals normal damage
            is_full_crit = False

        damage = roll_damage(damage_dice, modifier=damage_modifier, critical=is_full_crit)
        return AttackResult(
            hit=True,
            critical_hit=is_full_crit,  # Only true crit if player OR using 2014 rules
            critical_miss=False,
            attack_roll=attack_roll,
            target_ac=target_ac,
            damage=damage,
            damage_type=damage_type
        )

    # Check for critical miss (natural 1 always misses)
    if attack_roll.natural_1:
        return AttackResult(
            hit=False,
            critical_hit=False,
            critical_miss=True,
            attack_roll=attack_roll,
            target_ac=target_ac
        )

    # Normal hit/miss check
    hit = attack_roll.total >= target_ac

    damage = None
    is_critical = False
    if hit:
        # Check for auto-crit (e.g., Assassinate against surprised targets)
        if auto_crit:
            is_critical = True
            damage = roll_damage(damage_dice, modifier=damage_modifier, critical=True)
        else:
            damage = roll_damage(damage_dice, modifier=damage_modifier, critical=False)

    return AttackResult(
        hit=hit,
        critical_hit=is_critical,
        critical_miss=False,
        attack_roll=attack_roll,
        target_ac=target_ac,
        damage=damage,
        damage_type=damage_type if hit else None
    )


def resolve_saving_throw(
    save_modifier: int,
    dc: int,
    advantage: bool = False,
    disadvantage: bool = False,
    auto_fail: bool = False,
    auto_succeed: bool = False
) -> SavingThrowResult:
    """
    Resolve a saving throw.

    Args:
        save_modifier: Total saving throw modifier (ability + proficiency if proficient)
        dc: Difficulty Class to beat
        advantage: Roll with advantage
        disadvantage: Roll with disadvantage
        auto_fail: Automatically fail (e.g., stunned condition for STR/DEX saves)
        auto_succeed: Automatically succeed (e.g., certain immunities)

    Returns:
        SavingThrowResult with success/failure and roll details
    """
    if auto_fail:
        # Create a fake roll showing failure
        roll = D20Result(rolls=[1], modifier=save_modifier, total=1 + save_modifier)
        return SavingThrowResult(success=False, roll=roll, dc=dc)

    if auto_succeed:
        roll = D20Result(rolls=[20], modifier=save_modifier, total=20 + save_modifier)
        return SavingThrowResult(success=True, roll=roll, dc=dc)

    roll = roll_d20(modifier=save_modifier, advantage=advantage, disadvantage=disadvantage)
    success = roll.total >= dc

    return SavingThrowResult(success=success, roll=roll, dc=dc)


def calculate_spell_save_dc(
    spellcasting_ability_modifier: int,
    proficiency_bonus: int
) -> int:
    """
    Calculate spell save DC.

    DC = 8 + proficiency bonus + spellcasting ability modifier

    Args:
        spellcasting_ability_modifier: Modifier for spellcasting ability (INT/WIS/CHA)
        proficiency_bonus: Character's proficiency bonus

    Returns:
        Spell save DC
    """
    return 8 + proficiency_bonus + spellcasting_ability_modifier


def calculate_spell_attack_bonus(
    spellcasting_ability_modifier: int,
    proficiency_bonus: int
) -> int:
    """
    Calculate spell attack bonus.

    Bonus = proficiency bonus + spellcasting ability modifier

    Args:
        spellcasting_ability_modifier: Modifier for spellcasting ability (INT/WIS/CHA)
        proficiency_bonus: Character's proficiency bonus

    Returns:
        Spell attack bonus
    """
    return proficiency_bonus + spellcasting_ability_modifier


def apply_damage(
    current_hp: int,
    max_hp: int,
    damage: int,
    resistance: bool = False,
    vulnerability: bool = False,
    immunity: bool = False
) -> tuple[int, int, bool]:
    """
    Apply damage to a creature.

    Args:
        current_hp: Current hit points
        max_hp: Maximum hit points
        damage: Damage to apply
        resistance: Creature has resistance (half damage)
        vulnerability: Creature has vulnerability (double damage)
        immunity: Creature is immune (no damage)

    Returns:
        Tuple of (new_hp, actual_damage_taken, is_unconscious)
    """
    if immunity:
        return current_hp, 0, False

    actual_damage = damage

    if resistance and vulnerability:
        # Cancel out
        pass
    elif resistance:
        actual_damage = damage // 2
    elif vulnerability:
        actual_damage = damage * 2

    new_hp = max(0, current_hp - actual_damage)
    is_unconscious = new_hp == 0

    return new_hp, actual_damage, is_unconscious


def apply_healing(current_hp: int, max_hp: int, healing: int) -> tuple[int, int]:
    """
    Apply healing to a creature.

    Args:
        current_hp: Current hit points
        max_hp: Maximum hit points
        healing: Amount of healing

    Returns:
        Tuple of (new_hp, actual_healing_received)
    """
    new_hp = min(max_hp, current_hp + healing)
    actual_healing = new_hp - current_hp
    return new_hp, actual_healing


def calculate_melee_attack_bonus(
    strength_modifier: int,
    proficiency_bonus: int,
    is_proficient: bool = True,
    is_finesse: bool = False,
    dexterity_modifier: int = 0,
    other_bonuses: int = 0
) -> int:
    """
    Calculate melee attack bonus.

    Args:
        strength_modifier: STR modifier
        proficiency_bonus: Proficiency bonus
        is_proficient: Whether proficient with the weapon
        is_finesse: If True, can use DEX instead of STR
        dexterity_modifier: DEX modifier (for finesse weapons)
        other_bonuses: Magic weapon bonus, etc.

    Returns:
        Total attack bonus
    """
    # For finesse weapons, use the higher of STR or DEX
    ability_mod = strength_modifier
    if is_finesse:
        ability_mod = max(strength_modifier, dexterity_modifier)

    prof = proficiency_bonus if is_proficient else 0

    return ability_mod + prof + other_bonuses


def calculate_ranged_attack_bonus(
    dexterity_modifier: int,
    proficiency_bonus: int,
    is_proficient: bool = True,
    other_bonuses: int = 0
) -> int:
    """
    Calculate ranged attack bonus.

    Args:
        dexterity_modifier: DEX modifier
        proficiency_bonus: Proficiency bonus
        is_proficient: Whether proficient with the weapon
        other_bonuses: Magic weapon bonus, etc.

    Returns:
        Total attack bonus
    """
    prof = proficiency_bonus if is_proficient else 0
    return dexterity_modifier + prof + other_bonuses


def parse_armor_class_string(armor_class_str: str) -> dict:
    """
    Parse D&D armor class strings into numeric values.

    D&D 5e armor AC formats:
    - Light armor: "11 + Dex modifier" → base_ac=11, max_dex_bonus=None (full DEX)
    - Medium armor: "12 + Dex modifier (max 2)" → base_ac=12, max_dex_bonus=2
    - Heavy armor: "14" or "16" → base_ac=14/16, max_dex_bonus=0 (no DEX)
    - Shield: "+2" → bonus_ac=2, is_shield=True

    Args:
        armor_class_str: The armor class string from the data file

    Returns:
        Dict with parsed values:
        - base_ac: Base armor class (int)
        - max_dex_bonus: Maximum DEX bonus allowed (None=unlimited, 0=no DEX)
        - is_shield: True if this is a shield bonus
    """
    import re

    if not armor_class_str:
        return {"base_ac": 10, "max_dex_bonus": None, "is_shield": False}

    armor_class_str = str(armor_class_str).strip()

    # Shield: "+2"
    if armor_class_str.startswith("+"):
        try:
            bonus = int(armor_class_str)
            return {"base_ac": bonus, "max_dex_bonus": None, "is_shield": True}
        except ValueError:
            return {"base_ac": 2, "max_dex_bonus": None, "is_shield": True}

    # Pure number (heavy armor): "14", "16", "18"
    if armor_class_str.isdigit():
        return {"base_ac": int(armor_class_str), "max_dex_bonus": 0, "is_shield": False}

    # Medium armor: "12 + Dex modifier (max 2)"
    max_pattern = r"(\d+)\s*\+\s*Dex\s+modifier\s*\(max\s*(\d+)\)"
    max_match = re.match(max_pattern, armor_class_str, re.IGNORECASE)
    if max_match:
        base_ac = int(max_match.group(1))
        max_dex = int(max_match.group(2))
        return {"base_ac": base_ac, "max_dex_bonus": max_dex, "is_shield": False}

    # Light armor: "11 + Dex modifier"
    dex_pattern = r"(\d+)\s*\+\s*Dex\s+modifier"
    dex_match = re.match(dex_pattern, armor_class_str, re.IGNORECASE)
    if dex_match:
        base_ac = int(dex_match.group(1))
        return {"base_ac": base_ac, "max_dex_bonus": None, "is_shield": False}

    # Fallback: try to extract first number
    numbers = re.findall(r"\d+", armor_class_str)
    if numbers:
        return {"base_ac": int(numbers[0]), "max_dex_bonus": None, "is_shield": False}

    # Default
    return {"base_ac": 10, "max_dex_bonus": None, "is_shield": False}


def is_in_range(
    attacker_x: int,
    attacker_y: int,
    target_x: int,
    target_y: int,
    weapon_range: int,
    feet_per_square: int = 5
) -> tuple[bool, bool]:
    """
    Check if target is within weapon range.

    Args:
        attacker_x, attacker_y: Attacker's grid position
        target_x, target_y: Target's grid position
        weapon_range: Weapon's range in feet
        feet_per_square: Feet per grid square (default 5)

    Returns:
        Tuple of (in_normal_range, in_long_range)
        For melee (5ft range): (True, False) if adjacent, (False, False) otherwise
    """
    # Calculate distance using Chebyshev distance (D&D diagonal movement)
    dx = abs(attacker_x - target_x)
    dy = abs(attacker_y - target_y)
    distance_squares = max(dx, dy)
    distance_feet = distance_squares * feet_per_square

    in_normal_range = distance_feet <= weapon_range

    # For ranged weapons, long range is typically 4x normal range
    # (e.g., shortbow 80/320, longbow 150/600)
    # This is simplified - actual weapons have specific long ranges
    in_long_range = distance_feet <= weapon_range * 4

    return in_normal_range, in_long_range
