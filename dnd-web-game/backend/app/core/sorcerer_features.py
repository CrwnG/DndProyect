"""
Sorcerer Features System for D&D 5e 2024

Comprehensive Sorcerer feature implementation:
- Sorcery Points (flexible magical energy)
- Metamagic options
- Spell slot to Sorcery Point conversion
- Sorcerous Origin features
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum


class SorcerousOrigin(str, Enum):
    """Sorcerer subclass options."""
    DRACONIC = "draconic_bloodline"
    WILD_MAGIC = "wild_magic"
    DIVINE_SOUL = "divine_soul"
    SHADOW = "shadow_magic"
    STORM = "storm_sorcery"
    ABERRANT = "aberrant_mind"
    CLOCKWORK = "clockwork_soul"


class MetamagicType(str, Enum):
    """Metamagic option types."""
    CAREFUL = "careful_spell"
    DISTANT = "distant_spell"
    EMPOWERED = "empowered_spell"
    EXTENDED = "extended_spell"
    HEIGHTENED = "heightened_spell"
    QUICKENED = "quickened_spell"
    SEEKING = "seeking_spell"
    SUBTLE = "subtle_spell"
    TRANSMUTED = "transmuted_spell"
    TWINNED = "twinned_spell"


@dataclass
class MetamagicOption:
    """A Metamagic option."""
    id: MetamagicType
    name: str
    cost: int  # Sorcery points (some are variable)
    description: str
    effect: str
    cost_is_variable: bool = False  # True if cost depends on spell level

    def get_cost(self, spell_level: int = 1) -> int:
        """Get the sorcery point cost for this metamagic."""
        if self.cost_is_variable:
            # Twinned Spell costs 1 point per spell level (min 1 for cantrips)
            return max(1, spell_level)
        return self.cost

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id.value,
            "name": self.name,
            "cost": self.cost,
            "cost_is_variable": self.cost_is_variable,
            "description": self.description,
            "effect": self.effect,
        }


# =============================================================================
# METAMAGIC OPTIONS
# =============================================================================

METAMAGIC_OPTIONS: Dict[MetamagicType, MetamagicOption] = {
    MetamagicType.CAREFUL: MetamagicOption(
        id=MetamagicType.CAREFUL,
        name="Careful Spell",
        cost=1,
        description="When you cast a spell that forces other creatures to make a saving throw, you can protect some of them from the spell's full force.",
        effect="Choose up to CHA mod creatures (min 1). They automatically succeed on their saving throws against the spell.",
    ),
    MetamagicType.DISTANT: MetamagicOption(
        id=MetamagicType.DISTANT,
        name="Distant Spell",
        cost=1,
        description="When you cast a spell that has a range of 5 feet or greater, you can double the range of the spell.",
        effect="Double the spell's range. If the spell has a range of touch, it becomes 30 feet instead.",
    ),
    MetamagicType.EMPOWERED: MetamagicOption(
        id=MetamagicType.EMPOWERED,
        name="Empowered Spell",
        cost=1,
        description="When you roll damage for a spell, you can reroll a number of the damage dice up to your Charisma modifier.",
        effect="Reroll up to CHA mod damage dice. Must use new rolls. Can combine with other Metamagic.",
    ),
    MetamagicType.EXTENDED: MetamagicOption(
        id=MetamagicType.EXTENDED,
        name="Extended Spell",
        cost=1,
        description="When you cast a spell that has a duration of 1 minute or longer, you can double its duration.",
        effect="Double duration (max 24 hours).",
    ),
    MetamagicType.HEIGHTENED: MetamagicOption(
        id=MetamagicType.HEIGHTENED,
        name="Heightened Spell",
        cost=3,
        description="When you cast a spell that forces a creature to make a saving throw, you can give one target disadvantage on its first save.",
        effect="One target has disadvantage on first saving throw against the spell.",
    ),
    MetamagicType.QUICKENED: MetamagicOption(
        id=MetamagicType.QUICKENED,
        name="Quickened Spell",
        cost=2,
        description="When you cast a spell that has a casting time of 1 action, you can change the casting time to 1 bonus action.",
        effect="Change casting time from 1 action to 1 bonus action.",
    ),
    MetamagicType.SEEKING: MetamagicOption(
        id=MetamagicType.SEEKING,
        name="Seeking Spell",
        cost=2,
        description="When you make an attack roll for a spell and miss, you can reroll the d20, and you must use the new roll.",
        effect="Reroll missed spell attack (must use new roll).",
    ),
    MetamagicType.SUBTLE: MetamagicOption(
        id=MetamagicType.SUBTLE,
        name="Subtle Spell",
        cost=1,
        description="When you cast a spell, you can cast it without any somatic or verbal components.",
        effect="No verbal or somatic components needed.",
    ),
    MetamagicType.TRANSMUTED: MetamagicOption(
        id=MetamagicType.TRANSMUTED,
        name="Transmuted Spell",
        cost=1,
        description="When you cast a spell that deals a type of damage from the following list, you can change that damage type to one of the other listed types: acid, cold, fire, lightning, poison, thunder.",
        effect="Change damage type (acid, cold, fire, lightning, poison, thunder).",
    ),
    MetamagicType.TWINNED: MetamagicOption(
        id=MetamagicType.TWINNED,
        name="Twinned Spell",
        cost=1,  # Base cost, multiplied by spell level
        cost_is_variable=True,
        description="When you cast a spell that targets only one creature and doesn't have a range of self, you can target a second creature with the same spell.",
        effect="Target a second creature. Cost = spell level (min 1 for cantrips). Only works on single-target spells.",
    ),
}


@dataclass
class SorceryPointState:
    """Tracks Sorcery Points for a sorcerer."""
    max_points: int = 0
    current_points: int = 0
    metamagic_known: List[MetamagicType] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_points": self.max_points,
            "current_points": self.current_points,
            "metamagic_known": [m.value for m in self.metamagic_known],
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "SorceryPointState":
        return cls(
            max_points=data.get("max_points", 0),
            current_points=data.get("current_points", 0),
            metamagic_known=[MetamagicType(m) for m in data.get("metamagic_known", [])],
        )


# =============================================================================
# SPELL SLOT <-> SORCERY POINT CONVERSION
# =============================================================================

SPELL_SLOT_POINT_COST: Dict[int, int] = {
    1: 2,
    2: 3,
    3: 5,
    4: 6,
    5: 7,
}

POINT_TO_SLOT_COST: Dict[int, int] = {
    1: 2,
    2: 3,
    3: 5,
    4: 6,
    5: 7,
}


def convert_slot_to_points(
    state: SorceryPointState,
    slot_level: int
) -> Tuple[bool, int, str]:
    """
    Convert a spell slot to sorcery points.

    Font of Magic feature (level 2+).

    Args:
        state: Current sorcery point state
        slot_level: Level of slot to convert (1-5)

    Returns:
        Tuple of (success, points_gained, message)
    """
    if slot_level < 1 or slot_level > 5:
        return False, 0, "Can only convert slots of levels 1-5"

    points_gained = SPELL_SLOT_POINT_COST.get(slot_level, slot_level)

    # Check if would exceed max
    new_total = state.current_points + points_gained
    if new_total > state.max_points:
        # Can still gain points, but excess is lost
        actual_gain = state.max_points - state.current_points
        state.current_points = state.max_points
        return True, actual_gain, f"Converted level {slot_level} slot to {actual_gain} points (capped at max)"

    state.current_points = new_total
    return True, points_gained, f"Converted level {slot_level} slot to {points_gained} sorcery points"


def convert_points_to_slot(
    state: SorceryPointState,
    slot_level: int
) -> Tuple[bool, str]:
    """
    Convert sorcery points to a spell slot.

    Creating Spell Slots table (2024 PHB):
    - 1st level: 2 points
    - 2nd level: 3 points
    - 3rd level: 5 points
    - 4th level: 6 points
    - 5th level: 7 points

    Cannot create slots above 5th level.
    Created slot vanishes at end of long rest.

    Args:
        state: Current sorcery point state
        slot_level: Level of slot to create (1-5)

    Returns:
        Tuple of (success, message)
    """
    if slot_level < 1 or slot_level > 5:
        return False, "Can only create slots of levels 1-5"

    cost = POINT_TO_SLOT_COST.get(slot_level, 7)

    if state.current_points < cost:
        return False, f"Not enough points (need {cost}, have {state.current_points})"

    state.current_points -= cost
    return True, f"Created level {slot_level} spell slot for {cost} sorcery points"


# =============================================================================
# METAMAGIC USAGE
# =============================================================================

def can_use_metamagic(
    state: SorceryPointState,
    metamagic_id: MetamagicType,
    spell_level: int = 1
) -> Tuple[bool, str]:
    """
    Check if a metamagic option can be used.

    Args:
        state: Current sorcery point state
        metamagic_id: The metamagic to use
        spell_level: Level of the spell (for Twinned)

    Returns:
        Tuple of (can_use, reason_if_not)
    """
    if metamagic_id not in state.metamagic_known:
        return False, f"You don't know {metamagic_id.value}"

    option = METAMAGIC_OPTIONS.get(metamagic_id)
    if not option:
        return False, f"Unknown metamagic: {metamagic_id}"

    cost = option.get_cost(spell_level)

    if state.current_points < cost:
        return False, f"Not enough sorcery points (need {cost}, have {state.current_points})"

    return True, ""


def use_metamagic(
    state: SorceryPointState,
    metamagic_id: MetamagicType,
    spell_level: int = 1
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Use a metamagic option.

    Args:
        state: Current sorcery point state
        metamagic_id: The metamagic to use
        spell_level: Level of the spell (for Twinned)

    Returns:
        Tuple of (success, message, effect_data)
    """
    can_use, reason = can_use_metamagic(state, metamagic_id, spell_level)
    if not can_use:
        return False, reason, {}

    option = METAMAGIC_OPTIONS[metamagic_id]
    cost = option.get_cost(spell_level)

    state.current_points -= cost

    effect_data = {
        "metamagic_id": metamagic_id.value,
        "metamagic_name": option.name,
        "cost": cost,
        "points_remaining": state.current_points,
        "effect": option.effect,
    }

    return True, f"Used {option.name}!", effect_data


