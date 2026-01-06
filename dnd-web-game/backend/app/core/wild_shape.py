"""
Druid Wild Shape System for D&D 5e 2024

Comprehensive Wild Shape implementation:
- Beast form transformations with CR limits by level
- Temporary HP from beast form
- Retained and replaced statistics
- Circle-specific form improvements (Moon, Land, etc.)
- Combat while Wild Shaped
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum


class DruidCircle(str, Enum):
    """Druid subclass circles."""
    LAND = "land"
    MOON = "moon"
    DREAMS = "dreams"
    SHEPHERD = "shepherd"
    SPORES = "spores"
    STARS = "stars"
    WILDFIRE = "wildfire"
    SEA = "sea"  # D&D 5e 2024


class LandType(str, Enum):
    """Terrain types for Circle of the Land."""
    ARCTIC = "arctic"
    COAST = "coast"
    DESERT = "desert"
    FOREST = "forest"
    GRASSLAND = "grassland"
    MOUNTAIN = "mountain"
    SWAMP = "swamp"
    UNDERDARK = "underdark"


class StarryFormType(str, Enum):
    """Starry Form constellations for Circle of the Stars."""
    ARCHER = "archer"      # Ranged spell attack bonus action
    CHALICE = "chalice"    # Healing bonus when casting healing spell
    DRAGON = "dragon"      # Minimum roll on concentration checks


# =============================================================================
# CIRCLE OF THE LAND - Circle Spells by Terrain
# =============================================================================

LAND_CIRCLE_SPELLS: Dict[LandType, Dict[int, List[str]]] = {
    LandType.ARCTIC: {
        3: ["hold_person", "spike_growth"],
        5: ["sleet_storm", "slow"],
        7: ["freedom_of_movement", "ice_storm"],
        9: ["commune_with_nature", "cone_of_cold"],
    },
    LandType.COAST: {
        3: ["mirror_image", "misty_step"],
        5: ["water_breathing", "water_walk"],
        7: ["control_water", "freedom_of_movement"],
        9: ["conjure_elemental", "scrying"],
    },
    LandType.DESERT: {
        3: ["blur", "silence"],
        5: ["create_food_and_water", "protection_from_energy"],
        7: ["blight", "hallucinatory_terrain"],
        9: ["insect_plague", "wall_of_stone"],
    },
    LandType.FOREST: {
        3: ["barkskin", "spider_climb"],
        5: ["call_lightning", "plant_growth"],
        7: ["divination", "freedom_of_movement"],
        9: ["commune_with_nature", "tree_stride"],
    },
    LandType.GRASSLAND: {
        3: ["invisibility", "pass_without_trace"],
        5: ["daylight", "haste"],
        7: ["divination", "freedom_of_movement"],
        9: ["dream", "insect_plague"],
    },
    LandType.MOUNTAIN: {
        3: ["spider_climb", "spike_growth"],
        5: ["lightning_bolt", "meld_into_stone"],
        7: ["stone_shape", "stoneskin"],
        9: ["passwall", "wall_of_stone"],
    },
    LandType.SWAMP: {
        3: ["darkness", "melfs_acid_arrow"],
        5: ["water_walk", "stinking_cloud"],
        7: ["freedom_of_movement", "locate_creature"],
        9: ["insect_plague", "scrying"],
    },
    LandType.UNDERDARK: {
        3: ["spider_climb", "web"],
        5: ["gaseous_form", "stinking_cloud"],
        7: ["greater_invisibility", "stone_shape"],
        9: ["cloudkill", "insect_plague"],
    },
}


# =============================================================================
# CIRCLE STATE DATACLASSES
# =============================================================================

@dataclass
class CircleLandState:
    """State tracking for Circle of the Land features."""
    land_type: Optional[LandType] = None
    natural_recovery_used: bool = False  # Resets on long rest

    def to_dict(self) -> Dict[str, Any]:
        return {
            "land_type": self.land_type.value if self.land_type else None,
            "natural_recovery_used": self.natural_recovery_used,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "CircleLandState":
        land_type = None
        if data.get("land_type"):
            land_type = LandType(data["land_type"])
        return cls(
            land_type=land_type,
            natural_recovery_used=data.get("natural_recovery_used", False),
        )


@dataclass
class CircleSeaState:
    """State tracking for Circle of the Sea features."""
    wrath_of_sea_active: bool = False
    wrath_of_sea_uses: int = 0
    max_wrath_uses: int = 0  # Equals WIS modifier (min 1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "wrath_of_sea_active": self.wrath_of_sea_active,
            "wrath_of_sea_uses": self.wrath_of_sea_uses,
            "max_wrath_uses": self.max_wrath_uses,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "CircleSeaState":
        return cls(
            wrath_of_sea_active=data.get("wrath_of_sea_active", False),
            wrath_of_sea_uses=data.get("wrath_of_sea_uses", 0),
            max_wrath_uses=data.get("max_wrath_uses", 0),
        )


@dataclass
class StarryFormState:
    """State tracking for Circle of the Stars Starry Form."""
    is_active: bool = False
    constellation: Optional[StarryFormType] = None
    uses_remaining: int = 2  # Uses equal to proficiency bonus
    max_uses: int = 2
    active_until_round: Optional[int] = None  # Duration: 10 minutes
    free_guiding_bolt_used: bool = False  # One free use per long rest at level 2

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_active": self.is_active,
            "constellation": self.constellation.value if self.constellation else None,
            "uses_remaining": self.uses_remaining,
            "max_uses": self.max_uses,
            "active_until_round": self.active_until_round,
            "free_guiding_bolt_used": self.free_guiding_bolt_used,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "StarryFormState":
        constellation = None
        if data.get("constellation"):
            constellation = StarryFormType(data["constellation"])
        return cls(
            is_active=data.get("is_active", False),
            constellation=constellation,
            uses_remaining=data.get("uses_remaining", 2),
            max_uses=data.get("max_uses", 2),
            active_until_round=data.get("active_until_round"),
            free_guiding_bolt_used=data.get("free_guiding_bolt_used", False),
        )


@dataclass
class BeastAttack:
    """A beast form's attack option."""
    name: str
    attack_bonus: int
    damage_dice: str
    damage_type: str
    reach: int = 5  # feet
    properties: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "attack_bonus": self.attack_bonus,
            "damage_dice": self.damage_dice,
            "damage_type": self.damage_type,
            "reach": self.reach,
            "properties": self.properties,
        }


