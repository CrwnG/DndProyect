"""
Cantrip Scaling System.

Handles level-based damage scaling for cantrips.
Damage cantrips scale at levels 5, 11, and 17.

This is part of both 2014 and 2024 rules, but the toggle
allows disabling it for custom games.
"""
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
import re

from app.core.dice import roll_damage, DamageResult
from app.core.rules_config import is_cantrip_scaling_enabled


# Cantrip scaling thresholds
CANTRIP_SCALING_LEVELS = [1, 5, 11, 17]


@dataclass
class ScaledCantripDamage:
    """Result of scaling a cantrip's damage."""
    base_dice: str
    scaled_dice: str
    die_count: int
    die_size: int
    modifier: int
    character_level: int
    scaling_tier: int  # 0=1-4, 1=5-10, 2=11-16, 3=17-20


def get_cantrip_scaling_tier(character_level: int) -> int:
    """
    Get the scaling tier for a character level.

    Tiers:
    - Tier 0: Levels 1-4 (base damage)
    - Tier 1: Levels 5-10 (2x dice)
    - Tier 2: Levels 11-16 (3x dice)
    - Tier 3: Levels 17-20 (4x dice)

    Args:
        character_level: The character's total level

    Returns:
        Scaling tier (0-3)
    """
    if character_level >= 17:
        return 3
    elif character_level >= 11:
        return 2
    elif character_level >= 5:
        return 1
    return 0


def get_cantrip_die_count(character_level: int) -> int:
    """
    Get the number of dice for a cantrip at a given level.

    Args:
        character_level: The character's total level

    Returns:
        Number of dice (1-4)
    """
    return get_cantrip_scaling_tier(character_level) + 1


def parse_base_damage(damage_dice: str) -> Tuple[int, int, int]:
    """
    Parse a damage dice string into components.

    Args:
        damage_dice: Dice notation like "1d10" or "2d6+3"

    Returns:
        Tuple of (die_count, die_size, modifier)
    """
    # Match patterns like "1d10", "2d6+3", "1d8-1"
    pattern = r'^(\d+)d(\d+)([+-]\d+)?$'
    match = re.match(pattern, damage_dice.strip())

    if not match:
        raise ValueError(f"Invalid damage dice format: {damage_dice}")

    die_count = int(match.group(1))
    die_size = int(match.group(2))
    modifier = int(match.group(3)) if match.group(3) else 0

    return die_count, die_size, modifier


def scale_cantrip_damage(
    base_damage: str,
    character_level: int,
    ignore_toggle: bool = False
) -> ScaledCantripDamage:
    """
    Scale a cantrip's damage based on character level.

    Args:
        base_damage: The base damage dice (e.g., "1d10" for Fire Bolt)
        character_level: The character's total level
        ignore_toggle: If True, always scale (for testing)

    Returns:
        ScaledCantripDamage with the scaled dice notation
    """
    # Parse the base damage
    base_count, die_size, modifier = parse_base_damage(base_damage)

    # Check if scaling is enabled
    if not ignore_toggle and not is_cantrip_scaling_enabled():
        # Return unscaled damage
        scaled_dice = base_damage
        return ScaledCantripDamage(
            base_dice=base_damage,
            scaled_dice=scaled_dice,
            die_count=base_count,
            die_size=die_size,
            modifier=modifier,
            character_level=character_level,
            scaling_tier=0
        )

    # Calculate scaled die count
    tier = get_cantrip_scaling_tier(character_level)
    scaled_count = base_count * (tier + 1)

    # Build the scaled dice string
    if modifier > 0:
        scaled_dice = f"{scaled_count}d{die_size}+{modifier}"
    elif modifier < 0:
        scaled_dice = f"{scaled_count}d{die_size}{modifier}"
    else:
        scaled_dice = f"{scaled_count}d{die_size}"

    return ScaledCantripDamage(
        base_dice=base_damage,
        scaled_dice=scaled_dice,
        die_count=scaled_count,
        die_size=die_size,
        modifier=modifier,
        character_level=character_level,
        scaling_tier=tier
    )


def roll_scaled_cantrip_damage(
    base_damage: str,
    character_level: int,
    additional_modifier: int = 0
) -> DamageResult:
    """
    Roll scaled cantrip damage.

    Args:
        base_damage: The base damage dice
        character_level: The character's total level
        additional_modifier: Any additional modifiers to add

    Returns:
        DamageResult with the rolled damage
    """
    scaled = scale_cantrip_damage(base_damage, character_level)

    # Add the additional modifier to the total
    total_modifier = scaled.modifier + additional_modifier

    return roll_damage(
        notation=f"{scaled.die_count}d{scaled.die_size}",
        modifier=total_modifier
    )


# =============================================================================
# CANTRIP DEFINITIONS
# =============================================================================

@dataclass
class CantripDefinition:
    """Definition of a damage cantrip."""
    id: str
    name: str
    base_damage: str
    damage_type: str
    attack_type: str  # "ranged_spell", "melee_spell", "save"
    save_type: Optional[str] = None  # For save-based cantrips
    range: int = 0
    description: str = ""


