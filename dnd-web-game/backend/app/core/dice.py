"""
Dice rolling system for D&D 5e mechanics.

Handles all dice operations including:
- Standard dice (d4, d6, d8, d10, d12, d20, d100)
- Advantage and disadvantage on d20 rolls
- Damage dice notation parsing (2d6+3, 1d8+1d6, etc.)
- Critical hit detection (natural 20) and fumbles (natural 1)
"""
import random
import re
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class D20Result:
    """Result of a d20 roll, tracking advantage/disadvantage and criticals."""
    rolls: List[int]  # All dice rolled (2 if advantage/disadvantage)
    modifier: int
    total: int
    advantage: bool = False
    disadvantage: bool = False
    natural_20: bool = False
    natural_1: bool = False

    @property
    def base_roll(self) -> int:
        """The d20 value used (after advantage/disadvantage selection)."""
        if self.advantage and not self.disadvantage:
            return max(self.rolls)
        elif self.disadvantage and not self.advantage:
            return min(self.rolls)
        return self.rolls[0]


@dataclass
class DamageResult:
    """Result of a damage roll."""
    rolls: List[int]  # Individual dice results
    modifier: int
    total: int
    dice_notation: str  # Original notation (e.g., "2d6+3")
    is_critical: bool = False  # If true, dice were doubled


def roll_die(sides: int) -> int:
    """Roll a single die with the given number of sides."""
    if sides < 1:
        raise ValueError(f"Invalid die: d{sides}")
    return random.randint(1, sides)


def roll_d20(modifier: int = 0, advantage: bool = False, disadvantage: bool = False) -> D20Result:
    """
    Roll a d20 with optional advantage/disadvantage.

    Args:
        modifier: Bonus to add to the roll (attack bonus, skill modifier, etc.)
        advantage: If True, roll twice and take the higher
        disadvantage: If True, roll twice and take the lower

    Returns:
        D20Result with all roll information

    Note: If both advantage and disadvantage are True, they cancel out
          and a single die is rolled (per D&D 5e rules).
    """
    # Advantage and disadvantage cancel each other out
    if advantage and disadvantage:
        advantage = False
        disadvantage = False

    # Roll the dice
    if advantage or disadvantage:
        rolls = [roll_die(20), roll_die(20)]
    else:
        rolls = [roll_die(20)]

    # Determine which roll to use
    if advantage:
        base_roll = max(rolls)
    elif disadvantage:
        base_roll = min(rolls)
    else:
        base_roll = rolls[0]

    return D20Result(
        rolls=rolls,
        modifier=modifier,
        total=base_roll + modifier,
        advantage=advantage,
        disadvantage=disadvantage,
        natural_20=(base_roll == 20),
        natural_1=(base_roll == 1)
    )


def parse_dice_notation(notation: str) -> List[Tuple[int, int, int]]:
    """
    Parse dice notation into components.

    Args:
        notation: Dice notation like "2d6+3", "1d8+1d6", "3d4-1"

    Returns:
        List of (count, sides, modifier) tuples.
        For "2d6+3+1d4", returns [(2, 6, 3), (1, 4, 0)]

    Raises:
        ValueError: If notation is invalid
    """
    if not notation:
        raise ValueError("Empty dice notation")

    notation = notation.lower().replace(" ", "")
    components = []

    # Split by + or - while keeping the sign
    parts = re.split(r'(?=[+-])', notation)

    current_modifier = 0

    for part in parts:
        if not part:
            continue

        # Check if it's a dice expression (contains 'd')
        dice_match = re.match(r'^([+-]?)(\d*)d(\d+)$', part)
        if dice_match:
            sign = -1 if dice_match.group(1) == '-' else 1
            count = int(dice_match.group(2)) if dice_match.group(2) else 1
            sides = int(dice_match.group(3))
            components.append((sign * count, sides, 0))
        else:
            # It's a flat modifier
            try:
                current_modifier += int(part)
            except ValueError:
                raise ValueError(f"Invalid dice notation: {notation}")

    # Add the modifier to the last component, or create a dummy if none
    if components:
        count, sides, _ = components[-1]
        components[-1] = (count, sides, current_modifier)
    elif current_modifier != 0:
        # Just a flat number, no dice
        components.append((0, 0, current_modifier))

    return components


