"""
D&D Combat Engine - Throwing System
BG3-style throwing of objects and creatures
"""

from enum import Enum
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass
from app.core.dice import roll_dice, roll_d20


class ThrowableType(str, Enum):
    """Types of throwable objects."""
    ROCK = "rock"
    BARREL = "barrel"
    EXPLOSIVE_BARREL = "explosive_barrel"
    ACID_BARREL = "acid_barrel"
    OIL_BARREL = "oil_barrel"
    POTION = "potion"
    CORPSE = "corpse"
    CREATURE = "creature"  # Throwing grappled creatures
    WEAPON = "weapon"  # Improvised thrown weapon
    FURNITURE = "furniture"  # Tables, chairs, etc.


@dataclass
class ThrowableObject:
    """Represents a throwable object."""
    object_type: ThrowableType
    weight_lb: float
    damage_dice: str = "1d4"
    damage_type: str = "bludgeoning"
    is_explosive: bool = False
    explosion_radius: int = 0
    explosion_damage: str = ""
    explosion_type: str = ""
    surface_effect: str = ""  # Surface created on impact
    name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "object_type": self.object_type.value,
            "weight_lb": self.weight_lb,
            "damage_dice": self.damage_dice,
            "damage_type": self.damage_type,
            "is_explosive": self.is_explosive,
            "explosion_radius": self.explosion_radius,
            "explosion_damage": self.explosion_damage,
            "explosion_type": self.explosion_type,
            "surface_effect": self.surface_effect,
            "name": self.name or self.object_type.value
        }


# Predefined throwable objects
THROWABLE_OBJECTS: Dict[str, ThrowableObject] = {
    "rock": ThrowableObject(
        object_type=ThrowableType.ROCK,
        weight_lb=5,
        damage_dice="1d4",
        damage_type="bludgeoning",
        name="Rock"
    ),
    "large_rock": ThrowableObject(
        object_type=ThrowableType.ROCK,
        weight_lb=20,
        damage_dice="2d6",
        damage_type="bludgeoning",
        name="Large Rock"
    ),
    "barrel": ThrowableObject(
        object_type=ThrowableType.BARREL,
        weight_lb=50,
        damage_dice="2d6",
        damage_type="bludgeoning",
        name="Barrel"
    ),
    "explosive_barrel": ThrowableObject(
        object_type=ThrowableType.EXPLOSIVE_BARREL,
        weight_lb=50,
        damage_dice="1d6",
        damage_type="bludgeoning",
        is_explosive=True,
        explosion_radius=2,  # 10ft radius
        explosion_damage="3d6",
        explosion_type="fire",
        surface_effect="fire",
        name="Explosive Barrel"
    ),
    "acid_barrel": ThrowableObject(
        object_type=ThrowableType.ACID_BARREL,
        weight_lb=50,
        damage_dice="1d6",
        damage_type="bludgeoning",
        is_explosive=True,
        explosion_radius=2,
        explosion_damage="2d6",
        explosion_type="acid",
        surface_effect="acid",
        name="Acid Barrel"
    ),
    "oil_barrel": ThrowableObject(
        object_type=ThrowableType.OIL_BARREL,
        weight_lb=50,
        damage_dice="1d6",
        damage_type="bludgeoning",
        surface_effect="oil",
        name="Oil Barrel"
    ),
    "healing_potion": ThrowableObject(
        object_type=ThrowableType.POTION,
        weight_lb=1,
        damage_dice="0",
        damage_type="",
        name="Healing Potion"
    ),
    "alchemist_fire": ThrowableObject(
        object_type=ThrowableType.POTION,
        weight_lb=1,
        damage_dice="1d4",
        damage_type="fire",
        surface_effect="fire",
        name="Alchemist's Fire"
    ),
    "acid_vial": ThrowableObject(
        object_type=ThrowableType.POTION,
        weight_lb=1,
        damage_dice="2d6",
        damage_type="acid",
        surface_effect="acid",
        name="Acid Vial"
    ),
    "chair": ThrowableObject(
        object_type=ThrowableType.FURNITURE,
        weight_lb=15,
        damage_dice="1d6",
        damage_type="bludgeoning",
        name="Chair"
    ),
    "table": ThrowableObject(
        object_type=ThrowableType.FURNITURE,
        weight_lb=40,
        damage_dice="2d6",
        damage_type="bludgeoning",
        name="Table"
    )
}