# =============================================================================
# SORCERER PROGRESSION
# =============================================================================

def get_max_sorcery_points(level: int) -> int:
    """Get maximum sorcery points (equals sorcerer level, gained at level 2)."""
    if level < 2:
        return 0
    return level


def get_metamagic_known_count(level: int) -> int:
    """Get number of Metamagic options known."""
    if level >= 17:
        return 4
    elif level >= 10:
        return 3
    elif level >= 3:
        return 2
    return 0


def get_cantrips_known(level: int) -> int:
    """Get number of cantrips known."""
    if level >= 10:
        return 6
    elif level >= 4:
        return 5
    else:
        return 4


def get_spells_known(level: int) -> int:
    """Get number of spells known."""
    if level >= 17:
        return 15
    elif level >= 15:
        return 14
    elif level >= 13:
        return 13
    elif level >= 11:
        return 12
    else:
        # Level 1-10: level + 1
        return level + 1


def initialize_sorcery_state(
    level: int,
    metamagic_choices: List[MetamagicType] = None
) -> SorceryPointState:
    """Create a new Sorcery Point state for a sorcerer."""
    max_points = get_max_sorcery_points(level)
    return SorceryPointState(
        max_points=max_points,
        current_points=max_points,
        metamagic_known=metamagic_choices or [],
    )