def roll_damage(notation: str, modifier: int = 0, critical: bool = False) -> DamageResult:
    """
    Roll damage dice from notation.

    Args:
        notation: Dice notation like "2d6", "1d8+2", "2d6+1d4"
        modifier: Additional modifier to add (weapon/ability bonus)
        critical: If True, double the number of dice rolled

    Returns:
        DamageResult with all roll information

    Examples:
        roll_damage("1d8", modifier=3) -> rolls 1d8+3
        roll_damage("2d6", critical=True) -> rolls 4d6 (doubled for crit)
    """
    components = parse_dice_notation(notation)
    all_rolls = []
    total = modifier  # Start with the extra modifier

    for count, sides, flat_mod in components:
        if sides == 0:
            # Flat modifier only
            total += flat_mod
            continue

        # Determine number of dice to roll
        num_dice = abs(count)
        if critical:
            num_dice *= 2  # Double dice on critical

        # Roll the dice
        sign = 1 if count >= 0 else -1
        for _ in range(num_dice):
            roll = roll_die(sides)
            all_rolls.append(roll * sign)
            total += roll * sign

        # Add flat modifier from this component
        total += flat_mod

    # Ensure minimum of 1 damage (D&D rule: damage can't go below 1 from resistance/modifiers)
    total = max(1, total)

    return DamageResult(
        rolls=all_rolls,
        modifier=modifier,
        total=total,
        dice_notation=notation,
        is_critical=critical
    )


def roll_initiative(dexterity_modifier: int = 0) -> int:
    """
    Roll initiative (d20 + DEX modifier).

    Args:
        dexterity_modifier: Character's DEX modifier

    Returns:
        Initiative value (can be used for turn order sorting)
    """
    result = roll_d20(modifier=dexterity_modifier)
    return result.total


def roll_saving_throw(
    modifier: int = 0,
    advantage: bool = False,
    disadvantage: bool = False
) -> D20Result:
    """
    Roll a saving throw.

    Args:
        modifier: Saving throw modifier (ability + proficiency if applicable)
        advantage: Roll with advantage
        disadvantage: Roll with disadvantage

    Returns:
        D20Result for comparison against DC
    """
    return roll_d20(modifier=modifier, advantage=advantage, disadvantage=disadvantage)


def roll_ability_check(
    modifier: int = 0,
    advantage: bool = False,
    disadvantage: bool = False
) -> D20Result:
    """
    Roll an ability check (skill check).

    Args:
        modifier: Ability modifier + proficiency if applicable
        advantage: Roll with advantage
        disadvantage: Roll with disadvantage

    Returns:
        D20Result for comparison against DC
    """
    return roll_d20(modifier=modifier, advantage=advantage, disadvantage=disadvantage)


# Convenience functions for common rolls
def roll_d4(count: int = 1) -> List[int]:
    """Roll one or more d4s."""
    return [roll_die(4) for _ in range(count)]


def roll_d6(count: int = 1) -> List[int]:
    """Roll one or more d6s."""
    return [roll_die(6) for _ in range(count)]


def roll_d8(count: int = 1) -> List[int]:
    """Roll one or more d8s."""
    return [roll_die(8) for _ in range(count)]


def roll_d10(count: int = 1) -> List[int]:
    """Roll one or more d10s."""
    return [roll_die(10) for _ in range(count)]


def roll_d12(count: int = 1) -> List[int]:
    """Roll one or more d12s."""
    return [roll_die(12) for _ in range(count)]


def roll_d100() -> int:
    """Roll percentile dice (d100)."""
    return roll_die(100)
