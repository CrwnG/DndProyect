"""
D&D 5e 2024 Spell System - Data Models.

Defines Pydantic models for spells, spellcasting, and spell casting requests/results.
"""
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class SpellSchool(str, Enum):
    """The eight schools of magic."""
    ABJURATION = "abjuration"
    CONJURATION = "conjuration"
    DIVINATION = "divination"
    ENCHANTMENT = "enchantment"
    EVOCATION = "evocation"
    ILLUSION = "illusion"
    NECROMANCY = "necromancy"
    TRANSMUTATION = "transmutation"


class DamageType(str, Enum):
    """Damage types in D&D 5e."""
    ACID = "acid"
    BLUDGEONING = "bludgeoning"
    COLD = "cold"
    FIRE = "fire"
    FORCE = "force"
    LIGHTNING = "lightning"
    NECROTIC = "necrotic"
    PIERCING = "piercing"
    POISON = "poison"
    PSYCHIC = "psychic"
    RADIANT = "radiant"
    SLASHING = "slashing"
    THUNDER = "thunder"


class SpellTargetType(str, Enum):
    """Types of spell targeting."""
    SELF = "self"
    TOUCH = "touch"
    SINGLE = "single"
    MULTIPLE = "multiple"
    AREA_SPHERE = "sphere"
    AREA_CONE = "cone"
    AREA_LINE = "line"
    AREA_CUBE = "cube"
    AREA_CYLINDER = "cylinder"
    POINT = "point"


class SpellEffectType(str, Enum):
    """Primary effect type of a spell."""
    DAMAGE = "damage"
    HEALING = "healing"
    BUFF = "buff"
    DEBUFF = "debuff"
    CONTROL = "control"
    UTILITY = "utility"
    SUMMONING = "summoning"


class CastingTimeType(str, Enum):
    """Types of casting times."""
    ACTION = "action"
    BONUS_ACTION = "bonus_action"
    REACTION = "reaction"
    MINUTE = "minute"
    HOUR = "hour"
    RITUAL = "ritual"


class SpellcastingType(str, Enum):
    """How a class handles spellcasting."""
    PREPARED = "prepared"      # Wizard, Cleric, Druid, Paladin - prepare from list
    KNOWN = "known"            # Bard, Sorcerer, Ranger - fixed known spells
    PACT_MAGIC = "pact_magic"  # Warlock - special slot recovery


class SpellComponents(BaseModel):
    """Spell component requirements."""
    verbal: bool = False
    somatic: bool = False
    material: Optional[str] = None  # Material component description if needed


class Spell(BaseModel):
    """A D&D 5e spell definition."""
    id: str
    name: str
    level: int = Field(ge=0, le=9)  # 0 for cantrips
    school: str  # SpellSchool value
    casting_time: str
    range: str
    components: SpellComponents
    duration: str
    concentration: bool = False
    ritual: bool = False
    description: str
    higher_levels: Optional[str] = None
    classes: List[str] = []

    # Combat-relevant parsed data (populated during loading)
    target_type: Optional[SpellTargetType] = None
    effect_type: Optional[SpellEffectType] = None
    damage_dice: Optional[str] = None
    damage_type: Optional[str] = None
    healing_dice: Optional[str] = None
    save_type: Optional[str] = None  # "dexterity", "wisdom", etc.
    attack_type: Optional[str] = None  # "melee_spell", "ranged_spell"
    area_size: Optional[int] = None
    max_targets: Optional[int] = None
    conditions_applied: List[str] = []
    combat_usable: bool = True  # Whether this spell can be used in combat (default True)
    trigger: Optional[str] = None  # "on_hit" for spells cast after hitting (Divine Smite, Ensnaring Strike)
    notes_2024: Optional[str] = None  # Notes about 2024 PHB changes

    class Config:
        use_enum_values = True