@dataclass
class BeastForm:
    """A beast form available for Wild Shape."""
    id: str
    name: str
    cr: float  # Challenge Rating (0, 1/8, 1/4, 1/2, 1, 2, etc.)
    hp: int
    ac: int
    speed: int
    swim_speed: int = 0
    fly_speed: int = 0
    climb_speed: int = 0
    burrow_speed: int = 0

    # Ability scores (used for attacks, saves, skills)
    strength: int = 10
    dexterity: int = 10
    constitution: int = 10

    # Attacks
    attacks: List[BeastAttack] = field(default_factory=list)
    multiattack: bool = False
    multiattack_description: str = ""

    # Special abilities
    special_abilities: List[str] = field(default_factory=list)
    senses: List[str] = field(default_factory=list)  # darkvision, blindsight, etc.

    # Size
    size: str = "medium"

    # Requirements
    requires_swim: bool = False
    requires_fly: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "cr": self.cr,
            "hp": self.hp,
            "ac": self.ac,
            "speed": self.speed,
            "swim_speed": self.swim_speed,
            "fly_speed": self.fly_speed,
            "climb_speed": self.climb_speed,
            "strength": self.strength,
            "dexterity": self.dexterity,
            "constitution": self.constitution,
            "attacks": [a.to_dict() for a in self.attacks],
            "multiattack": self.multiattack,
            "special_abilities": self.special_abilities,
            "senses": self.senses,
            "size": self.size,
        }


# =============================================================================
# BEAST FORM DEFINITIONS
# =============================================================================

