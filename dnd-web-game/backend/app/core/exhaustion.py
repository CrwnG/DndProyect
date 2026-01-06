"""
Exhaustion System for D&D 5e 2024

Implements the 6-level exhaustion mechanic with cumulative effects:
- Level 1: Disadvantage on ability checks
- Level 2: Speed halved
- Level 3: Disadvantage on attack rolls and saving throws
- Level 4: Hit point maximum halved
- Level 5: Speed reduced to 0
- Level 6: Death

Exhaustion is gained from various sources:
- Forced march without rest
- Starvation/dehydration
- Certain spells and abilities
- Environmental hazards

Exhaustion is reduced by:
- Long rest: Reduces by 1 level (with food and drink)
- Greater Restoration spell: Reduces by 1 level
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import Dict, List, Any, Optional, Set


class ExhaustionLevel(IntEnum):
    """Exhaustion levels from 0 (none) to 6 (death)."""
    NONE = 0
    LEVEL_1 = 1
    LEVEL_2 = 2
    LEVEL_3 = 3
    LEVEL_4 = 4
    LEVEL_5 = 5
    LEVEL_6 = 6


# Effects at each exhaustion level (cumulative)
EXHAUSTION_EFFECTS: Dict[int, Dict[str, Any]] = {
    1: {
        "name": "Exhaustion 1",
        "description": "Disadvantage on ability checks",
        "disadvantage_on": ["ability_checks"],
        "speed_modifier": 1.0,  # No change
        "max_hp_modifier": 1.0,  # No change
    },
    2: {
        "name": "Exhaustion 2",
        "description": "Disadvantage on ability checks, speed halved",
        "disadvantage_on": ["ability_checks"],
        "speed_modifier": 0.5,  # Half speed
        "max_hp_modifier": 1.0,
    },
    3: {
        "name": "Exhaustion 3",
        "description": "Disadvantage on ability checks, attacks, and saves; speed halved",
        "disadvantage_on": ["ability_checks", "attack_rolls", "saving_throws"],
        "speed_modifier": 0.5,
        "max_hp_modifier": 1.0,
    },
    4: {
        "name": "Exhaustion 4",
        "description": "Disadvantage on ability checks, attacks, and saves; speed halved; max HP halved",
        "disadvantage_on": ["ability_checks", "attack_rolls", "saving_throws"],
        "speed_modifier": 0.5,
        "max_hp_modifier": 0.5,  # Half max HP
    },
    5: {
        "name": "Exhaustion 5",
        "description": "Disadvantage on ability checks, attacks, and saves; speed 0; max HP halved",
        "disadvantage_on": ["ability_checks", "attack_rolls", "saving_throws"],
        "speed_modifier": 0.0,  # Speed reduced to 0
        "max_hp_modifier": 0.5,
    },
    6: {
        "name": "Exhaustion 6",
        "description": "Death",
        "death": True,
    },
}


@dataclass
class ExhaustionModifiers:
    """
    Calculated modifiers from exhaustion for easy application.
    """
    disadvantage_on_ability_checks: bool = False
    disadvantage_on_attacks: bool = False
    disadvantage_on_saves: bool = False
    speed_multiplier: float = 1.0
    max_hp_multiplier: float = 1.0
    is_dead: bool = False

    def get_disadvantage_types(self) -> List[str]:
        """Get list of roll types that have disadvantage."""
        types = []
        if self.disadvantage_on_ability_checks:
            types.append("ability_checks")
        if self.disadvantage_on_attacks:
            types.append("attack_rolls")
        if self.disadvantage_on_saves:
            types.append("saving_throws")
        return types

    def applies_disadvantage_to(self, roll_type: str) -> bool:
        """Check if disadvantage applies to a specific roll type."""
        if roll_type in ("ability_check", "ability_checks", "check"):
            return self.disadvantage_on_ability_checks
        if roll_type in ("attack", "attack_roll", "attack_rolls"):
            return self.disadvantage_on_attacks
        if roll_type in ("save", "saving_throw", "saving_throws"):
            return self.disadvantage_on_saves
        return False


@dataclass
class ExhaustionState:
    """
    Tracks a creature's exhaustion level and provides effect calculations.
    """
    level: int = 0

    def __post_init__(self):
        """Ensure level is within valid range."""
        self.level = max(0, min(6, self.level))

    @property
    def is_exhausted(self) -> bool:
        """Check if creature has any exhaustion."""
        return self.level > 0

    @property
    def is_dead(self) -> bool:
        """Check if exhaustion has caused death (level 6)."""
        return self.level >= 6

    @property
    def current_effects(self) -> Optional[Dict[str, Any]]:
        """Get the effect data for current exhaustion level."""
        if self.level == 0:
            return None
        return EXHAUSTION_EFFECTS.get(self.level)

    def get_modifiers(self) -> ExhaustionModifiers:
        """
        Calculate all modifiers from current exhaustion level.

        Returns:
            ExhaustionModifiers with all current effects
        """
        if self.level == 0:
            return ExhaustionModifiers()

        # Exhaustion effects are cumulative
        modifiers = ExhaustionModifiers()

        for lvl in range(1, self.level + 1):
            effects = EXHAUSTION_EFFECTS.get(lvl, {})

            # Check for disadvantage effects
            disadvantage_types = effects.get("disadvantage_on", [])
            if "ability_checks" in disadvantage_types:
                modifiers.disadvantage_on_ability_checks = True
            if "attack_rolls" in disadvantage_types:
                modifiers.disadvantage_on_attacks = True
            if "saving_throws" in disadvantage_types:
                modifiers.disadvantage_on_saves = True

            # Speed modifier (take the lowest)
            speed_mod = effects.get("speed_modifier", 1.0)
            modifiers.speed_multiplier = min(modifiers.speed_multiplier, speed_mod)

            # HP modifier (take the lowest)
            hp_mod = effects.get("max_hp_modifier", 1.0)
            modifiers.max_hp_multiplier = min(modifiers.max_hp_multiplier, hp_mod)

            # Death check
            if effects.get("death", False):
                modifiers.is_dead = True

        return modifiers

    def gain_exhaustion(self, amount: int = 1) -> Dict[str, Any]:
        """
        Gain exhaustion levels.

        Args:
            amount: Number of exhaustion levels to gain (default 1)

        Returns:
            Dict with result information
        """
        old_level = self.level
        self.level = min(6, self.level + amount)
        new_level = self.level

        result = {
            "old_level": old_level,
            "new_level": new_level,
            "levels_gained": new_level - old_level,
            "effects": self.current_effects,
            "died": self.is_dead,
        }

        if self.is_dead:
            result["message"] = "Creature has died from exhaustion!"
        elif new_level > old_level:
            result["message"] = f"Gained {new_level - old_level} exhaustion level(s). Now at level {new_level}."
        else:
            result["message"] = "Already at maximum exhaustion."

        return result

    def reduce_exhaustion(self, amount: int = 1) -> Dict[str, Any]:
        """
        Reduce exhaustion levels.

        Args:
            amount: Number of exhaustion levels to reduce (default 1)

        Returns:
            Dict with result information
        """
        old_level = self.level
        self.level = max(0, self.level - amount)
        new_level = self.level

        result = {
            "old_level": old_level,
            "new_level": new_level,
            "levels_reduced": old_level - new_level,
            "effects": self.current_effects,
            "fully_recovered": new_level == 0,
        }

        if old_level > new_level:
            result["message"] = f"Reduced exhaustion by {old_level - new_level} level(s). Now at level {new_level}."
        else:
            result["message"] = "No exhaustion to reduce."

        return result

    def long_rest_recovery(self, has_food_and_drink: bool = True) -> Dict[str, Any]:
        """
        Process exhaustion recovery from a long rest.

        Per D&D 5e rules, a long rest reduces exhaustion by 1 level
        if the creature has had food and drink.

        Args:
            has_food_and_drink: Whether food/drink requirements were met

        Returns:
            Dict with recovery result
        """
        if not has_food_and_drink:
            return {
                "old_level": self.level,
                "new_level": self.level,
                "levels_reduced": 0,
                "message": "No exhaustion recovery - food and drink required."
            }

        return self.reduce_exhaustion(1)

    def apply_speed_modifier(self, base_speed: int) -> int:
        """
        Apply exhaustion speed modifier to base speed.

        Args:
            base_speed: Character's base speed in feet

        Returns:
            Modified speed after exhaustion effects
        """
        modifiers = self.get_modifiers()
        return int(base_speed * modifiers.speed_multiplier)

    def apply_max_hp_modifier(self, base_max_hp: int) -> int:
        """
        Apply exhaustion HP modifier to base max HP.

        Args:
            base_max_hp: Character's base maximum HP

        Returns:
            Modified max HP after exhaustion effects
        """
        modifiers = self.get_modifiers()
        return max(1, int(base_max_hp * modifiers.max_hp_multiplier))

    def get_description(self) -> str:
        """Get a human-readable description of current exhaustion."""
        if self.level == 0:
            return "No exhaustion"

        effects = self.current_effects
        if effects:
            return f"Exhaustion {self.level}: {effects.get('description', 'Unknown effects')}"
        return f"Exhaustion level {self.level}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        modifiers = self.get_modifiers()
        return {
            "level": self.level,
            "is_exhausted": self.is_exhausted,
            "is_dead": self.is_dead,
            "description": self.get_description(),
            "modifiers": {
                "disadvantage_on_ability_checks": modifiers.disadvantage_on_ability_checks,
                "disadvantage_on_attacks": modifiers.disadvantage_on_attacks,
                "disadvantage_on_saves": modifiers.disadvantage_on_saves,
                "speed_multiplier": modifiers.speed_multiplier,
                "max_hp_multiplier": modifiers.max_hp_multiplier,
            }
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ExhaustionState":
        """Create from dictionary data."""
        if isinstance(data, dict):
            return cls(level=data.get("level", 0))
        return cls(level=int(data) if data else 0)


# Exhaustion source definitions
class ExhaustionSource:
    """Common sources of exhaustion in D&D 5e."""

    FORCED_MARCH = "forced_march"
    STARVATION = "starvation"
    DEHYDRATION = "dehydration"
    EXTREME_COLD = "extreme_cold"
    EXTREME_HEAT = "extreme_heat"
    SPELL_EFFECT = "spell_effect"
    FRENZY = "frenzy"  # Berserker Barbarian
    RESURRECTION = "resurrection"  # Coming back from death


# Exhaustion gain conditions
EXHAUSTION_CONDITIONS: Dict[str, Dict[str, Any]] = {
    ExhaustionSource.FORCED_MARCH: {
        "description": "For each hour of travel beyond 8 hours, make a DC 10 CON save or gain 1 exhaustion",
        "save_dc": 10,
        "save_ability": "constitution",
        "levels_gained": 1,
        "dc_increase_per_hour": 1,  # DC increases by 1 for each additional hour
    },
    ExhaustionSource.STARVATION: {
        "description": "After going without food for days beyond CON mod (minimum 1), gain 1 exhaustion per day",
        "levels_gained": 1,
    },
    ExhaustionSource.DEHYDRATION: {
        "description": "Character must drink 1 gallon per day (2 in hot weather) or risk exhaustion",
        "levels_gained": 1,
    },
    ExhaustionSource.EXTREME_COLD: {
        "description": "In extreme cold without protection, make DC 10 CON save each hour or gain 1 exhaustion",
        "save_dc": 10,
        "save_ability": "constitution",
        "levels_gained": 1,
    },
    ExhaustionSource.EXTREME_HEAT: {
        "description": "In extreme heat, make CON save each hour (DC 5 + 1 per hour) or gain 1 exhaustion",
        "save_dc": 5,
        "save_ability": "constitution",
        "levels_gained": 1,
        "dc_increase_per_hour": 1,
    },
    ExhaustionSource.FRENZY: {
        "description": "When Berserker rage ends, gain 1 level of exhaustion",
        "levels_gained": 1,
    },
    ExhaustionSource.RESURRECTION: {
        "description": "Some resurrection effects impose exhaustion",
        "levels_gained": 1,  # Varies by spell
    },
}


def check_exhaustion_disadvantage(
    exhaustion_level: int,
    roll_type: str
) -> bool:
    """
    Check if exhaustion imposes disadvantage on a roll type.

    Args:
        exhaustion_level: Current exhaustion level (0-6)
        roll_type: Type of roll ("ability_check", "attack", "save")

    Returns:
        True if disadvantage applies
    """
    if exhaustion_level <= 0:
        return False

    state = ExhaustionState(level=exhaustion_level)
    modifiers = state.get_modifiers()
    return modifiers.applies_disadvantage_to(roll_type)


def calculate_exhausted_speed(base_speed: int, exhaustion_level: int) -> int:
    """
    Calculate speed with exhaustion applied.

    Args:
        base_speed: Base movement speed in feet
        exhaustion_level: Current exhaustion level

    Returns:
        Modified speed
    """
    state = ExhaustionState(level=exhaustion_level)
    return state.apply_speed_modifier(base_speed)


def calculate_exhausted_max_hp(base_max_hp: int, exhaustion_level: int) -> int:
    """
    Calculate max HP with exhaustion applied.

    Args:
        base_max_hp: Base maximum hit points
        exhaustion_level: Current exhaustion level

    Returns:
        Modified max HP
    """
    state = ExhaustionState(level=exhaustion_level)
    return state.apply_max_hp_modifier(base_max_hp)