def restore_sorcery_points(
    state: SorceryPointState,
    is_long_rest: bool = False
) -> int:
    """
    Restore sorcery points on rest.

    Only long rest restores all sorcery points.

    Returns:
        Number of points restored
    """
    if not is_long_rest:
        return 0

    restored = state.max_points - state.current_points
    state.current_points = state.max_points
    return restored


# =============================================================================
# SORCEROUS ORIGIN FEATURES
# =============================================================================

@dataclass
class OriginFeature:
    """A Sorcerous Origin feature."""
    id: str
    name: str
    level: int
    description: str
    grants_spells: List[str] = field(default_factory=list)
    passive_effect: Optional[str] = None


DRACONIC_FEATURES: List[OriginFeature] = [
    OriginFeature(
        id="dragon_ancestor",
        name="Dragon Ancestor",
        level=1,
        description="Choose a dragon type. You learn Draconic and have advantage on Charisma checks with dragons.",
    ),
    OriginFeature(
        id="draconic_resilience",
        name="Draconic Resilience",
        level=1,
        description="Your HP maximum increases by 1 per sorcerer level. When unarmored, AC = 13 + DEX mod.",
        passive_effect="HP +1/level, Unarmored AC = 13 + DEX",
    ),
    OriginFeature(
        id="elemental_affinity",
        name="Elemental Affinity",
        level=6,
        description="Add CHA mod to damage of spells matching your dragon's type. Spend 1 sorcery point to gain resistance to that damage type for 1 hour.",
        passive_effect="+CHA damage to dragon type spells",
    ),
    OriginFeature(
        id="dragon_wings",
        name="Dragon Wings",
        level=14,
        description="As a bonus action, sprout dragon wings gaining flying speed equal to your walking speed.",
        passive_effect="Bonus action: fly speed = walk speed",
    ),
    OriginFeature(
        id="draconic_presence",
        name="Draconic Presence",
        level=18,
        description="Spend 5 sorcery points to emanate an aura of awe or fear (60 feet) for 1 minute.",
    ),
]

