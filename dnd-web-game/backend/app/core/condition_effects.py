"""
Condition Effects System for D&D 5e 2024.

Loads condition data from conditions.json and provides methods to:
- Apply advantage/disadvantage to attack rolls
- Apply speed modifications
- Check for auto-fail conditions on saves
- Check if combatant is incapacitated
- Apply prone-specific melee/ranged modifiers
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import json


# =============================================================================
# CONDITION DATA
# =============================================================================

@dataclass
class ConditionData:
    """Parsed condition data from JSON."""
    id: str
    name: str
    description: str
    effects: Dict[str, Any] = field(default_factory=dict)
    icon: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "effects": self.effects,
            "icon": self.icon,
        }


# Condition data cache
_condition_cache: Dict[str, ConditionData] = {}


def load_conditions() -> Dict[str, ConditionData]:
    """Load conditions from conditions.json."""
    global _condition_cache

    if _condition_cache:
        return _condition_cache

    conditions_path = Path(__file__).parent.parent / "data" / "conditions.json"
    try:
        with open(conditions_path, encoding="utf-8") as f:
            data = json.load(f)

        for condition_data in data.get("conditions", []):
            cond = ConditionData(
                id=condition_data["id"],
                name=condition_data["name"],
                description=condition_data["description"],
                effects=condition_data.get("effects", {}),
                icon=condition_data.get("icon", ""),
            )
            _condition_cache[cond.id] = cond

    except Exception as e:
        print(f"[ConditionEffects] Failed to load conditions.json: {e}")
        # Fallback with built-in conditions
        _init_default_conditions()

    return _condition_cache


def _init_default_conditions():
    """Initialize default conditions if JSON fails to load."""
    global _condition_cache

    defaults = [
        ConditionData(
            id="prone",
            name="Prone",
            description="Crawl only, attack disadvantage, melee advantage against, ranged disadvantage against.",
            effects={
                "movement": "crawl_only",
                "attack_disadvantage": True,
                "melee_attacks_against_advantage": True,
                "ranged_attacks_against_disadvantage": True,
                "standing_cost": "half_movement",
            },
        ),
        ConditionData(
            id="stunned",
            name="Stunned",
            description="Incapacitated, can't move, auto-fail STR and DEX saves, attacks have advantage.",
            effects={
                "incapacitated": True,
                "speed_zero": True,
                "auto_fail_saves": ["strength", "dexterity"],
                "attacks_against_advantage": True,
            },
        ),
        ConditionData(
            id="poisoned",
            name="Poisoned",
            description="Disadvantage on attack rolls and ability checks.",
            effects={
                "attack_disadvantage": True,
                "ability_check_disadvantage": True,
            },
        ),
        ConditionData(
            id="frightened",
            name="Frightened",
            description="Disadvantage on ability checks and attacks while source is visible. Can't approach source.",
            effects={
                "attack_disadvantage": True,
                "ability_check_disadvantage": True,
                "cannot_approach_source": True,
                "requires_line_of_sight_to_source": True,
            },
        ),
        ConditionData(
            id="restrained",
            name="Restrained",
            description="Speed 0, attack disadvantage, attacks have advantage, DEX save disadvantage.",
            effects={
                "speed_zero": True,
                "attack_disadvantage": True,
                "attacks_against_advantage": True,
                "save_disadvantage": ["dexterity"],
            },
        ),
        ConditionData(
            id="paralyzed",
            name="Paralyzed",
            description="Incapacitated, can't move or speak, auto-fail STR and DEX saves, attacks have advantage, hits within 5ft are critical.",
            effects={
                "incapacitated": True,
                "speed_zero": True,
                "auto_fail_saves": ["strength", "dexterity"],
                "attacks_against_advantage": True,
                "melee_hits_are_critical": True,
            },
        ),
        ConditionData(
            id="incapacitated",
            name="Incapacitated",
            description="Can't take actions or reactions.",
            effects={
                "incapacitated": True,
            },
        ),
        ConditionData(
            id="blinded",
            name="Blinded",
            description="Auto-fail sight-based checks, attack disadvantage, attacks have advantage.",
            effects={
                "attack_disadvantage": True,
                "attacks_against_advantage": True,
                "auto_fail_sight_checks": True,
            },
        ),
        ConditionData(
            id="charmed",
            name="Charmed",
            description="Can't attack charmer, charmer has advantage on social checks.",
            effects={
                "cannot_attack_source": True,
                "source_social_advantage": True,
            },
        ),
        ConditionData(
            id="deafened",
            name="Deafened",
            description="Auto-fail hearing-based checks.",
            effects={
                "auto_fail_hearing_checks": True,
            },
        ),
        ConditionData(
            id="grappled",
            name="Grappled",
            description="Speed becomes 0, ends if grappler is incapacitated or forced apart.",
            effects={
                "speed_zero": True,
            },
        ),
        ConditionData(
            id="invisible",
            name="Invisible",
            description="Attack advantage, attacks against have disadvantage.",
            effects={
                "attack_advantage": True,
                "attacks_against_disadvantage": True,
            },
        ),
        ConditionData(
            id="petrified",
            name="Petrified",
            description="Transformed to stone, incapacitated, weight increases, resistance to all damage.",
            effects={
                "incapacitated": True,
                "speed_zero": True,
                "auto_fail_saves": ["strength", "dexterity"],
                "attacks_against_advantage": True,
                "resistance_all": True,
            },
        ),
        ConditionData(
            id="unconscious",
            name="Unconscious",
            description="Incapacitated, drop held items, fall prone, auto-fail STR and DEX saves, attacks have advantage, hits within 5ft are critical.",
            effects={
                "incapacitated": True,
                "speed_zero": True,
                "prone": True,
                "auto_fail_saves": ["strength", "dexterity"],
                "attacks_against_advantage": True,
                "melee_hits_are_critical": True,
            },
        ),
        ConditionData(
            id="exhaustion",
            name="Exhaustion",
            description="Cumulative levels of exhaustion with escalating penalties.",
            effects={
                "exhaustion_levels": True,
            },
        ),
    ]

    for cond in defaults:
        _condition_cache[cond.id] = cond


def get_condition(condition_id: str) -> Optional[ConditionData]:
    """Get a specific condition by ID."""
    conditions = load_conditions()
    return conditions.get(condition_id.lower())


def get_all_conditions() -> List[ConditionData]:
    """Get all available conditions."""
    conditions = load_conditions()
    return list(conditions.values())


# =============================================================================
# COMBAT EFFECT CALCULATIONS
# =============================================================================

@dataclass
class AttackModifiers:
    """Advantage/disadvantage modifiers for an attack."""
    advantage: bool = False
    disadvantage: bool = False
    auto_critical: bool = False
    reasons: List[str] = field(default_factory=list)


def get_attack_modifiers(
    attacker_conditions: List[str],
    target_conditions: List[str],
    is_melee: bool = True,
    distance_ft: int = 5,
) -> AttackModifiers:
    """
    Calculate attack advantage/disadvantage based on conditions.

    Args:
        attacker_conditions: Conditions on the attacker
        target_conditions: Conditions on the target
        is_melee: True for melee attacks, False for ranged
        distance_ft: Distance to target in feet

    Returns:
        AttackModifiers with advantage, disadvantage, and reasons
    """
    conditions = load_conditions()
    result = AttackModifiers()

    # Check attacker conditions
    for cond_id in attacker_conditions:
        cond = conditions.get(cond_id.lower())
        if not cond:
            continue

        effects = cond.effects

        # Attacker has disadvantage
        if effects.get("attack_disadvantage"):
            result.disadvantage = True
            result.reasons.append(f"Attacker is {cond.name} (disadvantage)")

        # Attacker has advantage (e.g., invisible)
        if effects.get("attack_advantage"):
            result.advantage = True
            result.reasons.append(f"Attacker is {cond.name} (advantage)")

    # Check target conditions
    for cond_id in target_conditions:
        cond = conditions.get(cond_id.lower())
        if not cond:
            continue

        effects = cond.effects

        # Attacks against target have advantage
        if effects.get("attacks_against_advantage"):
            result.advantage = True
            result.reasons.append(f"Target is {cond.name} (advantage)")

        # Attacks against target have disadvantage (e.g., invisible target)
        if effects.get("attacks_against_disadvantage"):
            result.disadvantage = True
            result.reasons.append(f"Target is {cond.name} (disadvantage)")

        # Prone-specific rules
        if cond_id.lower() == "prone":
            if is_melee and distance_ft <= 5:
                if effects.get("melee_attacks_against_advantage"):
                    result.advantage = True
                    result.reasons.append("Target is Prone (melee advantage)")
            else:
                if effects.get("ranged_attacks_against_disadvantage"):
                    result.disadvantage = True
                    result.reasons.append("Target is Prone (ranged disadvantage)")

        # Auto-critical hits (paralyzed, unconscious within 5ft)
        if effects.get("melee_hits_are_critical") and is_melee and distance_ft <= 5:
            result.auto_critical = True
            result.reasons.append(f"Target is {cond.name} (auto-crit on hit)")

    return result


def get_save_modifiers(
    target_conditions: List[str],
    save_type: str,
) -> Tuple[bool, bool, bool, List[str]]:
    """
    Calculate saving throw modifiers based on conditions.

    Args:
        target_conditions: Conditions on the target making the save
        save_type: Type of save (strength, dexterity, constitution, etc.)

    Returns:
        Tuple of (auto_fail, advantage, disadvantage, reasons)
    """
    conditions = load_conditions()
    auto_fail = False
    advantage = False
    disadvantage = False
    reasons = []

    save_type_lower = save_type.lower()

    for cond_id in target_conditions:
        cond = conditions.get(cond_id.lower())
        if not cond:
            continue

        effects = cond.effects

        # Auto-fail certain saves
        auto_fail_saves = effects.get("auto_fail_saves", [])
        if save_type_lower in [s.lower() for s in auto_fail_saves]:
            auto_fail = True
            reasons.append(f"{cond.name}: auto-fail {save_type} saves")

        # Disadvantage on certain saves
        save_disadvantage = effects.get("save_disadvantage", [])
        if save_type_lower in [s.lower() for s in save_disadvantage]:
            disadvantage = True
            reasons.append(f"{cond.name}: disadvantage on {save_type} saves")

    return auto_fail, advantage, disadvantage, reasons


def get_ability_check_modifiers(
    conditions: List[str],
    ability: str = None,
    skill: str = None,
) -> Tuple[bool, bool, List[str]]:
    """
    Calculate ability check modifiers based on conditions.

    Args:
        conditions: Conditions on the character
        ability: Ability being checked (optional)
        skill: Skill being checked (optional)

    Returns:
        Tuple of (advantage, disadvantage, reasons)
    """
    condition_data = load_conditions()
    advantage = False
    disadvantage = False
    reasons = []

    for cond_id in conditions:
        cond = condition_data.get(cond_id.lower())
        if not cond:
            continue

        effects = cond.effects

        # General ability check disadvantage (poisoned, frightened)
        if effects.get("ability_check_disadvantage"):
            disadvantage = True
            reasons.append(f"{cond.name}: disadvantage on ability checks")

        # Sight-based checks auto-fail for blinded
        if effects.get("auto_fail_sight_checks") and skill:
            sight_skills = ["perception", "investigation"]
            if skill.lower() in sight_skills:
                # This would be an auto-fail, but we represent as severe disadvantage
                disadvantage = True
                reasons.append(f"{cond.name}: auto-fail on sight-based checks")

    return advantage, disadvantage, reasons


def get_effective_speed(
    base_speed: int,
    conditions: List[str],
    is_standing_from_prone: bool = False,
) -> Tuple[int, str, List[str]]:
    """
    Calculate effective movement speed based on conditions.

    Args:
        base_speed: Base movement speed
        conditions: Conditions on the combatant
        is_standing_from_prone: If True, calculate cost to stand up

    Returns:
        Tuple of (effective_speed, movement_type, reasons)
        movement_type: "normal", "crawl", or "zero"
    """
    condition_data = load_conditions()
    speed = base_speed
    movement_type = "normal"
    reasons = []

    for cond_id in conditions:
        cond = condition_data.get(cond_id.lower())
        if not cond:
            continue

        effects = cond.effects

        # Speed becomes 0
        if effects.get("speed_zero"):
            speed = 0
            movement_type = "zero"
            reasons.append(f"{cond.name}: speed is 0")

        # Crawl only (prone)
        if effects.get("movement") == "crawl_only":
            if movement_type != "zero":  # speed_zero takes precedence
                movement_type = "crawl"
                reasons.append(f"{cond.name}: can only crawl")

    # Standing from prone costs half movement
    if is_standing_from_prone and "prone" in [c.lower() for c in conditions]:
        prone_cond = condition_data.get("prone")
        if prone_cond and prone_cond.effects.get("standing_cost") == "half_movement":
            # Don't modify speed here, but inform caller
            reasons.append("Standing from prone costs half movement")

    return speed, movement_type, reasons


def is_incapacitated(conditions: List[str]) -> Tuple[bool, List[str]]:
    """
    Check if a combatant is incapacitated.

    Incapacitated creatures cannot take actions or reactions.

    Args:
        conditions: Conditions on the combatant

    Returns:
        Tuple of (is_incapacitated, reasons)
    """
    condition_data = load_conditions()
    reasons = []

    for cond_id in conditions:
        cond = condition_data.get(cond_id.lower())
        if not cond:
            continue

        if cond.effects.get("incapacitated"):
            reasons.append(f"{cond.name}: incapacitated")
            return True, reasons

    return False, reasons


def can_take_reactions(conditions: List[str]) -> Tuple[bool, List[str]]:
    """
    Check if a combatant can take reactions.

    Args:
        conditions: Conditions on the combatant

    Returns:
        Tuple of (can_react, reasons_if_not)
    """
    incapacitated, reasons = is_incapacitated(conditions)
    if incapacitated:
        return False, reasons
    return True, []


def get_standing_cost(base_speed: int) -> int:
    """
    Get the movement cost to stand from prone.

    D&D 5e Rule: Standing up costs half your movement.

    Args:
        base_speed: Base movement speed

    Returns:
        Movement cost to stand
    """
    return base_speed // 2


def can_approach_target(
    attacker_conditions: List[str],
    target_id: str,
    fear_source_id: Optional[str] = None,
) -> Tuple[bool, List[str]]:
    """
    Check if an attacker can willingly move toward a target.

    Frightened creatures cannot willingly move closer to the source of fear.

    Args:
        attacker_conditions: Conditions on the attacker
        target_id: ID of the target they want to approach
        fear_source_id: ID of the creature causing the fear (if any)

    Returns:
        Tuple of (can_approach, reasons_if_not)
    """
    if not fear_source_id or target_id != fear_source_id:
        return True, []

    condition_data = load_conditions()
    reasons = []

    for cond_id in attacker_conditions:
        cond = condition_data.get(cond_id.lower())
        if not cond:
            continue

        if cond.effects.get("cannot_approach_source"):
            reasons.append(f"{cond.name}: cannot move closer to source of fear")
            return False, reasons

    return True, []


def get_condition_summary(conditions: List[str]) -> List[Dict[str, Any]]:
    """
    Get a summary of active conditions for display.

    Args:
        conditions: List of condition IDs

    Returns:
        List of condition summaries with name, icon, and brief effect description
    """
    condition_data = load_conditions()
    summaries = []

    for cond_id in conditions:
        cond = condition_data.get(cond_id.lower())
        if not cond:
            summaries.append({
                "id": cond_id,
                "name": cond_id.title(),
                "icon": "",
                "brief": "Unknown condition",
            })
            continue

        # Build brief effect description
        effects = cond.effects
        brief_parts = []

        if effects.get("speed_zero"):
            brief_parts.append("Speed 0")
        if effects.get("attack_disadvantage"):
            brief_parts.append("Attack -")
        if effects.get("attack_advantage"):
            brief_parts.append("Attack +")
        if effects.get("attacks_against_advantage"):
            brief_parts.append("Attacks vs +")
        if effects.get("incapacitated"):
            brief_parts.append("Incapacitated")
        if effects.get("auto_fail_saves"):
            saves = effects["auto_fail_saves"]
            brief_parts.append(f"Auto-fail {'/'.join(s[:3].upper() for s in saves)} saves")

        brief = ", ".join(brief_parts) if brief_parts else "See description"

        summaries.append({
            "id": cond.id,
            "name": cond.name,
            "icon": cond.icon,
            "brief": brief,
            "description": cond.description,
        })

    return summaries


# =============================================================================
# CONDITION APPLICATION
# =============================================================================

def apply_condition(
    current_conditions: List[str],
    condition_id: str,
    duration: Optional[int] = None,
    source_id: Optional[str] = None,
) -> Tuple[List[str], str]:
    """
    Apply a condition to a combatant.

    Args:
        current_conditions: Current list of conditions
        condition_id: Condition to apply
        duration: Optional duration in rounds
        source_id: Optional source of the condition

    Returns:
        Tuple of (new_conditions_list, message)
    """
    condition_data = load_conditions()
    cond = condition_data.get(condition_id.lower())

    if not cond:
        return current_conditions, f"Unknown condition: {condition_id}"

    new_conditions = list(current_conditions)

    if condition_id.lower() not in [c.lower() for c in new_conditions]:
        new_conditions.append(condition_id.lower())
        return new_conditions, f"Applied {cond.name}"
    else:
        return new_conditions, f"Already has {cond.name}"


def remove_condition(
    current_conditions: List[str],
    condition_id: str,
) -> Tuple[List[str], str]:
    """
    Remove a condition from a combatant.

    Args:
        current_conditions: Current list of conditions
        condition_id: Condition to remove

    Returns:
        Tuple of (new_conditions_list, message)
    """
    condition_data = load_conditions()
    cond = condition_data.get(condition_id.lower())
    cond_name = cond.name if cond else condition_id.title()

    new_conditions = [c for c in current_conditions if c.lower() != condition_id.lower()]

    if len(new_conditions) < len(current_conditions):
        return new_conditions, f"Removed {cond_name}"
    else:
        return new_conditions, f"Did not have {cond_name}"
