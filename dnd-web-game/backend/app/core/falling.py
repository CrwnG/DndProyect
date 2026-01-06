"""
D&D Combat Engine - Falling Damage System
Handles fall damage calculations including Monk Slow Fall and Feather Fall
"""

from typing import Dict, Any, Optional, Tuple
from app.core.dice import roll_dice


def calculate_fall_damage(
    fall_distance_ft: int,
    combatant_stats: Dict[str, Any],
    conditions: list = None
) -> Tuple[int, str, bool]:
    """
    Calculate falling damage based on D&D 5e rules.

    Rules:
    - 1d6 bludgeoning damage per 10 feet fallen
    - Maximum 20d6 (200 feet)
    - Creature lands prone unless it avoids damage

    Args:
        fall_distance_ft: Distance fallen in feet
        combatant_stats: Combatant's stats dictionary
        conditions: List of active conditions/effects

    Returns:
        Tuple of (damage, description, lands_prone)
    """
    if fall_distance_ft < 10:
        return 0, "Fall too short for damage", False

    conditions = conditions or []

    # Check for Feather Fall - negates all falling damage
    if "feather_fall" in conditions or "feather_falling" in conditions:
        return 0, "Feather Fall negates falling damage", False

    # Calculate base damage dice (1d6 per 10ft, max 20d6)
    damage_dice = min(fall_distance_ft // 10, 20)
    base_damage = roll_dice(f"{damage_dice}d6")

    damage = base_damage
    description_parts = [f"Fell {fall_distance_ft}ft: {damage_dice}d6 = {base_damage} bludgeoning"]

    # Check for Monk Slow Fall (level 4+)
    # Reduces damage by 5 * monk level
    class_id = combatant_stats.get("class_id", combatant_stats.get("class", "")).lower()
    level = combatant_stats.get("level", 1)

    if class_id == "monk" and level >= 4:
        slow_fall_reduction = level * 5
        damage = max(0, damage - slow_fall_reduction)
        description_parts.append(f"Slow Fall reduces by {slow_fall_reduction}")

        if damage == 0:
            return 0, " | ".join(description_parts) + " | No damage!", False

    # Check for features that might reduce falling damage
    features = combatant_stats.get("features", [])

    # Barbarian Rage - resistance to bludgeoning
    if "raging" in conditions:
        damage = damage // 2
        description_parts.append("Rage halves bludgeoning")

    # Check for bludgeoning resistance
    resistances = combatant_stats.get("resistances", [])
    if "bludgeoning" in resistances and "raging" not in conditions:
        damage = damage // 2
        description_parts.append("Resistance halves damage")

    # Check for bludgeoning immunity
    immunities = combatant_stats.get("immunities", [])
    if "bludgeoning" in immunities:
        return 0, "Immune to bludgeoning damage", False

    # Creature lands prone unless damage was negated
    lands_prone = damage > 0

    if lands_prone:
        description_parts.append("Lands prone")

    return damage, " | ".join(description_parts), lands_prone


def apply_falling_damage(
    combatant: Any,
    combatant_stats: Dict[str, Any],
    fall_distance_ft: int,
    combat_state: Any = None
) -> Dict[str, Any]:
    """
    Apply falling damage to a combatant.

    Args:
        combatant: The combatant object
        combatant_stats: Combatant's stats dictionary
        fall_distance_ft: Distance fallen in feet
        combat_state: Optional combat state for event tracking

    Returns:
        Dictionary with damage result details
    """
    conditions = getattr(combatant, "conditions", [])
    if isinstance(conditions, str):
        conditions = [conditions]

    # Also check stats for conditions
    stat_conditions = combatant_stats.get("conditions", [])
    all_conditions = list(set(conditions + stat_conditions))

    damage, description, lands_prone = calculate_fall_damage(
        fall_distance_ft,
        combatant_stats,
        all_conditions
    )

    result = {
        "success": True,
        "damage": damage,
        "description": description,
        "lands_prone": lands_prone,
        "fall_distance_ft": fall_distance_ft,
        "combatant_id": combatant.id if hasattr(combatant, 'id') else None
    }

    if damage > 0:
        # Apply the damage
        old_hp = combatant.hp
        combatant.hp = max(0, combatant.hp - damage)
        result["old_hp"] = old_hp
        result["new_hp"] = combatant.hp

        # Check for death
        if combatant.hp <= 0:
            result["unconscious"] = True
            if hasattr(combatant, 'is_active'):
                # Player goes unconscious, monster dies
                from app.core.initiative import CombatantType
                if hasattr(combatant, 'combatant_type') and combatant.combatant_type == CombatantType.PLAYER:
                    result["death_saves_needed"] = True
                else:
                    combatant.is_active = False
                    result["defeated"] = True

    if lands_prone:
        # Add prone condition
        if hasattr(combatant, 'conditions'):
            if "prone" not in combatant.conditions:
                combatant.conditions.append("prone")
        result["applied_prone"] = True

    # Log the event if combat state available
    if combat_state and hasattr(combat_state, 'add_event'):
        event_type = "fall_damage" if damage > 0 else "fall_safe"
        combat_state.add_event(
            event_type,
            description,
            combatant_id=result["combatant_id"]
        )

    return result


def check_fall_from_position(
    grid: Any,
    from_x: int,
    from_y: int,
    to_x: int,
    to_y: int
) -> int:
    """
    Check if moving between positions causes a fall.

    Args:
        grid: The combat grid
        from_x, from_y: Starting position
        to_x, to_y: Destination position

    Returns:
        Fall distance in feet (0 if no fall)
    """
    if not grid:
        return 0

    try:
        from_cell = grid.cells[from_y][from_x]
        to_cell = grid.cells[to_y][to_x]

        from_elevation = getattr(from_cell, 'elevation', 0)
        to_elevation = getattr(to_cell, 'elevation', 0)

        # Check if destination is significantly lower
        elevation_diff = from_elevation - to_elevation

        # Only consider it a fall if dropping 10+ feet
        if elevation_diff >= 10:
            return elevation_diff

        return 0
    except (IndexError, AttributeError):
        return 0


def check_pit_fall(
    grid: Any,
    x: int,
    y: int
) -> Tuple[bool, int]:
    """
    Check if a position is a pit and calculate fall distance.

    Args:
        grid: The combat grid
        x, y: Position to check

    Returns:
        Tuple of (is_pit, fall_distance_ft)
    """
    if not grid:
        return False, 0

    try:
        cell = grid.cells[y][x]

        # Check terrain type for pit
        from app.core.movement import TerrainType
        terrain = getattr(cell, 'terrain', None)

        if terrain == TerrainType.PIT:
            # Pits have configurable depth, default 10ft
            pit_depth = getattr(cell, 'pit_depth', 10)
            return True, pit_depth

        return False, 0
    except (IndexError, AttributeError):
        return False, 0


def can_avoid_fall(
    combatant_stats: Dict[str, Any],
    conditions: list = None
) -> Tuple[bool, str]:
    """
    Check if a combatant can avoid a fall (e.g., flying, levitating).

    Args:
        combatant_stats: Combatant's stats
        conditions: Active conditions

    Returns:
        Tuple of (can_avoid, reason)
    """
    conditions = conditions or []

    # Flying creatures don't fall (unless incapacitated)
    if combatant_stats.get("flying", False):
        incapacitated_conditions = ["unconscious", "stunned", "paralyzed", "incapacitated"]
        if not any(c in conditions for c in incapacitated_conditions):
            return True, "Flying"

    # Levitate spell
    if "levitating" in conditions or "levitate" in conditions:
        return True, "Levitating"

    # Fly spell
    if "fly" in conditions:
        incapacitated_conditions = ["unconscious", "stunned", "paralyzed", "incapacitated"]
        if not any(c in conditions for c in incapacitated_conditions):
            return True, "Fly spell"

    # Hover trait (some creatures)
    if combatant_stats.get("hover", False):
        return True, "Hover"

    return False, ""
