"""
Monster Ability System for D&D 5e 2024.

Parses and executes monster special abilities from JSON data.
Handles breath weapons, multiattack, legendary actions, eye rays, etc.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum
import re
import random

from app.core.dice import roll_damage, roll_d20


class AbilityType(Enum):
    """Types of monster abilities."""
    MELEE_ATTACK = "melee_attack"
    RANGED_ATTACK = "ranged_attack"
    BREATH_WEAPON = "breath_weapon"
    MULTIATTACK = "multiattack"
    FRIGHTFUL_PRESENCE = "frightful_presence"
    LEGENDARY_ACTION = "legendary_action"
    SPELL = "spell"
    SPECIAL = "special"
    EYE_RAY = "eye_ray"
    MIND_BLAST = "mind_blast"
    AOE_SAVE = "aoe_save"  # Generic area-of-effect with save


class AreaShape(Enum):
    """Shapes of area-of-effect abilities."""
    LINE = "line"
    CONE = "cone"
    SPHERE = "sphere"
    CUBE = "cube"
    CYLINDER = "cylinder"
    SINGLE_TARGET = "single_target"


@dataclass
class MonsterAbility:
    """Parsed monster ability with structured combat data."""
    id: str
    name: str
    original_description: str
    ability_type: AbilityType

    # Attack properties
    attack_bonus: Optional[int] = None
    reach: Optional[int] = None

    # Damage properties
    damage_dice: Optional[str] = None  # e.g., "2d10+6"
    damage_type: Optional[str] = None  # e.g., "piercing", "acid"
    extra_damage_dice: Optional[str] = None  # e.g., "1d8" for extra acid
    extra_damage_type: Optional[str] = None

    # Save properties
    save_dc: Optional[int] = None
    save_type: Optional[str] = None  # "dex", "str", "con", "wis", etc.
    half_on_save: bool = True  # Most breath weapons deal half on success

    # Area properties
    area_shape: Optional[AreaShape] = None
    area_size: Optional[int] = None  # In feet (e.g., 60 for "60-foot line")
    area_width: Optional[int] = None  # For lines (e.g., 5 for "5 feet wide")

    # Recharge properties
    recharge_type: Optional[str] = None  # "5-6", "6", "short_rest", "long_rest"
    recharge_min: Optional[int] = None  # Minimum d6 roll to recharge (e.g., 5)
    uses_per_day: Optional[int] = None  # For "3/Day" abilities

    # Multiattack components
    multiattack_pattern: Optional[List[str]] = None  # ["bite", "claw", "claw"]
    includes_frightful_presence: bool = False

    # Effect properties
    conditions: List[str] = field(default_factory=list)  # ["frightened", "prone"]
    duration: Optional[str] = None  # "1 minute", "until end of next turn"

    # Legendary action cost
    legendary_cost: int = 1  # 1, 2, or 3 actions

    def is_available(self, recharge_state: Dict[str, bool]) -> bool:
        """Check if ability is currently available based on recharge state."""
        if self.recharge_type:
            return recharge_state.get(self.id, True)
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "name": self.name,
            "ability_type": self.ability_type.value,
            "damage_dice": self.damage_dice,
            "damage_type": self.damage_type,
            "save_dc": self.save_dc,
            "save_type": self.save_type,
            "area_shape": self.area_shape.value if self.area_shape else None,
            "area_size": self.area_size,
            "recharge_type": self.recharge_type,
            "conditions": self.conditions,
        }


def parse_monster_action(action_dict: Dict[str, Any], monster_id: str = "") -> MonsterAbility:
    """
    Parse a monster action from JSON into structured MonsterAbility.

    Args:
        action_dict: Raw action from monster JSON (has "name" and "description")
        monster_id: ID of the monster (for generating unique ability IDs)

    Returns:
        MonsterAbility with extracted combat data
    """
    name = action_dict.get("name", "Unknown")
    description = action_dict.get("description", "")

    # Generate unique ID
    ability_id = f"{monster_id}_{name.lower().replace(' ', '_').replace('(', '').replace(')', '')}"

    # Detect ability type and parse accordingly
    ability_type = _detect_ability_type(name, description)

    # Create base ability
    ability = MonsterAbility(
        id=ability_id,
        name=name,
        original_description=description,
        ability_type=ability_type
    )

    # Parse based on type
    if ability_type == AbilityType.MELEE_ATTACK:
        _parse_melee_attack(ability, description)
    elif ability_type == AbilityType.RANGED_ATTACK:
        _parse_ranged_attack(ability, description)
    elif ability_type == AbilityType.BREATH_WEAPON:
        _parse_breath_weapon(ability, name, description)
    elif ability_type == AbilityType.MULTIATTACK:
        _parse_multiattack(ability, description)
    elif ability_type == AbilityType.FRIGHTFUL_PRESENCE:
        _parse_frightful_presence(ability, description)
    elif ability_type == AbilityType.EYE_RAY:
        _parse_eye_ray(ability, description)
    elif ability_type == AbilityType.MIND_BLAST:
        _parse_mind_blast(ability, description)
    elif ability_type == AbilityType.AOE_SAVE:
        _parse_aoe_save(ability, description)

    # Parse recharge from name
    _parse_recharge(ability, name)

    return ability


def _detect_ability_type(name: str, description: str) -> AbilityType:
    """Detect the type of ability from name and description."""
    name_lower = name.lower()
    desc_lower = description.lower()

    # Multiattack
    if "multiattack" in name_lower:
        return AbilityType.MULTIATTACK

    # Breath weapons
    if "breath" in name_lower:
        return AbilityType.BREATH_WEAPON

    # Frightful Presence
    if "frightful presence" in name_lower:
        return AbilityType.FRIGHTFUL_PRESENCE

    # Eye Rays (Beholder)
    if "eye ray" in name_lower or "eye rays" in name_lower:
        return AbilityType.EYE_RAY

    # Mind Blast (Mind Flayer)
    if "mind blast" in name_lower:
        return AbilityType.MIND_BLAST

    # Melee vs Ranged attack
    if "melee weapon attack" in desc_lower:
        return AbilityType.MELEE_ATTACK
    if "ranged weapon attack" in desc_lower:
        return AbilityType.RANGED_ATTACK

    # AOE with save (generic)
    if "saving throw" in desc_lower and ("foot" in desc_lower or "feet" in desc_lower):
        return AbilityType.AOE_SAVE

    # Spells
    if "cast" in desc_lower and "spell" in desc_lower:
        return AbilityType.SPELL

    return AbilityType.SPECIAL


def _parse_melee_attack(ability: MonsterAbility, description: str) -> None:
    """Parse melee weapon attack details."""
    # Extract attack bonus: "+11 to hit"
    attack_match = re.search(r'([+-]\d+)\s*to hit', description)
    if attack_match:
        ability.attack_bonus = int(attack_match.group(1))

    # Extract reach: "reach 10 ft."
    reach_match = re.search(r'reach\s+(\d+)\s*ft', description)
    if reach_match:
        ability.reach = int(reach_match.group(1))

    # Extract damage: "17 (2d10+6) piercing damage"
    damage_match = re.search(r'Hit:\s*\d+\s*\((\d+d\d+(?:[+-]\d+)?)\)\s*(\w+)\s*damage', description)
    if damage_match:
        ability.damage_dice = damage_match.group(1)
        ability.damage_type = damage_match.group(2)

    # Check for extra damage: "plus 4 (1d8) acid damage"
    extra_match = re.search(r'plus\s*\d+\s*\((\d+d\d+(?:[+-]\d+)?)\)\s*(\w+)\s*damage', description)
    if extra_match:
        ability.extra_damage_dice = extra_match.group(1)
        ability.extra_damage_type = extra_match.group(2)


def _parse_ranged_attack(ability: MonsterAbility, description: str) -> None:
    """Parse ranged weapon attack details."""
    # Attack bonus
    attack_match = re.search(r'([+-]\d+)\s*to hit', description)
    if attack_match:
        ability.attack_bonus = int(attack_match.group(1))

    # Range: "range 80/320 ft."
    range_match = re.search(r'range\s+(\d+)(?:/\d+)?\s*ft', description)
    if range_match:
        ability.reach = int(range_match.group(1))

    # Damage
    damage_match = re.search(r'Hit:\s*\d+\s*\((\d+d\d+(?:[+-]\d+)?)\)\s*(\w+)\s*damage', description)
    if damage_match:
        ability.damage_dice = damage_match.group(1)
        ability.damage_type = damage_match.group(2)


def _parse_breath_weapon(ability: MonsterAbility, name: str, description: str) -> None:
    """Parse breath weapon details."""
    # Extract area shape and size: "60-foot line" or "30-foot cone"
    line_match = re.search(r'(\d+)-foot\s+line', description)
    cone_match = re.search(r'(\d+)-foot\s+cone', description)

    if line_match:
        ability.area_shape = AreaShape.LINE
        ability.area_size = int(line_match.group(1))
        # Line width
        width_match = re.search(r'(\d+)\s*feet?\s*wide', description)
        if width_match:
            ability.area_width = int(width_match.group(1))
    elif cone_match:
        ability.area_shape = AreaShape.CONE
        ability.area_size = int(cone_match.group(1))

    # Extract save: "DC 18 Dexterity saving throw"
    save_match = re.search(r'DC\s*(\d+)\s*(\w+)\s*saving throw', description, re.IGNORECASE)
    if save_match:
        ability.save_dc = int(save_match.group(1))
        ability.save_type = save_match.group(2).lower()[:3]  # "dex", "str", etc.

    # Extract damage: "54 (12d8) acid damage"
    damage_match = re.search(r'(?:tak(?:e|ing)|deals?)\s*\d+\s*\((\d+d\d+(?:[+-]\d+)?)\)\s*(\w+)\s*damage', description)
    if damage_match:
        ability.damage_dice = damage_match.group(1)
        ability.damage_type = damage_match.group(2)

    # Check half on save
    ability.half_on_save = "half as much" in description.lower()

    # Detect damage type from name if not in description
    if not ability.damage_type:
        name_lower = name.lower()
        if "acid" in name_lower:
            ability.damage_type = "acid"
        elif "fire" in name_lower:
            ability.damage_type = "fire"
        elif "cold" in name_lower:
            ability.damage_type = "cold"
        elif "lightning" in name_lower:
            ability.damage_type = "lightning"
        elif "poison" in name_lower:
            ability.damage_type = "poison"


def _parse_multiattack(ability: MonsterAbility, description: str) -> None:
    """Parse multiattack pattern."""
    desc_lower = description.lower()

    # Check for Frightful Presence
    if "frightful presence" in desc_lower:
        ability.includes_frightful_presence = True

    # Extract attack pattern: "one with its bite and two with its claws"
    pattern = []

    # Count attacks
    bite_match = re.search(r'(one|two|three|1|2|3)\s+(?:with its |)bite', desc_lower)
    claw_match = re.search(r'(one|two|three|1|2|3)\s+(?:with its |)claw', desc_lower)
    tail_match = re.search(r'(one|two|three|1|2|3)\s+(?:with its |)tail', desc_lower)

    count_map = {"one": 1, "two": 2, "three": 3, "1": 1, "2": 2, "3": 3}

    if bite_match:
        count = count_map.get(bite_match.group(1), 1)
        pattern.extend(["bite"] * count)

    if claw_match:
        count = count_map.get(claw_match.group(1), 1)
        pattern.extend(["claw"] * count)

    if tail_match:
        count = count_map.get(tail_match.group(1), 1)
        pattern.extend(["tail"] * count)

    # Generic "three attacks"
    if not pattern:
        generic_match = re.search(r'makes?\s+(one|two|three|four|five|\d+)\s+attacks?', desc_lower)
        if generic_match:
            count_word = generic_match.group(1)
            word_map = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
            count = word_map.get(count_word, int(count_word) if count_word.isdigit() else 1)
            pattern = ["attack"] * count

    ability.multiattack_pattern = pattern if pattern else ["attack", "attack"]


def _parse_frightful_presence(ability: MonsterAbility, description: str) -> None:
    """Parse Frightful Presence details."""
    # Area: "within 120 feet"
    range_match = re.search(r'within\s+(\d+)\s*feet', description)
    if range_match:
        ability.area_size = int(range_match.group(1))
        ability.area_shape = AreaShape.SPHERE

    # Save DC
    save_match = re.search(r'DC\s*(\d+)\s*(\w+)\s*saving throw', description, re.IGNORECASE)
    if save_match:
        ability.save_dc = int(save_match.group(1))
        ability.save_type = save_match.group(2).lower()[:3]

    ability.conditions = ["frightened"]
    ability.duration = "1 minute"


def _parse_eye_ray(ability: MonsterAbility, description: str) -> None:
    """Parse Beholder eye ray details."""
    # Eye rays are complex - they involve random selection
    ability.area_shape = AreaShape.SINGLE_TARGET

    # Range: "within 120 feet"
    range_match = re.search(r'within\s+(\d+)\s*feet', description)
    if range_match:
        ability.area_size = int(range_match.group(1))


def _parse_mind_blast(ability: MonsterAbility, description: str) -> None:
    """Parse Mind Blast details."""
    # Cone area
    cone_match = re.search(r'(\d+)-foot\s+cone', description)
    if cone_match:
        ability.area_shape = AreaShape.CONE
        ability.area_size = int(cone_match.group(1))

    # Save
    save_match = re.search(r'DC\s*(\d+)\s*(\w+)\s*saving throw', description, re.IGNORECASE)
    if save_match:
        ability.save_dc = int(save_match.group(1))
        ability.save_type = save_match.group(2).lower()[:3]

    # Damage - match "take", "taking", "deal", "deals"
    damage_match = re.search(r'(?:tak(?:e|ing)|deals?)\s*\d+\s*\((\d+d\d+(?:[+-]\d+)?)\)\s*(\w+)\s*damage', description)
    if damage_match:
        ability.damage_dice = damage_match.group(1)
        ability.damage_type = damage_match.group(2)

    # Stun condition
    if "stunned" in description.lower():
        ability.conditions = ["stunned"]


def _parse_aoe_save(ability: MonsterAbility, description: str) -> None:
    """Parse generic area-of-effect save ability."""
    # Save
    save_match = re.search(r'DC\s*(\d+)\s*(\w+)\s*saving throw', description, re.IGNORECASE)
    if save_match:
        ability.save_dc = int(save_match.group(1))
        ability.save_type = save_match.group(2).lower()[:3]

    # Area
    line_match = re.search(r'(\d+)-foot\s+line', description)
    cone_match = re.search(r'(\d+)-foot\s+cone', description)
    sphere_match = re.search(r'(\d+)-foot[- ]radius', description)

    if line_match:
        ability.area_shape = AreaShape.LINE
        ability.area_size = int(line_match.group(1))
    elif cone_match:
        ability.area_shape = AreaShape.CONE
        ability.area_size = int(cone_match.group(1))
    elif sphere_match:
        ability.area_shape = AreaShape.SPHERE
        ability.area_size = int(sphere_match.group(1))

    # Damage - match "take", "taking", "deal", "deals"
    damage_match = re.search(r'(?:tak(?:e|ing)|deals?)\s*\d+\s*\((\d+d\d+(?:[+-]\d+)?)\)\s*(\w+)\s*damage', description)
    if damage_match:
        ability.damage_dice = damage_match.group(1)
        ability.damage_type = damage_match.group(2)

    ability.half_on_save = "half as much" in description.lower()


def _parse_recharge(ability: MonsterAbility, name: str) -> None:
    """Parse recharge mechanics from ability name."""
    # "Recharge 5-6" or "Recharge 6"
    recharge_match = re.search(r'\(Recharge\s+(\d+)(?:-(\d+))?\)', name, re.IGNORECASE)
    if recharge_match:
        min_roll = int(recharge_match.group(1))
        ability.recharge_type = f"{min_roll}-6" if recharge_match.group(2) else str(min_roll)
        ability.recharge_min = min_roll

    # "3/Day"
    daily_match = re.search(r'\((\d+)/Day\)', name, re.IGNORECASE)
    if daily_match:
        ability.recharge_type = "per_day"
        ability.uses_per_day = int(daily_match.group(1))


def parse_legendary_action(action_dict: Dict[str, Any], monster_id: str = "") -> MonsterAbility:
    """Parse a legendary action entry."""
    ability = parse_monster_action(action_dict, monster_id)
    ability.ability_type = AbilityType.LEGENDARY_ACTION

    # Extract cost from name: "Wing Attack (Costs 2 Actions)"
    name = action_dict.get("name", "")
    cost_match = re.search(r'\(Costs?\s*(\d+)\s*Actions?\)', name, re.IGNORECASE)
    if cost_match:
        ability.legendary_cost = int(cost_match.group(1))
    else:
        ability.legendary_cost = 1

    return ability


def roll_recharge(ability: MonsterAbility) -> bool:
    """
    Roll to see if an ability recharges.

    Args:
        ability: The ability with recharge mechanics

    Returns:
        True if the ability recharges, False otherwise
    """
    if not ability.recharge_min:
        return True  # No recharge needed

    roll = random.randint(1, 6)
    return roll >= ability.recharge_min


@dataclass
class AbilityResult:
    """Result of executing a monster ability."""
    success: bool
    ability_name: str
    ability_type: str
    description: str
    targets_hit: List[str] = field(default_factory=list)
    targets_saved: List[str] = field(default_factory=list)
    damage_dealt: Dict[str, int] = field(default_factory=dict)  # {target_id: damage}
    conditions_applied: Dict[str, List[str]] = field(default_factory=dict)  # {target_id: [conditions]}
    on_cooldown: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "ability_name": self.ability_name,
            "ability_type": self.ability_type,
            "description": self.description,
            "targets_hit": self.targets_hit,
            "targets_saved": self.targets_saved,
            "damage_dealt": self.damage_dealt,
            "conditions_applied": self.conditions_applied,
            "on_cooldown": self.on_cooldown,
        }


def execute_breath_weapon(
    ability: MonsterAbility,
    targets: List[Dict[str, Any]],
    attacker_id: str
) -> AbilityResult:
    """
    Execute a breath weapon against targets.

    Args:
        ability: The breath weapon ability
        targets: List of targets in the area {"id": str, "save_mod": int, "has_evasion": bool}
        attacker_id: ID of the attacking monster

    Returns:
        AbilityResult with damage and effects
    """
    result = AbilityResult(
        success=True,
        ability_name=ability.name,
        ability_type="breath_weapon",
        description=f"{ability.name} unleashed!"
    )

    # Roll damage once for all targets
    if ability.damage_dice:
        total_damage = roll_damage(ability.damage_dice).total
    else:
        total_damage = 0

    # Check if this is a DEX save (Evasion only applies to DEX saves)
    is_dex_save = ability.save_type and ability.save_type.lower().startswith("dex")

    for target in targets:
        target_id = target.get("id", "unknown")
        save_mod = target.get("save_mod", 0)
        has_evasion = target.get("has_evasion", False) and is_dex_save

        # Roll save
        save_roll = roll_d20(modifier=save_mod)
        save_success = save_roll.total >= (ability.save_dc or 10)

        if save_success:
            # Saved
            result.targets_saved.append(target_id)
            if has_evasion:
                # Evasion: No damage on successful save
                result.damage_dealt[target_id] = 0
                result.extra_data[f"{target_id}_evasion"] = "no_damage"
            elif ability.half_on_save:
                result.damage_dealt[target_id] = total_damage // 2
            else:
                result.damage_dealt[target_id] = 0
        else:
            # Failed
            result.targets_hit.append(target_id)
            if has_evasion:
                # Evasion: Half damage on failed save (instead of full)
                result.damage_dealt[target_id] = total_damage // 2
                result.extra_data[f"{target_id}_evasion"] = "half_damage"
            else:
                result.damage_dealt[target_id] = total_damage

    # Mark on cooldown
    result.on_cooldown = True

    return result


def execute_frightful_presence(
    ability: MonsterAbility,
    targets: List[Dict[str, Any]],
    attacker_id: str,
    immune_targets: List[str] = None
) -> AbilityResult:
    """
    Execute Frightful Presence against targets.

    Args:
        ability: The Frightful Presence ability
        targets: List of targets in range {"id": str, "save_mod": int}
        attacker_id: ID of the dragon
        immune_targets: IDs of targets already immune (saved previously)

    Returns:
        AbilityResult with frightened conditions
    """
    immune_targets = immune_targets or []

    result = AbilityResult(
        success=True,
        ability_name=ability.name,
        ability_type="frightful_presence",
        description="A terrifying presence fills the area!"
    )

    for target in targets:
        target_id = target.get("id", "unknown")

        # Skip immune targets
        if target_id in immune_targets:
            result.targets_saved.append(target_id)
            continue

        save_mod = target.get("save_mod", 0)
        save_roll = roll_d20(modifier=save_mod)

        if save_roll.total >= (ability.save_dc or 10):
            # Saved - becomes immune
            result.targets_saved.append(target_id)
        else:
            # Failed - becomes frightened
            result.targets_hit.append(target_id)
            result.conditions_applied[target_id] = ["frightened"]

    return result


def execute_mind_blast(
    ability: MonsterAbility,
    targets: List[Dict[str, Any]],
    attacker_id: str
) -> AbilityResult:
    """
    Execute Mind Blast against targets in cone.

    Args:
        ability: The Mind Blast ability
        targets: List of targets in cone {"id": str, "save_mod": int}
        attacker_id: ID of the mind flayer

    Returns:
        AbilityResult with psychic damage and stun
    """
    result = AbilityResult(
        success=True,
        ability_name=ability.name,
        ability_type="mind_blast",
        description="A wave of psychic energy erupts!"
    )

    # Roll damage once
    if ability.damage_dice:
        total_damage = roll_damage(ability.damage_dice).total
    else:
        total_damage = 0

    for target in targets:
        target_id = target.get("id", "unknown")
        save_mod = target.get("save_mod", 0)

        save_roll = roll_d20(modifier=save_mod)

        if save_roll.total >= (ability.save_dc or 10):
            # Saved - half damage, no stun
            result.targets_saved.append(target_id)
            result.damage_dealt[target_id] = total_damage // 2
        else:
            # Failed - full damage and stunned
            result.targets_hit.append(target_id)
            result.damage_dealt[target_id] = total_damage
            result.conditions_applied[target_id] = ["stunned"]

    result.on_cooldown = True
    return result


def get_monster_abilities(monster_stats: Dict[str, Any]) -> List[MonsterAbility]:
    """
    Parse all abilities from a monster's stats.

    Args:
        monster_stats: Full monster stat block from JSON

    Returns:
        List of parsed MonsterAbility objects
    """
    abilities = []
    monster_id = monster_stats.get("id", "unknown")

    # Parse regular actions
    for action in monster_stats.get("actions", []):
        ability = parse_monster_action(action, monster_id)
        abilities.append(ability)

    # Parse legendary actions
    for leg_action in monster_stats.get("legendary_actions", []):
        ability = parse_legendary_action(leg_action, monster_id)
        abilities.append(ability)

    return abilities


def get_breath_weapons(abilities: List[MonsterAbility]) -> List[MonsterAbility]:
    """Filter abilities to only breath weapons."""
    return [a for a in abilities if a.ability_type == AbilityType.BREATH_WEAPON]


def get_melee_attacks(abilities: List[MonsterAbility]) -> List[MonsterAbility]:
    """Filter abilities to only melee attacks."""
    return [a for a in abilities if a.ability_type == AbilityType.MELEE_ATTACK]


def get_legendary_actions(abilities: List[MonsterAbility]) -> List[MonsterAbility]:
    """Filter abilities to only legendary actions."""
    return [a for a in abilities if a.ability_type == AbilityType.LEGENDARY_ACTION]


def get_multiattack(abilities: List[MonsterAbility]) -> Optional[MonsterAbility]:
    """Get the multiattack ability if present."""
    for ability in abilities:
        if ability.ability_type == AbilityType.MULTIATTACK:
            return ability
    return None