class CharacterSpellcasting(BaseModel):
    """A character's spellcasting capability and state."""
    # Spellcasting basics
    ability: str  # "intelligence", "wisdom", "charisma"
    spell_save_dc: int = 10
    spell_attack_bonus: int = 0
    spellcasting_type: SpellcastingType = SpellcastingType.PREPARED

    # Spell slots
    spell_slots_max: Dict[int, int] = {}  # {1: 4, 2: 3, ...} max slots per level
    spell_slots_used: Dict[int, int] = {}  # {1: 0, 2: 0, ...} used slots per level

    # Warlock Pact Magic (separate pool)
    pact_slots_max: int = 0
    pact_slot_level: int = 0
    pact_slots_used: int = 0

    # Spells
    cantrips_known: List[str] = []  # List of cantrip IDs
    spells_known: List[str] = []    # For known casters (Bard, Sorcerer, etc.)
    spellbook: List[str] = []       # For Wizards
    prepared_spells: List[str] = [] # Currently prepared spell IDs
    max_prepared: int = 0           # How many can be prepared

    # Concentration tracking
    concentrating_on: Optional[str] = None  # Spell ID if concentrating
    concentration_start_round: Optional[int] = None

    def get_available_slots(self, level: int) -> int:
        """Get remaining spell slots for a level."""
        max_slots = self.spell_slots_max.get(level, 0)
        used_slots = self.spell_slots_used.get(level, 0)
        return max(0, max_slots - used_slots)

    def has_slot(self, level: int) -> bool:
        """Check if character has an available slot at given level."""
        if level == 0:
            return True  # Cantrips don't use slots
        return self.get_available_slots(level) > 0

    def use_slot(self, level: int) -> bool:
        """Use a spell slot. Returns True if successful."""
        if level == 0:
            return True  # Cantrips don't use slots
        if not self.has_slot(level):
            return False
        self.spell_slots_used[level] = self.spell_slots_used.get(level, 0) + 1
        return True

    def restore_all_slots(self):
        """Restore all spell slots (long rest)."""
        self.spell_slots_used = {k: 0 for k in self.spell_slots_max.keys()}
        self.pact_slots_used = 0

    def restore_pact_slots(self):
        """Restore pact magic slots (short rest for Warlock)."""
        self.pact_slots_used = 0

    class Config:
        use_enum_values = True


class CastSpellRequest(BaseModel):
    """Request to cast a spell in combat."""
    caster_id: str
    spell_id: str
    slot_level: Optional[int] = None  # None for cantrips
    target_ids: List[str] = []        # Target combatant IDs
    target_point: Optional[Dict[str, int]] = None  # {x, y} for area spells


class SpellTargetInfo(BaseModel):
    """Information about a valid spell target."""
    id: str
    name: str
    distance: int
    is_ally: bool
    is_self: bool = False


class SpellCastResult(BaseModel):
    """Result of casting a spell."""
    success: bool
    spell_id: str
    spell_name: str
    slot_used: Optional[int] = None
    caster_id: str
    caster_name: str

    # Attack spells
    attack_roll: Optional[int] = None
    attack_total: Optional[int] = None
    hit: Optional[bool] = None
    critical: Optional[bool] = None

    # Save spells
    save_dc: Optional[int] = None
    save_type: Optional[str] = None
    save_results: Optional[Dict[str, Dict[str, Any]]] = None  # {target_id: {roll, total, saved}}

    # Effects
    damage_dealt: Optional[Dict[str, int]] = None    # {target_id: damage}
    damage_type: Optional[str] = None
    damage_dice: Optional[str] = None                # "1d8" - for damage animation
    damage_rolls: Optional[List[int]] = None         # [4] - individual die results
    healing_done: Optional[Dict[str, int]] = None    # {target_id: healing}
    conditions_applied: Optional[Dict[str, List[str]]] = None  # {target_id: [conditions]}

    # Concentration
    concentration_started: bool = False
    concentration_ended: Optional[str] = None  # Previous spell that ended

    # Description for combat log
    description: str = ""

    # Additional effect data for special mechanics (metamagic, buffs, etc.)
    extra_data: Optional[Dict[str, Any]] = None
    buff_effects: Optional[Dict[str, Any]] = None


class PrepareSpellsRequest(BaseModel):
    """Request to prepare spells for the day."""
    spell_ids: List[str]


class SpellListFilter(BaseModel):
    """Filters for spell list queries."""
    level: Optional[int] = None
    school: Optional[str] = None
    class_name: Optional[str] = None
    ritual: Optional[bool] = None
    concentration: Optional[bool] = None
    search: Optional[str] = None


class SpellListResponse(BaseModel):
    """Response containing a list of spells."""
    spells: List[Spell]
    total: int
    filtered: int


class CharacterSpellsResponse(BaseModel):
    """Response containing character's spell information."""
    spellcasting: CharacterSpellcasting
    cantrips: List[Spell] = []
    prepared_spells: List[Spell] = []
    available_spells: List[Spell] = []  # Spells that can currently be cast
