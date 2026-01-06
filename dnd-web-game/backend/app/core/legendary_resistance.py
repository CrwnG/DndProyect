"""
Legendary Resistance System for D&D 5e 2024

Legendary creatures can choose to succeed on a failed saving throw
by using one of their legendary resistances.

This module provides:
- LegendaryResistanceState: Tracks uses remaining
- Functions to parse, check, and use legendary resistance
- AI decision logic for when to use legendary resistance
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Tuple
import re


@dataclass
class LegendaryResistanceState:
    """Tracks legendary resistance uses for a creature."""
    max_uses: int = 0
    uses_remaining: int = 0
    used_this_combat: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_uses": self.max_uses,
            "uses_remaining": self.uses_remaining,
            "used_this_combat": self.used_this_combat,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "LegendaryResistanceState":
        return cls(
            max_uses=data.get("max_uses", 0),
            uses_remaining=data.get("uses_remaining", 0),
            used_this_combat=data.get("used_this_combat", 0),
        )


def parse_legendary_resistance(traits: List[Dict[str, Any]]) -> Optional[int]:
    """
    Parse legendary resistance count from monster traits.

    Looks for traits named like "Legendary Resistance (3/Day)".

    Args:
        traits: List of trait dicts with "name" and "description" keys

    Returns:
        Number of legendary resistance uses, or None if not found
    """
    for trait in traits:
        name = trait.get("name", "").lower()
        if "legendary resistance" in name:
            # Extract number from format like "(3/Day)" or "(3/day)"
            match = re.search(r"\((\d+)/[dD]ay\)", trait.get("name", ""))
            if match:
                return int(match.group(1))

            # Also check description for the pattern
            description = trait.get("description", "")
            match = re.search(r"(\d+)/[dD]ay", description)
            if match:
                return int(match.group(1))

            # Default to 3 if we found the trait but couldn't parse count
            return 3

    return None


def initialize_legendary_resistance(
    traits: List[Dict[str, Any]]
) -> Optional[LegendaryResistanceState]:
    """
    Initialize legendary resistance state from monster traits.

    Args:
        traits: List of monster traits

    Returns:
        LegendaryResistanceState if creature has legendary resistance, else None
    """
    uses = parse_legendary_resistance(traits)
    if uses is None:
        return None

    return LegendaryResistanceState(
        max_uses=uses,
        uses_remaining=uses,
        used_this_combat=0,
    )


def has_legendary_resistance(state: Optional[LegendaryResistanceState]) -> bool:
    """Check if creature has legendary resistance available."""
    if state is None:
        return False
    return state.uses_remaining > 0


def use_legendary_resistance(
    state: LegendaryResistanceState
) -> Tuple[bool, str]:
    """
    Use one legendary resistance to succeed on a failed save.

    Args:
        state: Current legendary resistance state

    Returns:
        Tuple of (success, message)
    """
    if state.uses_remaining <= 0:
        return False, "No legendary resistance uses remaining"

    state.uses_remaining -= 1
    state.used_this_combat += 1

    remaining = state.uses_remaining
    return True, f"Used Legendary Resistance! ({remaining}/{state.max_uses} remaining)"


def restore_legendary_resistance(state: LegendaryResistanceState) -> int:
    """
    Restore all legendary resistance uses (typically after long rest).

    Returns:
        Number of uses restored
    """
    restored = state.max_uses - state.uses_remaining
    state.uses_remaining = state.max_uses
    state.used_this_combat = 0
    return restored


# =============================================================================
# AI DECISION LOGIC
# =============================================================================

# Conditions that are particularly dangerous and worth using LR on
CRITICAL_CONDITIONS = [
    "paralyzed",
    "petrified",
    "stunned",
    "unconscious",
    "dominated",  # If such a thing exists
]

# Conditions worth using LR on if we have uses to spare
IMPORTANT_CONDITIONS = [
    "frightened",
    "charmed",
    "restrained",
    "blinded",
    "incapacitated",
]

# Spells that are worth using LR against (high impact)
HIGH_IMPACT_EFFECTS = [
    "hold monster",
    "hold person",
    "polymorph",
    "banishment",
    "maze",
    "feeblemind",
    "dominate",
    "power word stun",
    "power word kill",
    "finger of death",
    "disintegrate",
    "flesh to stone",
]


def should_use_legendary_resistance(
    state: LegendaryResistanceState,
    failed_save_type: str,
    effect_name: Optional[str] = None,
    effect_damage: int = 0,
    condition_applied: Optional[str] = None,
    creature_current_hp: int = 100,
    creature_max_hp: int = 100,
) -> Tuple[bool, str]:
    """
    AI logic to determine if legendary resistance should be used.

    Considers:
    - How many uses remain
    - The severity of the effect being avoided
    - Current HP (save resources if near death anyway)
    - The type of effect (conditions are usually worse than damage)

    Args:
        state: Legendary resistance state
        failed_save_type: Type of save that was failed
        effect_name: Name of the spell/effect causing the save
        effect_damage: Damage that would be taken on failed save
        condition_applied: Condition that would be applied on failure
        creature_current_hp: Current HP of the creature
        creature_max_hp: Maximum HP of the creature

    Returns:
        Tuple of (should_use, reasoning)
    """
    if not has_legendary_resistance(state):
        return False, "No legendary resistance available"

    uses_remaining = state.uses_remaining
    hp_percent = creature_current_hp / max(1, creature_max_hp)

    # Don't waste LR if we're about to die anyway
    if hp_percent < 0.1 and uses_remaining <= 1:
        return False, "HP too low to justify using last legendary resistance"

    # Always use for critical conditions
    if condition_applied and condition_applied.lower() in CRITICAL_CONDITIONS:
        return True, f"Using LR to avoid critical condition: {condition_applied}"

    # Check for high-impact spell effects
    if effect_name:
        effect_lower = effect_name.lower()
        for high_impact in HIGH_IMPACT_EFFECTS:
            if high_impact in effect_lower:
                return True, f"Using LR against high-impact effect: {effect_name}"

    # Use for important conditions if we have uses to spare
    if condition_applied and condition_applied.lower() in IMPORTANT_CONDITIONS:
        if uses_remaining >= 2:
            return True, f"Using LR to avoid important condition: {condition_applied}"
        elif hp_percent > 0.5:
            return True, f"Using LR (healthy enough to use last one on {condition_applied})"

    # Consider using for high damage
    damage_percent = effect_damage / max(1, creature_max_hp)
    if damage_percent > 0.25 and uses_remaining >= 2:
        return True, f"Using LR to avoid significant damage ({effect_damage} HP)"

    # Save LR for potentially worse effects
    return False, "Saving legendary resistance for more dangerous effects"


def get_legendary_resistance_summary(
    state: Optional[LegendaryResistanceState]
) -> Dict[str, Any]:
    """Get a summary of legendary resistance status for display."""
    if state is None:
        return {
            "has_legendary_resistance": False,
        }

    return {
        "has_legendary_resistance": True,
        "uses_remaining": state.uses_remaining,
        "max_uses": state.max_uses,
        "used_this_combat": state.used_this_combat,
        "description": f"Legendary Resistance ({state.uses_remaining}/{state.max_uses})",
    }


# =============================================================================
# COMBAT INTEGRATION HELPERS
# =============================================================================

def check_and_apply_legendary_resistance(
    combatant_stats: Dict[str, Any],
    failed_save_type: str,
    effect_name: Optional[str] = None,
    effect_damage: int = 0,
    condition_applied: Optional[str] = None,
) -> Tuple[bool, bool, str]:
    """
    Check if a combatant should use legendary resistance and apply if so.

    This is the main integration point for the combat engine.

    Args:
        combatant_stats: Combatant's stats dict (contains legendary_resistance state)
        failed_save_type: Type of save that was failed
        effect_name: Name of the effect
        effect_damage: Potential damage
        condition_applied: Condition that would be applied

    Returns:
        Tuple of (has_lr, used_lr, message)
    """
    # Get or initialize legendary resistance state
    lr_data = combatant_stats.get("legendary_resistance")
    if not lr_data:
        # Try to parse from traits
        traits = combatant_stats.get("traits", [])
        lr_state = initialize_legendary_resistance(traits)
        if lr_state:
            combatant_stats["legendary_resistance"] = lr_state.to_dict()
            lr_data = combatant_stats["legendary_resistance"]
        else:
            return False, False, ""

    # Create state object
    state = LegendaryResistanceState.from_dict(lr_data)

    if not has_legendary_resistance(state):
        return True, False, "Legendary Resistance exhausted"

    # AI decision
    current_hp = combatant_stats.get("current_hp", 100)
    max_hp = combatant_stats.get("max_hp", 100)

    should_use, reasoning = should_use_legendary_resistance(
        state=state,
        failed_save_type=failed_save_type,
        effect_name=effect_name,
        effect_damage=effect_damage,
        condition_applied=condition_applied,
        creature_current_hp=current_hp,
        creature_max_hp=max_hp,
    )

    if should_use:
        success, message = use_legendary_resistance(state)
        if success:
            # Update the stats dict
            combatant_stats["legendary_resistance"] = state.to_dict()
            return True, True, message

    return True, False, reasoning
