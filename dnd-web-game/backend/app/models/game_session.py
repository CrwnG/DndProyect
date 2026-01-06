"""
Game Session Models.

Tracks the state of an active campaign playthrough:
- Current encounter and phase
- Party characters and their state
- World state (flags, variables, time)
- Combat state when in combat
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime
import uuid

from .campaign import Campaign, WorldState, RestType


class SessionPhase(str, Enum):
    """Current phase of the game session."""
    MENU = "menu"                       # Campaign menu / lobby
    STORY_INTRO = "story_intro"         # Displaying encounter intro
    EXPLORATION = "exploration"         # Free exploration mode
    CHOICE = "choice"                   # Player making a choice (skill check)
    CHOICE_RESULT = "choice_result"     # Showing skill check result
    COMBAT_SETUP = "combat_setup"       # Pre-combat party positioning
    COMBAT = "combat"                   # Active combat
    COMBAT_RESOLUTION = "combat_resolution"  # Post-combat summary
    STORY_OUTCOME = "story_outcome"     # Displaying outcome narrative
    REST = "rest"                       # Short/long rest screen
    LEVEL_UP = "level_up"               # Level up screen
    GAME_OVER = "game_over"             # Defeat screen
    VICTORY = "victory"                 # Campaign complete


@dataclass
class PartyMember:
    """A character in the party."""
    id: str
    name: str

    # Multiclass support (D&D 5e 2024)
    # class_levels tracks levels per class: {"fighter": 5, "rogue": 3}
    class_levels: Dict[str, int] = field(default_factory=dict)
    primary_class: str = ""  # First class taken (determines starting proficiencies)

    # Legacy fields for backward compatibility
    character_class: str = ""  # Use get_primary_class() instead
    _level: int = 1  # Internal level storage for legacy support

    # Database link - for syncing progress back to Character table
    character_id: Optional[str] = None  # UUID of the Character in database

    # Individual gold (not party pool)
    gold: int = 0

    # Combat stats
    max_hp: int = 10
    current_hp: int = 10
    temp_hp: int = 0
    ac: int = 10
    speed: int = 30

    # Ability scores
    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10

    # Hit Dice System (D&D 5e) - legacy fields for single-class compatibility
    hit_die_size: int = 8  # d6=6, d8=8, d10=10, d12=12 (primary class die)
    hit_dice_total: int = 1  # Equal to total level
    hit_dice_remaining: int = 1  # For short rest healing

    # Multiclass hit dice pool (tracks dice per class)
    hit_dice_by_class: Dict[str, Dict[str, int]] = field(default_factory=dict)
    # Format: {"fighter": {"size": 10, "total": 5, "remaining": 3}, "rogue": {"size": 8, "total": 3, "remaining": 2}}

    # Spell slots
    spell_slots: Dict[int, int] = field(default_factory=dict)  # level: slots remaining
    spell_slots_max: Dict[int, int] = field(default_factory=dict)  # level: max slots

    # Warlock Pact Magic (tracked separately from other casters per D&D 5e multiclass rules)
    pact_magic_slots: int = 0
    pact_magic_slots_max: int = 0
    pact_magic_slot_level: int = 0

    # Class resources
    class_resources: Dict[str, int] = field(default_factory=dict)  # e.g. {"second_wind": 1}

    # Subclasses per class (multiclass support)
    subclasses: Dict[str, str] = field(default_factory=dict)  # {"fighter": "champion", "rogue": "thief"}

    # Legacy subclass field for backward compatibility
    subclass: Optional[str] = None

    # Experience
    xp: int = 0

    # Equipment reference (for combat)
    equipment_data: Optional[Dict[str, Any]] = None

    # Weapons list (for combat display)
    weapons: List[Dict[str, Any]] = field(default_factory=list)

    # Spellcasting data (spells known, cantrips, spell attack, spell save DC)
    spellcasting: Optional[Dict[str, Any]] = None

    # Conditions
    conditions: List[str] = field(default_factory=list)

    # Exhaustion (0-6, 6 = death)
    exhaustion_level: int = 0

    # Death Saving Throws
    death_save_successes: int = 0
    death_save_failures: int = 0
    is_stable: bool = False
    is_dead: bool = False

    # Is this character active (not unconscious/removed)
    is_active: bool = True

    # Wild Shape state (for Druids)
    # Format: {"is_active": bool, "form_id": str, "form_hp": int, "form_max_hp": int,
    #          "uses_remaining": int, "max_uses": int, "original_hp": int, "original_temp_hp": int}
    wild_shape_state: Optional[Dict[str, Any]] = None

    # =========================================================================
    # MULTICLASS HELPER PROPERTIES
    # =========================================================================

    @property
    def total_level(self) -> int:
        """Get total character level (sum of all class levels)."""
        if self.class_levels:
            return sum(self.class_levels.values())
        # Fallback for legacy single-class data
        return self._level

    @property
    def level(self) -> int:
        """Alias for total_level (backward compatibility)."""
        return self.total_level

    @property
    def is_multiclass(self) -> bool:
        """Check if character has levels in multiple classes."""
        return len(self.class_levels) > 1

    def get_class_level(self, class_name: str) -> int:
        """Get level in a specific class."""
        return self.class_levels.get(class_name.lower(), 0)

    def get_primary_class(self) -> str:
        """Get the character's primary (first) class."""
        if self.primary_class:
            return self.primary_class
        if self.class_levels:
            # If no primary set, return the class with highest level
            return max(self.class_levels, key=self.class_levels.get)
        # Fallback to legacy field
        return self.character_class or "fighter"

    def get_all_classes(self) -> Dict[str, int]:
        """Get all class levels."""
        if self.class_levels:
            return dict(self.class_levels)
        # Fallback for legacy single-class data
        if self.character_class:
            return {self.character_class.lower(): self.total_level}
        return {}

    def add_class_level(self, class_name: str) -> None:
        """Add a level to a class (used during level-up)."""
        class_name = class_name.lower()
        if class_name in self.class_levels:
            self.class_levels[class_name] += 1
        else:
            self.class_levels[class_name] = 1
            # Set primary class if this is the first class
            if not self.primary_class:
                self.primary_class = class_name

    def get_subclass(self, class_name: str) -> Optional[str]:
        """Get subclass for a specific class."""
        return self.subclasses.get(class_name.lower())

    def set_subclass(self, class_name: str, subclass_name: str) -> None:
        """Set subclass for a specific class."""
        self.subclasses[class_name.lower()] = subclass_name
        # Also update legacy field for backward compatibility
        if class_name.lower() == self.get_primary_class().lower():
            self.subclass = subclass_name

    def _migrate_legacy_data(self) -> None:
        """Migrate single-class data to multiclass format."""
        if not self.class_levels and self.character_class:
            # Migrate legacy single-class character
            char_class = self.character_class.lower()
            self.class_levels = {char_class: getattr(self, '_level', 1)}
            self.primary_class = char_class
            if self.subclass:
                self.subclasses = {char_class: self.subclass}

    def __post_init__(self):
        """Initialize multiclass data from legacy format if needed."""
        self._migrate_legacy_data()

    # =========================================================================
    # WILD SHAPE HELPER PROPERTIES & METHODS
    # =========================================================================

    @property
    def is_wild_shaped(self) -> bool:
        """Check if character is currently in Wild Shape form."""
        if self.wild_shape_state is None:
            return False
        return self.wild_shape_state.get("is_active", False)

    @property
    def wild_shape_form_hp(self) -> int:
        """Get current HP of Wild Shape form (0 if not transformed)."""
        if not self.is_wild_shaped:
            return 0
        return self.wild_shape_state.get("form_hp", 0)

    @property
    def wild_shape_form_max_hp(self) -> int:
        """Get max HP of Wild Shape form (0 if not transformed)."""
        if not self.is_wild_shaped:
            return 0
        return self.wild_shape_state.get("form_max_hp", 0)

    def get_wild_shape_form_id(self) -> Optional[str]:
        """Get the ID of the current Wild Shape form."""
        if not self.is_wild_shaped:
            return None
        return self.wild_shape_state.get("form_id")

    def init_wild_shape_state(self, druid_level: int) -> None:
        """Initialize Wild Shape state for a druid."""
        if self.wild_shape_state is None:
            max_uses = 2 if druid_level < 20 else 999  # Unlimited at 20
            self.wild_shape_state = {
                "is_active": False,
                "form_id": None,
                "form_hp": 0,
                "form_max_hp": 0,
                "uses_remaining": max_uses,
                "max_uses": max_uses,
                "original_hp": 0,
                "original_temp_hp": 0,
            }

    # =========================================================================
    # CORE METHODS
    # =========================================================================

    def heal(self, amount: int) -> int:
        """Heal the character, return actual amount healed."""
        actual = min(amount, self.max_hp - self.current_hp)
        self.current_hp += actual
        return actual

    def take_damage(self, amount: int, is_critical: bool = False) -> Dict[str, Any]:
        """
        Take damage, applying Wild Shape form HP and temp HP first.

        D&D 5e Wild Shape Damage Rules:
        - Damage reduces beast form HP first
        - If form HP drops to 0, excess damage carries over to druid HP
        - Character reverts to druid form when form HP reaches 0

        Args:
            amount: Damage amount
            is_critical: Whether this was a critical hit (2 death save failures if dying)

        Returns:
            Dict with damage info and state changes
        """
        result = {
            "damage_taken": 0,
            "temp_hp_absorbed": 0,
            "knocked_unconscious": False,
            "death_save_failure": False,
            "instant_death": False,
            # Wild Shape specific
            "wild_shape_damage": 0,
            "wild_shape_reverted": False,
            "overflow_damage": 0,
        }

        # Already dead
        if self.is_dead:
            return result

        # =====================================================================
        # WILD SHAPE DAMAGE HANDLING
        # =====================================================================
        if self.is_wild_shaped:
            form_hp = self.wild_shape_state.get("form_hp", 0)
            damage_to_form = min(amount, form_hp)

            # Apply damage to form
            self.wild_shape_state["form_hp"] = form_hp - damage_to_form
            result["wild_shape_damage"] = damage_to_form

            # Calculate overflow
            overflow = amount - damage_to_form

            # Check if form dropped to 0 HP
            if self.wild_shape_state["form_hp"] <= 0:
                result["wild_shape_reverted"] = True
                result["overflow_damage"] = overflow

                # Revert to druid form - restore original HP
                original_hp = self.wild_shape_state.get("original_hp", self.current_hp)
                original_temp_hp = self.wild_shape_state.get("original_temp_hp", 0)

                # Clear wild shape state
                self.wild_shape_state["is_active"] = False
                self.wild_shape_state["form_id"] = None
                self.wild_shape_state["form_hp"] = 0
                self.wild_shape_state["form_max_hp"] = 0

                # Restore druid's HP
                self.current_hp = original_hp
                self.temp_hp = original_temp_hp

                # If there's overflow damage, apply it to the druid
                if overflow > 0:
                    amount = overflow
                    # Continue to normal damage processing below
                else:
                    return result
            else:
                # Form absorbed all damage
                return result

        # =====================================================================
        # STANDARD DAMAGE HANDLING (or overflow from Wild Shape)
        # =====================================================================

        # Damage while at 0 HP (dying)
        if self.current_hp == 0 and not self.is_stable:
            failures = 2 if is_critical else 1
            self.death_save_failures += failures
            result["death_save_failure"] = True
            result["failures_added"] = failures

            if self.death_save_failures >= 3:
                self.is_dead = True
                self.is_active = False
                result["died"] = True

            return result

        # Absorb with temp HP first
        if self.temp_hp > 0:
            absorbed = min(self.temp_hp, amount)
            self.temp_hp -= absorbed
            amount -= absorbed
            result["temp_hp_absorbed"] = absorbed

        # Apply remaining damage
        old_hp = self.current_hp
        self.current_hp = max(0, self.current_hp - amount)
        result["damage_taken"] = old_hp - self.current_hp

        # Check for dropping to 0 HP
        if self.current_hp == 0 and old_hp > 0:
            # Check for instant death (damage remaining >= max HP)
            remaining_damage = amount - (old_hp - self.current_hp)
            if remaining_damage >= self.max_hp:
                self.is_dead = True
                self.is_active = False
                result["instant_death"] = True
                result["died"] = True
            else:
                # Start dying
                self.death_save_successes = 0
                self.death_save_failures = 0
                self.is_stable = False
                result["knocked_unconscious"] = True
                # Note: is_active stays True - unconscious but not removed

        return result

    def stabilize(self) -> bool:
        """
        Stabilize a dying character.

        Returns:
            True if successfully stabilized
        """
        if self.current_hp == 0 and not self.is_dead and not self.is_stable:
            self.is_stable = True
            self.death_save_successes = 0
            self.death_save_failures = 0
            return True
        return False

    def regain_consciousness(self, hp: int = 1) -> bool:
        """
        Regain consciousness from 0 HP.

        Args:
            hp: HP to set (default 1)

        Returns:
            True if successful
        """
        if self.current_hp == 0 and not self.is_dead:
            self.current_hp = min(hp, self.max_hp)
            self.death_save_successes = 0
            self.death_save_failures = 0
            self.is_stable = False
            return True
        return False

    def short_rest(self, hit_dice_to_spend: int = 0) -> Dict[str, Any]:
        """
        Apply short rest benefits (D&D 5e 2024).

        Args:
            hit_dice_to_spend: Number of hit dice to spend for healing

        Returns:
            Summary of what was restored
        """
        import random

        restored = {
            "hp_healed": 0,
            "hit_dice_spent": 0,
            "hit_dice_remaining": self.hit_dice_remaining,
            "hit_die_rolls": [],
            "abilities_restored": [],
            "spell_slots_restored": {},
        }

        # Calculate CON modifier
        con_mod = (self.constitution - 10) // 2

        # Spend hit dice for healing
        dice_to_spend = min(hit_dice_to_spend, self.hit_dice_remaining)

        for _ in range(dice_to_spend):
            if self.current_hp >= self.max_hp:
                break  # Already at full HP

            # Roll hit die
            roll = random.randint(1, self.hit_die_size)
            healing = max(1, roll + con_mod)  # Minimum 1 HP
            actual_heal = self.heal(healing)

            restored["hit_die_rolls"].append({
                "die_size": self.hit_die_size,
                "roll": roll,
                "con_mod": con_mod,
                "healing": actual_heal
            })

            restored["hp_healed"] += actual_heal
            self.hit_dice_remaining -= 1
            restored["hit_dice_spent"] += 1

        restored["hit_dice_remaining"] = self.hit_dice_remaining

        # Restore short rest abilities
        short_rest_abilities = ["second_wind", "action_surge"]
        for ability in short_rest_abilities:
            if ability in self.class_resources:
                self.class_resources[ability] = 1
                restored["abilities_restored"].append(ability)

        # Warlock Pact Magic - restore all spell slots on short rest
        if self.character_class.lower() == "warlock":
            from app.core.class_spellcasting import get_warlock_pact_slots
            try:
                pact_info = get_warlock_pact_slots(self.level)
                slot_level = pact_info["slot_level"]
                num_slots = pact_info["slots"]
                self.spell_slots[slot_level] = num_slots
                self.spell_slots_max[slot_level] = num_slots
                restored["spell_slots_restored"][slot_level] = num_slots
                restored["abilities_restored"].append("Pact Magic")
            except (ImportError, KeyError):
                pass  # Class spellcasting not available

        # Wizard Arcane Recovery (once per long rest, would need tracking)
        # This is handled separately via class feature usage

        return restored

    def long_rest(self) -> Dict[str, Any]:
        """
        Apply long rest benefits (D&D 5e 2024).

        Returns:
            Summary of what was restored
        """
        restored = {
            "hp_healed": self.max_hp - self.current_hp,
            "hit_dice_restored": 0,
            "spell_slots_restored": {},
            "abilities_restored": [],
            "exhaustion_reduced": False,
            "conditions_cleared": list(self.conditions),
        }

        # Full HP restoration
        self.current_hp = self.max_hp
        self.temp_hp = 0

        # Reset death saves
        self.death_save_successes = 0
        self.death_save_failures = 0
        self.is_stable = False

        # Restore half of max hit dice (minimum 1)
        self.hit_dice_total = self.level  # Ensure total matches level
        dice_to_restore = max(1, self.hit_dice_total // 2)
        dice_actually_restored = min(
            dice_to_restore,
            self.hit_dice_total - self.hit_dice_remaining
        )
        self.hit_dice_remaining = min(
            self.hit_dice_total,
            self.hit_dice_remaining + dice_to_restore
        )
        restored["hit_dice_restored"] = dice_actually_restored

        # Restore all spell slots based on class
        try:
            from app.core.class_spellcasting import get_spell_slots_for_level
            full_slots = get_spell_slots_for_level(
                self.character_class.lower(),
                self.level
            )
            if full_slots:
                for level, slots in full_slots.items():
                    old_slots = self.spell_slots.get(level, 0)
                    self.spell_slots[level] = slots
                    self.spell_slots_max[level] = slots
                    if slots > old_slots:
                        restored["spell_slots_restored"][level] = slots
        except (ImportError, KeyError):
            pass  # Class spellcasting not available

        # Restore all class resources
        for resource in self.class_resources:
            self.class_resources[resource] = 1  # Simplified - would need max values
            restored["abilities_restored"].append(resource)

        # Reduce exhaustion by 1 (with food and drink)
        if self.exhaustion_level > 0:
            self.exhaustion_level -= 1
            restored["exhaustion_reduced"] = True
            restored["new_exhaustion_level"] = self.exhaustion_level

        # Clear conditions (most conditions end on long rest)
        self.conditions = []

        return restored

    def get_effective_speed(self) -> int:
        """
        Get speed with exhaustion modifier applied.

        Returns:
            Effective movement speed in feet
        """
        if self.exhaustion_level >= 5:
            return 0  # Speed reduced to 0
        elif self.exhaustion_level >= 2:
            return self.speed // 2  # Speed halved
        return self.speed

    def get_effective_max_hp(self) -> int:
        """
        Get max HP with exhaustion modifier applied.

        Returns:
            Effective maximum HP
        """
        if self.exhaustion_level >= 4:
            return max(1, self.max_hp // 2)  # Max HP halved
        return self.max_hp

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            # Multiclass fields
            "class_levels": self.class_levels,
            "primary_class": self.primary_class or self.get_primary_class(),
            "subclasses": self.subclasses,
            "is_multiclass": self.is_multiclass,
            # Legacy fields for backward compatibility
            "character_class": self.character_class or self.get_primary_class(),
            "level": self.total_level,
            "subclass": self.subclass,
            # Database link
            "character_id": self.character_id,
            "gold": self.gold,
            # Combat stats
            "max_hp": self.max_hp,
            "current_hp": self.current_hp,
            "temp_hp": self.temp_hp,
            "ac": self.ac,
            "speed": self.speed,
            "effective_speed": self.get_effective_speed(),
            "effective_max_hp": self.get_effective_max_hp(),
            # Ability scores
            "strength": self.strength,
            "dexterity": self.dexterity,
            "constitution": self.constitution,
            "intelligence": self.intelligence,
            "wisdom": self.wisdom,
            "charisma": self.charisma,
            # Hit dice (legacy single-class format)
            "hit_die_size": self.hit_die_size,
            "hit_dice_total": self.hit_dice_total,
            "hit_dice_remaining": self.hit_dice_remaining,
            # Hit dice (multiclass format)
            "hit_dice_by_class": self.hit_dice_by_class,
            # Spell slots
            "spell_slots": self.spell_slots,
            "spell_slots_max": self.spell_slots_max,
            # Warlock Pact Magic (separate from other casters)
            "pact_magic_slots": self.pact_magic_slots,
            "pact_magic_slots_max": self.pact_magic_slots_max,
            "pact_magic_slot_level": self.pact_magic_slot_level,
            # Resources
            "class_resources": self.class_resources,
            "xp": self.xp,
            "equipment_data": self.equipment_data,
            "weapons": self.weapons,
            "spellcasting": self.spellcasting,
            "conditions": self.conditions,
            "exhaustion_level": self.exhaustion_level,
            "death_save_successes": self.death_save_successes,
            "death_save_failures": self.death_save_failures,
            "is_stable": self.is_stable,
            "is_dead": self.is_dead,
            "is_active": self.is_active,
            # Wild Shape state
            "wild_shape_state": self.wild_shape_state,
            "is_wild_shaped": self.is_wild_shaped,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PartyMember":
        # Handle multiclass vs legacy single-class data
        class_levels = data.get("class_levels", {})
        primary_class = data.get("primary_class", "")
        character_class = data.get("character_class", "Fighter")
        level = data.get("level", 1)

        # If no class_levels but we have character_class, this is legacy data
        if not class_levels and character_class:
            class_levels = {character_class.lower(): level}
            primary_class = character_class.lower()

        # Import hit die helper to get correct die size
        try:
            from app.core.hit_dice import get_hit_die_for_class
            # Use primary class for default die size
            primary = primary_class or character_class or "Fighter"
            default_die_size = get_hit_die_for_class(primary)
        except ImportError:
            default_die_size = 8

        # Handle subclasses (multiclass vs legacy)
        subclasses = data.get("subclasses", {})
        subclass = data.get("subclass")
        if subclass and not subclasses and primary_class:
            subclasses = {primary_class.lower(): subclass}

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", "Unknown"),
            # Multiclass fields
            class_levels=class_levels,
            primary_class=primary_class,
            subclasses=subclasses,
            # Legacy fields
            character_class=character_class,
            _level=level,  # Internal level storage
            subclass=subclass,
            # Database link
            character_id=data.get("character_id"),
            gold=data.get("gold", 0),
            # Combat stats
            max_hp=data.get("max_hp", 10),
            current_hp=data.get("current_hp", 10),
            temp_hp=data.get("temp_hp", 0),
            ac=data.get("ac", 10),
            speed=data.get("speed", 30),
            # Ability scores
            strength=data.get("strength", 10),
            dexterity=data.get("dexterity", 10),
            constitution=data.get("constitution", 10),
            intelligence=data.get("intelligence", 10),
            wisdom=data.get("wisdom", 10),
            charisma=data.get("charisma", 10),
            # Hit dice (legacy)
            hit_die_size=data.get("hit_die_size", default_die_size),
            hit_dice_total=data.get("hit_dice_total", level),
            hit_dice_remaining=data.get("hit_dice_remaining", level),
            # Hit dice (multiclass)
            hit_dice_by_class=data.get("hit_dice_by_class", {}),
            # Spell slots
            spell_slots=data.get("spell_slots", {}),
            spell_slots_max=data.get("spell_slots_max", {}),
            # Pact Magic
            pact_magic_slots=data.get("pact_magic_slots", 0),
            pact_magic_slots_max=data.get("pact_magic_slots_max", 0),
            pact_magic_slot_level=data.get("pact_magic_slot_level", 0),
            # Resources
            class_resources=data.get("class_resources", {}),
            xp=data.get("xp", 0),
            equipment_data=data.get("equipment_data"),
            weapons=data.get("weapons", []),
            spellcasting=data.get("spellcasting"),
            conditions=data.get("conditions", []),
            exhaustion_level=data.get("exhaustion_level", 0),
            death_save_successes=data.get("death_save_successes", 0),
            death_save_failures=data.get("death_save_failures", 0),
            is_stable=data.get("is_stable", False),
            is_dead=data.get("is_dead", False),
            is_active=data.get("is_active", True),
            # Wild Shape state
            wild_shape_state=data.get("wild_shape_state"),
        )


@dataclass
class GameSession:
    """An active campaign playthrough session."""
    id: str
    campaign_id: str
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    # Current state
    phase: SessionPhase = SessionPhase.MENU
    current_encounter_id: Optional[str] = None
    current_chapter_index: int = 0

    # Party
    party: List[PartyMember] = field(default_factory=list)
    party_gold: int = 0
    party_inventory: List[Dict[str, Any]] = field(default_factory=list)  # Shared party loot

    # World state
    world_state: WorldState = field(default_factory=WorldState)

    # Combat state (when in combat)
    combat_id: Optional[str] = None

    # Multiplayer
    host_player_id: Optional[str] = None
    connected_players: List[str] = field(default_factory=list)

    # Reference to loaded campaign (not serialized)
    _campaign: Optional[Campaign] = field(default=None, repr=False)

    def set_campaign(self, campaign: Campaign):
        """Set the campaign reference."""
        self._campaign = campaign
        self.campaign_id = campaign.id

    def get_current_encounter(self):
        """Get the current encounter object."""
        if self._campaign and self.current_encounter_id:
            return self._campaign.get_encounter(self.current_encounter_id)
        return None

    def advance_to_encounter(self, encounter_id: str):
        """Move to a new encounter."""
        self.current_encounter_id = encounter_id
        self.phase = SessionPhase.STORY_INTRO
        self.combat_id = None
        self.updated_at = datetime.utcnow().isoformat()

    def start_combat(self, combat_id: str):
        """Enter combat phase."""
        self.combat_id = combat_id
        self.phase = SessionPhase.COMBAT
        self.updated_at = datetime.utcnow().isoformat()

    def end_combat(self, victory: bool):
        """End combat and move to resolution."""
        self.combat_id = None
        self.phase = SessionPhase.COMBAT_RESOLUTION if victory else SessionPhase.GAME_OVER
        self.updated_at = datetime.utcnow().isoformat()

    def apply_rewards(self, xp: int, gold: int, items: List[str], flags: List[str]):
        """Apply encounter rewards to party."""
        # Distribute XP to active party members
        active_members = [p for p in self.party if p.is_active]
        if active_members:
            xp_per_member = xp // len(active_members)
            for member in active_members:
                member.xp += xp_per_member

        # Add gold
        self.party_gold += gold

        # Set story flags
        for flag in flags:
            self.world_state.set_flag(flag)

        # Add items to party inventory
        for item in items:
            if isinstance(item, str):
                # Simple item name string - create basic item entry
                item_entry = {
                    "id": str(uuid.uuid4()),
                    "name": item,
                    "type": "reward",
                    "quantity": 1,
                    "acquired_at": datetime.utcnow().isoformat(),
                }
            elif isinstance(item, dict):
                # Full item dict - add ID if missing
                item_entry = item.copy()
                if "id" not in item_entry:
                    item_entry["id"] = str(uuid.uuid4())
                item_entry["acquired_at"] = datetime.utcnow().isoformat()
            else:
                continue  # Skip invalid items

            self.party_inventory.append(item_entry)

        self.updated_at = datetime.utcnow().isoformat()

    def rest(self, rest_type: RestType) -> Dict[str, Any]:
        """Apply rest to all party members."""
        results = {"type": rest_type.value, "members": []}

        for member in self.party:
            if not member.is_active:
                continue

            if rest_type == RestType.SHORT:
                restored = member.short_rest()
                self.world_state.advance_time(1)  # 1 hour
            else:
                restored = member.long_rest()
                self.world_state.advance_time(8)  # 8 hours

            results["members"].append({
                "name": member.name,
                "restored": restored,
            })

        self.updated_at = datetime.utcnow().isoformat()
        return results

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "campaign_id": self.campaign_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "phase": self.phase.value,
            "current_encounter_id": self.current_encounter_id,
            "current_chapter_index": self.current_chapter_index,
            "party": [p.to_dict() for p in self.party],
            "party_gold": self.party_gold,
            "party_inventory": self.party_inventory,
            "world_state": self.world_state.to_dict(),
            "combat_id": self.combat_id,
            "host_player_id": self.host_player_id,
            "connected_players": self.connected_players,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GameSession":
        party = [PartyMember.from_dict(p) for p in data.get("party", [])]
        world_state = WorldState.from_dict(data.get("world_state", {}))

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            campaign_id=data.get("campaign_id", ""),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
            updated_at=data.get("updated_at", datetime.utcnow().isoformat()),
            phase=SessionPhase(data.get("phase", "menu")),
            current_encounter_id=data.get("current_encounter_id"),
            current_chapter_index=data.get("current_chapter_index", 0),
            party=party,
            party_gold=data.get("party_gold", 0),
            party_inventory=data.get("party_inventory", []),
            world_state=world_state,
            combat_id=data.get("combat_id"),
            host_player_id=data.get("host_player_id"),
            connected_players=data.get("connected_players", []),
        )

    @classmethod
    def create_new(cls, campaign: Campaign, party: List[PartyMember] = None) -> "GameSession":
        """Create a new game session for a campaign."""
        session = cls(
            id=str(uuid.uuid4()),
            campaign_id=campaign.id,
            current_encounter_id=campaign.starting_encounter,
            party=party or [],
            party_gold=campaign.starting_gold,
        )
        session.set_campaign(campaign)
        return session