WILD_MAGIC_FEATURES: List[OriginFeature] = [
    OriginFeature(
        id="wild_magic_surge",
        name="Wild Magic Surge",
        level=1,
        description="After casting a sorcerer spell of 1st level or higher, DM can have you roll d20. On 1, roll on Wild Magic Surge table.",
    ),
    OriginFeature(
        id="tides_of_chaos",
        name="Tides of Chaos",
        level=1,
        description="Gain advantage on one attack roll, ability check, or saving throw. Regain use after long rest or DM-triggered Wild Magic Surge.",
    ),
    OriginFeature(
        id="bend_luck",
        name="Bend Luck",
        level=6,
        description="When a creature you see makes an attack roll, ability check, or saving throw, spend 2 sorcery points to roll 1d4 and add or subtract from their roll.",
    ),
    OriginFeature(
        id="controlled_chaos",
        name="Controlled Chaos",
        level=14,
        description="When you roll on Wild Magic Surge table, roll twice and use either number.",
    ),
    OriginFeature(
        id="spell_bombardment",
        name="Spell Bombardment",
        level=18,
        description="When you roll max damage on a damage die, you can roll that die again and add the extra damage.",
    ),
]

ORIGIN_FEATURES: Dict[SorcerousOrigin, List[OriginFeature]] = {
    SorcerousOrigin.DRACONIC: DRACONIC_FEATURES,
    SorcerousOrigin.WILD_MAGIC: WILD_MAGIC_FEATURES,
    # Add more origins as needed
}


def get_origin_features_at_level(
    origin: SorcerousOrigin,
    level: int
) -> List[OriginFeature]:
    """Get all origin features available at a given level."""
    features = ORIGIN_FEATURES.get(origin, [])
    return [f for f in features if f.level <= level]


def get_new_origin_features_at_level(
    origin: SorcerousOrigin,
    level: int
) -> List[OriginFeature]:
    """Get origin features gained exactly at a given level."""
    features = ORIGIN_FEATURES.get(origin, [])
    return [f for f in features if f.level == level]


# =============================================================================
# DRAGON ANCESTOR DAMAGE TYPES
# =============================================================================

DRAGON_DAMAGE_TYPES: Dict[str, str] = {
    "black": "acid",
    "blue": "lightning",
    "brass": "fire",
    "bronze": "lightning",
    "copper": "acid",
    "gold": "fire",
    "green": "poison",
    "red": "fire",
    "silver": "cold",
    "white": "cold",
}


def get_dragon_damage_type(dragon_color: str) -> str:
    """Get the damage type associated with a dragon color."""
    return DRAGON_DAMAGE_TYPES.get(dragon_color.lower(), "fire")


# =============================================================================
# INNATE SORCERY (2024 PHB)
# =============================================================================

@dataclass
class InnateSorceryState:
    """
    Tracks Innate Sorcery feature state for D&D 5e 2024.

    Innate Sorcery (Level 1):
    - Bonus action to activate
    - Advantage on attack rolls for sorcerer spells
    - +1 to sorcerer spell save DC
    - Duration: 1 minute (10 rounds)
    - Uses: Equal to proficiency bonus per long rest
    """
    max_uses: int = 2  # Proficiency bonus at level 1
    uses_remaining: int = 2
    is_active: bool = False
    active_until_round: Optional[int] = None  # Round when effect ends

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_uses": self.max_uses,
            "uses_remaining": self.uses_remaining,
            "is_active": self.is_active,
            "active_until_round": self.active_until_round,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "InnateSorceryState":
        return cls(
            max_uses=data.get("max_uses", 2),
            uses_remaining=data.get("uses_remaining", 2),
            is_active=data.get("is_active", False),
            active_until_round=data.get("active_until_round"),
        )