BEAST_FORMS: Dict[str, BeastForm] = {
    # CR 0
    "cat": BeastForm(
        id="cat",
        name="Cat",
        cr=0,
        hp=2,
        ac=12,
        speed=40,
        climb_speed=30,
        strength=3,
        dexterity=15,
        constitution=10,
        size="tiny",
        attacks=[
            BeastAttack("Claws", 0, "1", "slashing"),
        ],
        senses=["darkvision 30 ft."],
        special_abilities=["Keen Smell"],
    ),
    "rat": BeastForm(
        id="rat",
        name="Rat",
        cr=0,
        hp=1,
        ac=10,
        speed=20,
        strength=2,
        dexterity=11,
        constitution=9,
        size="tiny",
        attacks=[
            BeastAttack("Bite", 0, "1", "piercing"),
        ],
        senses=["darkvision 30 ft."],
        special_abilities=["Keen Smell"],
    ),

    # CR 1/8
    "giant_rat": BeastForm(
        id="giant_rat",
        name="Giant Rat",
        cr=0.125,
        hp=7,
        ac=12,
        speed=30,
        strength=7,
        dexterity=15,
        constitution=11,
        size="small",
        attacks=[
            BeastAttack("Bite", 4, "1d4+2", "piercing"),
        ],
        senses=["darkvision 60 ft."],
        special_abilities=["Keen Smell", "Pack Tactics"],
    ),
    "poisonous_snake": BeastForm(
        id="poisonous_snake",
        name="Poisonous Snake",
        cr=0.125,
        hp=2,
        ac=13,
        speed=30,
        swim_speed=30,
        strength=2,
        dexterity=16,
        constitution=11,
        size="tiny",
        attacks=[
            BeastAttack("Bite", 5, "1+3d4 poison", "piercing"),  # 3d4 on failed DC 10 CON save
        ],
        senses=["blindsight 10 ft."],
    ),

    # CR 1/4
    "wolf": BeastForm(
        id="wolf",
        name="Wolf",
        cr=0.25,
        hp=11,
        ac=13,
        speed=40,
        strength=12,
        dexterity=15,
        constitution=12,
        size="medium",
        attacks=[
            BeastAttack("Bite", 4, "2d4+2", "piercing"),  # Knocks prone on hit DC 11 STR
        ],
        senses=["darkvision 60 ft."],
        special_abilities=["Keen Hearing and Smell", "Pack Tactics"],
    ),
    "giant_frog": BeastForm(
        id="giant_frog",
        name="Giant Frog",
        cr=0.25,
        hp=18,
        ac=11,
        speed=30,
        swim_speed=30,
        strength=12,
        dexterity=13,
        constitution=11,
        size="medium",
        requires_swim=True,
        attacks=[
            BeastAttack("Bite", 3, "1d6+1", "piercing"),  # Grapple on hit
        ],
        special_abilities=["Amphibious", "Standing Leap"],
    ),
    "giant_badger": BeastForm(
        id="giant_badger",
        name="Giant Badger",
        cr=0.25,
        hp=13,
        ac=10,
        speed=30,
        burrow_speed=10,
        strength=13,
        dexterity=10,
        constitution=15,
        size="medium",
        attacks=[
            BeastAttack("Bite", 3, "1d6+1", "piercing"),
            BeastAttack("Claws", 3, "2d4+1", "slashing"),
        ],
        multiattack=True,
        multiattack_description="The badger makes two attacks: one bite and one claws.",
        senses=["darkvision 30 ft."],
        special_abilities=["Keen Smell"],
    ),

    # CR 1/2
    "ape": BeastForm(
        id="ape",
        name="Ape",
        cr=0.5,
        hp=19,
        ac=12,
        speed=30,
        climb_speed=30,
        strength=16,
        dexterity=14,
        constitution=14,
        size="medium",
        attacks=[
            BeastAttack("Fist", 5, "1d6+3", "bludgeoning"),
            BeastAttack("Rock", 5, "1d6+3", "bludgeoning"),  # Range 25/50
        ],
        multiattack=True,
        multiattack_description="The ape makes two fist attacks.",
    ),
    "black_bear": BeastForm(
        id="black_bear",
        name="Black Bear",
        cr=0.5,
        hp=19,
        ac=11,
        speed=40,
        climb_speed=30,
        strength=15,
        dexterity=10,
        constitution=14,
        size="medium",
        attacks=[
            BeastAttack("Bite", 4, "1d6+2", "piercing"),
            BeastAttack("Claws", 4, "2d4+2", "slashing"),
        ],
        multiattack=True,
        multiattack_description="The bear makes two attacks: one bite and one claws.",
        senses=["darkvision 60 ft."],
        special_abilities=["Keen Smell"],
    ),
    "crocodile": BeastForm(
        id="crocodile",
        name="Crocodile",
        cr=0.5,
        hp=19,
        ac=12,
        speed=20,
        swim_speed=30,
        strength=15,
        dexterity=10,
        constitution=13,
        size="large",
        requires_swim=True,
        attacks=[
            BeastAttack("Bite", 4, "1d10+2", "piercing"),  # Grapple on hit
        ],
        special_abilities=["Hold Breath"],
    ),
    "giant_goat": BeastForm(
        id="giant_goat",
        name="Giant Goat",
        cr=0.5,
        hp=19,
        ac=11,
        speed=40,
        strength=17,
        dexterity=11,
        constitution=12,
        size="large",
        attacks=[
            BeastAttack("Ram", 5, "2d4+3", "bludgeoning"),  # Charge for extra damage
        ],
        special_abilities=["Charge", "Sure-Footed"],
    ),

    # CR 1
    "brown_bear": BeastForm(
        id="brown_bear",
        name="Brown Bear",
        cr=1,
        hp=34,
        ac=11,
        speed=40,
        climb_speed=30,
        strength=19,
        dexterity=10,
        constitution=16,
        size="large",
        attacks=[
            BeastAttack("Bite", 6, "1d8+4", "piercing"),
            BeastAttack("Claws", 6, "2d6+4", "slashing"),
        ],
        multiattack=True,
        multiattack_description="The bear makes two attacks: one bite and one claws.",
        senses=["darkvision 60 ft."],
        special_abilities=["Keen Smell"],
    ),
    "dire_wolf": BeastForm(
        id="dire_wolf",
        name="Dire Wolf",
        cr=1,
        hp=37,
        ac=14,
        speed=50,
        strength=17,
        dexterity=15,
        constitution=15,
        size="large",
        attacks=[
            BeastAttack("Bite", 5, "2d6+3", "piercing"),  # Knocks prone DC 13
        ],
        senses=["darkvision 60 ft."],
        special_abilities=["Keen Hearing and Smell", "Pack Tactics"],
    ),
    "giant_spider": BeastForm(
        id="giant_spider",
        name="Giant Spider",
        cr=1,
        hp=26,
        ac=14,
        speed=30,
        climb_speed=30,
        strength=14,
        dexterity=16,
        constitution=12,
        size="large",
        attacks=[
            BeastAttack("Bite", 5, "1d8+3+2d8 poison", "piercing"),  # DC 11 CON poison
            BeastAttack("Web", 5, "0", "none"),  # Restrained, DC 12 to escape
        ],
        senses=["blindsight 10 ft.", "darkvision 60 ft."],
        special_abilities=["Spider Climb", "Web Sense", "Web Walker"],
    ),
    "giant_eagle": BeastForm(
        id="giant_eagle",
        name="Giant Eagle",
        cr=1,
        hp=26,
        ac=13,
        speed=10,
        fly_speed=80,
        strength=16,
        dexterity=17,
        constitution=13,
        size="large",
        requires_fly=True,
        attacks=[
            BeastAttack("Beak", 5, "1d6+3", "piercing"),
            BeastAttack("Talons", 5, "2d6+3", "slashing"),
        ],
        multiattack=True,
        multiattack_description="The eagle makes two attacks: one beak and one talons.",
        senses=["darkvision 60 ft."],
        special_abilities=["Keen Sight"],
    ),

    # CR 2 (Moon Druid forms)
    "giant_constrictor_snake": BeastForm(
        id="giant_constrictor_snake",
        name="Giant Constrictor Snake",
        cr=2,
        hp=60,
        ac=12,
        speed=30,
        swim_speed=30,
        strength=19,
        dexterity=14,
        constitution=12,
        size="huge",
        requires_swim=True,
        attacks=[
            BeastAttack("Bite", 6, "2d6+4", "piercing"),
            BeastAttack("Constrict", 6, "2d8+4", "bludgeoning"),  # Grapple & restrain
        ],
        senses=["blindsight 10 ft."],
    ),
    "polar_bear": BeastForm(
        id="polar_bear",
        name="Polar Bear",
        cr=2,
        hp=42,
        ac=12,
        speed=40,
        swim_speed=30,
        strength=20,
        dexterity=10,
        constitution=16,
        size="large",
        attacks=[
            BeastAttack("Bite", 7, "1d8+5", "piercing"),
            BeastAttack("Claws", 7, "2d6+5", "slashing"),
        ],
        multiattack=True,
        multiattack_description="The bear makes two attacks: one bite and one claws.",
        senses=["darkvision 60 ft."],
        special_abilities=["Keen Smell"],
    ),
    "giant_elk": BeastForm(
        id="giant_elk",
        name="Giant Elk",
        cr=2,
        hp=42,
        ac=14,
        speed=60,
        strength=19,
        dexterity=16,
        constitution=14,
        size="huge",
        attacks=[
            BeastAttack("Ram", 6, "2d6+4", "bludgeoning"),  # Charge for knockdown
            BeastAttack("Hooves", 6, "4d8+4", "bludgeoning"),  # Only vs prone
        ],
        special_abilities=["Charge"],
    ),
}


@dataclass
class WildShapeState:
    """Tracks active Wild Shape state for a druid."""
    is_active: bool = False
    form_id: Optional[str] = None
    form_hp: int = 0
    form_max_hp: int = 0
    uses_remaining: int = 2  # Per short/long rest
    max_uses: int = 2

    # Original druid stats (to restore when reverting)
    original_hp: int = 0
    original_temp_hp: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_active": self.is_active,
            "form_id": self.form_id,
            "form_hp": self.form_hp,
            "form_max_hp": self.form_max_hp,
            "uses_remaining": self.uses_remaining,
            "max_uses": self.max_uses,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "WildShapeState":
        return cls(
            is_active=data.get("is_active", False),
            form_id=data.get("form_id"),
            form_hp=data.get("form_hp", 0),
            form_max_hp=data.get("form_max_hp", 0),
            uses_remaining=data.get("uses_remaining", 2),
            max_uses=data.get("max_uses", 2),
            original_hp=data.get("original_hp", 0),
            original_temp_hp=data.get("original_temp_hp", 0),
        )


