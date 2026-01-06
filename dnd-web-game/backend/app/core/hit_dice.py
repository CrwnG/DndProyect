"""
Hit Dice System for D&D 5e 2024

Manages hit dice pools for characters, including:
- Hit die size by class (d6, d8, d10, d12)
- Spending hit dice during short rests
- Restoring hit dice during long rests
- Rolling hit dice for HP recovery
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import random


# Hit die size by class (D&D 5e 2024)
HIT_DIE_BY_CLASS: Dict[str, int] = {
    # d12 classes
    "barbarian": 12,

    # d10 classes
    "fighter": 10,
    "paladin": 10,
    "ranger": 10,

    # d8 classes
    "bard": 8,
    "cleric": 8,
    "druid": 8,
    "monk": 8,
    "rogue": 8,
    "warlock": 8,

    # d6 classes
    "sorcerer": 6,
    "wizard": 6,
    "artificer": 8,  # Added for completeness
}


def get_hit_die_for_class(class_name: str) -> int:
    """
    Get the hit die size for a class.

    Args:
        class_name: The class name (case-insensitive)

    Returns:
        Hit die size (6, 8, 10, or 12). Defaults to 8 if class unknown.
    """
    return HIT_DIE_BY_CLASS.get(class_name.lower(), 8)


def roll_hit_die(die_size: int) -> int:
    """
    Roll a single hit die.

    Args:
        die_size: Size of the die (6, 8, 10, or 12)

    Returns:
        The roll result (1 to die_size)
    """
    return random.randint(1, die_size)


def get_hit_die_average(die_size: int) -> int:
    """
    Get the average roll for a hit die (rounded up, as per 5e rules).

    Args:
        die_size: Size of the die

    Returns:
        Average value rounded up (d6=4, d8=5, d10=6, d12=7)
    """
    return (die_size // 2) + 1


@dataclass
class HitDieRoll:
    """Result of rolling a hit die for healing."""
    die_size: int
    roll: int
    con_modifier: int
    total_healing: int

    @property
    def description(self) -> str:
        """Human-readable description of the roll."""
        sign = "+" if self.con_modifier >= 0 else ""
        return f"1d{self.die_size} ({self.roll}) {sign}{self.con_modifier} = {self.total_healing} HP"


@dataclass
class HitDicePool:
    """
    Tracks a character's available hit dice for short rest healing.

    In D&D 5e:
    - Characters have hit dice equal to their level
    - Each die is the size of their class hit die
    - Can spend dice during short rest to heal (die roll + CON mod)
    - Long rest restores half of total dice (minimum 1)
    """

    class_name: str
    die_size: int
    total_dice: int  # Equal to character level
    remaining_dice: int

    @classmethod
    def create_for_character(cls, class_name: str, level: int) -> "HitDicePool":
        """
        Create a hit dice pool for a character.

        Args:
            class_name: Character's class
            level: Character's level (determines total dice)

        Returns:
            A new HitDicePool with full dice available
        """
        die_size = get_hit_die_for_class(class_name)
        return cls(
            class_name=class_name.lower(),
            die_size=die_size,
            total_dice=level,
            remaining_dice=level
        )

    @classmethod
    def from_dict(cls, data: Dict) -> "HitDicePool":
        """Create from dictionary data."""
        return cls(
            class_name=data.get("class_name", "fighter"),
            die_size=data.get("die_size", 10),
            total_dice=data.get("total_dice", 1),
            remaining_dice=data.get("remaining_dice", 1)
        )

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "class_name": self.class_name,
            "die_size": self.die_size,
            "total_dice": self.total_dice,
            "remaining_dice": self.remaining_dice
        }

    def can_spend(self, count: int = 1) -> bool:
        """
        Check if the character can spend hit dice.

        Args:
            count: Number of dice to check

        Returns:
            True if enough dice are available
        """
        return self.remaining_dice >= count

    def spend_die(self, con_modifier: int = 0) -> Optional[HitDieRoll]:
        """
        Spend one hit die to heal during a short rest.

        Args:
            con_modifier: Character's Constitution modifier

        Returns:
            HitDieRoll with the result, or None if no dice available
        """
        if not self.can_spend(1):
            return None

        self.remaining_dice -= 1
        roll = roll_hit_die(self.die_size)

        # HP healed is roll + CON modifier, minimum 1
        total_healing = max(1, roll + con_modifier)

        return HitDieRoll(
            die_size=self.die_size,
            roll=roll,
            con_modifier=con_modifier,
            total_healing=total_healing
        )

    def spend_multiple_dice(
        self,
        count: int,
        con_modifier: int = 0
    ) -> Tuple[int, List[HitDieRoll]]:
        """
        Spend multiple hit dice during a short rest.

        Args:
            count: Number of dice to spend
            con_modifier: Character's Constitution modifier

        Returns:
            Tuple of (total HP healed, list of individual rolls)
        """
        rolls: List[HitDieRoll] = []
        total_healing = 0

        actual_count = min(count, self.remaining_dice)

        for _ in range(actual_count):
            roll_result = self.spend_die(con_modifier)
            if roll_result:
                rolls.append(roll_result)
                total_healing += roll_result.total_healing

        return total_healing, rolls

    def restore_dice(self, amount: Optional[int] = None) -> int:
        """
        Restore hit dice (typically during long rest).

        Long rest rules: Restore half of total hit dice (minimum 1)

        Args:
            amount: Specific amount to restore, or None for long rest default

        Returns:
            Number of dice actually restored
        """
        if amount is None:
            # Long rest: restore half, minimum 1
            amount = max(1, self.total_dice // 2)

        # Calculate how many we can actually restore
        dice_to_restore = min(amount, self.total_dice - self.remaining_dice)
        self.remaining_dice += dice_to_restore

        return dice_to_restore

    def restore_all(self) -> int:
        """
        Restore all hit dice to full.

        Returns:
            Number of dice restored
        """
        dice_restored = self.total_dice - self.remaining_dice
        self.remaining_dice = self.total_dice
        return dice_restored

    def level_up(self) -> None:
        """
        Increase total hit dice when leveling up.
        Grants one additional die but doesn't automatically restore it.
        """
        self.total_dice += 1

    @property
    def spent_dice(self) -> int:
        """Number of dice that have been spent."""
        return self.total_dice - self.remaining_dice

    @property
    def average_healing_per_die(self) -> int:
        """Average healing per die (without CON mod)."""
        return get_hit_die_average(self.die_size)

    def __str__(self) -> str:
        return f"{self.remaining_dice}/{self.total_dice} d{self.die_size}"


@dataclass
class MulticlassHitDicePool:
    """
    Tracks hit dice for a multiclass character.

    Multiclass characters have separate pools of hit dice for each class,
    each using that class's hit die size.
    """

    pools: Dict[str, HitDicePool] = field(default_factory=dict)

    def add_class_levels(self, class_name: str, levels: int) -> None:
        """
        Add levels in a class to the hit dice pool.

        Args:
            class_name: The class to add levels for
            levels: Number of levels to add
        """
        class_lower = class_name.lower()

        if class_lower in self.pools:
            for _ in range(levels):
                self.pools[class_lower].level_up()
        else:
            self.pools[class_lower] = HitDicePool.create_for_character(
                class_name, levels
            )

    @property
    def total_dice(self) -> int:
        """Total hit dice across all classes."""
        return sum(pool.total_dice for pool in self.pools.values())

    @property
    def remaining_dice(self) -> int:
        """Total remaining dice across all classes."""
        return sum(pool.remaining_dice for pool in self.pools.values())

    def spend_die(self, class_name: str, con_modifier: int = 0) -> Optional[HitDieRoll]:
        """
        Spend a hit die from a specific class pool.

        Args:
            class_name: Which class's die to use
            con_modifier: Constitution modifier

        Returns:
            Roll result or None if unavailable
        """
        class_lower = class_name.lower()
        if class_lower not in self.pools:
            return None
        return self.pools[class_lower].spend_die(con_modifier)

    def spend_largest_die(self, con_modifier: int = 0) -> Optional[HitDieRoll]:
        """
        Spend the largest available hit die (optimal for healing).

        Args:
            con_modifier: Constitution modifier

        Returns:
            Roll result or None if no dice available
        """
        # Sort pools by die size descending, filter those with remaining dice
        available_pools = [
            (name, pool) for name, pool in self.pools.items()
            if pool.remaining_dice > 0
        ]

        if not available_pools:
            return None

        available_pools.sort(key=lambda x: x[1].die_size, reverse=True)
        return available_pools[0][1].spend_die(con_modifier)

    def restore_dice_long_rest(self) -> Dict[str, int]:
        """
        Restore hit dice for a long rest.

        Returns:
            Dict mapping class name to dice restored
        """
        # Total dice to restore (half of total, minimum 1)
        total_to_restore = max(1, self.total_dice // 2)

        # Restore to each pool proportionally
        restored = {}
        remaining_to_restore = total_to_restore

        # Prioritize larger dice (better for healing)
        sorted_pools = sorted(
            self.pools.items(),
            key=lambda x: x[1].die_size,
            reverse=True
        )

        for class_name, pool in sorted_pools:
            if remaining_to_restore <= 0:
                break

            pool_spent = pool.spent_dice
            dice_for_pool = min(pool_spent, remaining_to_restore)

            if dice_for_pool > 0:
                pool.restore_dice(dice_for_pool)
                restored[class_name] = dice_for_pool
                remaining_to_restore -= dice_for_pool

        return restored

    def get_summary(self) -> Dict[str, str]:
        """Get a summary of all hit dice pools."""
        return {name: str(pool) for name, pool in self.pools.items()}


# Utility functions for level-up HP calculations

def calculate_level_up_hp(
    class_name: str,
    new_level: int,
    con_modifier: int,
    use_average: bool = True,
    roll_result: Optional[int] = None
) -> int:
    """
    Calculate HP gained when leveling up.

    Args:
        class_name: The character's class
        new_level: The level being gained
        con_modifier: Constitution modifier
        use_average: If True, use average die value; if False, use roll_result
        roll_result: The actual roll if not using average

    Returns:
        HP gained this level (minimum 1)
    """
    die_size = get_hit_die_for_class(class_name)

    if new_level == 1:
        # First level: max die + CON mod
        return die_size + con_modifier

    if use_average:
        # Average rounded up + CON mod
        base_hp = get_hit_die_average(die_size)
    elif roll_result is not None:
        base_hp = roll_result
    else:
        # Roll if no average and no roll provided
        base_hp = roll_hit_die(die_size)

    return max(1, base_hp + con_modifier)


def calculate_max_hp(
    class_name: str,
    level: int,
    con_modifier: int,
    use_average: bool = True,
    hp_rolls: Optional[List[int]] = None
) -> int:
    """
    Calculate total max HP for a character.

    Args:
        class_name: The character's class
        level: Character level
        con_modifier: Constitution modifier
        use_average: If True, use average for levels 2+
        hp_rolls: Optional list of HP rolls for each level (starting at level 2)

    Returns:
        Total max HP
    """
    die_size = get_hit_die_for_class(class_name)

    # Level 1: max die + CON
    total_hp = die_size + con_modifier

    # Levels 2+
    for i in range(1, level):
        level_num = i + 1

        if use_average:
            level_hp = get_hit_die_average(die_size)
        elif hp_rolls and i - 1 < len(hp_rolls):
            level_hp = hp_rolls[i - 1]
        else:
            level_hp = roll_hit_die(die_size)

        total_hp += max(1, level_hp + con_modifier)

    return max(1, total_hp)
