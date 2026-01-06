"""
Monk Ki System for D&D 5e 2024

Comprehensive Ki point management:
- Ki point pool (equal to monk level)
- Ki abilities by level
- Stunning Strike, Flurry of Blows, Patient Defense, Step of the Wind
- Ki save DC calculation
- Resource restoration on rest
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import random


class KiAbilityType(str, Enum):
    """Types of Ki abilities."""
    BONUS_ACTION = "bonus_action"
    ACTION = "action"
    REACTION = "reaction"
    ON_HIT = "on_hit"
    PASSIVE = "passive"


@dataclass
class KiAbility:
    """A Ki-powered ability."""
    id: str
    name: str
    ki_cost: int
    level_required: int
    ability_type: KiAbilityType
    description: str
    duration: Optional[str] = None  # "1 round", "1 minute", etc.
    requires_melee_hit: bool = False
    requires_target: bool = False
    save_type: Optional[str] = None  # "constitution", "wisdom", etc.

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "ki_cost": self.ki_cost,
            "level_required": self.level_required,
            "ability_type": self.ability_type.value,
            "description": self.description,
            "duration": self.duration,
            "requires_melee_hit": self.requires_melee_hit,
            "save_type": self.save_type,
        }


# =============================================================================
# KI ABILITIES
# =============================================================================

KI_ABILITIES: Dict[str, KiAbility] = {
    "flurry_of_blows": KiAbility(
        id="flurry_of_blows",
        name="Flurry of Blows",
        ki_cost=1,
        level_required=2,
        ability_type=KiAbilityType.BONUS_ACTION,
        description="Immediately after you take the Attack action on your turn, you can make two unarmed strikes as a bonus action.",
    ),
    "patient_defense": KiAbility(
        id="patient_defense",
        name="Patient Defense",
        ki_cost=1,
        level_required=2,
        ability_type=KiAbilityType.BONUS_ACTION,
        description="You take the Dodge action as a bonus action.",
        duration="until start of next turn",
    ),
    "step_of_the_wind": KiAbility(
        id="step_of_the_wind",
        name="Step of the Wind",
        ki_cost=1,
        level_required=2,
        ability_type=KiAbilityType.BONUS_ACTION,
        description="You take the Disengage or Dash action as a bonus action, and your jump distance is doubled for the turn.",
        duration="1 turn",
    ),
    "stunning_strike": KiAbility(
        id="stunning_strike",
        name="Stunning Strike",
        ki_cost=1,
        level_required=5,
        ability_type=KiAbilityType.ON_HIT,
        description="When you hit a creature with a melee weapon attack, the target must succeed on a Constitution saving throw or be stunned until the end of your next turn.",
        requires_melee_hit=True,
        save_type="constitution",
        duration="until end of next turn",
    ),
    "focused_aim": KiAbility(
        id="focused_aim",
        name="Focused Aim",
        ki_cost=1,  # 1-3 ki for +2 to +6
        level_required=5,
        ability_type=KiAbilityType.ON_HIT,
        description="When you miss with an attack roll, spend 1-3 ki points to increase the roll by 2 for each point spent, potentially turning a miss into a hit.",
    ),
    "quickened_healing": KiAbility(
        id="quickened_healing",
        name="Quickened Healing",
        ki_cost=2,
        level_required=4,
        ability_type=KiAbilityType.ACTION,
        description="As an action, you regain hit points equal to one roll of your Martial Arts die + your proficiency bonus.",
    ),
    "deflect_missiles": KiAbility(
        id="deflect_missiles",
        name="Deflect Missiles",
        ki_cost=1,
        level_required=3,
        ability_type=KiAbilityType.REACTION,
        description="When you are hit by a ranged weapon attack, reduce the damage by 1d10 + DEX + monk level. If reduced to 0, catch the missile. Spend 1 ki to throw it back as an attack.",
    ),
    "slow_fall": KiAbility(
        id="slow_fall",
        name="Slow Fall",
        ki_cost=0,  # Free
        level_required=4,
        ability_type=KiAbilityType.REACTION,
        description="When you fall, reduce falling damage by five times your monk level.",
    ),
    "stillness_of_mind": KiAbility(
        id="stillness_of_mind",
        name="Stillness of Mind",
        ki_cost=0,  # Free
        level_required=7,
        ability_type=KiAbilityType.ACTION,
        description="You can end one effect on yourself that is causing you to be charmed or frightened.",
    ),
    "empty_body": KiAbility(
        id="empty_body",
        name="Empty Body",
        ki_cost=4,
        level_required=18,
        ability_type=KiAbilityType.ACTION,
        description="Become invisible and have resistance to all damage except force for 1 minute. Spend 8 ki points to cast Astral Projection without material components.",
        duration="1 minute",
    ),
}


@dataclass
class KiState:
    """Tracks Ki points for a monk."""
    max_ki: int = 0
    current_ki: int = 0
    ki_save_dc: int = 8  # 8 + proficiency + WIS mod
    martial_arts_die: str = "1d4"

    # Tracking for once-per-turn abilities
    stunning_strike_used_this_turn: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_ki": self.max_ki,
            "current_ki": self.current_ki,
            "ki_save_dc": self.ki_save_dc,
            "martial_arts_die": self.martial_arts_die,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "KiState":
        return cls(
            max_ki=data.get("max_ki", 0),
            current_ki=data.get("current_ki", 0),
            ki_save_dc=data.get("ki_save_dc", 8),
            martial_arts_die=data.get("martial_arts_die", "1d4"),
        )


def calculate_ki_save_dc(wisdom_score: int, proficiency_bonus: int) -> int:
    """Calculate Ki save DC: 8 + proficiency + WIS modifier."""
    wis_mod = (wisdom_score - 10) // 2
    return 8 + proficiency_bonus + wis_mod


def get_martial_arts_die(level: int) -> str:
    """Get Martial Arts die size for monk level."""
    if level >= 17:
        return "1d12"
    elif level >= 11:
        return "1d10"
    elif level >= 5:
        return "1d8"
    else:
        return "1d6"  # 2024 PHB starts at d6


def get_max_ki_points(level: int) -> int:
    """Get maximum Ki points (equals monk level)."""
    return level


def initialize_ki_state(
    level: int,
    wisdom_score: int,
    proficiency_bonus: int
) -> KiState:
    """Create a new Ki state for a monk."""
    max_ki = get_max_ki_points(level)
    return KiState(
        max_ki=max_ki,
        current_ki=max_ki,
        ki_save_dc=calculate_ki_save_dc(wisdom_score, proficiency_bonus),
        martial_arts_die=get_martial_arts_die(level),
    )


def get_available_ki_abilities(level: int) -> List[KiAbility]:
    """Get all Ki abilities available at a given monk level."""
    return [
        ability for ability in KI_ABILITIES.values()
        if ability.level_required <= level
    ]


def can_use_ability(
    state: KiState,
    ability_id: str,
    level: int
) -> Tuple[bool, str]:
    """
    Check if a Ki ability can be used.

    Returns:
        Tuple of (can_use, reason_if_not)
    """
    ability = KI_ABILITIES.get(ability_id)
    if not ability:
        return False, f"Unknown Ki ability: {ability_id}"

    if level < ability.level_required:
        return False, f"Requires monk level {ability.level_required}"

    if state.current_ki < ability.ki_cost:
        return False, f"Not enough Ki points (need {ability.ki_cost}, have {state.current_ki})"

    # Special check for Stunning Strike
    if ability_id == "stunning_strike" and state.stunning_strike_used_this_turn:
        return False, "Already used Stunning Strike this turn"

    return True, ""


def use_ki_ability(
    state: KiState,
    ability_id: str,
    level: int,
    ki_spent: Optional[int] = None  # For variable-cost abilities like Focused Aim
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Use a Ki ability.

    Args:
        state: Current Ki state
        ability_id: ID of the ability to use
        level: Monk level
        ki_spent: Override ki cost (for variable abilities)

    Returns:
        Tuple of (success, message, effect_data)
    """
    can_use, reason = can_use_ability(state, ability_id, level)
    if not can_use:
        return False, reason, {}

    ability = KI_ABILITIES[ability_id]
    cost = ki_spent if ki_spent is not None else ability.ki_cost

    if state.current_ki < cost:
        return False, f"Not enough Ki points (need {cost}, have {state.current_ki})", {}

    # Spend Ki
    state.current_ki -= cost

    # Track ability usage
    if ability_id == "stunning_strike":
        state.stunning_strike_used_this_turn = True

    effect_data = {
        "ability_id": ability_id,
        "ability_name": ability.name,
        "ki_spent": cost,
        "ki_remaining": state.current_ki,
    }

    # Add ability-specific effects
    if ability_id == "flurry_of_blows":
        effect_data["grants_extra_attacks"] = 2

    elif ability_id == "patient_defense":
        effect_data["grants_dodge"] = True

    elif ability_id == "step_of_the_wind":
        effect_data["grants_disengage"] = True
        effect_data["grants_dash"] = True
        effect_data["jump_distance_doubled"] = True

    elif ability_id == "stunning_strike":
        effect_data["save_type"] = "constitution"
        effect_data["save_dc"] = state.ki_save_dc
        effect_data["condition_on_fail"] = "stunned"
        effect_data["duration"] = "until end of next turn"

    elif ability_id == "focused_aim":
        effect_data["attack_bonus"] = cost * 2  # +2 per ki spent

    elif ability_id == "quickened_healing":
        # Roll martial arts die + proficiency
        die_match = state.martial_arts_die.split("d")
        die_size = int(die_match[1]) if len(die_match) > 1 else 6
        healing_roll = random.randint(1, die_size)
        proficiency = 2 + ((level - 1) // 4)
        total_healing = healing_roll + proficiency
        effect_data["healing"] = total_healing
        effect_data["roll"] = healing_roll
        effect_data["proficiency_bonus"] = proficiency

    elif ability_id == "deflect_missiles":
        effect_data["can_throw_back"] = True

    elif ability_id == "empty_body":
        effect_data["invisible"] = True
        effect_data["resistance_all"] = True
        effect_data["duration_minutes"] = 1

    return True, f"Used {ability.name}!", effect_data


def restore_ki_on_rest(state: KiState, is_long_rest: bool = False) -> int:
    """
    Restore Ki points on rest.

    Both short and long rest restore all Ki points.

    Returns:
        Number of Ki points restored
    """
    restored = state.max_ki - state.current_ki
    state.current_ki = state.max_ki
    return restored


def reset_turn_tracking(state: KiState) -> None:
    """Reset per-turn ability tracking."""
    state.stunning_strike_used_this_turn = False


# =============================================================================
# STUNNING STRIKE RESOLUTION
# =============================================================================

def resolve_stunning_strike(
    target_con_score: int,
    target_proficient_con_save: bool,
    target_level: int,
    ki_save_dc: int,
    advantage: bool = False,
    disadvantage: bool = False
) -> Tuple[bool, int, str]:
    """
    Resolve a Stunning Strike save.

    Args:
        target_con_score: Target's Constitution score
        target_proficient_con_save: Whether target is proficient in CON saves
        target_level: Target's level (for proficiency if proficient)
        ki_save_dc: Monk's Ki save DC
        advantage: Target has advantage on the save
        disadvantage: Target has disadvantage on the save

    Returns:
        Tuple of (stunned, roll, description)
    """
    con_mod = (target_con_score - 10) // 2
    save_bonus = con_mod

    if target_proficient_con_save:
        proficiency = 2 + ((target_level - 1) // 4)
        save_bonus += proficiency

    # Roll save
    roll1 = random.randint(1, 20)
    roll2 = random.randint(1, 20)

    if advantage and not disadvantage:
        roll = max(roll1, roll2)
        roll_desc = f"({roll1}, {roll2}, take {roll})"
    elif disadvantage and not advantage:
        roll = min(roll1, roll2)
        roll_desc = f"({roll1}, {roll2}, take {roll})"
    else:
        roll = roll1
        roll_desc = str(roll)

    total = roll + save_bonus
    success = total >= ki_save_dc

    if success:
        description = f"CON save: {roll_desc} + {save_bonus} = {total} vs DC {ki_save_dc} - Success! Not stunned."
    else:
        description = f"CON save: {roll_desc} + {save_bonus} = {total} vs DC {ki_save_dc} - Failed! Stunned until end of next turn."

    return not success, roll, description


# =============================================================================
# MARTIAL ARTS UTILITY
# =============================================================================

def get_unarmed_strike_damage(level: int) -> Tuple[str, int]:
    """
    Get unarmed strike damage for a monk.

    Monks can use DEX for unarmed strikes and use Martial Arts die.

    Returns:
        Tuple of (damage_dice, minimum_damage)
    """
    die = get_martial_arts_die(level)
    return die, 1


def get_unarmored_defense_ac(dexterity: int, wisdom: int) -> int:
    """
    Calculate Unarmored Defense AC.

    AC = 10 + DEX mod + WIS mod (when not wearing armor or shield)
    """
    dex_mod = (dexterity - 10) // 2
    wis_mod = (wisdom - 10) // 2
    return 10 + dex_mod + wis_mod


def get_unarmored_movement_bonus(level: int) -> int:
    """
    Get Unarmored Movement speed bonus.

    Level 2: +10 ft
    Level 6: +15 ft
    Level 10: +20 ft
    Level 14: +25 ft
    Level 18: +30 ft
    """
    if level >= 18:
        return 30
    elif level >= 14:
        return 25
    elif level >= 10:
        return 20
    elif level >= 6:
        return 15
    elif level >= 2:
        return 10
    return 0


def get_ki_ability_summary(level: int) -> List[Dict[str, Any]]:
    """Get a summary of available Ki abilities for display."""
    abilities = get_available_ki_abilities(level)
    return [
        {
            "id": a.id,
            "name": a.name,
            "ki_cost": a.ki_cost,
            "type": a.ability_type.value,
            "description": a.description,
        }
        for a in abilities
    ]