def get_max_cr_for_level(level: int, circle: Optional[DruidCircle] = None) -> float:
    """
    Get the maximum CR beast form available at a druid level.

    Standard progression:
    - Level 2: CR 1/4, no flying or swimming
    - Level 4: CR 1/2, swimming allowed
    - Level 8: CR 1, flying allowed

    Moon Druid progression:
    - Level 2: CR 1
    - Level 6: CR equal to level / 3 (rounded down)
    """
    if circle == DruidCircle.MOON:
        if level >= 6:
            return level // 3
        elif level >= 2:
            return 1
    else:
        if level >= 8:
            return 1
        elif level >= 4:
            return 0.5
        elif level >= 2:
            return 0.25

    return 0


def can_use_swim_forms(level: int) -> bool:
    """Check if druid can use forms with swim speed."""
    return level >= 4


def can_use_fly_forms(level: int) -> bool:
    """Check if druid can use forms with fly speed."""
    return level >= 8


def get_wild_shape_uses(level: int) -> int:
    """Get number of Wild Shape uses per rest."""
    if level >= 20:
        return 999  # Unlimited at level 20
    return 2


def get_available_forms(
    level: int,
    circle: Optional[DruidCircle] = None
) -> List[BeastForm]:
    """
    Get all beast forms available to a druid at their level.

    Args:
        level: Druid level
        circle: Druid circle subclass (affects CR limits)

    Returns:
        List of available BeastForm objects
    """
    max_cr = get_max_cr_for_level(level, circle)
    can_swim = can_use_swim_forms(level)
    can_fly = can_use_fly_forms(level)

    available = []
    for form in BEAST_FORMS.values():
        # Check CR limit
        if form.cr > max_cr:
            continue

        # Check movement restrictions
        if form.requires_swim and not can_swim:
            continue
        if form.requires_fly and not can_fly:
            continue

        available.append(form)

    # Sort by CR, then by name
    available.sort(key=lambda f: (f.cr, f.name))
    return available


def transform(
    state: WildShapeState,
    form_id: str,
    druid_hp: int,
    druid_temp_hp: int = 0
) -> Tuple[bool, str, Optional[BeastForm]]:
    """
    Transform into a beast form.

    Args:
        state: Current Wild Shape state
        form_id: ID of the beast form to take
        druid_hp: Current HP before transforming
        druid_temp_hp: Current temp HP before transforming

    Returns:
        Tuple of (success, message, beast_form)
    """
    if state.is_active:
        return False, "Already in Wild Shape form", None

    if state.uses_remaining <= 0:
        return False, "No Wild Shape uses remaining", None

    form = BEAST_FORMS.get(form_id)
    if not form:
        return False, f"Unknown beast form: {form_id}", None

    # Store original stats
    state.original_hp = druid_hp
    state.original_temp_hp = druid_temp_hp

    # Transform
    state.is_active = True
    state.form_id = form_id
    state.form_hp = form.hp
    state.form_max_hp = form.hp
    state.uses_remaining -= 1

    return True, f"Transformed into {form.name}!", form


def take_damage_in_form(
    state: WildShapeState,
    damage: int
) -> Tuple[int, bool, int]:
    """
    Handle taking damage while in Wild Shape form.

    D&D Rules:
    - Damage reduces form HP first
    - Excess damage carries over to druid HP
    - Dropping to 0 in form reverts to druid form

    Args:
        state: Current Wild Shape state
        damage: Damage to take

    Returns:
        Tuple of (damage_to_form, reverted, overflow_damage)
    """
    if not state.is_active:
        return 0, False, damage

    damage_to_form = min(damage, state.form_hp)
    state.form_hp -= damage_to_form

    overflow = damage - damage_to_form
    reverted = False

    if state.form_hp <= 0:
        state.form_hp = 0
        reverted = True
        revert(state)

    return damage_to_form, reverted, overflow


def revert(state: WildShapeState) -> Tuple[int, int]:
    """
    Revert from beast form to druid form.

    Returns:
        Tuple of (original_hp, original_temp_hp)
    """
    original_hp = state.original_hp
    original_temp_hp = state.original_temp_hp

    state.is_active = False
    state.form_id = None
    state.form_hp = 0
    state.form_max_hp = 0
    state.original_hp = 0
    state.original_temp_hp = 0

    return original_hp, original_temp_hp


def heal_form(state: WildShapeState, amount: int) -> int:
    """
    Heal the current beast form.

    Args:
        state: Current Wild Shape state
        amount: Amount to heal

    Returns:
        Actual amount healed
    """
    if not state.is_active:
        return 0

    old_hp = state.form_hp
    state.form_hp = min(state.form_hp + amount, state.form_max_hp)
    return state.form_hp - old_hp


def rest_restore_uses(state: WildShapeState, is_long_rest: bool = False) -> None:
    """Restore Wild Shape uses on rest."""
    # Both short and long rest restore all uses
    state.uses_remaining = state.max_uses


def get_form_stats(form_id: str) -> Optional[Dict[str, Any]]:
    """Get full stats for a beast form."""
    form = BEAST_FORMS.get(form_id)
    if not form:
        return None
    return form.to_dict()


def get_combat_actions(state: WildShapeState) -> List[Dict[str, Any]]:
    """Get available combat actions while in Wild Shape."""
    if not state.is_active or not state.form_id:
        return []

    form = BEAST_FORMS.get(state.form_id)
    if not form:
        return []

    actions = []

    # Add attacks
    for attack in form.attacks:
        actions.append({
            "type": "attack",
            "name": attack.name,
            "attack_bonus": attack.attack_bonus,
            "damage": attack.damage_dice,
            "damage_type": attack.damage_type,
            "reach": attack.reach,
        })

    # Note multiattack
    if form.multiattack:
        actions.append({
            "type": "multiattack",
            "name": "Multiattack",
            "description": form.multiattack_description,
        })

    return actions