# Core damage cantrips
DAMAGE_CANTRIPS: Dict[str, CantripDefinition] = {
    "fire_bolt": CantripDefinition(
        id="fire_bolt",
        name="Fire Bolt",
        base_damage="1d10",
        damage_type="fire",
        attack_type="ranged_spell",
        range=120,
        description="Hurl a mote of fire at a creature."
    ),
    "sacred_flame": CantripDefinition(
        id="sacred_flame",
        name="Sacred Flame",
        base_damage="1d8",
        damage_type="radiant",
        attack_type="save",
        save_type="dexterity",
        range=60,
        description="Flame-like radiance descends on a creature."
    ),
    "ray_of_frost": CantripDefinition(
        id="ray_of_frost",
        name="Ray of Frost",
        base_damage="1d8",
        damage_type="cold",
        attack_type="ranged_spell",
        range=60,
        description="A frigid beam of blue-white light."
    ),
    "chill_touch": CantripDefinition(
        id="chill_touch",
        name="Chill Touch",
        base_damage="1d8",
        damage_type="necrotic",
        attack_type="ranged_spell",
        range=120,
        description="Ghostly, skeletal hand grasps at the target."
    ),
    "eldritch_blast": CantripDefinition(
        id="eldritch_blast",
        name="Eldritch Blast",
        base_damage="1d10",
        damage_type="force",
        attack_type="ranged_spell",
        range=120,
        description="A beam of crackling energy."
    ),
    "toll_the_dead": CantripDefinition(
        id="toll_the_dead",
        name="Toll the Dead",
        base_damage="1d8",  # 1d12 if target is damaged
        damage_type="necrotic",
        attack_type="save",
        save_type="wisdom",
        range=60,
        description="Dolorous sound that wraps around the target."
    ),
    "shocking_grasp": CantripDefinition(
        id="shocking_grasp",
        name="Shocking Grasp",
        base_damage="1d8",
        damage_type="lightning",
        attack_type="melee_spell",
        range=5,
        description="Lightning springs from your hand."
    ),
    "acid_splash": CantripDefinition(
        id="acid_splash",
        name="Acid Splash",
        base_damage="1d6",
        damage_type="acid",
        attack_type="save",
        save_type="dexterity",
        range=60,
        description="A bubble of acid."
    ),
    "poison_spray": CantripDefinition(
        id="poison_spray",
        name="Poison Spray",
        base_damage="1d12",
        damage_type="poison",
        attack_type="save",
        save_type="constitution",
        range=10,
        description="A puff of noxious gas."
    ),
    "produce_flame": CantripDefinition(
        id="produce_flame",
        name="Produce Flame",
        base_damage="1d8",
        damage_type="fire",
        attack_type="ranged_spell",
        range=30,
        description="A flickering flame in your hand."
    ),
    "word_of_radiance": CantripDefinition(
        id="word_of_radiance",
        name="Word of Radiance",
        base_damage="1d6",
        damage_type="radiant",
        attack_type="save",
        save_type="constitution",
        range=5,  # 5ft radius
        description="Burning radiance erupts from you."
    ),
}


def get_cantrip_definition(cantrip_id: str) -> Optional[CantripDefinition]:
    """
    Get a cantrip definition by ID.

    Args:
        cantrip_id: The cantrip's ID

    Returns:
        CantripDefinition if found, None otherwise
    """
    return DAMAGE_CANTRIPS.get(cantrip_id.lower())


def get_scaled_cantrip_info(
    cantrip_id: str,
    character_level: int
) -> Optional[Dict]:
    """
    Get full information about a scaled cantrip.

    Args:
        cantrip_id: The cantrip's ID
        character_level: The character's total level

    Returns:
        Dictionary with cantrip info and scaled damage, or None if not found
    """
    cantrip = get_cantrip_definition(cantrip_id)
    if not cantrip:
        return None

    scaled = scale_cantrip_damage(cantrip.base_damage, character_level)

    return {
        "id": cantrip.id,
        "name": cantrip.name,
        "base_damage": cantrip.base_damage,
        "scaled_damage": scaled.scaled_dice,
        "damage_type": cantrip.damage_type,
        "attack_type": cantrip.attack_type,
        "save_type": cantrip.save_type,
        "range": cantrip.range,
        "description": cantrip.description,
        "character_level": character_level,
        "scaling_tier": scaled.scaling_tier,
    }


# =============================================================================
# SPECIAL CANTRIP HANDLING
# =============================================================================

def get_eldritch_blast_beams(character_level: int) -> int:
    """
    Get the number of Eldritch Blast beams at a given level.

    Eldritch Blast is special - it fires multiple beams instead of
    rolling more dice on a single beam.

    Args:
        character_level: The character's total level

    Returns:
        Number of beams (1-4)
    """
    return get_cantrip_die_count(character_level)


def get_toll_the_dead_damage(
    character_level: int,
    target_is_damaged: bool
) -> str:
    """
    Get Toll the Dead damage dice.

    Toll the Dead deals d8 normally, d12 if target is missing HP.

    Args:
        character_level: The character's total level
        target_is_damaged: Whether the target is below max HP

    Returns:
        Scaled damage dice string
    """
    base_die = "1d12" if target_is_damaged else "1d8"
    scaled = scale_cantrip_damage(base_die, character_level)
    return scaled.scaled_dice


def format_cantrip_scaling_description(
    cantrip_id: str,
    character_level: int
) -> str:
    """
    Get a formatted description of cantrip scaling.

    Args:
        cantrip_id: The cantrip's ID
        character_level: The character's total level

    Returns:
        Human-readable scaling description
    """
    cantrip = get_cantrip_definition(cantrip_id)
    if not cantrip:
        return "Unknown cantrip."

    scaled = scale_cantrip_damage(cantrip.base_damage, character_level)

    if cantrip_id == "eldritch_blast":
        beams = get_eldritch_blast_beams(character_level)
        return f"{cantrip.name}: {beams} beam(s), each dealing {cantrip.base_damage} {cantrip.damage_type} damage."

    if scaled.scaling_tier == 0:
        return f"{cantrip.name}: {scaled.scaled_dice} {cantrip.damage_type} damage."
    else:
        tier_names = ["base", "5th level", "11th level", "17th level"]
        return (
            f"{cantrip.name}: {scaled.scaled_dice} {cantrip.damage_type} damage "
            f"(scaled at {tier_names[scaled.scaling_tier]})."
        )
