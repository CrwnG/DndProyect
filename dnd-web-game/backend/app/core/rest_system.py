"""
Rest System for D&D 5e 2024

Comprehensive rest management including:
- Short rest with hit dice spending
- Long rest with full resource restoration
- Rest interruption handling
- Party-wide rest coordination

This module provides the high-level orchestration for rests,
integrating hit dice, spell slots, exhaustion, and class features.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from app.models.game_session import PartyMember, GameSession


class RestType(str, Enum):
    """Types of rest in D&D 5e."""
    SHORT = "short"
    LONG = "long"


@dataclass
class HitDieSpendResult:
    """Result of spending a single hit die."""
    die_size: int
    roll: int
    con_modifier: int
    healing: int

    @property
    def description(self) -> str:
        sign = "+" if self.con_modifier >= 0 else ""
        return f"d{self.die_size}: {self.roll} {sign}{self.con_modifier} = {self.healing} HP"


@dataclass
class ShortRestResult:
    """Complete result of a short rest for one character."""
    character_id: str
    character_name: str
    hp_before: int
    hp_after: int
    hp_healed: int
    hit_dice_spent: int
    hit_dice_remaining: int
    hit_die_rolls: List[HitDieSpendResult]
    abilities_restored: List[str]
    spell_slots_restored: Dict[int, int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "character_id": self.character_id,
            "character_name": self.character_name,
            "hp_before": self.hp_before,
            "hp_after": self.hp_after,
            "hp_healed": self.hp_healed,
            "hit_dice_spent": self.hit_dice_spent,
            "hit_dice_remaining": self.hit_dice_remaining,
            "hit_die_rolls": [
                {
                    "die_size": r.die_size,
                    "roll": r.roll,
                    "con_modifier": r.con_modifier,
                    "healing": r.healing,
                    "description": r.description,
                }
                for r in self.hit_die_rolls
            ],
            "abilities_restored": self.abilities_restored,
            "spell_slots_restored": self.spell_slots_restored,
        }


@dataclass
class LongRestResult:
    """Complete result of a long rest for one character."""
    character_id: str
    character_name: str
    hp_before: int
    hp_after: int
    hp_healed: int
    hit_dice_restored: int
    hit_dice_remaining: int
    spell_slots_restored: Dict[int, int]
    abilities_restored: List[str]
    exhaustion_reduced: bool
    exhaustion_level: int
    conditions_cleared: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "character_id": self.character_id,
            "character_name": self.character_name,
            "hp_before": self.hp_before,
            "hp_after": self.hp_after,
            "hp_healed": self.hp_healed,
            "hit_dice_restored": self.hit_dice_restored,
            "hit_dice_remaining": self.hit_dice_remaining,
            "spell_slots_restored": self.spell_slots_restored,
            "abilities_restored": self.abilities_restored,
            "exhaustion_reduced": self.exhaustion_reduced,
            "exhaustion_level": self.exhaustion_level,
            "conditions_cleared": self.conditions_cleared,
        }


@dataclass
class PartyRestResult:
    """Result of rest for entire party."""
    rest_type: RestType
    duration_hours: int
    time_of_day_after: str
    member_results: List[Dict[str, Any]]
    was_interrupted: bool = False
    interruption_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rest_type": self.rest_type.value,
            "duration_hours": self.duration_hours,
            "time_of_day_after": self.time_of_day_after,
            "member_results": self.member_results,
            "was_interrupted": self.was_interrupted,
            "interruption_reason": self.interruption_reason,
        }


@dataclass
class ShortRestRequest:
    """Request parameters for a short rest."""
    hit_dice_allocation: Dict[str, int] = field(default_factory=dict)
    # character_id -> number of hit dice to spend


@dataclass
class LongRestRequest:
    """Request parameters for a long rest."""
    has_food_and_drink: bool = True
    safe_location: bool = True
    # Can add more options like light activity, watch rotation, etc.


def perform_short_rest(
    member: "PartyMember",
    hit_dice_to_spend: int = 0
) -> ShortRestResult:
    """
    Perform a short rest for a single party member.

    Short rest rules (D&D 5e 2024):
    - Takes at least 1 hour
    - Can spend any number of available hit dice
    - Each die heals 1d[hit_die] + CON modifier (minimum 1)
    - Certain abilities restore on short rest

    Args:
        member: The party member taking the rest
        hit_dice_to_spend: Number of hit dice to spend (0 = don't spend any)

    Returns:
        ShortRestResult with complete rest information
    """
    hp_before = member.current_hp

    # Perform the rest
    rest_result = member.short_rest(hit_dice_to_spend)

    # Convert hit die roll data to proper objects
    hit_die_rolls = [
        HitDieSpendResult(
            die_size=r["die_size"],
            roll=r["roll"],
            con_modifier=r["con_mod"],
            healing=r["healing"]
        )
        for r in rest_result.get("hit_die_rolls", [])
    ]

    return ShortRestResult(
        character_id=member.id,
        character_name=member.name,
        hp_before=hp_before,
        hp_after=member.current_hp,
        hp_healed=rest_result.get("hp_healed", 0),
        hit_dice_spent=rest_result.get("hit_dice_spent", 0),
        hit_dice_remaining=rest_result.get("hit_dice_remaining", member.hit_dice_remaining),
        hit_die_rolls=hit_die_rolls,
        abilities_restored=rest_result.get("abilities_restored", []),
        spell_slots_restored=rest_result.get("spell_slots_restored", {}),
    )


def perform_long_rest(member: "PartyMember") -> LongRestResult:
    """
    Perform a long rest for a single party member.

    Long rest rules (D&D 5e 2024):
    - Takes at least 8 hours
    - Must have at least 1 HP to benefit
    - Restores all HP
    - Restores half of max hit dice (minimum 1)
    - Restores all spell slots
    - Restores most class abilities
    - Reduces exhaustion by 1 (with food/drink)
    - Clears most conditions

    Args:
        member: The party member taking the rest

    Returns:
        LongRestResult with complete rest information
    """
    hp_before = member.current_hp
    conditions_before = list(member.conditions)

    # Perform the rest
    rest_result = member.long_rest()

    return LongRestResult(
        character_id=member.id,
        character_name=member.name,
        hp_before=hp_before,
        hp_after=member.current_hp,
        hp_healed=rest_result.get("hp_healed", 0),
        hit_dice_restored=rest_result.get("hit_dice_restored", 0),
        hit_dice_remaining=member.hit_dice_remaining,
        spell_slots_restored=rest_result.get("spell_slots_restored", {}),
        abilities_restored=rest_result.get("abilities_restored", []),
        exhaustion_reduced=rest_result.get("exhaustion_reduced", False),
        exhaustion_level=member.exhaustion_level,
        conditions_cleared=conditions_before,
    )


def party_short_rest(
    session: "GameSession",
    hit_dice_allocation: Dict[str, int] = None
) -> PartyRestResult:
    """
    Perform a short rest for the entire party.

    Args:
        session: The game session
        hit_dice_allocation: Dict mapping character_id to hit dice to spend

    Returns:
        PartyRestResult with all member results
    """
    if hit_dice_allocation is None:
        hit_dice_allocation = {}

    member_results = []

    for member in session.party:
        if not member.is_active or member.is_dead:
            continue

        dice_to_spend = hit_dice_allocation.get(member.id, 0)
        result = perform_short_rest(member, dice_to_spend)
        member_results.append(result.to_dict())

    # Advance time
    session.world_state.advance_time(1)  # 1 hour

    return PartyRestResult(
        rest_type=RestType.SHORT,
        duration_hours=1,
        time_of_day_after=session.world_state.get_time_of_day(),
        member_results=member_results,
    )


def party_long_rest(
    session: "GameSession",
    has_food_and_drink: bool = True,
    safe_location: bool = True
) -> PartyRestResult:
    """
    Perform a long rest for the entire party.

    Args:
        session: The game session
        has_food_and_drink: Whether provisions are available
        safe_location: Whether the rest location is safe

    Returns:
        PartyRestResult with all member results
    """
    member_results = []

    for member in session.party:
        if member.is_dead:
            continue

        # Even unconscious characters benefit from long rest (if not dead)
        result = perform_long_rest(member)
        member_results.append(result.to_dict())

        # If didn't have food/drink, don't reduce exhaustion
        # (This is handled in long_rest, but we note it here)

    # Advance time
    session.world_state.advance_time(8)  # 8 hours

    return PartyRestResult(
        rest_type=RestType.LONG,
        duration_hours=8,
        time_of_day_after=session.world_state.get_time_of_day(),
        member_results=member_results,
    )


def calculate_recommended_hit_dice(member: "PartyMember") -> int:
    """
    Calculate recommended number of hit dice to spend based on current HP.

    Uses a simple heuristic:
    - If below 50% HP, recommend spending enough to get above 50%
    - If below 25% HP, recommend spending all available dice
    - Otherwise, recommend 0

    Args:
        member: The party member

    Returns:
        Recommended number of hit dice to spend
    """
    if member.current_hp >= member.max_hp:
        return 0

    hp_percent = member.current_hp / member.max_hp

    if hp_percent >= 0.5:
        return 0

    # Calculate average healing per die
    con_mod = (member.constitution - 10) // 2
    avg_healing = (member.hit_die_size // 2 + 1) + con_mod
    avg_healing = max(1, avg_healing)

    # Calculate HP needed
    if hp_percent < 0.25:
        # Try to get to at least 75%
        target_hp = int(member.max_hp * 0.75)
    else:
        # Try to get to at least 60%
        target_hp = int(member.max_hp * 0.60)

    hp_needed = target_hp - member.current_hp
    dice_needed = (hp_needed + avg_healing - 1) // avg_healing  # Round up

    return min(dice_needed, member.hit_dice_remaining)


def get_rest_preview(
    member: "PartyMember",
    rest_type: RestType,
    hit_dice_to_spend: int = 0
) -> Dict[str, Any]:
    """
    Get a preview of what a rest would provide without performing it.

    Args:
        member: The party member
        rest_type: Type of rest
        hit_dice_to_spend: For short rest, how many dice to spend

    Returns:
        Dict with preview information
    """
    con_mod = (member.constitution - 10) // 2

    if rest_type == RestType.SHORT:
        # Estimate healing from hit dice
        avg_roll = member.hit_die_size // 2 + 1
        avg_healing_per_die = max(1, avg_roll + con_mod)
        dice_can_spend = min(hit_dice_to_spend, member.hit_dice_remaining)
        estimated_healing = dice_can_spend * avg_healing_per_die
        max_healing = member.max_hp - member.current_hp

        return {
            "rest_type": "short",
            "duration_hours": 1,
            "hit_dice_available": member.hit_dice_remaining,
            "hit_dice_to_spend": dice_can_spend,
            "estimated_healing": min(estimated_healing, max_healing),
            "avg_healing_per_die": avg_healing_per_die,
            "abilities_that_restore": _get_short_rest_abilities(member),
            "recommended_dice": calculate_recommended_hit_dice(member),
        }
    else:  # Long rest
        return {
            "rest_type": "long",
            "duration_hours": 8,
            "hp_to_restore": member.max_hp - member.current_hp,
            "hit_dice_to_restore": max(1, member.hit_dice_total // 2),
            "current_exhaustion": member.exhaustion_level,
            "exhaustion_will_reduce": member.exhaustion_level > 0,
            "spell_slots_will_restore": True if member.spell_slots else False,
            "conditions_to_clear": list(member.conditions),
        }


def _get_short_rest_abilities(member: "PartyMember") -> List[str]:
    """Get list of abilities that restore on short rest for this character."""
    abilities = []

    char_class = member.character_class.lower()

    # Fighter
    if char_class == "fighter":
        abilities.extend(["Second Wind", "Action Surge"])

    # Warlock
    if char_class == "warlock":
        abilities.append("Pact Magic Spell Slots")

    # Monk
    if char_class == "monk":
        abilities.append("Ki Points")

    # Bard (Font of Inspiration at level 5+)
    if char_class == "bard" and member.level >= 5:
        abilities.append("Bardic Inspiration")

    # Cleric/Paladin Channel Divinity (if certain features)
    # Add more as needed

    return abilities