# =============================================================================
# CIRCLE OF THE MOON SPECIFIC
# =============================================================================

def get_moon_druid_cr_at_level(level: int) -> float:
    """Get max CR for Moon Druid at a given level."""
    if level >= 18:
        return 6
    elif level >= 15:
        return 5
    elif level >= 12:
        return 4
    elif level >= 9:
        return 3
    elif level >= 6:
        return level // 3
    elif level >= 2:
        return 1
    return 0


def can_wild_shape_as_bonus_action(circle: Optional[DruidCircle]) -> bool:
    """Moon Druids can Wild Shape as a bonus action."""
    return circle == DruidCircle.MOON


def get_moon_druid_temp_hp(druid_level: int) -> int:
    """
    Get temporary HP gained when Moon Druid transforms.

    D&D 5e 2024 Rule: Moon Druids gain temp HP equal to 3 × druid level
    when they transform using Combat Wild Shape.

    Args:
        druid_level: Level in the Druid class

    Returns:
        Temporary HP to add
    """
    return 3 * druid_level


def get_moon_druid_form_ac(wisdom_modifier: int) -> int:
    """
    Get the AC override for Moon Druid Wild Shape forms.

    D&D 5e 2024 Rule: When a Circle of the Moon druid is in Wild Shape,
    their AC can be 13 + WIS modifier if that's higher than the beast's AC.

    Args:
        wisdom_modifier: Druid's Wisdom modifier

    Returns:
        Moon Druid AC floor
    """
    return 13 + wisdom_modifier


def get_effective_wild_shape_ac(
    form: BeastForm,
    circle: Optional[DruidCircle],
    wisdom_modifier: int = 0
) -> int:
    """
    Get effective AC for a Wild Shape form, accounting for Moon Druid.

    Args:
        form: The beast form
        circle: Druid circle (Moon gets AC override)
        wisdom_modifier: Druid's Wisdom modifier

    Returns:
        Effective AC to use
    """
    base_ac = form.ac

    if circle == DruidCircle.MOON:
        moon_ac = get_moon_druid_form_ac(wisdom_modifier)
        return max(base_ac, moon_ac)

    return base_ac


# =============================================================================
# PARTY MEMBER INTEGRATION
# =============================================================================

def transform_party_member(
    member: Any,  # PartyMember type to avoid circular import
    form_id: str,
    druid_level: int,
    circle: Optional[DruidCircle] = None,
    wisdom_modifier: int = 0
) -> Tuple[bool, str, Optional[BeastForm]]:
    """
    Transform a PartyMember into a Wild Shape form.

    Args:
        member: PartyMember to transform
        form_id: ID of the beast form to take
        druid_level: Druid class level
        circle: Druid circle subclass
        wisdom_modifier: Druid's Wisdom modifier (for Moon Druid AC)

    Returns:
        Tuple of (success, message, beast_form)
    """
    form = BEAST_FORMS.get(form_id)
    if not form:
        return False, f"Unknown beast form: {form_id}", None

    # Check CR restriction
    max_cr = get_max_cr_for_level(druid_level, circle)
    if form.cr > max_cr:
        return False, f"CR {form.cr} exceeds maximum CR {max_cr} at level {druid_level}", None

    # Check movement restrictions
    if form.requires_swim and not can_use_swim_forms(druid_level):
        return False, "Swimming forms require druid level 4+", None
    if form.requires_fly and not can_use_fly_forms(druid_level):
        return False, "Flying forms require druid level 8+", None

    # Initialize wild shape state if needed
    if member.wild_shape_state is None:
        member.init_wild_shape_state(druid_level)

    # Check uses remaining
    if member.wild_shape_state.get("uses_remaining", 0) <= 0:
        return False, "No Wild Shape uses remaining", None

    # Check if already transformed
    if member.wild_shape_state.get("is_active", False):
        return False, "Already in Wild Shape form", None

    # Store original druid stats
    member.wild_shape_state["original_hp"] = member.current_hp
    member.wild_shape_state["original_temp_hp"] = member.temp_hp

    # Calculate form HP (Moon Druids get temp HP bonus)
    form_hp = form.hp
    temp_hp_bonus = 0
    if circle == DruidCircle.MOON:
        temp_hp_bonus = get_moon_druid_temp_hp(druid_level)

    # Calculate effective AC (Moon Druids get AC override)
    effective_ac = get_effective_wild_shape_ac(form, circle, wisdom_modifier)

    # Transform
    member.wild_shape_state["is_active"] = True
    member.wild_shape_state["form_id"] = form_id
    member.wild_shape_state["form_hp"] = form_hp + temp_hp_bonus
    member.wild_shape_state["form_max_hp"] = form_hp + temp_hp_bonus
    member.wild_shape_state["form_base_hp"] = form_hp  # Track base HP without bonus
    member.wild_shape_state["form_temp_hp_bonus"] = temp_hp_bonus
    member.wild_shape_state["form_ac"] = effective_ac
    member.wild_shape_state["circle"] = circle.value if circle else None
    member.wild_shape_state["uses_remaining"] -= 1

    bonus_msg = ""
    if temp_hp_bonus > 0:
        bonus_msg = f" (+{temp_hp_bonus} temp HP from Combat Wild Shape)"

    return True, f"Transformed into {form.name}!{bonus_msg}", form


def revert_party_member(member: Any) -> Tuple[bool, str]:
    """
    Revert a PartyMember from Wild Shape form.

    Args:
        member: PartyMember to revert

    Returns:
        Tuple of (success, message)
    """
    if member.wild_shape_state is None:
        return False, "No Wild Shape state", None

    if not member.wild_shape_state.get("is_active", False):
        return False, "Not currently in Wild Shape form", None

    # Restore original HP
    original_hp = member.wild_shape_state.get("original_hp", member.current_hp)
    original_temp_hp = member.wild_shape_state.get("original_temp_hp", 0)

    member.current_hp = original_hp
    member.temp_hp = original_temp_hp

    # Clear form state
    member.wild_shape_state["is_active"] = False
    member.wild_shape_state["form_id"] = None
    member.wild_shape_state["form_hp"] = 0
    member.wild_shape_state["form_max_hp"] = 0
    member.wild_shape_state["original_hp"] = 0
    member.wild_shape_state["original_temp_hp"] = 0

    return True, "Reverted from Wild Shape form"