def get_innate_sorcery_uses(level: int) -> int:
    """
    Get maximum Innate Sorcery uses based on proficiency bonus.

    Uses = Proficiency bonus per long rest.
    """
    return 2 + ((level - 1) // 4)


def initialize_innate_sorcery(level: int) -> InnateSorceryState:
    """Create a new Innate Sorcery state for a sorcerer."""
    max_uses = get_innate_sorcery_uses(level)
    return InnateSorceryState(
        max_uses=max_uses,
        uses_remaining=max_uses,
        is_active=False,
        active_until_round=None,
    )


def activate_innate_sorcery(
    state: InnateSorceryState,
    current_round: int = 1
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Activate Innate Sorcery (bonus action).

    Args:
        state: Current Innate Sorcery state
        current_round: Current combat round

    Returns:
        Tuple of (success, message, effect_data)
    """
    if state.is_active:
        return False, "Innate Sorcery is already active", {}

    if state.uses_remaining <= 0:
        return False, "No uses of Innate Sorcery remaining", {}

    state.uses_remaining -= 1
    state.is_active = True
    state.active_until_round = current_round + 10  # 1 minute = 10 rounds

    effect_data = {
        "feature": "innate_sorcery",
        "action_type": "bonus_action",
        "duration_rounds": 10,
        "active_until_round": state.active_until_round,
        "effects": {
            "spell_attack_advantage": True,
            "spell_save_dc_bonus": 1,
        },
        "uses_remaining": state.uses_remaining,
    }

    return True, "Innate Sorcery activated! Advantage on spell attacks, +1 to spell save DC for 1 minute.", effect_data


def check_innate_sorcery_expiration(
    state: InnateSorceryState,
    current_round: int
) -> bool:
    """
    Check if Innate Sorcery should expire based on current round.

    Args:
        state: Current Innate Sorcery state
        current_round: Current combat round

    Returns:
        True if the effect expired this check
    """
    if not state.is_active:
        return False

    if state.active_until_round is not None and current_round >= state.active_until_round:
        state.is_active = False
        state.active_until_round = None
        return True

    return False


def deactivate_innate_sorcery(state: InnateSorceryState) -> bool:
    """
    Manually deactivate Innate Sorcery (e.g., if concentration broken or knocked unconscious).

    Returns:
        True if was active and is now deactivated
    """
    if state.is_active:
        state.is_active = False
        state.active_until_round = None
        return True
    return False


def restore_innate_sorcery(state: InnateSorceryState, level: int) -> int:
    """
    Restore Innate Sorcery uses on long rest.

    Args:
        state: Current Innate Sorcery state
        level: Sorcerer level (for proficiency calculation)

    Returns:
        Number of uses restored
    """
    max_uses = get_innate_sorcery_uses(level)
    state.max_uses = max_uses
    restored = max_uses - state.uses_remaining
    state.uses_remaining = max_uses
    state.is_active = False
    state.active_until_round = None
    return restored


def get_innate_sorcery_modifiers(state: InnateSorceryState) -> Dict[str, Any]:
    """
    Get the current modifiers from Innate Sorcery if active.

    Returns:
        Dict with spell attack advantage and DC bonus if active, else empty.
    """
    if not state.is_active:
        return {}

    return {
        "spell_attack_advantage": True,
        "spell_save_dc_bonus": 1,
    }


# =============================================================================
# MISSING SORCEROUS ORIGIN FEATURES
# =============================================================================

DIVINE_SOUL_FEATURES: List[OriginFeature] = [
    OriginFeature(
        id="divine_magic",
        name="Divine Magic",
        level=1,
        description="Your link to the divine allows you to learn spells from the cleric spell list. Choose an affinity: Good, Evil, Law, Chaos, or Neutrality.",
        grants_spells=["cure_wounds"],  # Bonus spell based on affinity
    ),
    OriginFeature(
        id="favored_by_the_gods",
        name="Favored by the Gods",
        level=1,
        description="When you fail a saving throw or miss with an attack roll, you can roll 2d4 and add it to the total, potentially changing the outcome. Once used, you can't use it again until you finish a short or long rest.",
    ),
    OriginFeature(
        id="empowered_healing",
        name="Empowered Healing",
        level=6,
        description="When you or an ally within 5 feet rolls dice to heal, you can spend 1 sorcery point to reroll any number of those dice once.",
    ),
    OriginFeature(
        id="otherworldly_wings",
        name="Otherworldly Wings",
        level=14,
        description="As a bonus action, manifest spectral wings from your back gaining a flying speed of 30 feet.",
        passive_effect="Bonus action: 30 ft flying speed",
    ),
    OriginFeature(
        id="unearthly_recovery",
        name="Unearthly Recovery",
        level=18,
        description="As a bonus action when you have fewer than half your hit points remaining, regain a number of hit points equal to half your hit point maximum.",
    ),
]

SHADOW_MAGIC_FEATURES: List[OriginFeature] = [
    OriginFeature(
        id="eyes_of_the_dark",
        name="Eyes of the Dark",
        level=1,
        description="You have darkvision with a range of 120 feet. When you reach 3rd level, you learn the Darkness spell, which doesn't count against your spells known. You can cast Darkness by spending 2 sorcery points, and you can see through this darkness.",
        grants_spells=["darkness"],
        passive_effect="120 ft darkvision",
    ),
    OriginFeature(
        id="strength_of_the_grave",
        name="Strength of the Grave",
        level=1,
        description="When damage reduces you to 0 hit points, make a Charisma saving throw (DC 5 + damage taken). On success, drop to 1 hit point instead. Doesn't work against radiant damage or critical hits.",
    ),
    OriginFeature(
        id="hound_of_ill_omen",
        name="Hound of Ill Omen",
        level=6,
        description="Spend 3 sorcery points as a bonus action to summon a dire wolf to attack a target you can see within 120 feet.",
    ),
    OriginFeature(
        id="shadow_walk",
        name="Shadow Walk",
        level=14,
        description="As a bonus action when in dim light or darkness, teleport up to 120 feet to an unoccupied space you can see that is also in dim light or darkness.",
        passive_effect="Bonus action: 120 ft teleport in darkness",
    ),
    OriginFeature(
        id="umbral_form",
        name="Umbral Form",
        level=18,
        description="Spend 6 sorcery points as a bonus action to become a shadowy form for 1 minute. Gain resistance to all damage except force and radiant, and can move through creatures and objects as difficult terrain.",
    ),
]

STORM_SORCERY_FEATURES: List[OriginFeature] = [
    OriginFeature(
        id="wind_speaker",
        name="Wind Speaker",
        level=1,
        description="You can speak, read, and write Primordial. Knowing this language allows you to understand and be understood by those who speak its dialects: Aquan, Auran, Ignan, and Terran.",
    ),
    OriginFeature(
        id="tempestuous_magic",
        name="Tempestuous Magic",
        level=1,
        description="When you cast a spell of 1st level or higher, you can use a bonus action to cause whirling gusts of elemental air to briefly surround you, allowing you to fly up to 10 feet without provoking opportunity attacks.",
        passive_effect="Bonus action: fly 10 ft after casting spell",
    ),
    OriginFeature(
        id="heart_of_the_storm",
        name="Heart of the Storm",
        level=6,
        description="You gain resistance to lightning and thunder damage. Whenever you cast a spell of 1st level or higher that deals lightning or thunder damage, stormy magic erupts, dealing lightning or thunder damage to creatures of your choice within 10 feet equal to half your sorcerer level.",
        passive_effect="Resistance to lightning and thunder",
    ),
    OriginFeature(
        id="storm_guide",
        name="Storm Guide",
        level=6,
        description="If it is raining, you can use an action to cause the rain to stop falling in a 20-foot-radius sphere centered on you. You can also cause winds to create calm around you.",
    ),
    OriginFeature(
        id="storms_fury",
        name="Storm's Fury",
        level=14,
        description="When hit by a melee attack, you can use your reaction to deal lightning damage to the attacker equal to your sorcerer level. The attacker must make a Strength saving throw or be pushed 20 feet away.",
    ),
    OriginFeature(
        id="wind_soul",
        name="Wind Soul",
        level=18,
        description="You gain immunity to lightning and thunder damage and a flying speed of 60 feet. You can also reduce your flying speed to 30 feet to grant 30 feet flying speed to up to 3 + CHA mod creatures for 1 hour.",
        passive_effect="Immunity to lightning and thunder, 60 ft flying speed",
    ),
]

ABERRANT_MIND_FEATURES: List[OriginFeature] = [
    OriginFeature(
        id="psionic_spells",
        name="Psionic Spells",
        level=1,
        description="You learn additional spells that don't count against your spells known. These spells are: arms of Hadar (1st), dissonant whispers (1st), calm emotions (3rd), detect thoughts (3rd), hunger of Hadar (5th), sending (5th), Evard's black tentacles (7th), summon aberration (7th), Rary's telepathic bond (9th), telekinesis (9th).",
        grants_spells=["arms_of_hadar", "dissonant_whispers"],
    ),
    OriginFeature(
        id="telepathic_speech",
        name="Telepathic Speech",
        level=1,
        description="As a bonus action, choose one creature within 30 feet. You and that creature can speak telepathically with each other while within a number of miles equal to your Charisma modifier.",
    ),
    OriginFeature(
        id="psionic_sorcery",
        name="Psionic Sorcery",
        level=6,
        description="When you cast any Psionic Spells spell, you can cast it by expending sorcery points equal to the spell's level instead of a spell slot. If cast this way, the spell requires no verbal or somatic components.",
    ),
    OriginFeature(
        id="psychic_defenses",
        name="Psychic Defenses",
        level=6,
        description="You gain resistance to psychic damage, and you have advantage on saving throws against being charmed or frightened.",
        passive_effect="Resistance to psychic, advantage vs charmed/frightened",
    ),
    OriginFeature(
        id="revelation_in_flesh",
        name="Revelation in Flesh",
        level=14,
        description="As a bonus action, spend 1 or more sorcery points to transform for 10 minutes: see invisible (1), swim + breathe water (1), squeeze through 1-inch space (1), or hover (1).",
    ),
    OriginFeature(
        id="warping_implosion",
        name="Warping Implosion",
        level=18,
        description="As an action, teleport to an unoccupied space you can see within 120 feet. Each creature within 30 feet of the space you left must make a Strength save or take 3d10 force damage and be pulled toward the space. On success, half damage and not pulled.",
    ),
]

CLOCKWORK_SOUL_FEATURES: List[OriginFeature] = [
    OriginFeature(
        id="clockwork_magic",
        name="Clockwork Magic",
        level=1,
        description="You learn additional spells that don't count against your spells known. These spells are: alarm (1st), protection from evil and good (1st), aid (3rd), lesser restoration (3rd), dispel magic (5th), protection from energy (5th), freedom of movement (7th), summon construct (7th), greater restoration (9th), wall of force (9th).",
        grants_spells=["alarm", "protection_from_evil_and_good"],
    ),
    OriginFeature(
        id="restore_balance",
        name="Restore Balance",
        level=1,
        description="When a creature you can see within 60 feet is about to roll a d20 with advantage or disadvantage, you can use your reaction to prevent the roll from being affected by advantage and disadvantage. Uses = proficiency bonus per long rest.",
    ),
    OriginFeature(
        id="bastion_of_law",
        name="Bastion of Law",
        level=6,
        description="As an action, spend 1 to 5 sorcery points to create a magical ward around a creature you can see within 30 feet. The ward has a number of d8s equal to the points spent. When the creature takes damage, expend any number of those dice to reduce damage by the amount rolled.",
    ),
    OriginFeature(
        id="trance_of_order",
        name="Trance of Order",
        level=14,
        description="As a bonus action, enter a state of clockwork consciousness for 1 minute. Attack rolls against you can't benefit from advantage, and when you make an attack roll, ability check, or saving throw, you can treat a roll of 9 or lower as a 10.",
        passive_effect="Can't be advantaged against, minimum roll 10",
    ),
    OriginFeature(
        id="clockwork_cavalcade",
        name="Clockwork Cavalcade",
        level=18,
        description="As an action, summon spirits of order in a 30-foot cube. Each creature of your choice takes 100 damage, and your choice of: restore up to 100 HP to any creatures in the cube, or repair damaged objects.",
    ),
]

# Update ORIGIN_FEATURES with all origins
ORIGIN_FEATURES.update({
    SorcerousOrigin.DIVINE_SOUL: DIVINE_SOUL_FEATURES,
    SorcerousOrigin.SHADOW: SHADOW_MAGIC_FEATURES,
    SorcerousOrigin.STORM: STORM_SORCERY_FEATURES,
    SorcerousOrigin.ABERRANT: ABERRANT_MIND_FEATURES,
    SorcerousOrigin.CLOCKWORK: CLOCKWORK_SOUL_FEATURES,
})


# =============================================================================
# ALIASES FOR API COMPATIBILITY
# =============================================================================

# Conversion table aliases
SLOT_TO_POINTS = SPELL_SLOT_POINT_COST
POINTS_TO_SLOT = POINT_TO_SLOT_COST

# Function alias
apply_metamagic = use_metamagic