@dataclass
class SaveGame:
    """A saved game snapshot."""
    id: str
    session_id: str
    slot_number: int
    name: str
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    # Full session state snapshot
    session_data: Dict[str, Any] = field(default_factory=dict)

    # Optional combat state if saved during combat
    combat_data: Optional[Dict[str, Any]] = None

    # Preview info for save menu
    campaign_name: str = ""
    encounter_name: str = ""
    party_summary: str = ""  # e.g., "Level 3 Fighter, Level 2 Wizard"
    playtime_minutes: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "slot_number": self.slot_number,
            "name": self.name,
            "created_at": self.created_at,
            "session_data": self.session_data,
            "combat_data": self.combat_data,
            "campaign_name": self.campaign_name,
            "encounter_name": self.encounter_name,
            "party_summary": self.party_summary,
            "playtime_minutes": self.playtime_minutes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SaveGame":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            session_id=data.get("session_id", ""),
            slot_number=data.get("slot_number", 0),
            name=data.get("name", "Save"),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
            session_data=data.get("session_data", {}),
            combat_data=data.get("combat_data"),
            campaign_name=data.get("campaign_name", ""),
            encounter_name=data.get("encounter_name", ""),
            party_summary=data.get("party_summary", ""),
            playtime_minutes=data.get("playtime_minutes", 0),
        )

    @classmethod
    def create_from_session(
        cls,
        session: GameSession,
        slot: int,
        name: str,
        campaign_name: str = "",
        encounter_name: str = "",
    ) -> "SaveGame":
        """Create a save from current session state."""
        # Build party summary
        party_parts = []
        for member in session.party[:3]:  # Show first 3
            party_parts.append(f"Lv{member.level} {member.character_class}")
        if len(session.party) > 3:
            party_parts.append(f"+{len(session.party) - 3} more")

        return cls(
            id=str(uuid.uuid4()),
            session_id=session.id,
            slot_number=slot,
            name=name,
            session_data=session.to_dict(),
            campaign_name=campaign_name,
            encounter_name=encounter_name,
            party_summary=", ".join(party_parts),
        )