def get_wild_shape_combat_stats(member: Any) -> Optional[Dict[str, Any]]:
    """
    Get combat stats for a Wild Shaped party member.

    Args:
        member: PartyMember in Wild Shape form

    Returns:
        Dict with form stats for combat, or None if not transformed
    """
    if not member.is_wild_shaped:
        return None

    form_id = member.wild_shape_state.get("form_id")
    if not form_id:
        return None

    form = BEAST_FORMS.get(form_id)
    if not form:
        return None

    # Use stored AC (may include Moon Druid override)
    effective_ac = member.wild_shape_state.get("form_ac", form.ac)

    return {
        "form_id": form_id,
        "form_name": form.name,
        "current_hp": member.wild_shape_state.get("form_hp", 0),
        "max_hp": member.wild_shape_state.get("form_max_hp", form.hp),
        "base_hp": member.wild_shape_state.get("form_base_hp", form.hp),
        "temp_hp_bonus": member.wild_shape_state.get("form_temp_hp_bonus", 0),
        "ac": effective_ac,
        "base_ac": form.ac,
        "speed": form.speed,
        "swim_speed": form.swim_speed,
        "fly_speed": form.fly_speed,
        "climb_speed": form.climb_speed,
        "strength": form.strength,
        "dexterity": form.dexterity,
        "constitution": form.constitution,
        "attacks": [a.to_dict() for a in form.attacks],
        "multiattack": form.multiattack,
        "multiattack_description": form.multiattack_description,
        "special_abilities": form.special_abilities,
        "senses": form.senses,
        "size": form.size,
        "circle": member.wild_shape_state.get("circle"),
    }


def heal_wild_shape_form(member: Any, amount: int) -> int:
    """
    Heal a Wild Shaped party member's form.

    Args:
        member: PartyMember in Wild Shape form
        amount: Healing amount

    Returns:
        Actual amount healed
    """
    if not member.is_wild_shaped:
        return 0

    form_hp = member.wild_shape_state.get("form_hp", 0)
    form_max_hp = member.wild_shape_state.get("form_max_hp", 0)

    old_hp = form_hp
    new_hp = min(form_hp + amount, form_max_hp)
    member.wild_shape_state["form_hp"] = new_hp

    return new_hp - old_hp


# =============================================================================
# CIRCLE OF THE MOON - Full Implementation
# =============================================================================

def get_moon_lunar_form_bonuses(druid_level: int) -> Dict[str, Any]:
    """
    Get lunar form bonuses for Circle of the Moon druids.

    D&D 5e 2024: At level 10+, Moon Druids gain Moonlight Step (teleport)
    and at level 14+, Lunar Form grants additional benefits.

    Args:
        druid_level: Level in the Druid class

    Returns:
        Dict of lunar bonuses
    """
    bonuses = {
        "temp_hp_on_transform": 3 * druid_level,  # Combat Wild Shape
        "ac_formula": "13 + WIS",
        "bonus_action_transform": True,
    }

    # Level 10: Moonlight Step
    if druid_level >= 10:
        bonuses["moonlight_step"] = True
        bonuses["moonlight_step_distance"] = 30  # feet

    # Level 14: Lunar Form
    if druid_level >= 14:
        bonuses["lunar_form_resistance"] = ["bludgeoning", "piercing", "slashing"]
        bonuses["lunar_radiance_damage"] = "2d10"  # radiant damage on hit

    return bonuses


def can_cast_beast_spells(druid_level: int) -> bool:
    """
    Check if druid can cast spells while in Wild Shape.

    D&D 5e Rule: At level 18, druids can cast spells while in beast form.

    Args:
        druid_level: Level in the Druid class

    Returns:
        True if Beast Spells is available
    """
    return druid_level >= 18


def is_archdruid(druid_level: int) -> bool:
    """
    Check if druid has Archdruid feature.

    D&D 5e Rule: At level 20, Wild Shape uses become unlimited.

    Args:
        druid_level: Level in the Druid class

    Returns:
        True if Archdruid is available
    """
    return druid_level >= 20


# =============================================================================
# CIRCLE OF THE LAND - Natural Recovery & Circle Spells
# =============================================================================

def initialize_land_circle_state(land_type: LandType) -> CircleLandState:
    """
    Initialize Circle of the Land state.

    Args:
        land_type: The chosen terrain type

    Returns:
        New CircleLandState
    """
    return CircleLandState(land_type=land_type, natural_recovery_used=False)


def get_land_circle_spells(land_type: LandType, druid_level: int) -> List[str]:
    """
    Get Circle Spells for a Circle of the Land druid.

    Args:
        land_type: The druid's chosen terrain
        druid_level: Level in the Druid class

    Returns:
        List of always-prepared spell IDs
    """
    terrain_spells = LAND_CIRCLE_SPELLS.get(land_type, {})
    spells = []

    for level, spell_list in terrain_spells.items():
        if druid_level >= level:
            spells.extend(spell_list)

    return spells


def use_natural_recovery(
    state: CircleLandState,
    druid_level: int,
    spell_slots_to_recover: List[Tuple[int, int]]  # [(level, count), ...]
) -> Tuple[bool, str, int]:
    """
    Use Natural Recovery to regain spell slots during short rest.

    D&D 5e Rule: Once per long rest, during a short rest, you can recover
    spell slots with a combined level equal to or less than half your druid
    level (rounded up).

    Args:
        state: CircleLandState
        druid_level: Level in the Druid class
        spell_slots_to_recover: List of (slot_level, count) to recover

    Returns:
        Tuple of (success, message, total_levels_recovered)
    """
    if state.natural_recovery_used:
        return False, "Natural Recovery already used since last long rest", 0

    max_recovery = (druid_level + 1) // 2  # Round up

    # Calculate total levels requested
    total_levels = sum(level * count for level, count in spell_slots_to_recover)

    if total_levels > max_recovery:
        return False, f"Cannot recover {total_levels} levels (max: {max_recovery})", 0

    # Check no slots above 5th level
    for level, count in spell_slots_to_recover:
        if level > 5:
            return False, "Cannot recover spell slots above 5th level", 0
        if level < 1:
            return False, "Invalid spell slot level", 0

    state.natural_recovery_used = True
    return True, f"Recovered {total_levels} levels of spell slots", total_levels


