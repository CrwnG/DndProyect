"""
Lair Actions System for D&D 5e 2024

Legendary creatures can have lair actions that occur on initiative count 20.
This module defines:
- LairAction: Individual lair action with effects
- LairDefinition: Complete lair definition for a monster type
- Functions to check and execute lair actions during combat
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import random


class LairEffectType(str, Enum):
    """Types of lair action effects."""
    DAMAGE = "damage"           # Direct damage to targets
    CONDITION = "condition"     # Apply a condition
    TERRAIN = "terrain"         # Modify terrain/movement
    SUMMON = "summon"           # Summon minions
    ENVIRONMENTAL = "environmental"  # Environmental hazard
    HEALING = "healing"         # Heal the lair owner
    BUFF = "buff"               # Buff the lair owner


class LairTargetType(str, Enum):
    """How lair action targets are selected."""
    ALL_ENEMIES = "all_enemies"       # All hostile creatures
    SINGLE_ENEMY = "single_enemy"     # One random enemy
    AREA = "area"                     # Area of effect
    LAIR_OWNER = "lair_owner"         # The creature whose lair this is
    NEAREST_ENEMY = "nearest_enemy"   # Closest enemy


@dataclass
class LairAction:
    """A single lair action."""
    id: str
    name: str
    description: str
    effect_type: LairEffectType
    target_type: LairTargetType = LairTargetType.AREA

    # Effect parameters
    save_type: Optional[str] = None  # "dexterity", "constitution", etc.
    save_dc: int = 15
    damage_dice: Optional[str] = None  # "2d10", "3d6", etc.
    damage_type: Optional[str] = None  # "fire", "cold", "necrotic", etc.
    condition: Optional[str] = None  # Condition to apply
    condition_duration: int = 1  # Rounds

    # Area parameters
    area_radius: int = 20  # feet

    # Recharge (some lair actions can only be used once)
    recharge_on: Optional[int] = None  # Roll this or higher on d6 to recharge

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "effect_type": self.effect_type.value,
            "target_type": self.target_type.value,
            "save_type": self.save_type,
            "save_dc": self.save_dc,
            "damage_dice": self.damage_dice,
            "damage_type": self.damage_type,
            "condition": self.condition,
            "area_radius": self.area_radius,
        }


@dataclass
class LairDefinition:
    """Complete lair definition for a monster type."""
    monster_id: str  # e.g., "adult_red_dragon", "lich"
    name: str  # Display name for the lair
    description: str
    lair_actions: List[LairAction] = field(default_factory=list)

    # Regional effects (always active near lair)
    regional_effects: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "monster_id": self.monster_id,
            "name": self.name,
            "description": self.description,
            "lair_actions": [a.to_dict() for a in self.lair_actions],
            "regional_effects": self.regional_effects,
        }


# =============================================================================
# LAIR DEFINITIONS
# =============================================================================

# Adult Red Dragon Lair
ADULT_RED_DRAGON_LAIR = LairDefinition(
    monster_id="adult_red_dragon",
    name="Dragon's Volcanic Lair",
    description="A cavern of molten rock and sulfurous fumes.",
    lair_actions=[
        LairAction(
            id="magma_eruption",
            name="Magma Eruption",
            description="Magma erupts from a point on the ground within 120 feet. Each creature within 20 feet must make a DC 15 DEX save or take 2d6 fire damage and be knocked prone.",
            effect_type=LairEffectType.DAMAGE,
            target_type=LairTargetType.AREA,
            save_type="dexterity",
            save_dc=15,
            damage_dice="2d6",
            damage_type="fire",
            condition="prone",
            area_radius=20,
        ),
        LairAction(
            id="volcanic_gas",
            name="Volcanic Gas",
            description="A cloud of sulfurous gas billows up in a 20-foot radius sphere. Each creature in the area must succeed on a DC 15 CON save or be poisoned until the end of their next turn.",
            effect_type=LairEffectType.CONDITION,
            target_type=LairTargetType.AREA,
            save_type="constitution",
            save_dc=15,
            condition="poisoned",
            condition_duration=1,
            area_radius=20,
        ),
        LairAction(
            id="tremor",
            name="Tremor",
            description="A tremor shakes the lair. Each creature on the ground must succeed on a DC 15 DEX save or be knocked prone.",
            effect_type=LairEffectType.TERRAIN,
            target_type=LairTargetType.ALL_ENEMIES,
            save_type="dexterity",
            save_dc=15,
            condition="prone",
        ),
    ],
    regional_effects=[
        "Water sources within 6 miles are supernaturally warm and tainted by sulfur.",
        "Rocky fissures within 1 mile form portals to the Elemental Plane of Fire.",
        "Small earthquakes are common within 6 miles of the lair.",
    ],
)

# Lich Lair
LICH_LAIR = LairDefinition(
    monster_id="lich",
    name="Lich's Sanctum",
    description="A chamber of dark magic and necromantic energy.",
    lair_actions=[
        LairAction(
            id="soul_drain",
            name="Soul Drain",
            description="The lich draws power from one creature within 120 feet. The target must succeed on a DC 18 CON save or take 2d10 necrotic damage, and the lich regains HP equal to half the damage dealt.",
            effect_type=LairEffectType.DAMAGE,
            target_type=LairTargetType.SINGLE_ENEMY,
            save_type="constitution",
            save_dc=18,
            damage_dice="2d10",
            damage_type="necrotic",
        ),
        LairAction(
            id="antilife_shell",
            name="Antilife Shell",
            description="The lich targets one creature within 60 feet. The target must succeed on a DC 18 WIS save or be paralyzed until initiative 20 of the next round.",
            effect_type=LairEffectType.CONDITION,
            target_type=LairTargetType.SINGLE_ENEMY,
            save_type="wisdom",
            save_dc=18,
            condition="paralyzed",
            condition_duration=1,
        ),
        LairAction(
            id="chill_of_death",
            name="Chill of Death",
            description="Deathly cold fills the lair. Each creature takes 2d6 cold damage, or half on a DC 18 CON save.",
            effect_type=LairEffectType.DAMAGE,
            target_type=LairTargetType.ALL_ENEMIES,
            save_type="constitution",
            save_dc=18,
            damage_dice="2d6",
            damage_type="cold",
        ),
    ],
    regional_effects=[
        "Undead within 1 mile have advantage on saving throws against turn undead.",
        "The area within 1 mile is lightly obscured by mist.",
        "Beasts within 6 miles avoid the area and become aggressive if forced near.",
    ],
)

# Beholder Lair
BEHOLDER_LAIR = LairDefinition(
    monster_id="beholder",
    name="Beholder's Domain",
    description="A spherical chamber of twisted reality.",
    lair_actions=[
        LairAction(
            id="eye_ray_surge",
            name="Eye Ray Surge",
            description="The beholder fires a random eye ray at a creature it can see within 120 feet.",
            effect_type=LairEffectType.DAMAGE,
            target_type=LairTargetType.SINGLE_ENEMY,
            save_type="dexterity",
            save_dc=16,
            damage_dice="3d10",
            damage_type="force",
        ),
        LairAction(
            id="slime_pool",
            name="Slime Pool",
            description="A 20-foot-radius pool of slime forms on the ground. Creatures entering or starting turn there must succeed on a DC 16 DEX save or be restrained.",
            effect_type=LairEffectType.TERRAIN,
            target_type=LairTargetType.AREA,
            save_type="dexterity",
            save_dc=16,
            condition="restrained",
            area_radius=20,
        ),
        LairAction(
            id="wall_grasp",
            name="Wall Grasp",
            description="Walls, ceiling, or floor sprout grasping appendages. One creature within 10 feet of a surface must succeed on a DC 16 DEX save or be grappled (escape DC 16).",
            effect_type=LairEffectType.CONDITION,
            target_type=LairTargetType.SINGLE_ENEMY,
            save_type="dexterity",
            save_dc=16,
            condition="grappled",
        ),
    ],
    regional_effects=[
        "Creatures within 1 mile suffer vivid, disturbing nightmares.",
        "Surfaces within 1 mile sometimes grow small eyes.",
        "Mundane items within 6 miles occasionally vanish or reappear elsewhere.",
    ],
)

# Ancient White Dragon Lair
ANCIENT_WHITE_DRAGON_LAIR = LairDefinition(
    monster_id="ancient_white_dragon",
    name="Frozen Throne",
    description="A cavern of eternal ice and howling winds.",
    lair_actions=[
        LairAction(
            id="freezing_fog",
            name="Freezing Fog",
            description="Freezing fog spreads in a 20-foot radius. Each creature takes 2d6 cold damage and has disadvantage on Perception checks until initiative 20 of next round.",
            effect_type=LairEffectType.DAMAGE,
            target_type=LairTargetType.AREA,
            save_type="constitution",
            save_dc=17,
            damage_dice="2d6",
            damage_type="cold",
            area_radius=20,
        ),
        LairAction(
            id="ice_spikes",
            name="Ice Spikes",
            description="Jagged ice erupts from the ground in a 20-foot radius. Each creature must succeed on a DC 17 DEX save or take 2d10 piercing damage and have speed halved until end of next turn.",
            effect_type=LairEffectType.DAMAGE,
            target_type=LairTargetType.AREA,
            save_type="dexterity",
            save_dc=17,
            damage_dice="2d10",
            damage_type="piercing",
            area_radius=20,
        ),
        LairAction(
            id="flash_freeze",
            name="Flash Freeze",
            description="One creature within 120 feet must succeed on a DC 17 CON save or be restrained by ice until initiative 20 of next round.",
            effect_type=LairEffectType.CONDITION,
            target_type=LairTargetType.SINGLE_ENEMY,
            save_type="constitution",
            save_dc=17,
            condition="restrained",
            condition_duration=1,
        ),
    ],
    regional_effects=[
        "Chilly fog lightly obscures land within 6 miles of the lair.",
        "Freezing precipitation falls within 6 miles of the lair.",
        "Icy wastes within 6 miles become supernaturally cold.",
    ],
)

# Death Knight Lair
DEATH_KNIGHT_LAIR = LairDefinition(
    monster_id="death_knight",
    name="Fortress of the Damned",
    description="A haunted fortress echoing with the cries of the fallen.",
    lair_actions=[
        LairAction(
            id="spectral_grasp",
            name="Spectral Grasp",
            description="Ghostly hands erupt from the ground in a 20-foot radius. Each creature must succeed on a DC 17 STR save or be restrained until initiative 20 of next round.",
            effect_type=LairEffectType.CONDITION,
            target_type=LairTargetType.AREA,
            save_type="strength",
            save_dc=17,
            condition="restrained",
            area_radius=20,
        ),
        LairAction(
            id="hellfire_burst",
            name="Hellfire Burst",
            description="Unholy fire erupts in a 10-foot radius. Each creature takes 3d6 fire damage and 3d6 necrotic damage, or half on a DC 17 DEX save.",
            effect_type=LairEffectType.DAMAGE,
            target_type=LairTargetType.AREA,
            save_type="dexterity",
            save_dc=17,
            damage_dice="3d6",
            damage_type="fire",
            area_radius=10,
        ),
        LairAction(
            id="dread_aura",
            name="Dread Aura",
            description="All enemies within 60 feet must succeed on a DC 17 WIS save or be frightened until initiative 20 of next round.",
            effect_type=LairEffectType.CONDITION,
            target_type=LairTargetType.ALL_ENEMIES,
            save_type="wisdom",
            save_dc=17,
            condition="frightened",
            condition_duration=1,
        ),
    ],
    regional_effects=[
        "Undead within 1 mile are restless and may rise spontaneously.",
        "An oppressive feeling of dread pervades the area within 1 mile.",
        "Divination magic within 1 mile often produces false or disturbing results.",
    ],
)


# Lair Registry
LAIR_REGISTRY: Dict[str, LairDefinition] = {
    "adult_red_dragon": ADULT_RED_DRAGON_LAIR,
    "ancient_red_dragon": ADULT_RED_DRAGON_LAIR,  # Same lair type
    "lich": LICH_LAIR,
    "beholder": BEHOLDER_LAIR,
    "ancient_white_dragon": ANCIENT_WHITE_DRAGON_LAIR,
    "adult_white_dragon": ANCIENT_WHITE_DRAGON_LAIR,  # Same lair type
    "death_knight": DEATH_KNIGHT_LAIR,
}


# =============================================================================
# LAIR ACTION FUNCTIONS
# =============================================================================

def get_lair_definition(monster_id: str) -> Optional[LairDefinition]:
    """Get lair definition for a monster ID."""
    return LAIR_REGISTRY.get(monster_id.lower())


def has_lair_actions(monster_id: str) -> bool:
    """Check if a monster type has lair actions defined."""
    return monster_id.lower() in LAIR_REGISTRY


def get_random_lair_action(lair: LairDefinition) -> Optional[LairAction]:
    """Select a random lair action from the lair definition."""
    if not lair.lair_actions:
        return None
    return random.choice(lair.lair_actions)


def roll_damage(damage_dice: str) -> int:
    """
    Roll damage dice (e.g., "2d6", "3d10").

    Args:
        damage_dice: Dice notation string

    Returns:
        Total damage rolled
    """
    if not damage_dice:
        return 0

    try:
        parts = damage_dice.lower().split("d")
        num_dice = int(parts[0]) if parts[0] else 1
        die_size = int(parts[1].split("+")[0].split("-")[0])

        total = sum(random.randint(1, die_size) for _ in range(num_dice))

        # Handle modifiers
        if "+" in damage_dice:
            modifier = int(damage_dice.split("+")[1])
            total += modifier
        elif "-" in damage_dice and "d" in damage_dice.split("-")[0]:
            modifier = int(damage_dice.split("-")[1])
            total -= modifier

        return max(0, total)
    except (ValueError, IndexError):
        return 0


def execute_lair_action(
    lair: LairDefinition,
    action: LairAction,
    enemies: List[Dict[str, Any]],
    lair_owner_stats: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Execute a lair action and return results.

    Args:
        lair: The lair definition
        action: The specific lair action to execute
        enemies: List of enemy combatant dicts (id, name, stats)
        lair_owner_stats: Stats of the creature whose lair this is

    Returns:
        Dict with action results (affected targets, damage, conditions, etc.)
    """
    results = {
        "action_id": action.id,
        "action_name": action.name,
        "description": action.description,
        "targets_affected": [],
        "total_damage": 0,
        "conditions_applied": [],
        "healing_done": 0,
    }

    # Select targets based on target type
    targets = []
    if action.target_type == LairTargetType.ALL_ENEMIES:
        targets = enemies
    elif action.target_type == LairTargetType.SINGLE_ENEMY:
        if enemies:
            targets = [random.choice(enemies)]
    elif action.target_type == LairTargetType.NEAREST_ENEMY:
        # Simplified - just pick first enemy
        if enemies:
            targets = [enemies[0]]
    elif action.target_type == LairTargetType.AREA:
        # Area affects subset of enemies (random selection for simulation)
        num_affected = min(len(enemies), max(1, len(enemies) // 2))
        targets = random.sample(enemies, num_affected) if enemies else []
    elif action.target_type == LairTargetType.LAIR_OWNER:
        # Effects that target the lair owner
        targets = []  # Handled separately

    # Process each target
    for target in targets:
        target_result = {
            "target_id": target.get("id", "unknown"),
            "target_name": target.get("name", "Unknown"),
            "save_made": False,
            "damage_taken": 0,
            "condition_applied": None,
        }

        # Make saving throw
        if action.save_type:
            save_ability = action.save_type.lower()
            ability_score = target.get(save_ability, 10)
            ability_mod = (ability_score - 10) // 2

            # Check proficiency
            save_profs = target.get("save_proficiencies", [])
            is_proficient = save_ability in [s.lower() for s in save_profs]

            level = target.get("level", target.get("cr", 1))
            if isinstance(level, float):
                level = max(1, int(level))
            proficiency = 2 + ((level - 1) // 4) if is_proficient else 0

            save_bonus = ability_mod + proficiency
            roll = random.randint(1, 20)
            total = roll + save_bonus

            target_result["save_roll"] = roll
            target_result["save_total"] = total
            target_result["save_dc"] = action.save_dc
            target_result["save_made"] = total >= action.save_dc

        # Apply damage
        if action.damage_dice:
            damage = roll_damage(action.damage_dice)
            if target_result["save_made"]:
                damage = damage // 2  # Half damage on save
            target_result["damage_taken"] = damage
            target_result["damage_type"] = action.damage_type
            results["total_damage"] += damage

        # Apply condition (only on failed save)
        if action.condition and not target_result["save_made"]:
            target_result["condition_applied"] = action.condition
            target_result["condition_duration"] = action.condition_duration
            results["conditions_applied"].append({
                "target_id": target.get("id"),
                "condition": action.condition,
                "duration": action.condition_duration,
            })

        results["targets_affected"].append(target_result)

    # Handle lair owner effects (healing, buffs)
    if action.effect_type == LairEffectType.HEALING:
        if action.damage_dice:
            healing = roll_damage(action.damage_dice)
            results["healing_done"] = healing

    return results


def check_lair_action_trigger(
    initiative_count: int,
    lair_owner_id: Optional[str] = None,
    combat_round: int = 1,
) -> bool:
    """
    Check if lair action should trigger.

    Lair actions trigger on initiative count 20 (losing ties).

    Args:
        initiative_count: Current initiative count
        lair_owner_id: ID of creature with lair
        combat_round: Current combat round

    Returns:
        True if lair action should trigger
    """
    # Lair actions occur on initiative 20
    return initiative_count == 20


def get_lair_action_summary(lair: LairDefinition) -> List[Dict[str, Any]]:
    """Get a summary of available lair actions for display."""
    return [
        {
            "id": a.id,
            "name": a.name,
            "description": a.description,
            "effect_type": a.effect_type.value,
            "save_dc": a.save_dc,
            "save_type": a.save_type,
        }
        for a in lair.lair_actions
    ]


def get_all_lairs() -> List[Dict[str, Any]]:
    """Get all registered lairs for reference."""
    return [
        {
            "monster_id": lair.monster_id,
            "name": lair.name,
            "description": lair.description,
            "num_actions": len(lair.lair_actions),
        }
        for lair in LAIR_REGISTRY.values()
    ]
