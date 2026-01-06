"""
Weapon Mastery System (2024 D&D Rules).

Each weapon type has a unique mastery property that skilled fighters can use.
This is a toggleable 2024 enhancement to the base 2014 rules.

Mastery Properties:
- Cleave: On hit, damage another adjacent enemy (no attack roll needed)
- Graze: On miss, still deal ability modifier damage
- Nick: Extra attack with light weapon as part of Attack action
- Push: Push target 10ft on hit (STR save negates)
- Sap: Target has disadvantage on next attack
- Slow: Reduce target speed by 10ft until your next turn
- Topple: Target must make STR save or fall prone
- Vex: Gain advantage on next attack against same target
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Dict, Any

from app.core.dice import roll_d20
from app.core.rules_engine import calculate_ability_modifier


class MasteryType(Enum):
    """The eight weapon mastery properties from 2024 rules."""
    CLEAVE = "cleave"
    GRAZE = "graze"
    NICK = "nick"
    PUSH = "push"
    SAP = "sap"
    SLOW = "slow"
    TOPPLE = "topple"
    VEX = "vex"


@dataclass
class MasteryEffect:
    """Result of applying a weapon mastery effect."""
    mastery_type: MasteryType
    success: bool
    description: str
    # Additional data depending on mastery type
    extra_damage: int = 0
    target_condition: Optional[str] = None
    affected_entity_ids: List[str] = None
    grants_advantage: bool = False
    push_distance: int = 0

    def __post_init__(self):
        if self.affected_entity_ids is None:
            self.affected_entity_ids = []


# Weapon to mastery mapping (2024 PHB)
WEAPON_MASTERY_MAP: Dict[str, MasteryType] = {
    # Simple Melee
    "club": MasteryType.SLOW,
    "dagger": MasteryType.NICK,
    "greatclub": MasteryType.PUSH,
    "handaxe": MasteryType.VEX,
    "javelin": MasteryType.SLOW,
    "light_hammer": MasteryType.NICK,
    "mace": MasteryType.SAP,
    "quarterstaff": MasteryType.TOPPLE,
    "sickle": MasteryType.NICK,
    "spear": MasteryType.SAP,

    # Simple Ranged
    "light_crossbow": MasteryType.SLOW,
    "dart": MasteryType.VEX,
    "shortbow": MasteryType.VEX,
    "sling": MasteryType.SLOW,

    # Martial Melee
    "battleaxe": MasteryType.TOPPLE,
    "flail": MasteryType.SAP,
    "glaive": MasteryType.GRAZE,
    "greataxe": MasteryType.CLEAVE,
    "greatsword": MasteryType.GRAZE,
    "halberd": MasteryType.CLEAVE,
    "lance": MasteryType.TOPPLE,
    "longsword": MasteryType.SAP,
    "maul": MasteryType.TOPPLE,
    "morningstar": MasteryType.SAP,
    "pike": MasteryType.PUSH,
    "rapier": MasteryType.VEX,
    "scimitar": MasteryType.NICK,
    "shortsword": MasteryType.VEX,
    "trident": MasteryType.TOPPLE,
    "war_pick": MasteryType.SAP,
    "warhammer": MasteryType.PUSH,
    "whip": MasteryType.SLOW,

    # Martial Ranged
    "blowgun": MasteryType.VEX,
    "hand_crossbow": MasteryType.VEX,
    "heavy_crossbow": MasteryType.PUSH,
    "longbow": MasteryType.SLOW,
    "net": MasteryType.SLOW,
}


def get_weapon_mastery(weapon_id: str) -> Optional[MasteryType]:
    """Get the mastery type for a weapon."""
    return WEAPON_MASTERY_MAP.get(weapon_id.lower().replace(" ", "_"))


def apply_cleave(
    attacker_strength_mod: int,
    adjacent_enemy_ids: List[str],
    original_target_id: str
) -> MasteryEffect:
    """
    CLEAVE: On hit, deal STR modifier damage to one adjacent enemy.
    No attack roll needed - just deals the damage.

    Args:
        attacker_strength_mod: Attacker's STR modifier
        adjacent_enemy_ids: IDs of enemies adjacent to the original target
        original_target_id: The target that was hit

    Returns:
        MasteryEffect with damage dealt to the secondary target
    """
    if not adjacent_enemy_ids:
        return MasteryEffect(
            mastery_type=MasteryType.CLEAVE,
            success=False,
            description="No adjacent enemies to cleave."
        )

    # Cleave hits the first adjacent enemy
    secondary_target = adjacent_enemy_ids[0]
    damage = max(1, attacker_strength_mod)  # Minimum 1 damage

    return MasteryEffect(
        mastery_type=MasteryType.CLEAVE,
        success=True,
        description=f"Cleaved through to deal {damage} damage to nearby enemy!",
        extra_damage=damage,
        affected_entity_ids=[secondary_target]
    )


def apply_graze(
    attacker_ability_mod: int,
    weapon_is_finesse: bool = False,
    attacker_dex_mod: int = 0
) -> MasteryEffect:
    """
    GRAZE: On miss, still deal ability modifier damage.
    Uses STR for normal weapons, DEX for finesse if higher.

    Args:
        attacker_ability_mod: Attacker's STR modifier (or DEX for finesse)
        weapon_is_finesse: Whether the weapon has the finesse property
        attacker_dex_mod: Attacker's DEX modifier (for finesse comparison)

    Returns:
        MasteryEffect with graze damage
    """
    # For finesse weapons, use higher of STR or DEX
    if weapon_is_finesse:
        damage = max(attacker_ability_mod, attacker_dex_mod)
    else:
        damage = attacker_ability_mod

    damage = max(1, damage)  # Minimum 1 damage

    return MasteryEffect(
        mastery_type=MasteryType.GRAZE,
        success=True,
        description=f"Grazed the target for {damage} damage despite the miss!",
        extra_damage=damage
    )


def apply_nick() -> MasteryEffect:
    """
    NICK: Allows an extra attack with a light weapon.
    This doesn't actually execute the attack - it grants the ability to make one.

    Returns:
        MasteryEffect indicating an extra attack is available
    """
    return MasteryEffect(
        mastery_type=MasteryType.NICK,
        success=True,
        description="Nick mastery: You can make an additional attack with your light weapon!",
        target_condition="extra_light_weapon_attack"
    )


def apply_push(
    target_strength_save_mod: int,
    attacker_dc: int
) -> MasteryEffect:
    """
    PUSH: Push target 10ft on hit, unless they succeed on a STR save.

    Args:
        target_strength_save_mod: Target's STR save modifier
        attacker_dc: DC for the save (typically 8 + prof + STR mod)

    Returns:
        MasteryEffect with push result
    """
    save_roll = roll_d20(modifier=target_strength_save_mod)

    if save_roll.total >= attacker_dc:
        return MasteryEffect(
            mastery_type=MasteryType.PUSH,
            success=False,
            description=f"Target resisted the push (rolled {save_roll.total} vs DC {attacker_dc})."
        )

    return MasteryEffect(
        mastery_type=MasteryType.PUSH,
        success=True,
        description="Target is pushed 10 feet away!",
        push_distance=10
    )


def apply_sap() -> MasteryEffect:
    """
    SAP: Target has disadvantage on their next attack roll.

    Returns:
        MasteryEffect applying disadvantage condition
    """
    return MasteryEffect(
        mastery_type=MasteryType.SAP,
        success=True,
        description="Target is rattled and has disadvantage on their next attack!",
        target_condition="sapped"
    )


def apply_slow() -> MasteryEffect:
    """
    SLOW: Reduce target's speed by 10ft until the start of your next turn.

    Returns:
        MasteryEffect applying slow condition
    """
    return MasteryEffect(
        mastery_type=MasteryType.SLOW,
        success=True,
        description="Target's speed is reduced by 10 feet until your next turn!",
        target_condition="slowed"
    )


def apply_topple(
    target_strength_save_mod: int,
    attacker_dc: int
) -> MasteryEffect:
    """
    TOPPLE: Target must make STR save or fall prone.

    Args:
        target_strength_save_mod: Target's STR save modifier
        attacker_dc: DC for the save (typically 8 + prof + STR mod)

    Returns:
        MasteryEffect with prone result
    """
    save_roll = roll_d20(modifier=target_strength_save_mod)

    if save_roll.total >= attacker_dc:
        return MasteryEffect(
            mastery_type=MasteryType.TOPPLE,
            success=False,
            description=f"Target kept their footing (rolled {save_roll.total} vs DC {attacker_dc})."
        )

    return MasteryEffect(
        mastery_type=MasteryType.TOPPLE,
        success=True,
        description="Target is knocked prone!",
        target_condition="prone"
    )


def apply_vex() -> MasteryEffect:
    """
    VEX: Gain advantage on your next attack against the same target.

    Returns:
        MasteryEffect granting advantage
    """
    return MasteryEffect(
        mastery_type=MasteryType.VEX,
        success=True,
        description="You have advantage on your next attack against this target!",
        grants_advantage=True
    )


def apply_weapon_mastery(
    mastery_type: MasteryType,
    hit: bool,
    attacker_data: Dict[str, Any],
    target_data: Dict[str, Any],
    combat_context: Dict[str, Any]
) -> Optional[MasteryEffect]:
    """
    Apply the appropriate weapon mastery effect.

    Args:
        mastery_type: The mastery type to apply
        hit: Whether the attack hit
        attacker_data: Attacker's stats (str_mod, dex_mod, proficiency, etc.)
        target_data: Target's stats (str_save_mod, etc.)
        combat_context: Combat state (adjacent_enemies, etc.)

    Returns:
        MasteryEffect if applicable, None if mastery doesn't apply
    """
    # Calculate attacker's DC for saves
    # DC = 8 + proficiency + ability modifier
    attacker_dc = 8 + attacker_data.get("proficiency", 2) + attacker_data.get("str_mod", 0)

    # Graze only applies on a MISS
    if mastery_type == MasteryType.GRAZE and not hit:
        return apply_graze(
            attacker_ability_mod=attacker_data.get("str_mod", 0),
            weapon_is_finesse=attacker_data.get("weapon_finesse", False),
            attacker_dex_mod=attacker_data.get("dex_mod", 0)
        )

    # All other masteries only apply on a HIT
    if not hit:
        return None

    if mastery_type == MasteryType.CLEAVE:
        return apply_cleave(
            attacker_strength_mod=attacker_data.get("str_mod", 0),
            adjacent_enemy_ids=combat_context.get("adjacent_enemies", []),
            original_target_id=target_data.get("id", "")
        )

    elif mastery_type == MasteryType.NICK:
        return apply_nick()

    elif mastery_type == MasteryType.PUSH:
        return apply_push(
            target_strength_save_mod=target_data.get("str_save_mod", 0),
            attacker_dc=attacker_dc
        )

    elif mastery_type == MasteryType.SAP:
        return apply_sap()

    elif mastery_type == MasteryType.SLOW:
        return apply_slow()

    elif mastery_type == MasteryType.TOPPLE:
        return apply_topple(
            target_strength_save_mod=target_data.get("str_save_mod", 0),
            attacker_dc=attacker_dc
        )

    elif mastery_type == MasteryType.VEX:
        return apply_vex()

    return None


def get_mastery_description(mastery_type: MasteryType) -> str:
    """Get a human-readable description of a mastery type."""
    descriptions = {
        MasteryType.CLEAVE: "On hit, deal STR modifier damage to one adjacent enemy.",
        MasteryType.GRAZE: "On miss, still deal ability modifier damage to the target.",
        MasteryType.NICK: "Make an extra attack with this light weapon as part of the Attack action.",
        MasteryType.PUSH: "On hit, push target 10ft away (STR save negates).",
        MasteryType.SAP: "On hit, target has disadvantage on their next attack.",
        MasteryType.SLOW: "On hit, reduce target's speed by 10ft until your next turn.",
        MasteryType.TOPPLE: "On hit, target must make STR save or fall prone.",
        MasteryType.VEX: "On hit, gain advantage on your next attack against this target.",
    }
    return descriptions.get(mastery_type, "Unknown mastery effect.")


def get_class_mastery_count(class_id: str, level: int) -> int:
    """
    Get how many weapon masteries a class can have at a given level.

    Args:
        class_id: The class ID (fighter, rogue, etc.)
        level: Character level

    Returns:
        Number of weapon masteries the character can have
    """
    mastery_progression = {
        "fighter": {1: 3, 4: 4, 10: 5, 16: 6},
        "rogue": {1: 2, 4: 3},
        "ranger": {1: 2, 4: 3},
        "barbarian": {1: 2, 4: 3},
        "paladin": {1: 2, 4: 3},
        # Other classes don't get weapon mastery by default
    }

    if class_id.lower() not in mastery_progression:
        return 0

    progression = mastery_progression[class_id.lower()]
    count = 0

    for req_level, masteries in sorted(progression.items()):
        if level >= req_level:
            count = masteries

    return count