def restore_natural_recovery(state: CircleLandState) -> None:
    """Reset Natural Recovery on long rest."""
    state.natural_recovery_used = False


def get_land_circle_features(druid_level: int) -> Dict[str, Any]:
    """
    Get Circle of the Land features available at a level.

    Args:
        druid_level: Level in the Druid class

    Returns:
        Dict of feature flags
    """
    features = {
        "circle_spells": druid_level >= 2,
        "natural_recovery": druid_level >= 2,
    }

    # Level 6: Land's Stride
    if druid_level >= 6:
        features["lands_stride"] = True
        features["ignore_difficult_terrain"] = True
        features["advantage_vs_plant_restraint"] = True

    # Level 10: Nature's Ward
    if druid_level >= 10:
        features["natures_ward"] = True
        features["immune_to_poison"] = True
        features["immune_to_disease"] = True
        features["immune_to_charm_fey_elemental"] = True

    # Level 14: Nature's Sanctuary
    if druid_level >= 14:
        features["natures_sanctuary"] = True
        features["beast_plant_wis_save_to_attack"] = True

    return features


# =============================================================================
# CIRCLE OF THE SEA - Wrath of the Sea
# =============================================================================

def initialize_sea_circle_state(wisdom_modifier: int) -> CircleSeaState:
    """
    Initialize Circle of the Sea state.

    Args:
        wisdom_modifier: Druid's Wisdom modifier

    Returns:
        New CircleSeaState
    """
    max_uses = max(1, wisdom_modifier)
    return CircleSeaState(
        wrath_of_sea_active=False,
        wrath_of_sea_uses=max_uses,
        max_wrath_uses=max_uses,
    )