def calculate_throw_distance(strength_score: int, weight_lb: float) -> int:
    """
    Calculate maximum throw distance based on strength and object weight.

    Based on D&D 5e improvised weapon rules with modifications for heavier objects.

    Args:
        strength_score: Thrower's STR score (not modifier)
        weight_lb: Weight of object in pounds

    Returns:
        Maximum throw distance in feet
    """
    # Base distance from strength
    # STR 10 = 20ft base, +5ft per 2 STR above 10
    base_distance = 20 + max(0, (strength_score - 10) // 2) * 5

    # Weight penalty
    # Light (under 5 lb): no penalty
    # Medium (5-20 lb): -5ft per 5 lb
    # Heavy (20-50 lb): -5ft per 10 lb
    # Very Heavy (50+ lb): requires STR 15+, heavily penalized

    if weight_lb < 5:
        weight_penalty = 0
    elif weight_lb < 20:
        weight_penalty = int((weight_lb - 5) / 5) * 5
    elif weight_lb < 50:
        weight_penalty = 15 + int((weight_lb - 20) / 10) * 5
    else:
        # Very heavy - require high strength
        if strength_score < 15:
            return 0  # Can't throw
        weight_penalty = 25 + int((weight_lb - 50) / 20) * 5

    # Minimum 5ft if throwable at all
    return max(5, base_distance - weight_penalty)


def calculate_throw_damage_bonus(strength_mod: int, weight_lb: float) -> int:
    """
    Calculate damage bonus for thrown objects.

    Args:
        strength_mod: Thrower's STR modifier
        weight_lb: Weight of object

    Returns:
        Bonus damage to add
    """
    # Light objects (under 5 lb): half STR mod
    # Medium objects (5-20 lb): full STR mod
    # Heavy objects (20+ lb): 1.5x STR mod (rounded down)

    if weight_lb < 5:
        return max(0, strength_mod // 2)
    elif weight_lb < 20:
        return strength_mod
    else:
        return int(strength_mod * 1.5)


def throw_object(
    thrower_stats: Dict[str, Any],
    throwable: ThrowableObject,
    target_x: int,
    target_y: int,
    target_combatant: Any = None,
    surface_manager: Any = None
) -> Dict[str, Any]:
    """
    Execute a throw action.

    Args:
        thrower_stats: Stats of the thrower
        throwable: The object being thrown
        target_x, target_y: Target position
        target_combatant: Target combatant (if targeting a creature)
        surface_manager: Surface manager for creating surface effects

    Returns:
        Result dictionary with damage, effects, etc.
    """
    str_score = thrower_stats.get("strength", 10)
    str_mod = thrower_stats.get("str_mod", (str_score - 10) // 2)
    proficiency = thrower_stats.get("proficiency_bonus", 2)

    # Check if can throw based on distance
    max_distance = calculate_throw_distance(str_score, throwable.weight_lb)
    if max_distance == 0:
        return {
            "success": False,
            "reason": f"Object too heavy to throw (requires STR 15+)"
        }

    result = {
        "success": True,
        "object": throwable.to_dict(),
        "target_position": (target_x, target_y),
        "max_distance": max_distance,
        "damage": 0,
        "damage_type": throwable.damage_type,
        "hit": False,
        "explosion": None,
        "surface_created": None
    }

    # If targeting a creature, make attack roll
    if target_combatant:
        # Improvised weapon attack: STR + proficiency (if proficient with improvised)
        # Most characters are NOT proficient with improvised weapons
        has_tavern_brawler = "tavern_brawler" in thrower_stats.get("feats", [])
        attack_bonus = str_mod + (proficiency if has_tavern_brawler else 0)

        target_ac = target_combatant.armor_class if hasattr(target_combatant, 'armor_class') else 10

        # Roll attack
        attack_roll = roll_d20(modifier=attack_bonus)
        result["attack_roll"] = attack_roll.total
        result["target_ac"] = target_ac

        if attack_roll.natural_1:
            result["hit"] = False
            result["critical_miss"] = True
        elif attack_roll.natural_20 or attack_roll.total >= target_ac:
            result["hit"] = True
            result["critical"] = attack_roll.natural_20

            # Calculate damage
            if throwable.damage_dice and throwable.damage_dice != "0":
                base_damage = roll_dice(throwable.damage_dice)
                damage_bonus = calculate_throw_damage_bonus(str_mod, throwable.weight_lb)

                # Double dice on crit
                if result.get("critical"):
                    base_damage += roll_dice(throwable.damage_dice)

                result["damage"] = base_damage + damage_bonus
                result["damage_breakdown"] = {
                    "dice": base_damage,
                    "str_bonus": damage_bonus
                }

    # Handle explosions
    if throwable.is_explosive:
        explosion_result = _handle_explosion(
            target_x, target_y,
            throwable.explosion_radius,
            throwable.explosion_damage,
            throwable.explosion_type,
            surface_manager
        )
        result["explosion"] = explosion_result

    # Create surface effect on impact
    if throwable.surface_effect and surface_manager:
        from app.core.surfaces import SurfaceType, SurfaceManager
        try:
            surface_type = SurfaceType(throwable.surface_effect)
            surface_result = surface_manager.add_surface(
                target_x, target_y,
                surface_type,
                duration_rounds=3
            )
            result["surface_created"] = surface_result
        except ValueError:
            pass  # Invalid surface type

    return result


def _handle_explosion(
    x: int,
    y: int,
    radius: int,
    damage_dice: str,
    damage_type: str,
    surface_manager: Any = None
) -> Dict[str, Any]:
    """
    Handle an explosion at a position.

    Args:
        x, y: Center of explosion
        radius: Radius in grid squares (5ft each)
        damage_dice: Damage dice for explosion
        damage_type: Type of damage
        surface_manager: For creating fire surfaces

    Returns:
        Explosion result
    """
    result = {
        "center": (x, y),
        "radius": radius,
        "radius_ft": radius * 5,
        "damage_dice": damage_dice,
        "damage_type": damage_type,
        "affected_cells": [],
        "surface_effects": []
    }

    # Calculate affected cells
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            # Check if within circular radius
            distance_sq = dx * dx + dy * dy
            if distance_sq <= radius * radius:
                cell = (x + dx, y + dy)
                result["affected_cells"].append(cell)

                # Create fire surface on explosion
                if damage_type == "fire" and surface_manager:
                    from app.core.surfaces import SurfaceType
                    surface_manager.add_surface(
                        cell[0], cell[1],
                        SurfaceType.FIRE,
                        duration_rounds=2
                    )
                    result["surface_effects"].append({
                        "position": cell,
                        "surface": "fire"
                    })

    # Roll damage once (shared by all targets in area)
    if damage_dice:
        result["damage_rolled"] = roll_dice(damage_dice)

    return result


def throw_creature(
    thrower_stats: Dict[str, Any],
    grappled_creature: Any,
    grappled_stats: Dict[str, Any],
    target_x: int,
    target_y: int,
    target_combatant: Any = None
) -> Dict[str, Any]:
    """
    Throw a grappled creature.

    Requires:
    - Creature must be grappled by the thrower
    - Creature must be at least one size smaller than thrower
    - Uses Athletics check, not attack roll

    Args:
        thrower_stats: Thrower's stats
        grappled_creature: The creature being thrown
        grappled_stats: Stats of the grappled creature
        target_x, target_y: Target position
        target_combatant: Another creature to hit (optional)

    Returns:
        Result dictionary
    """
    # Size comparison
    size_order = ["tiny", "small", "medium", "large", "huge", "gargantuan"]
    thrower_size = thrower_stats.get("size", "medium").lower()
    target_size = grappled_stats.get("size", "medium").lower()

    try:
        thrower_idx = size_order.index(thrower_size)
        target_idx = size_order.index(target_size)
    except ValueError:
        return {"success": False, "reason": "Invalid creature size"}

    if target_idx >= thrower_idx:
        return {
            "success": False,
            "reason": "Can only throw creatures at least one size smaller"
        }

    # Calculate throw distance based on size difference and strength
    str_score = thrower_stats.get("strength", 10)
    size_diff = thrower_idx - target_idx

    # Base distance: 10ft for 1 size smaller, +5ft per additional size
    base_distance = 10 + (size_diff - 1) * 5

    # STR bonus: +5ft per 2 points above 10
    str_bonus = max(0, (str_score - 10) // 2) * 5

    throw_distance = base_distance + str_bonus

    # Estimate weight (creatures are heavier than objects)
    estimated_weight = {
        "tiny": 10,
        "small": 50,
        "medium": 150,
        "large": 500,
        "huge": 2000
    }
    weight = estimated_weight.get(target_size, 150)

    result = {
        "success": True,
        "thrown_creature": grappled_creature.id if hasattr(grappled_creature, 'id') else None,
        "target_position": (target_x, target_y),
        "throw_distance": throw_distance,
        "thrown_damage": 0,
        "target_damage": 0
    }

    # Both creatures take fall damage based on distance thrown
    # Treat as falling from height = throw distance / 2
    fall_height = throw_distance // 2

    if fall_height >= 10:
        from app.core.falling import calculate_fall_damage

        # Thrown creature takes fall damage
        thrown_damage, thrown_desc, thrown_prone = calculate_fall_damage(
            fall_height, grappled_stats, grappled_creature.conditions if hasattr(grappled_creature, 'conditions') else []
        )
        result["thrown_damage"] = thrown_damage
        result["thrown_description"] = thrown_desc
        result["thrown_prone"] = thrown_prone

    # If hitting another creature
    if target_combatant:
        str_mod = thrower_stats.get("str_mod", (str_score - 10) // 2)
        proficiency = thrower_stats.get("proficiency_bonus", 2)

        # Athletics check vs target's AC
        athletics_bonus = str_mod + proficiency
        athletics_check = roll_d20(modifier=athletics_bonus)

        target_ac = target_combatant.armor_class if hasattr(target_combatant, 'armor_class') else 10

        result["athletics_check"] = athletics_check.total
        result["target_ac"] = target_ac

        if athletics_check.total >= target_ac:
            # Both target and thrown creature take damage
            impact_damage = roll_dice("2d6") + str_mod
            result["target_damage"] = impact_damage
            result["thrown_damage"] = result.get("thrown_damage", 0) + impact_damage
            result["hit_target"] = True

            # Both end up prone
            result["target_prone"] = True
            result["thrown_prone"] = True
        else:
            result["hit_target"] = False

    return result


def get_throwable_objects_at(grid: Any, x: int, y: int) -> List[ThrowableObject]:
    """
    Get list of throwable objects at a grid position.

    Args:
        grid: The combat grid
        x, y: Position to check

    Returns:
        List of throwable objects
    """
    throwables = []

    if not grid:
        return throwables

    try:
        cell = grid.cells[y][x]

        # Check cell features for throwable objects
        features = getattr(cell, 'features', [])
        for feature in features:
            feature_name = feature.lower() if isinstance(feature, str) else ""
            if "barrel" in feature_name:
                if "explosive" in feature_name or "fire" in feature_name:
                    throwables.append(THROWABLE_OBJECTS["explosive_barrel"])
                elif "acid" in feature_name:
                    throwables.append(THROWABLE_OBJECTS["acid_barrel"])
                elif "oil" in feature_name:
                    throwables.append(THROWABLE_OBJECTS["oil_barrel"])
                else:
                    throwables.append(THROWABLE_OBJECTS["barrel"])
            elif "rock" in feature_name or "stone" in feature_name:
                if "large" in feature_name or "boulder" in feature_name:
                    throwables.append(THROWABLE_OBJECTS["large_rock"])
                else:
                    throwables.append(THROWABLE_OBJECTS["rock"])
            elif "chair" in feature_name:
                throwables.append(THROWABLE_OBJECTS["chair"])
            elif "table" in feature_name:
                throwables.append(THROWABLE_OBJECTS["table"])

        # Check for items/loot that can be thrown
        items = getattr(cell, 'items', [])
        for item in items:
            item_name = item.get("name", "").lower() if isinstance(item, dict) else str(item).lower()
            if "alchemist" in item_name and "fire" in item_name:
                throwables.append(THROWABLE_OBJECTS["alchemist_fire"])
            elif "acid" in item_name:
                throwables.append(THROWABLE_OBJECTS["acid_vial"])

    except (IndexError, AttributeError):
        pass

    return throwables