def activate_wrath_of_sea(
    state: CircleSeaState,
    current_round: int
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Activate Wrath of the Sea aura.

    D&D 5e 2024: As a bonus action, you create an aura that lasts for 10 rounds.
    Hostile creatures that end turn within 10 feet take cold damage.

    Args:
        state: CircleSeaState
        current_round: Current combat round

    Returns:
        Tuple of (success, message, effect_data)
    """
    if state.wrath_of_sea_active:
        return False, "Wrath of the Sea is already active", {}

    if state.wrath_of_sea_uses <= 0:
        return False, "No uses of Wrath of the Sea remaining", {}

    state.wrath_of_sea_active = True
    state.wrath_of_sea_uses -= 1

    return True, "Wrath of the Sea activated!", {
        "aura_radius": 10,
        "damage_type": "cold",
        "uses_remaining": state.wrath_of_sea_uses,
    }


def deactivate_wrath_of_sea(state: CircleSeaState) -> bool:
    """Deactivate Wrath of the Sea."""
    if not state.wrath_of_sea_active:
        return False
    state.wrath_of_sea_active = False
    return True


def get_wrath_of_sea_damage(druid_level: int) -> str:
    """
    Get Wrath of the Sea damage dice.

    Scales with druid level.
    """
    if druid_level >= 17:
        return "4d6"
    elif druid_level >= 11:
        return "3d6"
    elif druid_level >= 5:
        return "2d6"
    return "1d6"


def restore_wrath_of_sea(state: CircleSeaState, wisdom_modifier: int) -> int:
    """
    Restore Wrath of the Sea uses on long rest.

    Args:
        state: CircleSeaState
        wisdom_modifier: Druid's Wisdom modifier

    Returns:
        Number of uses restored
    """
    max_uses = max(1, wisdom_modifier)
    state.max_wrath_uses = max_uses
    restored = max_uses - state.wrath_of_sea_uses
    state.wrath_of_sea_uses = max_uses
    state.wrath_of_sea_active = False
    return restored


def get_sea_circle_features(druid_level: int) -> Dict[str, Any]:
    """
    Get Circle of the Sea features available at a level.

    Args:
        druid_level: Level in the Druid class

    Returns:
        Dict of feature flags
    """
    features = {
        "wrath_of_the_sea": druid_level >= 2,
        "aquatic_affinity": druid_level >= 2,
        "swim_speed": True,  # Equals walking speed
    }

    # Level 6: Aquatic Affinity
    if druid_level >= 6:
        features["water_breathing"] = True
        features["underwater_spellcasting"] = True
        features["ignore_underwater_disadvantage"] = True

    # Level 10: Stormborn
    if druid_level >= 10:
        features["stormborn"] = True
        features["fly_speed_outdoor"] = 60
        features["resistance_lightning"] = True
        features["resistance_thunder"] = True

    # Level 14: Oceanic Gift
    if druid_level >= 14:
        features["oceanic_gift"] = True
        features["wrath_of_sea_bonus_action_teleport"] = 30  # feet

    return features


# =============================================================================
# CIRCLE OF THE STARS - Starry Form
# =============================================================================

def get_proficiency_bonus(level: int) -> int:
    """Get proficiency bonus for a character level."""
    return (level - 1) // 4 + 2


def initialize_starry_form_state(druid_level: int) -> StarryFormState:
    """
    Initialize Circle of the Stars Starry Form state.

    Args:
        druid_level: Level in the Druid class

    Returns:
        New StarryFormState
    """
    max_uses = get_proficiency_bonus(druid_level)
    return StarryFormState(
        is_active=False,
        constellation=None,
        uses_remaining=max_uses,
        max_uses=max_uses,
        free_guiding_bolt_used=False,
    )


def activate_starry_form(
    state: StarryFormState,
    constellation: StarryFormType,
    current_round: int
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Activate Starry Form with a chosen constellation.

    D&D 5e Rule: As a bonus action, you assume a starry form for 10 minutes.
    Choose Archer, Chalice, or Dragon constellation.

    Args:
        state: StarryFormState
        constellation: Which constellation to manifest
        current_round: Current combat round

    Returns:
        Tuple of (success, message, effect_data)
    """
    if state.is_active:
        return False, "Starry Form is already active", {}

    if state.uses_remaining <= 0:
        return False, "No uses of Starry Form remaining", {}

    state.is_active = True
    state.constellation = constellation
    state.uses_remaining -= 1
    state.active_until_round = current_round + 100  # ~10 minutes

    effects = get_starry_form_effects(constellation)

    return True, f"Entered Starry Form ({constellation.value})!", effects


def get_starry_form_effects(constellation: StarryFormType) -> Dict[str, Any]:
    """
    Get the effects of a Starry Form constellation.

    Args:
        constellation: The active constellation

    Returns:
        Dict of effects
    """
    if constellation == StarryFormType.ARCHER:
        return {
            "constellation": "archer",
            "bonus_action_attack": True,
            "attack_type": "ranged_spell",
            "range": 60,
            "damage": "1d8+WIS radiant",
            "description": "Bonus action: Make a ranged spell attack (60ft) for 1d8+WIS radiant damage",
        }
    elif constellation == StarryFormType.CHALICE:
        return {
            "constellation": "chalice",
            "healing_bonus": True,
            "bonus_healing": "1d8+WIS",
            "heal_self_or_other": True,
            "description": "When you cast a healing spell, you or another creature within 30ft regains 1d8+WIS HP",
        }
    elif constellation == StarryFormType.DRAGON:
        return {
            "constellation": "dragon",
            "concentration_minimum": 10,
            "fly_speed_hover": 20,  # At level 10+
            "description": "Treat rolls below 10 as 10 for concentration saves. Level 10+: 20ft fly (hover)",
        }
    return {}


def change_starry_constellation(
    state: StarryFormState,
    new_constellation: StarryFormType,
    druid_level: int
) -> Tuple[bool, str]:
    """
    Change constellation while in Starry Form (requires level 10+).

    Args:
        state: StarryFormState
        new_constellation: New constellation to assume
        druid_level: Level in the Druid class

    Returns:
        Tuple of (success, message)
    """
    if not state.is_active:
        return False, "Not in Starry Form"

    if druid_level < 10:
        return False, "Changing constellations requires druid level 10+"

    if state.constellation == new_constellation:
        return False, f"Already in {new_constellation.value} constellation"

    state.constellation = new_constellation
    return True, f"Changed to {new_constellation.value} constellation"


def check_starry_form_expiration(state: StarryFormState, current_round: int) -> bool:
    """
    Check if Starry Form has expired.

    Args:
        state: StarryFormState
        current_round: Current combat round

    Returns:
        True if just expired
    """
    if not state.is_active:
        return False

    if state.active_until_round and current_round >= state.active_until_round:
        deactivate_starry_form(state)
        return True

    return False


def deactivate_starry_form(state: StarryFormState) -> bool:
    """Deactivate Starry Form."""
    if not state.is_active:
        return False

    state.is_active = False
    state.constellation = None
    state.active_until_round = None
    return True


def restore_starry_form(state: StarryFormState, druid_level: int) -> int:
    """
    Restore Starry Form uses on long rest.

    Args:
        state: StarryFormState
        druid_level: Level in the Druid class

    Returns:
        Number of uses restored
    """
    max_uses = get_proficiency_bonus(druid_level)
    state.max_uses = max_uses
    restored = max_uses - state.uses_remaining
    state.uses_remaining = max_uses
    state.is_active = False
    state.constellation = None
    state.active_until_round = None
    state.free_guiding_bolt_used = False
    return restored


def get_stars_circle_features(druid_level: int) -> Dict[str, Any]:
    """
    Get Circle of the Stars features available at a level.

    Args:
        druid_level: Level in the Druid class

    Returns:
        Dict of feature flags
    """
    features = {
        "star_map": druid_level >= 2,
        "free_guiding_bolt": druid_level >= 2,  # Once per long rest
        "starry_form": druid_level >= 2,
    }

    # Level 6: Cosmic Omen
    if druid_level >= 6:
        features["cosmic_omen"] = True
        features["cosmic_omen_reaction"] = True
        features["weal_or_woe_bonus"] = "1d6"  # Add/subtract from roll

    # Level 10: Twinkling Constellations
    if druid_level >= 10:
        features["twinkling_constellations"] = True
        features["change_constellation"] = True
        features["dragon_fly_speed"] = 20

    # Level 14: Full of Stars
    if druid_level >= 14:
        features["full_of_stars"] = True
        features["starry_form_resistance"] = ["bludgeoning", "piercing", "slashing"]

    return features


# =============================================================================
# CIRCLE UTILITY FUNCTIONS
# =============================================================================

def get_druid_circle_features(
    circle: DruidCircle,
    druid_level: int
) -> Dict[str, Any]:
    """
    Get all features for a druid circle at a given level.

    Args:
        circle: The druid's circle subclass
        druid_level: Level in the Druid class

    Returns:
        Dict of all circle features
    """
    if circle == DruidCircle.MOON:
        return get_moon_lunar_form_bonuses(druid_level)
    elif circle == DruidCircle.LAND:
        return get_land_circle_features(druid_level)
    elif circle == DruidCircle.SEA:
        return get_sea_circle_features(druid_level)
    elif circle == DruidCircle.STARS:
        return get_stars_circle_features(druid_level)
    else:
        return {}


def get_circle_always_prepared_spells(
    circle: DruidCircle,
    druid_level: int,
    land_type: Optional[LandType] = None
) -> List[str]:
    """
    Get always-prepared spells granted by a druid circle.

    Args:
        circle: The druid's circle subclass
        druid_level: Level in the Druid class
        land_type: For Circle of the Land, the chosen terrain

    Returns:
        List of always-prepared spell IDs
    """
    spells = []

    if circle == DruidCircle.LAND and land_type:
        spells = get_land_circle_spells(land_type, druid_level)
    elif circle == DruidCircle.STARS:
        if druid_level >= 2:
            spells.append("guiding_bolt")

    return spells
