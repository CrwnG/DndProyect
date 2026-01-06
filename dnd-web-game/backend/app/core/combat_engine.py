"""
Combat Engine.

Core state machine for managing combat encounters.
Handles combat phases, actions, and turn resolution.
"""
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Dict, Any, Callable
from pathlib import Path
import json
import uuid
import random

from app.core.initiative import (
    InitiativeTracker,
    Combatant,
    CombatantType,
    create_initiative_tracker,
)
from app.core.dice import roll_d20, roll_damage
from app.core.rules_engine import (
    resolve_attack,
    apply_damage,
    calculate_ac,
    AttackResult,
)
from app.core.condition_effects import (
    get_attack_modifiers,
    get_effective_speed as get_condition_speed,
    is_incapacitated,
    get_save_modifiers,
    get_condition_summary,
)
from app.core.movement import (
    get_elevation_attack_modifier,
    get_cover_between,
    CombatGrid,
    check_opportunity_attack_triggers,
)
from app.core.ammunition import (
    AmmunitionTracker,
    check_ammunition_for_attack,
    consume_ammunition_for_attack,
)
from app.core.subclass_registry import (
    get_subclass_registry,
    get_critical_range,
    get_combat_modifiers,
)


# Weapon data cache
_weapon_cache: Dict[str, Dict[str, Any]] = {}


def load_weapon_data(weapon_id: str) -> Optional[Dict[str, Any]]:
    """
    Load weapon data from weapons.json.

    Args:
        weapon_id: ID of the weapon (e.g., 'longsword', 'longbow')

    Returns:
        Weapon data dict or None if not found
    """
    global _weapon_cache

    # Check cache first
    if weapon_id in _weapon_cache:
        return _weapon_cache[weapon_id]

    # Load weapons file if cache is empty
    if not _weapon_cache:
        weapons_path = Path(__file__).parent.parent / "data" / "weapons" / "weapons.json"
        try:
            with open(weapons_path) as f:
                data = json.load(f)
            # Index all weapons by ID
            for category in data.get("weapons", {}).values():
                for weapon in category:
                    _weapon_cache[weapon["id"]] = weapon
        except Exception as e:
            print(f"[CombatEngine] Failed to load weapons.json: {e}")
            return None

    return _weapon_cache.get(weapon_id)


class CombatPhase(Enum):
    """Current phase of combat."""
    NOT_IN_COMBAT = auto()
    ROLLING_INITIATIVE = auto()
    COMBAT_ACTIVE = auto()
    COMBAT_ENDED = auto()


class TurnPhase(Enum):
    """Phase within a combatant's turn."""
    START_OF_TURN = auto()
    MOVEMENT = auto()
    ACTION = auto()
    BONUS_ACTION = auto()
    END_OF_TURN = auto()


class ActionType(Enum):
    """Types of actions a combatant can take."""
    ATTACK = "attack"
    CAST_SPELL = "cast_spell"
    DASH = "dash"
    DISENGAGE = "disengage"
    DODGE = "dodge"
    HELP = "help"
    HIDE = "hide"
    READY = "ready"
    USE_OBJECT = "use_object"
    CLASS_FEATURE = "class_feature"
    GRAPPLE = "grapple"  # Special attack - contested Athletics
    SHOVE = "shove"  # Special attack - shove prone or push away
    ESCAPE_GRAPPLE = "escape_grapple"  # Action to escape a grapple
    MONSTER_ABILITY = "monster_ability"  # Monster special abilities (breath weapon, etc.)
    MULTIATTACK = "multiattack"  # Monster multiattack pattern


class BonusActionType(Enum):
    """Types of bonus actions."""
    OFFHAND_ATTACK = "offhand_attack"
    CUNNING_ACTION = "cunning_action"
    SECOND_WIND = "second_wind"
    CAST_BONUS_SPELL = "cast_bonus_spell"
    CLASS_FEATURE = "class_feature"
    RAGE = "rage"  # Barbarian rage activation
    MARTIAL_ARTS = "martial_arts"  # Monk unarmed strike
    FLURRY_OF_BLOWS = "flurry_of_blows"  # Monk: 2 unarmed strikes (costs 1 ki)
    PATIENT_DEFENSE = "patient_defense"  # Monk: Dodge as bonus action (costs 1 ki)
    STEP_OF_THE_WIND = "step_of_the_wind"  # Monk: Dash/Disengage as bonus (costs 1 ki)
    SPIRITUAL_WEAPON = "spiritual_weapon"  # Cleric: attack with spiritual weapon
    ACTIVATE_ITEM = "activate_item"  # Activate a magic item


@dataclass
class ActionResult:
    """Result of taking an action in combat."""
    success: bool
    action_type: str
    description: str
    damage_dealt: int = 0
    target_id: Optional[str] = None
    effects_applied: List[str] = field(default_factory=list)
    extra_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TurnState:
    """Tracks what a combatant has done on their turn."""
    combatant_id: str
    movement_used: int = 0
    action_taken: bool = False
    bonus_action_taken: bool = False
    reaction_used: bool = False
    free_object_interaction_used: bool = False
    current_phase: TurnPhase = TurnPhase.START_OF_TURN

    # Extra Attack tracking (D&D 5e)
    attacks_made: int = 0
    max_attacks: int = 1

    # Two-Weapon Fighting tracking (D&D 5e)
    can_offhand_attack: bool = False
    main_hand_weapon: Optional[str] = None

    # Class feature tracking (D&D 5e)
    sneak_attack_used: bool = False      # Rogue: once per turn
    reckless_attack_active: bool = False  # Barbarian: advantage but enemies have advantage too
    action_surge_used: bool = False       # Fighter: can use once per turn

    def reset(self) -> None:
        """Reset turn state for a new turn."""
        self.movement_used = 0
        self.action_taken = False
        self.bonus_action_taken = False
        self.free_object_interaction_used = False
        self.current_phase = TurnPhase.START_OF_TURN
        self.attacks_made = 0
        self.can_offhand_attack = False
        self.main_hand_weapon = None
        self.sneak_attack_used = False
        self.reckless_attack_active = False
        self.action_surge_used = False
        # Note: reaction_used resets at START of turn, not end
        # Note: max_attacks is set at turn start based on class features

    def can_take_action(self) -> bool:
        """Check if combatant can still take an action."""
        return not self.action_taken

    def can_attack(self) -> bool:
        """Check if combatant can make another attack (Extra Attack)."""
        return self.attacks_made < self.max_attacks

    def use_attack(self) -> int:
        """
        Use one attack. Returns remaining attacks.

        D&D 5e Rule: Action is only 'taken' when all attacks are used.
        """
        self.attacks_made += 1
        remaining = self.max_attacks - self.attacks_made
        if remaining <= 0:
            self.action_taken = True
        return remaining

    def can_take_bonus_action(self) -> bool:
        """Check if combatant can still take a bonus action."""
        return not self.bonus_action_taken

    def can_move(self, distance: int, speed: int) -> bool:
        """Check if combatant can move the specified distance."""
        return self.movement_used + distance <= speed


@dataclass
class CombatEvent:
    """An event that occurred during combat."""
    event_type: str
    round_number: int
    combatant_id: Optional[str]
    description: str
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CombatState:
    """
    Complete state of a combat encounter.

    This is the main data structure that holds all combat information.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    phase: CombatPhase = CombatPhase.NOT_IN_COMBAT
    initiative_tracker: InitiativeTracker = field(default_factory=InitiativeTracker)
    current_turn: Optional[TurnState] = None
    event_log: List[CombatEvent] = field(default_factory=list)

    # Grid positions (combatant_id -> (x, y))
    positions: Dict[str, tuple] = field(default_factory=dict)

    # Combat grid for terrain, elevation, and cover
    grid: Optional[CombatGrid] = None

    # Combatant details cache (for quick lookup)
    combatant_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Monster ability recharge tracking: {monster_id: {ability_id: is_available}}
    monster_ability_recharge: Dict[str, Dict[str, bool]] = field(default_factory=dict)

    # Legendary action tracking: {monster_id: actions_remaining_this_round}
    legendary_actions_remaining: Dict[str, int] = field(default_factory=dict)

    # Frightful presence immunity tracking: {monster_id: [immune_target_ids]}
    frightful_presence_immune: Dict[str, List[str]] = field(default_factory=dict)

    # Reaction tracking: {combatant_id: True} if reaction used this round
    # Resets at the start of each combatant's turn
    reactions_used_this_round: Dict[str, bool] = field(default_factory=dict)

    def add_event(
        self,
        event_type: str,
        description: str,
        combatant_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> CombatEvent:
        """Add an event to the combat log."""
        event = CombatEvent(
            event_type=event_type,
            round_number=self.initiative_tracker.current_round,
            combatant_id=combatant_id,
            description=description,
            data=data or {}
        )
        self.event_log.append(event)
        return event


class CombatEngine:
    """
    Main combat engine that manages combat encounters.

    Handles:
    - Combat initialization and teardown
    - Turn management
    - Action resolution
    - State transitions
    """

    def __init__(self, combat_state: Optional[CombatState] = None):
        """
        Initialize the combat engine.

        Args:
            combat_state: Existing state to resume, or None to create new
        """
        self.state = combat_state or CombatState()

    # =========================================================================
    # COMBAT LIFECYCLE
    # =========================================================================

    def start_combat(
        self,
        players: List[Dict[str, Any]],
        enemies: List[Dict[str, Any]],
        positions: Optional[Dict[str, tuple]] = None,
        grid: Optional[CombatGrid] = None,
        grid_width: int = 8,
        grid_height: int = 8
    ) -> List[Dict[str, Any]]:
        """
        Start a new combat encounter.

        Args:
            players: List of player data dicts
            enemies: List of enemy data dicts
            positions: Optional initial positions
            grid: Optional pre-configured combat grid
            grid_width: Width of grid to create if no grid provided
            grid_height: Height of grid to create if no grid provided

        Returns:
            List of initiative results
        """
        if self.state.phase != CombatPhase.NOT_IN_COMBAT:
            raise ValueError("Combat already in progress")

        # Create initiative tracker with combatants
        self.state.initiative_tracker = create_initiative_tracker(players, enemies)

        # Store positions
        if positions:
            self.state.positions = positions.copy()

        # Setup combat grid for terrain, elevation, and cover
        if grid:
            self.state.grid = grid
        else:
            self.state.grid = CombatGrid(width=grid_width, height=grid_height)

        # Cache combatant stats for quick lookup
        for player in players:
            self._cache_combatant_stats(player, CombatantType.PLAYER)
        for enemy in enemies:
            self._cache_combatant_stats(enemy, CombatantType.ENEMY)

        # Transition to rolling initiative
        self.state.phase = CombatPhase.ROLLING_INITIATIVE
        self.state.add_event(
            "combat_started",
            "Combat has begun!",
            data={"player_count": len(players), "enemy_count": len(enemies)}
        )

        # Roll initiative for everyone
        results = self.state.initiative_tracker.roll_all_initiative()

        # Initialize legendary action pools for legendary creatures
        self._initialize_legendary_actions()

        # Transition to active combat
        self.state.phase = CombatPhase.COMBAT_ACTIVE

        # Start first combatant's turn
        self._start_current_turn()

        # Log initiative results
        self.state.add_event(
            "initiative_rolled",
            "Initiative rolled for all combatants",
            data={"order": [r.__dict__ for r in results]}
        )

        return [r.__dict__ for r in results]

    def end_combat(self, reason: str = "combat_ended") -> Dict[str, Any]:
        """
        End the current combat encounter.

        Args:
            reason: Why combat ended (victory, defeat, fled, etc.)

        Returns:
            Combat summary
        """
        if self.state.phase not in [CombatPhase.COMBAT_ACTIVE, CombatPhase.ROLLING_INITIATIVE]:
            raise ValueError("No combat in progress")

        result = self.state.initiative_tracker.get_combat_result()

        self.state.phase = CombatPhase.COMBAT_ENDED
        self.state.add_event(
            "combat_ended",
            f"Combat ended: {reason}",
            data={"result": result, "rounds": self.state.initiative_tracker.current_round}
        )

        return {
            "result": result,
            "reason": reason,
            "rounds": self.state.initiative_tracker.current_round,
            "events": len(self.state.event_log)
        }

    def _cache_combatant_stats(
        self,
        combatant_data: Dict[str, Any],
        combatant_type: CombatantType
    ) -> None:
        """Cache combatant stats for quick lookup during combat."""
        combatant_id = combatant_data.get("id", str(uuid.uuid4()))

        # Get abilities dict (may contain class/level from frontend)
        abilities = combatant_data.get("abilities", {})
        # Get stats dict (campaign_engine.py sends class/level here)
        stats = combatant_data.get("stats", {})

        # Get class and level - check multiple locations
        char_class = combatant_data.get("class") or stats.get("class") or abilities.get("class", "")
        level = combatant_data.get("level") or stats.get("level") or abilities.get("level", 1)

        # Calculate class feature resources
        # Barbarian: rage uses
        rage_uses = 0
        if char_class.lower() == "barbarian":
            from app.core.class_features import get_rage_uses
            rage_uses = get_rage_uses(level)

        # Fighter: action surge uses (1 per short rest at level 2+, 2 at level 17+)
        action_surge_uses = 0
        if char_class.lower() == "fighter" and level >= 2:
            action_surge_uses = 2 if level >= 17 else 1

        # Paladin: spell slots for Divine Smite, Lay on Hands pool
        spell_slots = combatant_data.get("spell_slots", {})
        lay_on_hands_pool = 0
        if char_class.lower() == "paladin":
            from app.core.class_features import get_lay_on_hands_pool
            lay_on_hands_pool = get_lay_on_hands_pool(level)
            # Default spell slots if not provided (based on level)
            if not spell_slots and level >= 2:
                if level >= 9:
                    spell_slots = {1: 4, 2: 3, 3: 3}
                elif level >= 7:
                    spell_slots = {1: 4, 2: 3, 3: 2}
                elif level >= 5:
                    spell_slots = {1: 4, 2: 2}
                elif level >= 3:
                    spell_slots = {1: 3}
                else:
                    spell_slots = {1: 2}

        # Build spellcasting data for caster classes
        spellcasting = None
        spellcasting_classes = {
            "wizard": "intelligence",
            "cleric": "wisdom",
            "druid": "wisdom",
            "bard": "charisma",
            "sorcerer": "charisma",
            "warlock": "charisma",
            "paladin": "charisma",
            "ranger": "wisdom",
            "artificer": "intelligence",
        }

        if char_class.lower() in spellcasting_classes:
            spellcasting_ability = spellcasting_classes[char_class.lower()]

            # Get existing spellcasting data from combatant if provided (check FIRST!)
            existing_spellcasting = combatant_data.get("spellcasting", {})

            # Use pre-calculated DC/bonus from campaign_engine if available
            if existing_spellcasting.get("spell_save_dc"):
                spell_save_dc = existing_spellcasting["spell_save_dc"]
                spell_attack_bonus = existing_spellcasting.get("spell_attack_bonus", 0)
            else:
                # Calculate from ability scores - check stats/abilities dicts too
                stats_dict = combatant_data.get("stats", {})
                abilities_dict = combatant_data.get("abilities", {})

                def get_ability(name, short_name):
                    """Get ability score from multiple possible locations."""
                    return (
                        combatant_data.get(name) or
                        combatant_data.get(short_name) or
                        stats_dict.get(name) or
                        stats_dict.get(short_name) or
                        abilities_dict.get(short_name) or
                        abilities_dict.get(f"{short_name}_score") or
                        10
                    )

                ability_scores = {
                    "strength": get_ability("strength", "str"),
                    "dexterity": get_ability("dexterity", "dex"),
                    "constitution": get_ability("constitution", "con"),
                    "intelligence": get_ability("intelligence", "int"),
                    "wisdom": get_ability("wisdom", "wis"),
                    "charisma": get_ability("charisma", "cha"),
                }

                ability_score = ability_scores.get(spellcasting_ability, 10)
                ability_mod = (ability_score - 10) // 2

                # Calculate proficiency bonus
                proficiency_bonus = 2 + ((level - 1) // 4)

                # Calculate spell save DC and attack bonus
                spell_save_dc = 8 + proficiency_bonus + ability_mod
                spell_attack_bonus = proficiency_bonus + ability_mod

            # Get cantrips (check both 'cantrips_known' and 'cantrips' keys for compatibility)
            cantrips = (
                existing_spellcasting.get("cantrips_known") or
                existing_spellcasting.get("cantrips") or
                combatant_data.get("cantrips_known") or
                combatant_data.get("cantrips") or
                []
            )

            spellcasting = {
                "class": char_class,
                "ability": spellcasting_ability,
                "spell_save_dc": spell_save_dc,
                "spell_attack_bonus": spell_attack_bonus,
                "cantrips_known": cantrips,
                "spells_known": existing_spellcasting.get("spells_known", combatant_data.get("spells_known", [])),
                "prepared_spells": existing_spellcasting.get("prepared_spells", combatant_data.get("prepared_spells", [])),
                "spell_slots": spell_slots,
                "spell_slots_used": existing_spellcasting.get("spell_slots_used", combatant_data.get("spell_slots_used", {})),
                "concentrating_on": None,
            }

        # Calculate AC from equipment if available
        equipment_data = combatant_data.get("equipment")
        effective_ac = combatant_data.get("ac", 10)
        weapon_stats = None

        if equipment_data:
            # Import equipment model
            from app.models.equipment import CharacterEquipment

            # Parse equipment if it's a dict
            if isinstance(equipment_data, dict):
                equipment = CharacterEquipment.from_dict(equipment_data)
            else:
                equipment = equipment_data

            # Calculate AC from equipment
            dexterity = abilities.get("dexterity", 10)
            ac_data = equipment.calculate_ac(dexterity)
            calculated_ac = ac_data["total_ac"]
            # Use the higher of calculated AC or original character AC
            # This handles cases where armor items don't have ac_bonus set
            original_ac = combatant_data.get("ac", 10)
            effective_ac = max(calculated_ac, original_ac)

            # Get main weapon stats
            weapon_stats = equipment.get_weapon_stats("main_hand")

        self.state.combatant_stats[combatant_id] = {
            "type": combatant_type.value,
            "name": combatant_data.get("name", "Unknown"),
            "current_hp": combatant_data.get("current_hp", combatant_data.get("hp", 10)),
            "max_hp": combatant_data.get("max_hp", combatant_data.get("hp", 10)),
            "ac": effective_ac,
            "speed": combatant_data.get("speed", 30),
            "str_mod": combatant_data.get("str_mod", 0),
            "dex_mod": combatant_data.get("dex_mod", 0),
            "attack_bonus": combatant_data.get("attack_bonus", 0),
            "damage_dice": weapon_stats["damage"] if weapon_stats else combatant_data.get("damage_dice", "1d6"),
            "damage_type": weapon_stats["damage_type"] if weapon_stats else combatant_data.get("damage_type", "slashing"),
            "weapon_magic_bonus": weapon_stats["magic_bonus"] if weapon_stats else 0,
            "resistances": combatant_data.get("resistances", []),
            "immunities": combatant_data.get("immunities", []),
            "vulnerabilities": combatant_data.get("vulnerabilities", []),
            "conditions": combatant_data.get("conditions", []),
            # Class and level for Extra Attack calculation
            "class": char_class,
            "level": level,
            # Store full abilities dict for class features
            "abilities": abilities,
            # Store stats dict for SpellCaster DC calculation (matches campaign_engine format)
            "stats": stats if stats else {
                "strength": abilities.get("str", abilities.get("str_score", 10)),
                "dexterity": abilities.get("dex", abilities.get("dex_score", 10)),
                "constitution": abilities.get("con", abilities.get("con_score", 10)),
                "intelligence": abilities.get("int", abilities.get("int_score", 10)),
                "wisdom": abilities.get("wis", abilities.get("wis_score", 10)),
                "charisma": abilities.get("cha", abilities.get("cha_score", 10)),
            },
            # Class feature resources
            "is_raging": False,
            "rage_damage_bonus": 0,
            "rage_uses_remaining": rage_uses,
            "action_surge_uses": action_surge_uses,
            "spell_slots": spell_slots,
            "lay_on_hands_pool": lay_on_hands_pool,
            # Creature type for Divine Smite bonus
            "creature_type": combatant_data.get("creature_type", "humanoid"),
            # Full spellcasting data for caster classes
            "spellcasting": spellcasting,
            # Equipment for weapon display and actions
            "equipment": equipment_data,
            # Weapon stats for attack resolution
            "weapon_stats": weapon_stats,
            # Inventory for consumables (potions, scrolls, etc.)
            "inventory": combatant_data.get("inventory", []),
        }

    # =========================================================================
    # TURN MANAGEMENT
    # =========================================================================

    def _start_current_turn(self) -> None:
        """Initialize turn state for the current combatant."""
        current = self.state.initiative_tracker.get_current_combatant()
        if current:
            self.state.current_turn = TurnState(combatant_id=current.id)
            self.state.current_turn.current_phase = TurnPhase.START_OF_TURN

            # Reset reaction at start of turn (both on TurnState and state-level tracking)
            self.state.current_turn.reaction_used = False
            self.state.reactions_used_this_round.pop(current.id, None)

            # Get combatant stats
            stats = self.state.combatant_stats.get(current.id, {})

            # Check for death saving throws (player at 0 HP)
            death_save_result = self._process_death_save_if_needed(current.id, stats)
            if death_save_result:
                # If character revived or died, the event was already logged
                if death_save_result.get("died"):
                    # Character died, their turn is effectively over
                    return
                if death_save_result.get("revived"):
                    # Character regained consciousness - refresh their turn
                    stats["can_act"] = True
                    stats["movement_remaining"] = stats.get("speed", 30)
                    self.state.add_event(
                        "revived",
                        f"{current.name} regains consciousness and can act!",
                        combatant_id=current.id
                    )

            # Calculate max attacks from class features (Extra Attack)
            class_id = stats.get("class", "").lower()
            level = stats.get("level", 1)

            # Import here to avoid circular imports
            try:
                from app.core.class_features import get_extra_attack_count
                extra_attacks = get_extra_attack_count(class_id, level)
            except ImportError:
                extra_attacks = 0

            self.state.current_turn.max_attacks = 1 + extra_attacks

            self.state.add_event(
                "turn_started",
                f"{current.name}'s turn begins",
                combatant_id=current.id,
                data={
                    "round": self.state.initiative_tracker.current_round,
                    "max_attacks": self.state.current_turn.max_attacks
                }
            )

            # Roll recharge for monster abilities at start of turn
            if current.combatant_type == CombatantType.ENEMY:
                self._roll_monster_ability_recharge(current.id, stats)
                # Reset legendary actions for legendary creatures at start of their turn
                self._reset_legendary_actions_for_creature(current.id)

    def _roll_monster_ability_recharge(
        self,
        monster_id: str,
        stats: Dict[str, Any]
    ) -> None:
        """
        Roll recharge for monster abilities at the start of their turn.

        Args:
            monster_id: The monster's combatant ID
            stats: Monster's stat block
        """
        import random

        # Initialize recharge tracking for this monster if not exists
        if monster_id not in self.state.monster_ability_recharge:
            self.state.monster_ability_recharge[monster_id] = {}

        # Get monster's actions and check for recharge abilities
        actions = stats.get("actions", [])
        recharge_state = self.state.monster_ability_recharge[monster_id]

        for action in actions:
            action_name = action.get("name", "")
            ability_id = f"{monster_id}_{action_name.lower().replace(' ', '_')}"

            # Check for recharge pattern in name: "(Recharge 5-6)" or "(Recharge 6)"
            import re
            recharge_match = re.search(r'\(Recharge\s+(\d+)(?:-\d+)?\)', action_name, re.IGNORECASE)

            if recharge_match:
                min_roll = int(recharge_match.group(1))

                # If ability is on cooldown (False), try to recharge it
                if ability_id in recharge_state and not recharge_state[ability_id]:
                    roll = random.randint(1, 6)
                    if roll >= min_roll:
                        recharge_state[ability_id] = True
                        # Get monster name for the event
                        monster_name = stats.get("name", "Monster")
                        self.state.add_event(
                            "ability_recharged",
                            f"{monster_name}'s {action_name.split('(')[0].strip()} has recharged!",
                            combatant_id=monster_id,
                            data={"ability": action_name, "roll": roll}
                        )
                elif ability_id not in recharge_state:
                    # Initialize as available
                    recharge_state[ability_id] = True

    # =========================================================================
    # LEGENDARY ACTIONS
    # =========================================================================

    def _initialize_legendary_actions(self) -> None:
        """
        Initialize legendary action pools for all legendary creatures.

        Called when combat starts. Sets up tracking for creatures
        with legendary actions.
        """
        for cid, stats in self.state.combatant_stats.items():
            legendary_per_round = stats.get("legendary_actions_per_round", 0)
            if legendary_per_round > 0:
                self.state.legendary_actions_remaining[cid] = legendary_per_round

    def _reset_legendary_actions_for_creature(self, monster_id: str) -> None:
        """
        Reset a legendary creature's action pool at the start of their turn.

        Args:
            monster_id: ID of the legendary creature
        """
        stats = self.state.combatant_stats.get(monster_id, {})
        legendary_per_round = stats.get("legendary_actions_per_round", 0)
        if legendary_per_round > 0:
            self.state.legendary_actions_remaining[monster_id] = legendary_per_round

    def get_legendary_creatures(self) -> List[str]:
        """
        Get IDs of all creatures with legendary actions.

        Returns:
            List of combatant IDs that have legendary actions
        """
        legendary = []
        for cid, stats in self.state.combatant_stats.items():
            if stats.get("legendary_actions_per_round", 0) > 0:
                # Check if creature is still alive
                if stats.get("current_hp", 0) > 0:
                    legendary.append(cid)
        return legendary

    def get_available_legendary_actions(
        self,
        monster_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get available legendary actions for a monster.

        Args:
            monster_id: ID of the monster

        Returns:
            List of available legendary actions with their cost
        """
        stats = self.state.combatant_stats.get(monster_id, {})
        remaining = self.state.legendary_actions_remaining.get(monster_id, 0)

        if remaining <= 0:
            return []

        # Parse legendary actions from stats
        legendary_actions = stats.get("legendary_actions", [])
        available = []

        for action in legendary_actions:
            action_name = action.get("name", "Unknown")
            description = action.get("description", "")

            # Parse cost from name "(Costs 2 Actions)"
            cost = 1
            import re
            cost_match = re.search(r'\(Costs?\s*(\d+)\s*Actions?\)', action_name, re.IGNORECASE)
            if cost_match:
                cost = int(cost_match.group(1))

            # Check if we have enough actions remaining
            if cost <= remaining:
                available.append({
                    "id": action_name.lower().replace(" ", "_").replace("(", "").replace(")", ""),
                    "name": action_name,
                    "description": description,
                    "cost": cost,
                })

        return available

    def execute_legendary_action(
        self,
        monster_id: str,
        action_id: str,
        target_id: Optional[str] = None
    ) -> ActionResult:
        """
        Execute a legendary action for a monster.

        Legendary actions can be used at the end of another creature's turn.
        They consume action points from the legendary action pool.

        Args:
            monster_id: ID of the monster using the action
            action_id: ID of the legendary action to use
            target_id: Optional target for the action

        Returns:
            ActionResult with the outcome
        """
        if self.state.phase != CombatPhase.COMBAT_ACTIVE:
            return ActionResult(
                success=False,
                action_type="legendary_action",
                description="Combat is not active"
            )

        # Get current combatant - legendary actions can only be used on OTHER creatures' turns
        current = self.state.initiative_tracker.get_current_combatant()
        if current and current.id == monster_id:
            return ActionResult(
                success=False,
                action_type="legendary_action",
                description="Cannot use legendary action on your own turn"
            )

        stats = self.state.combatant_stats.get(monster_id, {})
        remaining = self.state.legendary_actions_remaining.get(monster_id, 0)

        if remaining <= 0:
            return ActionResult(
                success=False,
                action_type="legendary_action",
                description="No legendary actions remaining"
            )

        # Find the action
        legendary_actions = stats.get("legendary_actions", [])
        action_data = None
        for action in legendary_actions:
            action_name = action.get("name", "")
            parsed_id = action_name.lower().replace(" ", "_").replace("(", "").replace(")", "")
            if parsed_id == action_id or action_name.lower() == action_id.lower():
                action_data = action
                break

        if not action_data:
            return ActionResult(
                success=False,
                action_type="legendary_action",
                description=f"Unknown legendary action: {action_id}"
            )

        # Parse cost
        action_name = action_data.get("name", "")
        cost = 1
        import re
        cost_match = re.search(r'\(Costs?\s*(\d+)\s*Actions?\)', action_name, re.IGNORECASE)
        if cost_match:
            cost = int(cost_match.group(1))

        if cost > remaining:
            return ActionResult(
                success=False,
                action_type="legendary_action",
                description=f"Not enough legendary actions (need {cost}, have {remaining})"
            )

        # Deduct cost
        self.state.legendary_actions_remaining[monster_id] = remaining - cost

        # Execute the action based on type
        # Common legendary actions: Detect, Tail Attack, Wing Attack, Move, etc.
        monster_name = stats.get("name", "Monster")
        action_name_lower = action_name.lower()

        # Handle specific action types
        if "detect" in action_name_lower:
            # Perception check - just log it
            self.state.add_event(
                "legendary_action",
                f"{monster_name} uses Detect (legendary action)",
                combatant_id=monster_id,
                data={"action": action_name, "cost": cost}
            )
            return ActionResult(
                success=True,
                action_type="legendary_action",
                description=f"{monster_name} makes a Perception check",
                combatant_id=monster_id,
                data={"action": action_name, "cost": cost, "remaining": remaining - cost}
            )

        elif "attack" in action_name_lower and target_id:
            # Perform an attack (tail attack, claw attack, etc.)
            # Use the attack handling logic
            from app.core.rules_engine import resolve_attack, DamageType

            target_stats = self.state.combatant_stats.get(target_id, {})
            target_ac = target_stats.get("armor_class", 10)

            # Get attack bonus and damage from action description
            description = action_data.get("description", "")
            damage_dice = "2d8"  # Default
            attack_bonus = 5  # Default

            # Try to parse from description
            hit_match = re.search(r'\+(\d+) to hit', description, re.IGNORECASE)
            if hit_match:
                attack_bonus = int(hit_match.group(1))

            damage_match = re.search(r'\((\d+d\d+(?:\+\d+)?)\)', description)
            if damage_match:
                damage_dice = damage_match.group(1)

            attack_result = resolve_attack(
                attack_bonus=attack_bonus,
                target_ac=target_ac,
                damage_dice=damage_dice,
                damage_modifier=0,
                damage_type=DamageType.BLUDGEONING,
                attacker_is_player=False
            )

            if attack_result.hit:
                damage = attack_result.total_damage
                target_stats["current_hp"] = max(0, target_stats.get("current_hp", 0) - damage)

                self.state.add_event(
                    "legendary_action",
                    f"{monster_name} uses {action_name} and hits for {damage} damage!",
                    combatant_id=monster_id,
                    target_id=target_id,
                    data={
                        "action": action_name,
                        "cost": cost,
                        "damage": damage,
                        "hit": True
                    }
                )
            else:
                self.state.add_event(
                    "legendary_action",
                    f"{monster_name} uses {action_name} but misses!",
                    combatant_id=monster_id,
                    target_id=target_id,
                    data={"action": action_name, "cost": cost, "hit": False}
                )

            return ActionResult(
                success=True,
                action_type="legendary_action",
                description=f"{monster_name} uses {action_name}: {'Hit!' if attack_result.hit else 'Miss'}",
                combatant_id=monster_id,
                target_id=target_id,
                data={
                    "action": action_name,
                    "cost": cost,
                    "remaining": remaining - cost,
                    "hit": attack_result.hit,
                    "damage": attack_result.total_damage if attack_result.hit else 0
                }
            )

        else:
            # Generic legendary action - just log it
            self.state.add_event(
                "legendary_action",
                f"{monster_name} uses {action_name} (legendary action)",
                combatant_id=monster_id,
                data={"action": action_name, "cost": cost, "description": action_data.get("description", "")}
            )

            return ActionResult(
                success=True,
                action_type="legendary_action",
                description=f"{monster_name} uses {action_name}",
                combatant_id=monster_id,
                data={
                    "action": action_name,
                    "cost": cost,
                    "remaining": remaining - cost,
                    "description": action_data.get("description", "")
                }
            )

    def _process_death_save_if_needed(
        self,
        combatant_id: str,
        stats: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Process death saving throw if combatant is dying.

        Only player characters make death saves. Enemies at 0 HP are dead.

        Args:
            combatant_id: The combatant's ID
            stats: Combatant stats dict

        Returns:
            Dict with death save result, or None if not applicable
        """
        # Only players make death saves
        combatant_type = stats.get("type", "enemy")
        if combatant_type != "player":
            return None

        current_hp = stats.get("current_hp", 1)
        if current_hp > 0:
            return None

        # Check if already stable or dead
        is_stable = stats.get("is_stable", False)
        is_dead = stats.get("is_dead", False)

        if is_dead:
            return {"died": True, "already_dead": True}

        if is_stable:
            return None  # Stable, no death save needed

        # Roll death save
        try:
            from app.core.death_saves import (
                DeathSaveState,
                roll_death_save,
                DeathSaveOutcome
            )

            state = DeathSaveState(
                successes=stats.get("death_save_successes", 0),
                failures=stats.get("death_save_failures", 0),
                is_stable=is_stable,
                is_dead=is_dead,
            )

            result = roll_death_save(state)

            # Update stats
            stats["death_save_successes"] = result.total_successes
            stats["death_save_failures"] = result.total_failures

            combatant = self.state.initiative_tracker.get_combatant(combatant_id)
            name = combatant.name if combatant else "Unknown"

            if result.outcome == DeathSaveOutcome.REVIVED:
                # Natural 20 - regain 1 HP
                stats["current_hp"] = 1
                stats["death_save_successes"] = 0
                stats["death_save_failures"] = 0
                stats["is_stable"] = False

                self.state.add_event(
                    "death_save_critical",
                    f"{name} rolls a natural 20! They regain consciousness with 1 HP!",
                    combatant_id=combatant_id,
                    data=result.to_dict()
                )
                return {"revived": True, "result": result.to_dict()}

            elif result.outcome == DeathSaveOutcome.STABILIZED:
                stats["is_stable"] = True
                stats["death_save_successes"] = 0
                stats["death_save_failures"] = 0

                self.state.add_event(
                    "death_save_stabilized",
                    f"{name} is now stable! They are unconscious but no longer dying.",
                    combatant_id=combatant_id,
                    data=result.to_dict()
                )
                return {"stabilized": True, "result": result.to_dict()}

            elif result.outcome == DeathSaveOutcome.DEAD:
                stats["is_dead"] = True
                stats["is_active"] = False
                if combatant:
                    combatant.is_active = False

                self.state.add_event(
                    "death_save_failed",
                    f"{name} has died!",
                    combatant_id=combatant_id,
                    data=result.to_dict()
                )
                return {"died": True, "result": result.to_dict()}

            else:
                # Continue dying
                self.state.add_event(
                    "death_save",
                    f"{name} makes a death saving throw: {result.description}",
                    combatant_id=combatant_id,
                    data=result.to_dict()
                )
                return {"continue": True, "result": result.to_dict()}

        except ImportError:
            return None

    def _check_concentration_on_damage(
        self,
        target_id: str,
        damage_dealt: int,
        damage_source: str = "damage"
    ) -> Optional[Dict[str, Any]]:
        """
        Check if taking damage breaks concentration.

        D&D 5e Rule: When you take damage while concentrating on a spell,
        you must make a Constitution saving throw to maintain concentration.
        DC = max(10, damage / 2)

        Args:
            target_id: ID of the combatant who took damage
            damage_dealt: Amount of damage taken
            damage_source: Description of what caused the damage

        Returns:
            Dict with concentration check result, or None if not concentrating
        """
        if damage_dealt <= 0:
            return None

        stats = self.state.combatant_stats.get(target_id, {})
        spellcasting = stats.get("spellcasting") or {}
        concentrating_on = spellcasting.get("concentrating_on")

        if not concentrating_on:
            return None

        combatant = self.state.initiative_tracker.get_combatant(target_id)
        if not combatant:
            return None

        # Calculate DC: max(10, damage / 2)
        dc = max(10, damage_dealt // 2)

        # Get Constitution modifier and proficiency if War Caster or proficient in CON saves
        con_mod = stats.get("con_mod", 0)
        if con_mod == 0 and "abilities" in stats:
            # Calculate from abilities if con_mod not provided
            con_score = stats["abilities"].get("constitution", 10)
            con_mod = (con_score - 10) // 2

        # Check for proficiency in Constitution saves
        level = stats.get("level", 1)
        proficiency_bonus = 2 + ((level - 1) // 4)

        # Check if proficient in CON saves (Fighter, Barbarian, Sorcerer)
        char_class = stats.get("class", "").lower()
        con_save_proficient_classes = ["fighter", "barbarian", "sorcerer"]
        is_proficient = char_class in con_save_proficient_classes

        save_bonus = con_mod
        if is_proficient:
            save_bonus += proficiency_bonus

        # Check for War Caster feat (advantage on concentration checks)
        # This would be in a feats list if the character has it
        feats = stats.get("feats", [])
        has_war_caster = "war_caster" in [f.lower().replace(" ", "_") for f in feats] or "war caster" in [f.lower() for f in feats]

        # Roll the save
        roll1 = random.randint(1, 20)
        if has_war_caster:
            roll2 = random.randint(1, 20)
            roll = max(roll1, roll2)
            roll_desc = f"with advantage ({roll1}, {roll2})"
        else:
            roll = roll1
            roll_desc = str(roll)

        total = roll + save_bonus
        success = total >= dc

        result = {
            "roll": roll,
            "modifier": save_bonus,
            "total": total,
            "dc": dc,
            "success": success,
            "spell": concentrating_on,
            "damage_taken": damage_dealt,
            "had_advantage": has_war_caster,
        }

        if success:
            self.state.add_event(
                "concentration_maintained",
                f"{combatant.name} maintains concentration on {concentrating_on}! "
                f"(CON save: {roll_desc} + {save_bonus} = {total} vs DC {dc})",
                combatant_id=target_id,
                data=result
            )
        else:
            # Break concentration
            spellcasting["concentrating_on"] = None
            result["concentration_broken"] = True

            self.state.add_event(
                "concentration_broken",
                f"{combatant.name} loses concentration on {concentrating_on}! "
                f"(CON save: {roll_desc} + {save_bonus} = {total} vs DC {dc})",
                combatant_id=target_id,
                data=result
            )

            # End any ongoing spell effects
            # This would tie into the spell effect system

        return result

    def end_turn(self) -> Optional[Combatant]:
        """
        End the current combatant's turn and advance to the next.

        Returns:
            The next combatant, or None if combat ended
        """
        # If combat has already ended, return None gracefully
        if self.state.phase == CombatPhase.COMBAT_ENDED:
            return None

        if self.state.phase != CombatPhase.COMBAT_ACTIVE:
            raise ValueError("Combat not active")

        if not self.state.current_turn:
            raise ValueError("No active turn")

        current = self.state.initiative_tracker.get_current_combatant()
        if current:
            self.state.add_event(
                "turn_ended",
                f"{current.name}'s turn ends",
                combatant_id=current.id
            )

        # Advance to next combatant
        next_combatant = self.state.initiative_tracker.advance_turn()

        # Check if combat is over
        if self.state.initiative_tracker.is_combat_over():
            self.end_combat("all_enemies_defeated" if self.state.initiative_tracker.get_combat_result() == "victory" else "party_defeated")
            return None

        # Start new turn
        if next_combatant:
            self._start_current_turn()

        return next_combatant

    def get_current_combatant(self) -> Optional[Combatant]:
        """Get the combatant whose turn it is."""
        return self.state.initiative_tracker.get_current_combatant()

    def get_turn_state(self) -> Optional[TurnState]:
        """Get the current turn state."""
        return self.state.current_turn

    # =========================================================================
    # ACTIONS
    # =========================================================================

    def take_action(
        self,
        action_type: ActionType,
        target_id: Optional[str] = None,
        **kwargs
    ) -> ActionResult:
        """
        Execute an action for the current combatant.

        Args:
            action_type: Type of action to take
            target_id: Target of the action (if applicable)
            **kwargs: Additional action-specific parameters

        Returns:
            ActionResult with the outcome
        """
        if self.state.phase != CombatPhase.COMBAT_ACTIVE:
            return ActionResult(
                success=False,
                action_type=action_type.value,
                description="Combat is not active"
            )

        if not self.state.current_turn:
            return ActionResult(
                success=False,
                action_type=action_type.value,
                description="No active turn"
            )

        # Check if combatant is incapacitated (stunned, paralyzed, unconscious, etc.)
        current = self.get_current_combatant()
        if current:
            current_stats = self.state.combatant_stats.get(current.id, {})
            conditions = current_stats.get("conditions", getattr(current, "conditions", []))
            incap, incap_reasons = is_incapacitated(conditions)
            if incap:
                return ActionResult(
                    success=False,
                    action_type=action_type.value,
                    description=f"Cannot take actions: {', '.join(incap_reasons)}"
                )

        # For attacks, check can_attack() (supports Extra Attack)
        # For other actions, check can_take_action()
        if action_type == ActionType.ATTACK:
            if not self.state.current_turn.can_attack():
                return ActionResult(
                    success=False,
                    action_type=action_type.value,
                    description="No attacks remaining this turn"
                )
        else:
            if not self.state.current_turn.can_take_action():
                return ActionResult(
                    success=False,
                    action_type=action_type.value,
                    description="Action already taken this turn"
                )

        # Route to specific action handler
        handlers = {
            ActionType.ATTACK: self._handle_attack,
            ActionType.DASH: self._handle_dash,
            ActionType.DISENGAGE: self._handle_disengage,
            ActionType.DODGE: self._handle_dodge,
            ActionType.HELP: self._handle_help,
            ActionType.HIDE: self._handle_hide,
            ActionType.READY: self._handle_ready,
            ActionType.GRAPPLE: self._handle_grapple,
            ActionType.SHOVE: self._handle_shove,
            ActionType.ESCAPE_GRAPPLE: self._handle_escape_grapple,
            ActionType.MONSTER_ABILITY: self._handle_monster_ability,
            ActionType.MULTIATTACK: self._handle_multiattack,
        }

        handler = handlers.get(action_type)
        if not handler:
            return ActionResult(
                success=False,
                action_type=action_type.value,
                description=f"Action type {action_type.value} not implemented"
            )

        result = handler(target_id, **kwargs)

        # For non-attack actions, mark action as taken
        # Attack actions manage their own action_taken via use_attack()
        if result.success and action_type != ActionType.ATTACK:
            self.state.current_turn.action_taken = True
            self.state.current_turn.current_phase = TurnPhase.BONUS_ACTION

        return result

    def take_bonus_action(
        self,
        bonus_type: BonusActionType,
        target_id: Optional[str] = None,
        **kwargs
    ) -> ActionResult:
        """
        Execute a bonus action for the current combatant.

        Args:
            bonus_type: Type of bonus action to take
            target_id: Target of the bonus action (if applicable)
            **kwargs: Additional action-specific parameters

        Returns:
            ActionResult with the outcome
        """
        if self.state.phase != CombatPhase.COMBAT_ACTIVE:
            return ActionResult(
                success=False,
                action_type=bonus_type.value,
                description="Combat is not active"
            )

        if not self.state.current_turn:
            return ActionResult(
                success=False,
                action_type=bonus_type.value,
                description="No active turn"
            )

        # Check if combatant is incapacitated
        current = self.get_current_combatant()
        if current:
            current_stats = self.state.combatant_stats.get(current.id, {})
            conditions = current_stats.get("conditions", getattr(current, "conditions", []))
            incap, incap_reasons = is_incapacitated(conditions)
            if incap:
                return ActionResult(
                    success=False,
                    action_type=bonus_type.value,
                    description=f"Cannot take bonus actions: {', '.join(incap_reasons)}"
                )

        if not self.state.current_turn.can_take_bonus_action():
            return ActionResult(
                success=False,
                action_type=bonus_type.value,
                description="Bonus action already taken this turn"
            )

        # Route to specific bonus action handler
        handlers = {
            BonusActionType.OFFHAND_ATTACK: self._handle_offhand_attack,
            BonusActionType.SECOND_WIND: self._handle_second_wind,
            BonusActionType.RAGE: self._handle_rage,
            BonusActionType.CUNNING_ACTION: self._handle_cunning_action,
            BonusActionType.MARTIAL_ARTS: self._handle_martial_arts,
            BonusActionType.FLURRY_OF_BLOWS: self._handle_flurry_of_blows,
            BonusActionType.PATIENT_DEFENSE: self._handle_patient_defense,
            BonusActionType.STEP_OF_THE_WIND: self._handle_step_of_the_wind,
        }

        handler = handlers.get(bonus_type)
        if not handler:
            return ActionResult(
                success=False,
                action_type=bonus_type.value,
                description=f"Bonus action type {bonus_type.value} not implemented"
            )

        result = handler(target_id, **kwargs)

        if result.success:
            self.state.current_turn.bonus_action_taken = True

        return result

    def _handle_offhand_attack(
        self,
        target_id: Optional[str],
        offhand_weapon: str = "dagger",
        **kwargs
    ) -> ActionResult:
        """
        Handle an off-hand attack for Two-Weapon Fighting.

        D&D 5e Rules:
        - Must have attacked with a light melee weapon this turn
        - Off-hand weapon must also be light
        - Do NOT add ability modifier to damage (unless negative or with feat)
        """
        if not self.state.current_turn.can_offhand_attack:
            return ActionResult(
                success=False,
                action_type=BonusActionType.OFFHAND_ATTACK.value,
                description="Must attack with a light melee weapon first to use off-hand attack"
            )

        if not target_id:
            return ActionResult(
                success=False,
                action_type=BonusActionType.OFFHAND_ATTACK.value,
                description="No target specified"
            )

        attacker = self.get_current_combatant()
        if not attacker:
            return ActionResult(
                success=False,
                action_type=BonusActionType.OFFHAND_ATTACK.value,
                description="No current combatant"
            )

        target = self.state.initiative_tracker.get_combatant(target_id)
        if not target:
            return ActionResult(
                success=False,
                action_type=BonusActionType.OFFHAND_ATTACK.value,
                description="Target not found"
            )

        if not target.is_active:
            return ActionResult(
                success=False,
                action_type=BonusActionType.OFFHAND_ATTACK.value,
                description="Target is not active"
            )

        # Validate off-hand weapon is light
        weapon_data = load_weapon_data(offhand_weapon)
        if weapon_data:
            weapon_properties = weapon_data.get("properties", [])
            if "light" not in weapon_properties:
                return ActionResult(
                    success=False,
                    action_type=BonusActionType.OFFHAND_ATTACK.value,
                    description=f"{weapon_data.get('name', offhand_weapon)} is not a light weapon"
                )
            # Check it's not a ranged weapon
            if "ammunition" in weapon_properties:
                return ActionResult(
                    success=False,
                    action_type=BonusActionType.OFFHAND_ATTACK.value,
                    description="Off-hand attack must use a melee weapon"
                )

        # Get attacker and target stats
        attacker_stats = self.state.combatant_stats.get(attacker.id, {})
        target_stats = self.state.combatant_stats.get(target.id, {})

        # Range check (must be in melee range)
        attacker_pos = self.state.positions.get(attacker.id)
        target_pos = self.state.positions.get(target.id)
        if attacker_pos and target_pos:
            dx = abs(attacker_pos[0] - target_pos[0])
            dy = abs(attacker_pos[1] - target_pos[1])
            distance_ft = max(dx, dy) * 5
            if distance_ft > 5:
                return ActionResult(
                    success=False,
                    action_type=BonusActionType.OFFHAND_ATTACK.value,
                    description=f"Target out of melee range ({distance_ft}ft)"
                )

        # Calculate attack bonus using D&D 5e rules:
        # Attack = d20 + ability_modifier + proficiency_bonus + weapon_bonus
        attack_bonus = attacker_stats.get("attack_bonus", 0)
        if attack_bonus == 0:
            # Get character level for proficiency calculation
            level = attacker_stats.get("level", 1)
            # D&D 5e proficiency: starts at +2, increases every 4 levels
            proficiency_bonus = 2 + ((level - 1) // 4)

            # Use DEX for finesse, otherwise STR
            if weapon_data and "finesse" in weapon_data.get("properties", []):
                ability_mod = max(
                    attacker_stats.get("str_mod", 0),
                    attacker_stats.get("dex_mod", 0)
                )
            else:
                ability_mod = attacker_stats.get("str_mod", 0)

            # Weapon bonus (magical weapons, etc.)
            weapon_bonus = weapon_data.get("attack_bonus", 0) if weapon_data else 0

            # D&D 5e attack bonus formula
            attack_bonus = ability_mod + proficiency_bonus + weapon_bonus

        target_ac = target_stats.get("ac", target.armor_class)

        # Resolve attack - NO modifier on damage for off-hand (D&D 5e rule)
        damage_dice = weapon_data.get("damage", "1d4") if weapon_data else "1d4"
        damage_type = weapon_data.get("damage_type", "slashing") if weapon_data else "slashing"

        # Check if attacker is a player (for 2024 crit rules)
        from app.core.initiative import CombatantType
        attacker_is_player = attacker.combatant_type == CombatantType.PLAYER

        attack_result = resolve_attack(
            attack_bonus=attack_bonus,
            target_ac=target_ac,
            damage_dice=damage_dice,
            damage_type=damage_type,
            damage_modifier=0,  # D&D 5e: NO ability modifier on off-hand damage
            attacker_is_player=attacker_is_player
        )

        # Apply damage if hit
        damage_dealt = 0
        if attack_result.hit:
            resistances = target_stats.get("resistances", [])
            immunities = target_stats.get("immunities", [])
            vulnerabilities = target_stats.get("vulnerabilities", [])

            has_resistance = damage_type in resistances
            has_immunity = damage_type in immunities
            has_vulnerability = damage_type in vulnerabilities

            new_hp, damage_dealt, is_unconscious = apply_damage(
                current_hp=target_stats.get("current_hp", target.current_hp),
                max_hp=target_stats.get("max_hp", target.max_hp),
                damage=attack_result.total_damage,
                resistance=has_resistance,
                immunity=has_immunity,
                vulnerability=has_vulnerability
            )

            # Update target HP
            target.current_hp = new_hp
            if target.id in self.state.combatant_stats:
                self.state.combatant_stats[target.id]["current_hp"] = new_hp

            # Check if target is defeated
            if new_hp <= 0:
                target.is_active = False
                self.state.add_event(
                    "combatant_defeated",
                    f"{target.name} is defeated!",
                    combatant_id=target.id
                )

        # Build description
        weapon_name = weapon_data.get("name", offhand_weapon) if weapon_data else offhand_weapon
        if attack_result.critical_hit:
            desc = f"{attacker.name} critically hits {target.name} with off-hand {weapon_name} for {damage_dealt} {damage_type} damage!"
        elif attack_result.hit:
            desc = f"{attacker.name} hits {target.name} with off-hand {weapon_name} for {damage_dealt} {damage_type} damage"
        elif attack_result.critical_miss:
            desc = f"{attacker.name} fumbles their off-hand attack against {target.name}!"
        else:
            desc = f"{attacker.name} misses {target.name} with off-hand {weapon_name}"

        # Log the event
        self.state.add_event(
            "offhand_attack",
            desc,
            combatant_id=attacker.id,
            data={
                "target_id": target.id,
                "hit": attack_result.hit,
                "damage": damage_dealt,
                "critical": attack_result.critical_hit,
                "roll": attack_result.attack_roll,
                "weapon": offhand_weapon,
                "main_hand_weapon": self.state.current_turn.main_hand_weapon
            }
        )

        # Disable further off-hand attacks this turn
        self.state.current_turn.can_offhand_attack = False

        return ActionResult(
            success=True,
            action_type=BonusActionType.OFFHAND_ATTACK.value,
            description=desc,
            damage_dealt=damage_dealt,
            target_id=target_id,
            extra_data={
                "hit": attack_result.hit,
                "critical_hit": attack_result.critical_hit,
                "critical_miss": attack_result.critical_miss,
                "attack_roll": attack_result.attack_roll,
                "target_ac": target_ac,
                "target_hp": target.current_hp,
                "target_defeated": not target.is_active,
                "weapon_name": weapon_name
            }
        )

    def _handle_second_wind(self, target_id: Optional[str], **kwargs) -> ActionResult:
        """
        Handle Fighter's Second Wind bonus action.

        D&D 5e: Regain 1d10 + fighter level HP. Once per short rest.
        """
        combatant = self.get_current_combatant()
        if not combatant:
            return ActionResult(
                success=False,
                action_type=BonusActionType.SECOND_WIND.value,
                description="No current combatant"
            )

        stats = self.state.combatant_stats.get(combatant.id, {})
        class_id = stats.get("class", "").lower()

        if class_id != "fighter":
            return ActionResult(
                success=False,
                action_type=BonusActionType.SECOND_WIND.value,
                description="Only Fighters can use Second Wind"
            )

        # Roll 1d10 + fighter level
        level = stats.get("level", 1)
        healing_roll = roll_damage("1d10", modifier=level)
        healing = healing_roll.total

        # Apply healing
        current_hp = stats.get("current_hp", combatant.current_hp)
        max_hp = stats.get("max_hp", combatant.max_hp)
        new_hp = min(current_hp + healing, max_hp)
        actual_healing = new_hp - current_hp

        # Update HP
        combatant.current_hp = new_hp
        if combatant.id in self.state.combatant_stats:
            self.state.combatant_stats[combatant.id]["current_hp"] = new_hp

        desc = f"{combatant.name} uses Second Wind and regains {actual_healing} HP"

        self.state.add_event(
            "second_wind",
            desc,
            combatant_id=combatant.id,
            data={"healing": actual_healing, "roll": healing_roll.total}
        )

        return ActionResult(
            success=True,
            action_type=BonusActionType.SECOND_WIND.value,
            description=desc,
            extra_data={
                "healing": actual_healing,
                "new_hp": new_hp,
                "max_hp": max_hp
            }
        )

    def _handle_rage(self, target_id: Optional[str], **kwargs) -> ActionResult:
        """
        Handle Barbarian's Rage bonus action.

        D&D 5e Rage Benefits:
        - Advantage on STR checks and saves
        - Bonus to melee weapon damage (level-based: +2/+3/+4)
        - Resistance to bludgeoning, piercing, slashing damage
        - Lasts 1 minute (10 rounds) or until knocked unconscious/end turn without attacking

        Returns:
            ActionResult with rage activation status
        """
        combatant = self.get_current_combatant()
        if not combatant:
            return ActionResult(
                success=False,
                action_type=BonusActionType.RAGE.value,
                description="No current combatant"
            )

        stats = self.state.combatant_stats.get(combatant.id, {})
        class_id = stats.get("class", "").lower()

        # Check if Barbarian
        if class_id != "barbarian":
            return ActionResult(
                success=False,
                action_type=BonusActionType.RAGE.value,
                description="Only Barbarians can Rage"
            )

        # Check if already raging
        if stats.get("is_raging", False):
            return ActionResult(
                success=False,
                action_type=BonusActionType.RAGE.value,
                description=f"{combatant.name} is already raging!"
            )

        # Check rage uses remaining
        rage_uses = stats.get("rage_uses_remaining", 0)
        if rage_uses <= 0:
            return ActionResult(
                success=False,
                action_type=BonusActionType.RAGE.value,
                description="No rage uses remaining! Take a long rest to recover."
            )

        # Activate rage
        level = stats.get("level", 1)
        from app.core.class_features import get_rage_damage_bonus
        damage_bonus = get_rage_damage_bonus(level)

        # Update combatant stats
        self.state.combatant_stats[combatant.id]["is_raging"] = True
        self.state.combatant_stats[combatant.id]["rage_damage_bonus"] = damage_bonus
        self.state.combatant_stats[combatant.id]["rage_uses_remaining"] -= 1

        # Add resistance to physical damage
        resistances = list(stats.get("resistances", []))
        for dmg_type in ["bludgeoning", "piercing", "slashing"]:
            if dmg_type not in resistances:
                resistances.append(dmg_type)
        self.state.combatant_stats[combatant.id]["resistances"] = resistances

        desc = f"{combatant.name} enters a RAGE! (+{damage_bonus} melee damage, resistance to B/P/S)"

        self.state.add_event(
            "rage",
            desc,
            combatant_id=combatant.id,
            data={
                "damage_bonus": damage_bonus,
                "resistances_gained": ["bludgeoning", "piercing", "slashing"],
                "uses_remaining": rage_uses - 1
            }
        )

        return ActionResult(
            success=True,
            action_type=BonusActionType.RAGE.value,
            description=desc,
            extra_data={
                "damage_bonus": damage_bonus,
                "resistances": resistances,
                "rage_uses_remaining": rage_uses - 1
            }
        )

    def _handle_cunning_action(
        self,
        target_id: Optional[str],
        cunning_type: str = "dash",
        **kwargs
    ) -> ActionResult:
        """
        Handle Rogue's Cunning Action bonus action.

        D&D 5e Cunning Action (Level 2+):
        - Use bonus action to Dash, Disengage, or Hide
        - These normally require an action

        Args:
            cunning_type: "dash", "disengage", or "hide"

        Returns:
            ActionResult with action outcome
        """
        combatant = self.get_current_combatant()
        if not combatant:
            return ActionResult(
                success=False,
                action_type=BonusActionType.CUNNING_ACTION.value,
                description="No current combatant"
            )

        stats = self.state.combatant_stats.get(combatant.id, {})
        class_id = stats.get("class", "").lower()
        level = stats.get("level", 1)

        # Check if Rogue
        if class_id != "rogue":
            return ActionResult(
                success=False,
                action_type=BonusActionType.CUNNING_ACTION.value,
                description="Only Rogues have Cunning Action"
            )

        # Check level requirement
        if level < 2:
            return ActionResult(
                success=False,
                action_type=BonusActionType.CUNNING_ACTION.value,
                description="Cunning Action requires Rogue level 2"
            )

        # Normalize cunning_type
        cunning_type = cunning_type.lower()

        # Route to appropriate action (but as bonus action, not using action)
        if cunning_type == "dash":
            # Use effective speed (includes encumbrance penalties)
            speed = self._get_effective_speed(combatant.id, stats)

            self.state.add_event(
                "cunning_action_dash",
                f"{combatant.name} uses Cunning Action: Dash, gaining {speed}ft additional movement",
                combatant_id=combatant.id
            )

            return ActionResult(
                success=True,
                action_type=BonusActionType.CUNNING_ACTION.value,
                description=f"{combatant.name} dashes (Cunning Action), gaining {speed}ft of additional movement",
                extra_data={"cunning_type": "dash", "additional_movement": speed}
            )

        elif cunning_type == "disengage":
            if "disengaged" not in combatant.conditions:
                combatant.conditions.append("disengaged")

            self.state.add_event(
                "cunning_action_disengage",
                f"{combatant.name} uses Cunning Action: Disengage",
                combatant_id=combatant.id
            )

            return ActionResult(
                success=True,
                action_type=BonusActionType.CUNNING_ACTION.value,
                description=f"{combatant.name} disengages (Cunning Action), avoiding opportunity attacks",
                effects_applied=["disengaged"],
                extra_data={"cunning_type": "disengage"}
            )

        elif cunning_type == "hide":
            # Roll Stealth check
            dex_mod = stats.get("dex_mod", 0)
            stealth_roll = roll_d20(modifier=dex_mod)

            if "hidden" not in combatant.conditions:
                combatant.conditions.append("hidden")

            self.state.add_event(
                "cunning_action_hide",
                f"{combatant.name} uses Cunning Action: Hide (Stealth: {stealth_roll.total})",
                combatant_id=combatant.id,
                data={"stealth_roll": stealth_roll.total}
            )

            return ActionResult(
                success=True,
                action_type=BonusActionType.CUNNING_ACTION.value,
                description=f"{combatant.name} hides (Cunning Action) - Stealth: {stealth_roll.total}",
                effects_applied=["hidden"],
                extra_data={
                    "cunning_type": "hide",
                    "stealth_roll": stealth_roll.total
                }
            )

        elif cunning_type == "steady_aim":
            # Steady Aim is a 2024 Rogue feature (level 3+)
            from app.core.rules_config import is_2024_class_features_enabled

            if not is_2024_class_features_enabled():
                return ActionResult(
                    success=False,
                    action_type=BonusActionType.CUNNING_ACTION.value,
                    description="Steady Aim requires 2024 rules to be enabled"
                )

            if level < 3:
                return ActionResult(
                    success=False,
                    action_type=BonusActionType.CUNNING_ACTION.value,
                    description="Steady Aim requires Rogue level 3"
                )

            # Steady Aim grants advantage on next attack but prevents movement
            # Use all remaining movement to signify no movement allowed
            speed = self._get_effective_speed(combatant.id, stats)
            self.state.current_turn.movement_used = speed

            # Add steady aim condition for advantage on next attack
            if "steady_aim" not in combatant.conditions:
                combatant.conditions.append("steady_aim")

            self.state.add_event(
                "cunning_action_steady_aim",
                f"{combatant.name} uses Cunning Action: Steady Aim (advantage on next attack, no movement this turn)",
                combatant_id=combatant.id
            )

            return ActionResult(
                success=True,
                action_type=BonusActionType.CUNNING_ACTION.value,
                description=f"{combatant.name} takes careful aim (Cunning Action) - advantage on next attack, cannot move this turn",
                effects_applied=["steady_aim"],
                extra_data={
                    "cunning_type": "steady_aim",
                    "grants_advantage": True,
                    "movement_blocked": True
                }
            )

        else:
            return ActionResult(
                success=False,
                action_type=BonusActionType.CUNNING_ACTION.value,
                description=f"Invalid Cunning Action type: {cunning_type}. Use 'dash', 'disengage', 'hide', or 'steady_aim' (2024, level 3+)."
            )

    def _handle_martial_arts(
        self,
        target_id: Optional[str],
        **kwargs
    ) -> ActionResult:
        """
        Handle Monk's Martial Arts bonus action - one unarmed strike.

        D&D 5e Rules:
        - When using Attack action with unarmed strike or monk weapon
        - Can make one unarmed strike as bonus action
        - Uses Martial Arts die for damage
        """
        combatant = self.get_current_combatant()
        if not combatant:
            return ActionResult(
                success=False,
                action_type=BonusActionType.MARTIAL_ARTS.value,
                description="No current combatant"
            )

        stats = self.state.combatant_stats.get(combatant.id, {})
        class_id = stats.get("class", "").lower()

        if class_id != "monk":
            return ActionResult(
                success=False,
                action_type=BonusActionType.MARTIAL_ARTS.value,
                description="Only Monks can use Martial Arts bonus action"
            )

        if not target_id:
            return ActionResult(
                success=False,
                action_type=BonusActionType.MARTIAL_ARTS.value,
                description="No target specified for unarmed strike"
            )

        target = self.state.initiative_tracker.get_combatant(target_id)
        if not target or not target.is_active:
            return ActionResult(
                success=False,
                action_type=BonusActionType.MARTIAL_ARTS.value,
                description="Invalid target"
            )

        # Check range (must be adjacent for unarmed strike)
        attacker_pos = self.state.positions.get(combatant.id)
        target_pos = self.state.positions.get(target_id)
        if attacker_pos and target_pos:
            dx = abs(target_pos[0] - attacker_pos[0])
            dy = abs(target_pos[1] - attacker_pos[1])
            if max(dx, dy) > 1:
                return ActionResult(
                    success=False,
                    action_type=BonusActionType.MARTIAL_ARTS.value,
                    description="Target not in melee range"
                )

        # Get Martial Arts die based on level
        level = stats.get("level", 1)
        if level >= 17:
            martial_arts_die = "1d12"
        elif level >= 11:
            martial_arts_die = "1d10"
        elif level >= 5:
            martial_arts_die = "1d8"
        else:
            martial_arts_die = "1d6"

        # Attack roll
        from app.core.rules_engine import resolve_attack, DamageType
        dex_mod = stats.get("dex_mod", 0)
        str_mod = stats.get("str_mod", 0)
        ability_mod = max(dex_mod, str_mod)  # Monks can use DEX for unarmed
        proficiency = 2 + ((level - 1) // 4)
        attack_bonus = ability_mod + proficiency

        target_stats = self.state.combatant_stats.get(target_id, {})
        target_ac = target_stats.get("ac", target.armor_class)

        attack_result = resolve_attack(
            attack_bonus=attack_bonus,
            target_ac=target_ac,
            damage_dice=martial_arts_die,
            damage_modifier=ability_mod,
            damage_type=DamageType.BLUDGEONING
        )

        damage_dealt = 0
        if attack_result.hit:
            from app.core.rules_engine import apply_damage
            new_hp, damage_dealt, _ = apply_damage(
                current_hp=target_stats.get("current_hp", target.current_hp),
                max_hp=target_stats.get("max_hp", target.max_hp),
                damage=attack_result.total_damage
            )
            target.current_hp = new_hp
            if target_id in self.state.combatant_stats:
                self.state.combatant_stats[target_id]["current_hp"] = new_hp

            if new_hp <= 0:
                target.is_active = False

        if attack_result.critical_hit:
            desc = f"{combatant.name} lands a critical Martial Arts strike on {target.name} for {damage_dealt} damage!"
        elif attack_result.hit:
            desc = f"{combatant.name} hits {target.name} with a Martial Arts strike for {damage_dealt} damage"
        else:
            desc = f"{combatant.name}'s Martial Arts strike misses {target.name}"

        self.state.add_event(
            "martial_arts",
            desc,
            combatant_id=combatant.id,
            data={"target_id": target_id, "damage": damage_dealt, "hit": attack_result.hit}
        )

        return ActionResult(
            success=True,
            action_type=BonusActionType.MARTIAL_ARTS.value,
            description=desc,
            damage_dealt=damage_dealt,
            target_id=target_id,
            extra_data={
                "hit": attack_result.hit,
                "critical": attack_result.critical_hit,
                "martial_arts_die": martial_arts_die,
                "attack_roll": attack_result.attack_roll.total if attack_result.attack_roll else 0,
            }
        )

    def _handle_flurry_of_blows(
        self,
        target_id: Optional[str],
        **kwargs
    ) -> ActionResult:
        """
        Handle Monk's Flurry of Blows - two unarmed strikes (costs 1 ki).

        D&D 5e Rules:
        - Immediately after Attack action
        - Spend 1 ki point
        - Make two unarmed strikes as bonus action
        """
        combatant = self.get_current_combatant()
        if not combatant:
            return ActionResult(
                success=False,
                action_type=BonusActionType.FLURRY_OF_BLOWS.value,
                description="No current combatant"
            )

        stats = self.state.combatant_stats.get(combatant.id, {})
        class_id = stats.get("class", "").lower()

        if class_id != "monk":
            return ActionResult(
                success=False,
                action_type=BonusActionType.FLURRY_OF_BLOWS.value,
                description="Only Monks can use Flurry of Blows"
            )

        # Check ki points
        ki_points = stats.get("ki_points", 0)
        if ki_points < 1:
            return ActionResult(
                success=False,
                action_type=BonusActionType.FLURRY_OF_BLOWS.value,
                description="Not enough ki points (need 1)"
            )

        if not target_id:
            return ActionResult(
                success=False,
                action_type=BonusActionType.FLURRY_OF_BLOWS.value,
                description="No target specified"
            )

        target = self.state.initiative_tracker.get_combatant(target_id)
        if not target or not target.is_active:
            return ActionResult(
                success=False,
                action_type=BonusActionType.FLURRY_OF_BLOWS.value,
                description="Invalid target"
            )

        # Check range
        attacker_pos = self.state.positions.get(combatant.id)
        target_pos = self.state.positions.get(target_id)
        if attacker_pos and target_pos:
            dx = abs(target_pos[0] - attacker_pos[0])
            dy = abs(target_pos[1] - attacker_pos[1])
            if max(dx, dy) > 1:
                return ActionResult(
                    success=False,
                    action_type=BonusActionType.FLURRY_OF_BLOWS.value,
                    description="Target not in melee range"
                )

        # Spend ki
        self.state.combatant_stats[combatant.id]["ki_points"] = ki_points - 1

        # Get Martial Arts die
        level = stats.get("level", 1)
        if level >= 17:
            martial_arts_die = "1d12"
        elif level >= 11:
            martial_arts_die = "1d10"
        elif level >= 5:
            martial_arts_die = "1d8"
        else:
            martial_arts_die = "1d6"

        from app.core.rules_engine import resolve_attack, apply_damage, DamageType
        dex_mod = stats.get("dex_mod", 0)
        str_mod = stats.get("str_mod", 0)
        ability_mod = max(dex_mod, str_mod)
        proficiency = 2 + ((level - 1) // 4)
        attack_bonus = ability_mod + proficiency

        target_stats = self.state.combatant_stats.get(target_id, {})
        target_ac = target_stats.get("ac", target.armor_class)

        total_damage = 0
        hits = 0
        descriptions = []

        # Two attacks
        for i in range(2):
            if not target.is_active:
                break

            attack_result = resolve_attack(
                attack_bonus=attack_bonus,
                target_ac=target_ac,
                damage_dice=martial_arts_die,
                damage_modifier=ability_mod,
                damage_type=DamageType.BLUDGEONING
            )

            if attack_result.hit:
                hits += 1
                current_hp = self.state.combatant_stats.get(target_id, {}).get("current_hp", target.current_hp)
                new_hp, damage_dealt, _ = apply_damage(
                    current_hp=current_hp,
                    max_hp=target_stats.get("max_hp", target.max_hp),
                    damage=attack_result.total_damage
                )
                total_damage += damage_dealt
                target.current_hp = new_hp
                if target_id in self.state.combatant_stats:
                    self.state.combatant_stats[target_id]["current_hp"] = new_hp

                if new_hp <= 0:
                    target.is_active = False
                    descriptions.append(f"Strike {i+1}: {damage_dealt} damage - {target.name} is defeated!")
                else:
                    descriptions.append(f"Strike {i+1}: {damage_dealt} damage")
            else:
                descriptions.append(f"Strike {i+1}: Miss")

        desc = f"{combatant.name} uses Flurry of Blows! " + ", ".join(descriptions)

        self.state.add_event(
            "flurry_of_blows",
            desc,
            combatant_id=combatant.id,
            data={"target_id": target_id, "total_damage": total_damage, "hits": hits}
        )

        return ActionResult(
            success=True,
            action_type=BonusActionType.FLURRY_OF_BLOWS.value,
            description=desc,
            damage_dealt=total_damage,
            target_id=target_id,
            extra_data={
                "hits": hits,
                "ki_spent": 1,
                "ki_remaining": ki_points - 1,
            }
        )

    def _handle_patient_defense(
        self,
        target_id: Optional[str],
        **kwargs
    ) -> ActionResult:
        """
        Handle Monk's Patient Defense - Dodge as bonus action (costs 1 ki).
        """
        combatant = self.get_current_combatant()
        if not combatant:
            return ActionResult(
                success=False,
                action_type=BonusActionType.PATIENT_DEFENSE.value,
                description="No current combatant"
            )

        stats = self.state.combatant_stats.get(combatant.id, {})
        class_id = stats.get("class", "").lower()

        if class_id != "monk":
            return ActionResult(
                success=False,
                action_type=BonusActionType.PATIENT_DEFENSE.value,
                description="Only Monks can use Patient Defense"
            )

        ki_points = stats.get("ki_points", 0)
        if ki_points < 1:
            return ActionResult(
                success=False,
                action_type=BonusActionType.PATIENT_DEFENSE.value,
                description="Not enough ki points (need 1)"
            )

        # Spend ki and apply dodge
        self.state.combatant_stats[combatant.id]["ki_points"] = ki_points - 1
        if "dodging" not in combatant.conditions:
            combatant.conditions.append("dodging")

        desc = f"{combatant.name} uses Patient Defense (1 ki), taking the Dodge action"

        self.state.add_event(
            "patient_defense",
            desc,
            combatant_id=combatant.id,
            data={"ki_spent": 1, "ki_remaining": ki_points - 1}
        )

        return ActionResult(
            success=True,
            action_type=BonusActionType.PATIENT_DEFENSE.value,
            description=desc,
            effects_applied=["dodging"],
            extra_data={
                "ki_spent": 1,
                "ki_remaining": ki_points - 1,
            }
        )

    def _handle_step_of_the_wind(
        self,
        target_id: Optional[str],
        step_type: str = "dash",
        **kwargs
    ) -> ActionResult:
        """
        Handle Monk's Step of the Wind - Dash or Disengage as bonus action (costs 1 ki).
        Also doubles jump distance for the turn.
        """
        combatant = self.get_current_combatant()
        if not combatant:
            return ActionResult(
                success=False,
                action_type=BonusActionType.STEP_OF_THE_WIND.value,
                description="No current combatant"
            )

        stats = self.state.combatant_stats.get(combatant.id, {})
        class_id = stats.get("class", "").lower()

        if class_id != "monk":
            return ActionResult(
                success=False,
                action_type=BonusActionType.STEP_OF_THE_WIND.value,
                description="Only Monks can use Step of the Wind"
            )

        ki_points = stats.get("ki_points", 0)
        if ki_points < 1:
            return ActionResult(
                success=False,
                action_type=BonusActionType.STEP_OF_THE_WIND.value,
                description="Not enough ki points (need 1)"
            )

        step_type = step_type.lower()
        if step_type not in ["dash", "disengage"]:
            return ActionResult(
                success=False,
                action_type=BonusActionType.STEP_OF_THE_WIND.value,
                description="step_type must be 'dash' or 'disengage'"
            )

        # Spend ki
        self.state.combatant_stats[combatant.id]["ki_points"] = ki_points - 1

        effects = []
        if step_type == "dash":
            speed = self._get_effective_speed(combatant.id, stats)
            desc = f"{combatant.name} uses Step of the Wind (Dash), gaining {speed}ft movement"
            effects.append("step_of_wind_dash")
        else:
            if "disengaged" not in combatant.conditions:
                combatant.conditions.append("disengaged")
            desc = f"{combatant.name} uses Step of the Wind (Disengage), avoiding opportunity attacks"
            effects.append("disengaged")

        self.state.add_event(
            "step_of_the_wind",
            desc,
            combatant_id=combatant.id,
            data={"step_type": step_type, "ki_spent": 1}
        )

        return ActionResult(
            success=True,
            action_type=BonusActionType.STEP_OF_THE_WIND.value,
            description=desc,
            effects_applied=effects,
            extra_data={
                "step_type": step_type,
                "ki_spent": 1,
                "ki_remaining": ki_points - 1,
            }
        )

    def use_action_surge(self) -> ActionResult:
        """
        Use Fighter's Action Surge to gain an additional action.

        D&D 5e Action Surge (Level 2+):
        - Gain one additional action this turn
        - Can only use once per turn
        - Resets on short or long rest
        - At level 17, can use twice per rest (but still once per turn)

        Returns:
            ActionResult with action surge status
        """
        combatant = self.get_current_combatant()
        if not combatant:
            return ActionResult(
                success=False,
                action_type="action_surge",
                description="No current combatant"
            )

        stats = self.state.combatant_stats.get(combatant.id, {})
        class_id = stats.get("class", "").lower()
        level = stats.get("level", 1)

        # Check if Fighter
        if class_id != "fighter":
            return ActionResult(
                success=False,
                action_type="action_surge",
                description="Only Fighters have Action Surge"
            )

        # Check level requirement
        if level < 2:
            return ActionResult(
                success=False,
                action_type="action_surge",
                description="Action Surge requires Fighter level 2"
            )

        # Check if already used this turn
        if self.state.current_turn.action_surge_used:
            return ActionResult(
                success=False,
                action_type="action_surge",
                description="Action Surge already used this turn"
            )

        # Check uses remaining
        uses = stats.get("action_surge_uses", 0)
        if uses <= 0:
            return ActionResult(
                success=False,
                action_type="action_surge",
                description="No Action Surge uses remaining! Take a short or long rest to recover."
            )

        # Grant extra action
        self.state.current_turn.action_taken = False  # Reset action availability
        self.state.current_turn.attacks_made = 0      # Reset attack counter
        self.state.current_turn.action_surge_used = True
        self.state.combatant_stats[combatant.id]["action_surge_uses"] -= 1

        desc = f"{combatant.name} uses Action Surge! An additional action is available!"

        self.state.add_event(
            "action_surge",
            desc,
            combatant_id=combatant.id,
            data={"uses_remaining": uses - 1}
        )

        return ActionResult(
            success=True,
            action_type="action_surge",
            description=desc,
            extra_data={
                "action_surge_uses_remaining": uses - 1,
                "action_available": True
            }
        )

    def use_divine_smite(self, slot_level: int, target_id: str) -> ActionResult:
        """
        Use Paladin's Divine Smite after a successful hit.

        D&D 5e Divine Smite (Level 2+):
        - Expend spell slot to deal extra radiant damage
        - 2d8 + 1d8 per slot level above 1st (max 5d8)
        - +1d8 vs undead or fiends
        - Can be used on any hit, decided after knowing hit succeeded

        Args:
            slot_level: Spell slot level to expend (1-5)
            target_id: ID of the target to damage

        Returns:
            ActionResult with Divine Smite damage
        """
        combatant = self.get_current_combatant()
        if not combatant:
            return ActionResult(
                success=False,
                action_type="divine_smite",
                description="No current combatant"
            )

        stats = self.state.combatant_stats.get(combatant.id, {})
        class_id = stats.get("class", "").lower()
        level = stats.get("level", 1)

        # Check if Paladin
        if class_id != "paladin":
            return ActionResult(
                success=False,
                action_type="divine_smite",
                description="Only Paladins can use Divine Smite"
            )

        # Check level requirement
        if level < 2:
            return ActionResult(
                success=False,
                action_type="divine_smite",
                description="Divine Smite requires Paladin level 2"
            )

        # Check spell slot availability
        spell_slots = stats.get("spell_slots", {})
        # Convert keys to int if needed
        slot_key = str(slot_level) if str(slot_level) in spell_slots else slot_level
        available = spell_slots.get(slot_key, 0)

        if available <= 0:
            return ActionResult(
                success=False,
                action_type="divine_smite",
                description=f"No level {slot_level} spell slots remaining"
            )

        # Get target info for undead/fiend bonus
        target = self.state.initiative_tracker.get_combatant(target_id)
        target_stats = self.state.combatant_stats.get(target_id, {})
        creature_type = target_stats.get("creature_type", "humanoid").lower()
        is_undead_or_fiend = creature_type in ["undead", "fiend"]

        # Calculate and deal Divine Smite damage
        from app.core.class_features import use_divine_smite
        smite_result = use_divine_smite(slot_level, is_undead_or_fiend)

        smite_damage = smite_result.value

        # Apply damage to target
        if target:
            current_hp = target_stats.get("current_hp", target.current_hp)
            new_hp = max(0, current_hp - smite_damage)

            target.current_hp = new_hp
            if target_id in self.state.combatant_stats:
                self.state.combatant_stats[target_id]["current_hp"] = new_hp

            # Check if target defeated
            if new_hp <= 0:
                target.is_active = False
                self.state.add_event(
                    "combatant_defeated",
                    f"{target.name} is defeated by Divine Smite!",
                    combatant_id=target_id
                )

        # Consume spell slot
        if str(slot_level) in spell_slots:
            spell_slots[str(slot_level)] -= 1
        else:
            spell_slots[slot_level] -= 1
        self.state.combatant_stats[combatant.id]["spell_slots"] = spell_slots

        # D&D 2024: Divine Smite is now a spell that costs a bonus action
        self.state.current_turn.bonus_action_taken = True

        target_name = target.name if target else "target"
        # Get damage type from smite result (2024: force, 2014: radiant)
        damage_type = smite_result.extra_data.get("damage_type", "radiant")
        desc = f"{combatant.name} uses Divine Smite! {smite_damage} {damage_type} damage to {target_name}!"
        if is_undead_or_fiend:
            desc += " (+1d8 vs undead/fiend)"

        self.state.add_event(
            "divine_smite",
            desc,
            combatant_id=combatant.id,
            data={
                "damage": smite_damage,
                "damage_type": damage_type,
                "slot_level": slot_level,
                "target_id": target_id,
                "vs_undead_fiend": is_undead_or_fiend
            }
        )

        return ActionResult(
            success=True,
            action_type="divine_smite",
            description=desc,
            damage_dealt=smite_damage,
            target_id=target_id,
            extra_data={
                "smite_damage": smite_damage,
                "damage_type": damage_type,
                "slot_level_used": slot_level,
                "target_hp": target.current_hp if target else 0,
                "target_defeated": not target.is_active if target else False,
                "vs_undead_fiend": is_undead_or_fiend
            }
        )

    def use_stunning_strike(self, target_id: str) -> ActionResult:
        """
        Use Monk's Stunning Strike after a successful melee hit.

        D&D 5e Stunning Strike (Level 5+):
        - Costs 1 Ki point
        - Target must make CON save or be stunned until end of your next turn
        - Can be used on any melee hit

        Args:
            target_id: ID of the target to attempt to stun

        Returns:
            ActionResult with Stunning Strike outcome
        """
        combatant = self.get_current_combatant()
        if not combatant:
            return ActionResult(
                success=False,
                action_type="stunning_strike",
                description="No current combatant"
            )

        stats = self.state.combatant_stats.get(combatant.id, {})
        class_id = stats.get("class", "").lower()
        level = stats.get("level", 1)

        # Check if Monk
        if class_id != "monk":
            return ActionResult(
                success=False,
                action_type="stunning_strike",
                description="Only Monks can use Stunning Strike"
            )

        # Check level requirement (level 5)
        if level < 5:
            return ActionResult(
                success=False,
                action_type="stunning_strike",
                description="Stunning Strike requires Monk level 5"
            )

        # Check Ki points
        ki_points = stats.get("ki_points", 0)
        if ki_points < 1:
            return ActionResult(
                success=False,
                action_type="stunning_strike",
                description="Not enough Ki points (need 1)"
            )

        # Get target
        target = self.state.initiative_tracker.get_combatant(target_id)
        if not target:
            return ActionResult(
                success=False,
                action_type="stunning_strike",
                description="Invalid target"
            )

        target_stats = self.state.combatant_stats.get(target_id, {})

        # Calculate Ki save DC: 8 + proficiency + WIS mod
        wisdom = stats.get("wisdom", 10)
        proficiency = 2 + ((level - 1) // 4)
        wis_mod = (wisdom - 10) // 2
        ki_save_dc = 8 + proficiency + wis_mod

        # Spend Ki point
        self.state.combatant_stats[combatant.id]["ki_points"] = ki_points - 1

        # Target makes CON save
        target_con = target_stats.get("constitution", 10)
        con_mod = (target_con - 10) // 2
        target_level = target_stats.get("level", target_stats.get("cr", 1))
        if isinstance(target_level, float):
            target_level = max(1, int(target_level))

        # Check if target is proficient in CON saves
        save_proficiencies = target_stats.get("save_proficiencies", [])
        target_proficient = "constitution" in [s.lower() for s in save_proficiencies]

        save_bonus = con_mod
        if target_proficient:
            target_prof = 2 + ((target_level - 1) // 4)
            save_bonus += target_prof

        # Roll the save
        import random
        roll = random.randint(1, 20)
        total = roll + save_bonus
        save_success = total >= ki_save_dc

        if save_success:
            desc = (
                f"{combatant.name} uses Stunning Strike on {target.name}! "
                f"CON save: {roll} + {save_bonus} = {total} vs DC {ki_save_dc} - Success! "
                f"Not stunned."
            )
            self.state.add_event(
                "stunning_strike",
                desc,
                combatant_id=combatant.id,
                data={
                    "target_id": target_id,
                    "ki_spent": 1,
                    "ki_remaining": ki_points - 1,
                    "save_dc": ki_save_dc,
                    "save_roll": roll,
                    "save_total": total,
                    "stunned": False,
                }
            )
            return ActionResult(
                success=True,
                action_type="stunning_strike",
                description=desc,
                target_id=target_id,
                extra_data={
                    "stunned": False,
                    "save_roll": roll,
                    "save_total": total,
                    "save_dc": ki_save_dc,
                    "ki_spent": 1,
                    "ki_remaining": ki_points - 1,
                }
            )

        # Target failed - apply stunned condition
        from app.core.condition_effects import apply_condition

        current_conditions = target_stats.get("conditions", [])
        new_conditions, msg = apply_condition(current_conditions, "stunned")
        self.state.combatant_stats[target_id]["conditions"] = new_conditions

        # Track when the stun ends (end of monk's next turn)
        if "condition_durations" not in self.state.combatant_stats[target_id]:
            self.state.combatant_stats[target_id]["condition_durations"] = {}
        self.state.combatant_stats[target_id]["condition_durations"]["stunned"] = {
            "source_id": combatant.id,
            "ends_on": "end_of_source_next_turn",
        }

        desc = (
            f"{combatant.name} uses Stunning Strike on {target.name}! "
            f"CON save: {roll} + {save_bonus} = {total} vs DC {ki_save_dc} - Failed! "
            f"{target.name} is stunned until the end of {combatant.name}'s next turn!"
        )

        self.state.add_event(
            "stunning_strike",
            desc,
            combatant_id=combatant.id,
            data={
                "target_id": target_id,
                "ki_spent": 1,
                "ki_remaining": ki_points - 1,
                "save_dc": ki_save_dc,
                "save_roll": roll,
                "save_total": total,
                "stunned": True,
            }
        )

        return ActionResult(
            success=True,
            action_type="stunning_strike",
            description=desc,
            target_id=target_id,
            extra_data={
                "stunned": True,
                "save_roll": roll,
                "save_total": total,
                "save_dc": ki_save_dc,
                "ki_spent": 1,
                "ki_remaining": ki_points - 1,
            }
        )

    def _handle_attack(
        self,
        target_id: Optional[str],
        weapon_name: str = "unarmed",
        **kwargs
    ) -> ActionResult:
        """
        Handle an attack action with D&D 5e rules:
        - Range checking for ranged weapons
        - Disadvantage at long range or close range with ranged
        - Extra Attack tracking
        - Two-Weapon Fighting enablement
        """
        if not target_id:
            return ActionResult(
                success=False,
                action_type=ActionType.ATTACK.value,
                description="No target specified"
            )

        attacker = self.get_current_combatant()
        if not attacker:
            return ActionResult(
                success=False,
                action_type=ActionType.ATTACK.value,
                description="No current combatant"
            )

        target = self.state.initiative_tracker.get_combatant(target_id)
        if not target:
            return ActionResult(
                success=False,
                action_type=ActionType.ATTACK.value,
                description="Target not found"
            )

        if not target.is_active:
            return ActionResult(
                success=False,
                action_type=ActionType.ATTACK.value,
                description="Target is not active"
            )

        # Get attacker and target stats
        attacker_stats = self.state.combatant_stats.get(attacker.id, {})
        target_stats = self.state.combatant_stats.get(target.id, {})

        # Load weapon data for range and properties
        weapon_data = load_weapon_data(weapon_name)
        weapon_properties = weapon_data.get("properties", []) if weapon_data else []
        weapon_range = weapon_data.get("range", 5) if weapon_data else 5
        long_range = weapon_data.get("long_range") if weapon_data else None
        is_ranged = weapon_data and ("ammunition" in weapon_properties or "thrown" in weapon_properties)
        has_loading = "loading" in weapon_properties
        is_light = "light" in weapon_properties
        is_heavy = "heavy" in weapon_properties

        # Get positions for range calculation
        attacker_pos = self.state.positions.get(attacker.id)
        target_pos = self.state.positions.get(target.id)

        # Calculate distance in feet (Chebyshev distance * 5)
        distance_ft = 5  # Default melee range
        if attacker_pos and target_pos:
            dx = abs(attacker_pos[0] - target_pos[0])
            dy = abs(attacker_pos[1] - target_pos[1])
            distance_ft = max(dx, dy) * 5

        # Range validation for ranged weapons
        max_range = long_range if long_range else (weapon_range * 4 if is_ranged else weapon_range)
        if distance_ft > max_range:
            return ActionResult(
                success=False,
                action_type=ActionType.ATTACK.value,
                description=f"Target out of range ({distance_ft}ft, max {max_range}ft)"
            )

        # Check Loading property (limits to 1 attack with crossbows)
        if has_loading and self.state.current_turn.attacks_made > 0:
            return ActionResult(
                success=False,
                action_type=ActionType.ATTACK.value,
                description=f"{weapon_data.get('name', weapon_name)} has Loading - only one attack per action"
            )

        # Check ammunition for ranged weapons
        ammo_check = None
        if "ammunition" in weapon_properties:
            # Get or create ammunition tracker from attacker stats
            ammo_data = attacker_stats.get("ammunition")
            ammo_tracker = None
            if ammo_data:
                if isinstance(ammo_data, AmmunitionTracker):
                    ammo_tracker = ammo_data
                elif isinstance(ammo_data, dict):
                    ammo_tracker = AmmunitionTracker.from_dict(ammo_data)

            ammo_check = check_ammunition_for_attack(
                ammo_tracker, weapon_name, weapon_properties
            )

            if not ammo_check["has_ammunition"]:
                return ActionResult(
                    success=False,
                    action_type=ActionType.ATTACK.value,
                    description=ammo_check["message"]
                )

        # Determine advantage/disadvantage
        advantage = False
        disadvantage = False
        attack_reasons = []

        # D&D Rule: Long range = disadvantage
        if is_ranged and long_range and distance_ft > weapon_range:
            disadvantage = True
            attack_reasons.append("Long range (disadvantage)")

        # D&D Rule: Ranged attack within 5ft of hostile = disadvantage
        if is_ranged and distance_ft <= 5:
            disadvantage = True
            attack_reasons.append("Ranged attack in melee (disadvantage)")

        # Weapon Mastery: Vex grants advantage on next attack vs same target
        vex_targets = attacker_stats.get("vex_targets", [])
        if target_id in vex_targets:
            advantage = True
            attack_reasons.append("Vex (advantage)")
            # Remove the vex advantage (one-time use)
            vex_targets.remove(target_id)
            self.state.combatant_stats[attacker.id]["vex_targets"] = vex_targets

        # Rogue Steady Aim (2024): Grants advantage on next attack
        if "steady_aim" in attacker.conditions:
            advantage = True
            attack_reasons.append("Steady Aim (advantage)")
            # Remove steady aim after using it (one-time use per turn)
            attacker.conditions.remove("steady_aim")

        # Apply condition-based advantage/disadvantage
        attacker_conditions = attacker_stats.get("conditions", getattr(attacker, "conditions", []))
        target_conditions = target_stats.get("conditions", getattr(target, "conditions", []))

        condition_mods = get_attack_modifiers(
            attacker_conditions=attacker_conditions,
            target_conditions=target_conditions,
            is_melee=not is_ranged,
            distance_ft=distance_ft,
        )

        if condition_mods.advantage:
            advantage = True
            attack_reasons.extend(condition_mods.reasons)
        if condition_mods.disadvantage:
            disadvantage = True
            attack_reasons.extend(condition_mods.reasons)

        # D&D Rule: Small creatures have disadvantage with heavy weapons
        if is_heavy:
            attacker_size = attacker_stats.get("size", "medium")
            # Also check the combatant object for size
            if not attacker_size or attacker_size == "medium":
                attacker_size = getattr(attacker, "size", "medium") or "medium"
            if attacker_size.lower() in ["small", "tiny"]:
                disadvantage = True
                attack_reasons.append("Heavy weapon (Small creature - disadvantage)")

        # Calculate attack bonus using D&D 5e rules:
        # Attack = d20 + ability_modifier + proficiency_bonus + weapon_bonus
        attack_bonus = attacker_stats.get("attack_bonus", 0)
        ability_mod = 0

        if attack_bonus == 0:
            # Get character level for proficiency calculation
            level = attacker_stats.get("level", 1)
            # D&D 5e proficiency: starts at +2, increases every 4 levels
            proficiency_bonus = 2 + ((level - 1) // 4)

            # D&D 5e ability score rules for weapons:
            # - Finesse: use higher of STR or DEX
            # - Ranged (ammunition): use DEX
            # - Thrown (without finesse): use STR
            is_finesse = "finesse" in weapon_properties
            is_thrown = "thrown" in weapon_properties
            is_ammunition_based = "ammunition" in weapon_properties

            if is_finesse:
                # Finesse weapons can use STR or DEX (player's choice, we use higher)
                ability_mod = max(
                    attacker_stats.get("str_mod", 0),
                    attacker_stats.get("dex_mod", 0)
                )
            elif is_ammunition_based:
                # Ranged weapons with ammunition use DEX
                ability_mod = attacker_stats.get("dex_mod", 0)
            else:
                # Melee and thrown weapons use STR
                ability_mod = attacker_stats.get("str_mod", 0)

            # Weapon bonus (magical weapons, etc.)
            weapon_bonus = weapon_data.get("attack_bonus", 0) if weapon_data else 0

            # Add magic weapon bonus from equipment
            weapon_magic_bonus = attacker_stats.get("weapon_magic_bonus", 0)
            weapon_bonus += weapon_magic_bonus

            # D&D 5e attack bonus formula
            attack_bonus = ability_mod + proficiency_bonus + weapon_bonus
        else:
            # If attack_bonus was provided, extract ability_mod for damage
            ability_mod = attacker_stats.get("str_mod", 0)

        # Get target AC
        target_ac = target_stats.get("ac", target.armor_class)

        # ============================================================
        # ELEVATION BONUS (High Ground)
        # ============================================================
        elevation_bonus = 0
        elevation_reason = ""
        if self.state.grid and attacker_pos and target_pos:
            elevation_bonus, elevation_reason = get_elevation_attack_modifier(
                self.state.grid,
                attacker_pos[0], attacker_pos[1],
                target_pos[0], target_pos[1]
            )
            if elevation_bonus != 0:
                attack_bonus += elevation_bonus
                attack_reasons.append(elevation_reason)

        # ============================================================
        # COVER BONUS (applies to target AC)
        # ============================================================
        cover_bonus = 0
        if self.state.grid and attacker_pos and target_pos:
            cover_bonus = get_cover_between(
                self.state.grid,
                attacker_pos[0], attacker_pos[1],
                target_pos[0], target_pos[1]
            )

            # Check for Sharpshooter feat (ignores cover for ranged attacks)
            attacker_feats = attacker_stats.get("feats", [])
            has_sharpshooter = "sharpshooter" in attacker_feats or "Sharpshooter" in attacker_feats

            # Check for Spell Sniper feat (ignores cover for spell attacks)
            has_spell_sniper = "spell_sniper" in attacker_feats or "Spell Sniper" in attacker_feats

            # Apply cover unless feat ignores it
            if cover_bonus > 0:
                if is_ranged and has_sharpshooter:
                    attack_reasons.append(f"Sharpshooter ignores {'+' + str(cover_bonus)} cover")
                    cover_bonus = 0
                elif has_spell_sniper:
                    # Spell Sniper would apply to spell attacks (not regular weapon attacks)
                    pass  # Only applies to spell attacks, not weapon attacks
                else:
                    target_ac += cover_bonus
                    cover_name = "half cover" if cover_bonus == 2 else "three-quarters cover"
                    attack_reasons.append(f"Target has {cover_name} (+{cover_bonus} AC)")

        # Calculate damage modifier (ability mod for melee, DEX for finesse/thrown ranged)
        # Note: Off-hand attacks don't add ability modifier to damage (handled in _handle_offhand)
        damage_modifier = ability_mod
        if weapon_data:
            damage_modifier += weapon_data.get("damage_bonus", 0)

        # Add magic weapon bonus to damage
        weapon_magic_bonus = attacker_stats.get("weapon_magic_bonus", 0)
        damage_modifier += weapon_magic_bonus

        # Check if attacker is a player (for 2024 crit rules)
        from app.core.initiative import CombatantType
        attacker_is_player = attacker.combatant_type == CombatantType.PLAYER

        # Determine critical hit range (Champion gets expanded crit range)
        crit_range = 20
        auto_crit = False  # For Assassinate
        if attacker_is_player:
            class_id = attacker_stats.get("class_id", attacker_stats.get("class", "")).lower()
            subclass_id = attacker_stats.get("subclass_id", "").lower()
            level = attacker_stats.get("level", 1)
            if class_id == "fighter" and subclass_id == "champion":
                crit_range = get_critical_range(subclass_id, level)

            # ============================================================
            # ASSASSINATE (Assassin Rogue) - Advantage and auto-crit on
            # surprised targets or targets that haven't acted yet in round 1
            # ============================================================
            if class_id == "rogue" and subclass_id == "assassin" and level >= 3:
                target_conditions = target_stats.get("conditions", getattr(target, "conditions", []))
                target_surprised = "surprised" in target_conditions

                # Check if it's round 1 and target hasn't acted yet
                current_round = self.state.initiative_tracker.current_round
                attacker_first = False

                if current_round == 1:
                    # Check initiative order to see if attacker goes before target
                    initiative_order = self.state.initiative_tracker.get_initiative_order()
                    try:
                        attacker_idx = initiative_order.index(attacker.id)
                        target_idx = initiative_order.index(target.id)
                        attacker_first = attacker_idx < target_idx
                    except ValueError:
                        pass

                # Apply Assassinate bonus
                from app.core.subclass_registry import assassinate_bonus
                assassinate_result = assassinate_bonus(target_surprised, attacker_first)

                if assassinate_result["advantage"]:
                    advantage = True
                    self.state.add_event(
                        "assassinate",
                        assassinate_result["description"],
                        combatant_id=attacker.id
                    )

                if assassinate_result["auto_crit"]:
                    auto_crit = True

        # Resolve the attack with advantage/disadvantage
        attack_result = resolve_attack(
            attack_bonus=attack_bonus,
            target_ac=target_ac,
            damage_dice=weapon_data.get("damage", attacker_stats.get("damage_dice", "1d6")) if weapon_data else attacker_stats.get("damage_dice", "1d6"),
            damage_modifier=damage_modifier,
            damage_type=weapon_data.get("damage_type", attacker_stats.get("damage_type", "slashing")) if weapon_data else attacker_stats.get("damage_type", "slashing"),
            advantage=advantage,
            disadvantage=disadvantage,
            attacker_is_player=attacker_is_player,
            crit_range=crit_range,
            auto_crit=auto_crit
        )

        # Consume ammunition after attack (hit or miss, ammunition is used)
        ammo_consumed = None
        if "ammunition" in weapon_properties and ammo_check:
            ammo_data = attacker_stats.get("ammunition")
            if ammo_data:
                if isinstance(ammo_data, AmmunitionTracker):
                    ammo_tracker = ammo_data
                elif isinstance(ammo_data, dict):
                    ammo_tracker = AmmunitionTracker.from_dict(ammo_data)
                else:
                    ammo_tracker = None

                if ammo_tracker:
                    ammo_consumed = consume_ammunition_for_attack(
                        ammo_tracker, weapon_name, weapon_properties
                    )
                    # Save updated ammunition tracker
                    self.state.combatant_stats[attacker.id]["ammunition"] = ammo_tracker.to_dict()

        # Apply damage if hit
        damage_dealt = 0
        sneak_attack_damage = 0
        rage_damage = 0
        can_divine_smite = False
        available_spell_slots = {}
        concentration_result = None

        if attack_result.hit:
            # Get class info for class features
            class_id = attacker_stats.get("class", "").lower()
            level = attacker_stats.get("level", 1)

            # Calculate base damage
            total_damage = attack_result.total_damage

            # ============================================================
            # SNEAK ATTACK (Rogue) - Auto-applies when conditions are met
            # ============================================================
            if class_id == "rogue" and not self.state.current_turn.sneak_attack_used:
                # Check Sneak Attack conditions:
                # 1. Using finesse or ranged weapon
                # 2. Have advantage OR ally adjacent to target (within 5ft)

                can_sneak_attack = False
                sneak_attack_reason = ""

                if "finesse" in weapon_properties or is_ranged:
                    # Check for advantage
                    if advantage and not disadvantage:
                        can_sneak_attack = True
                        sneak_attack_reason = "advantage"
                    else:
                        # Check for ally adjacent to target
                        for ally_id, ally_pos in self.state.positions.items():
                            if ally_id == attacker.id or ally_id == target_id:
                                continue
                            ally = self.state.initiative_tracker.get_combatant(ally_id)
                            if ally and ally.is_active and ally.combatant_type == attacker.combatant_type:
                                # Check if ally is within 5ft of target (1 square)
                                tdx = abs(ally_pos[0] - target_pos[0])
                                tdy = abs(ally_pos[1] - target_pos[1])
                                if max(tdx, tdy) <= 1:
                                    can_sneak_attack = True
                                    sneak_attack_reason = f"ally ({ally.name}) adjacent"
                                    break

                if can_sneak_attack:
                    from app.core.class_features import roll_sneak_attack
                    sneak_result = roll_sneak_attack(level)
                    sneak_attack_damage = sneak_result.value
                    total_damage += sneak_attack_damage
                    self.state.current_turn.sneak_attack_used = True

                    self.state.add_event(
                        "sneak_attack",
                        f"{attacker.name} deals {sneak_attack_damage} Sneak Attack damage! ({sneak_attack_reason})",
                        combatant_id=attacker.id,
                        data={
                            "damage": sneak_attack_damage,
                            "dice": sneak_result.extra_data.get("dice"),
                            "reason": sneak_attack_reason
                        }
                    )

            # ============================================================
            # RAGE DAMAGE BONUS (Barbarian) - Adds to melee attacks
            # ============================================================
            if not is_ranged and attacker_stats.get("is_raging", False):
                rage_damage = attacker_stats.get("rage_damage_bonus", 0)
                if rage_damage > 0:
                    total_damage += rage_damage

            # ============================================================
            # DIVINE SMITE OPPORTUNITY (Paladin) - Returns option to player
            # D&D 2024: Divine Smite is a spell that costs a bonus action
            # ============================================================
            if class_id == "paladin" and level >= 2:
                # Check if bonus action is still available (D&D 2024 requirement)
                bonus_action_available = not self.state.current_turn.bonus_action_taken
                if bonus_action_available:
                    spell_slots = attacker_stats.get("spell_slots", {})
                    # Convert string keys to int if needed
                    if spell_slots:
                        available_spell_slots = {
                            int(k) if isinstance(k, str) else k: v
                            for k, v in spell_slots.items() if v > 0
                        }
                        if available_spell_slots:
                            can_divine_smite = True

            # Check for resistance/immunity/vulnerability to damage type
            damage_type = attack_result.damage_type
            resistances = target_stats.get("resistances", [])
            immunities = target_stats.get("immunities", [])
            vulnerabilities = target_stats.get("vulnerabilities", [])

            has_resistance = damage_type in resistances
            has_immunity = damage_type in immunities
            has_vulnerability = damage_type in vulnerabilities

            new_hp, damage_dealt, is_unconscious = apply_damage(
                current_hp=target_stats.get("current_hp", target.current_hp),
                max_hp=target_stats.get("max_hp", target.max_hp),
                damage=total_damage,
                resistance=has_resistance,
                immunity=has_immunity,
                vulnerability=has_vulnerability
            )

            # Update target HP
            target.current_hp = new_hp
            if target.id in self.state.combatant_stats:
                self.state.combatant_stats[target.id]["current_hp"] = new_hp

            # Check if target is defeated
            if new_hp <= 0:
                target.is_active = False
                self.state.add_event(
                    "combatant_defeated",
                    f"{target.name} is defeated!",
                    combatant_id=target.id
                )

            # ============================================================
            # CONCENTRATION CHECK - Target must save to maintain concentration
            # ============================================================
            concentration_result = None
            if damage_dealt > 0:
                concentration_result = self._check_concentration_on_damage(
                    target_id=target.id,
                    damage_dealt=damage_dealt,
                    damage_source=f"attack from {attacker.name}"
                )

        # ============================================================
        # WEAPON MASTERY (2024 Rule) - Apply mastery effects
        # ============================================================
        mastery_effect = None
        mastery_extra_damage = 0
        mastery_description = ""

        from app.core.rules_config import is_weapon_mastery_enabled
        if is_weapon_mastery_enabled() and attacker_is_player and weapon_name:
            from app.core.weapon_mastery import (
                get_weapon_mastery, apply_weapon_mastery, MasteryType
            )

            # Check if character has weapon mastery for this weapon
            weapon_key = weapon_name.lower().replace(" ", "_")
            mastery_type = get_weapon_mastery(weapon_key)

            if mastery_type:
                # Get attacker's mastered weapons (if configured)
                mastered_weapons = attacker_stats.get("mastered_weapons", [])

                # Check if character has mastery for this weapon type
                # If no mastered_weapons configured, assume they have all class masteries
                has_mastery = (
                    not mastered_weapons or
                    weapon_key in mastered_weapons or
                    mastery_type.value in mastered_weapons
                )

                if has_mastery:
                    # Calculate save DC: 8 + proficiency + ability mod
                    level = attacker_stats.get("level", 1)
                    proficiency_bonus = 2 + ((level - 1) // 4)
                    save_dc = 8 + proficiency_bonus + attacker_stats.get("str_mod", 0)

                    # Find adjacent enemies for Cleave
                    adjacent_enemies = []
                    if mastery_type == MasteryType.CLEAVE and attack_result.hit:
                        target_pos = self.state.positions.get(target.id)
                        if target_pos:
                            for eid, epos in self.state.positions.items():
                                if eid == target.id or eid == attacker.id:
                                    continue
                                e_combatant = self.state.initiative_tracker.get_combatant(eid)
                                if e_combatant and e_combatant.is_active:
                                    # Check if enemy type (not player ally)
                                    if e_combatant.combatant_type != attacker.combatant_type:
                                        dx = abs(epos[0] - target_pos[0])
                                        dy = abs(epos[1] - target_pos[1])
                                        if max(dx, dy) <= 1:  # Adjacent
                                            adjacent_enemies.append(eid)

                    # Apply weapon mastery effect
                    mastery_effect = apply_weapon_mastery(
                        mastery_type=mastery_type,
                        hit=attack_result.hit,
                        attacker_data={
                            "str_mod": attacker_stats.get("str_mod", 0),
                            "dex_mod": attacker_stats.get("dex_mod", 0),
                            "proficiency": proficiency_bonus,
                            "weapon_finesse": "finesse" in weapon_properties,
                        },
                        target_data={
                            "id": target.id,
                            "str_save_mod": target_stats.get("str_save_mod", target_stats.get("str_mod", 0)),
                        },
                        combat_context={
                            "adjacent_enemies": adjacent_enemies,
                        }
                    )

                    if mastery_effect and mastery_effect.success:
                        mastery_description = f" [{mastery_effect.description}]"

                        # Handle mastery extra damage (Graze, Cleave)
                        if mastery_effect.extra_damage > 0:
                            mastery_extra_damage = mastery_effect.extra_damage

                            # For Graze, apply damage to original target
                            if mastery_type == MasteryType.GRAZE:
                                new_hp, graze_dealt, _ = apply_damage(
                                    current_hp=target_stats.get("current_hp", target.current_hp),
                                    max_hp=target_stats.get("max_hp", target.max_hp),
                                    damage=mastery_extra_damage
                                )
                                target.current_hp = new_hp
                                if target.id in self.state.combatant_stats:
                                    self.state.combatant_stats[target.id]["current_hp"] = new_hp
                                damage_dealt += graze_dealt

                                # Concentration check for Graze damage
                                if graze_dealt > 0:
                                    self._check_concentration_on_damage(
                                        target_id=target.id,
                                        damage_dealt=graze_dealt,
                                        damage_source="Graze mastery"
                                    )

                            # For Cleave, apply damage to secondary target
                            elif mastery_type == MasteryType.CLEAVE and mastery_effect.affected_entity_ids:
                                cleave_target_id = mastery_effect.affected_entity_ids[0]
                                cleave_target = self.state.initiative_tracker.get_combatant(cleave_target_id)
                                cleave_stats = self.state.combatant_stats.get(cleave_target_id, {})
                                if cleave_target:
                                    new_hp, cleave_dealt, _ = apply_damage(
                                        current_hp=cleave_stats.get("current_hp", cleave_target.current_hp),
                                        max_hp=cleave_stats.get("max_hp", cleave_target.max_hp),
                                        damage=mastery_extra_damage
                                    )
                                    cleave_target.current_hp = new_hp
                                    if cleave_target_id in self.state.combatant_stats:
                                        self.state.combatant_stats[cleave_target_id]["current_hp"] = new_hp

                                    # Concentration check for Cleave damage
                                    if cleave_dealt > 0:
                                        self._check_concentration_on_damage(
                                            target_id=cleave_target_id,
                                            damage_dealt=cleave_dealt,
                                            damage_source="Cleave mastery"
                                        )

                        # Handle target conditions (Sap, Slow, Prone, etc.)
                        if mastery_effect.target_condition:
                            if mastery_effect.target_condition not in target.conditions:
                                target.conditions.append(mastery_effect.target_condition)

                        # Handle Vex (grants advantage on next attack vs target)
                        if mastery_effect.grants_advantage:
                            # Store vexed state for this attacker against this target
                            if "vex_targets" not in self.state.combatant_stats.get(attacker.id, {}):
                                self.state.combatant_stats[attacker.id]["vex_targets"] = []
                            self.state.combatant_stats[attacker.id]["vex_targets"].append(target.id)

                        # Log mastery event
                        self.state.add_event(
                            "weapon_mastery",
                            f"{attacker.name} uses {mastery_type.value.capitalize()} mastery! {mastery_effect.description}",
                            combatant_id=attacker.id,
                            data={
                                "mastery_type": mastery_type.value,
                                "effect": mastery_effect.description,
                                "extra_damage": mastery_extra_damage,
                                "condition_applied": mastery_effect.target_condition,
                            }
                        )

        # Build description
        if attack_result.critical_hit:
            desc = f"{attacker.name} critically hits {target.name} for {damage_dealt} {attack_result.damage_type} damage!"
        elif attack_result.hit:
            desc = f"{attacker.name} hits {target.name} for {damage_dealt} {attack_result.damage_type} damage"
        elif attack_result.critical_miss:
            desc = f"{attacker.name} fumbles their attack against {target.name}!"
        else:
            desc = f"{attacker.name} misses {target.name}"

        # Add mastery description if applicable
        if mastery_description:
            desc += mastery_description

        # Use attack counter (Extra Attack tracking)
        attacks_remaining = self.state.current_turn.use_attack()

        # Two-Weapon Fighting: Enable offhand attack if using light melee weapon
        if is_light and not is_ranged:
            self.state.current_turn.can_offhand_attack = True
            self.state.current_turn.main_hand_weapon = weapon_name

        # Log the event
        self.state.add_event(
            "attack",
            desc,
            combatant_id=attacker.id,
            data={
                "target_id": target.id,
                "hit": attack_result.hit,
                "damage": damage_dealt,
                "critical": attack_result.critical_hit,
                "roll": attack_result.attack_roll,
                "weapon": weapon_name,
                "distance": distance_ft,
                "disadvantage": disadvantage
            }
        )

        # Build damage roll breakdown for frontend display
        damage_roll_info = None
        if attack_result.hit and attack_result.damage:
            damage_roll_info = {
                "rolls": attack_result.damage.rolls if hasattr(attack_result.damage, 'rolls') else [],
                "modifier": attack_result.damage.modifier if hasattr(attack_result.damage, 'modifier') else 0,
                "total": damage_dealt,
                "dice_notation": attack_result.damage.dice_notation if hasattr(attack_result.damage, 'dice_notation') else "",
                "is_critical": attack_result.critical_hit,
            }

        # Check if this missed melee attack could trigger Riposte
        is_melee_attack = not is_ranged
        could_trigger_riposte = (
            is_melee_attack and
            not attack_result.hit and
            distance_ft <= 5  # Within melee reach
        )

        return ActionResult(
            success=True,
            action_type=ActionType.ATTACK.value,
            description=desc,
            damage_dealt=damage_dealt,
            target_id=target_id,
            extra_data={
                "hit": attack_result.hit,
                "critical_hit": attack_result.critical_hit,
                "critical_miss": attack_result.critical_miss,
                "attack_roll": attack_result.attack_roll,
                "target_ac": target_ac,
                "target_hp": target.current_hp,
                "target_defeated": not target.is_active,
                # Damage roll breakdown for frontend display
                "damage_roll": damage_roll_info,
                # Extra Attack tracking
                "attacks_remaining": attacks_remaining,
                "max_attacks": self.state.current_turn.max_attacks,
                # Two-Weapon Fighting
                "can_offhand_attack": self.state.current_turn.can_offhand_attack,
                # Range info
                "weapon_name": weapon_name,
                "distance": distance_ft,
                "disadvantage": disadvantage,
                "is_melee_attack": is_melee_attack,
                # Class features
                "sneak_attack_damage": sneak_attack_damage,
                "rage_damage": rage_damage,
                "can_divine_smite": can_divine_smite,
                "available_spell_slots": available_spell_slots,
                # Weapon Mastery (2024)
                "weapon_mastery_applied": mastery_effect is not None and mastery_effect.success if mastery_effect else False,
                "weapon_mastery_type": mastery_effect.mastery_type.value if mastery_effect and mastery_effect.success else None,
                "weapon_mastery_extra_damage": mastery_extra_damage,
                # Concentration check result
                "concentration_check": concentration_result,
                # Riposte opportunity (for Battlemaster)
                "could_trigger_riposte": could_trigger_riposte,
                "attacker_id": attacker.id,
            }
        )

    def _handle_dash(self, target_id: Optional[str], **kwargs) -> ActionResult:
        """Handle a Dash action (double movement)."""
        combatant = self.get_current_combatant()
        if not combatant:
            return ActionResult(
                success=False,
                action_type=ActionType.DASH.value,
                description="No current combatant"
            )

        stats = self.state.combatant_stats.get(combatant.id, {})
        # Use effective speed (includes encumbrance penalties)
        speed = self._get_effective_speed(combatant.id, stats)

        self.state.add_event(
            "dash",
            f"{combatant.name} dashes, gaining {speed}ft of additional movement",
            combatant_id=combatant.id
        )

        return ActionResult(
            success=True,
            action_type=ActionType.DASH.value,
            description=f"{combatant.name} dashes, gaining {speed}ft of additional movement",
            extra_data={"additional_movement": speed}
        )

    def _handle_disengage(self, target_id: Optional[str], **kwargs) -> ActionResult:
        """Handle a Disengage action (no opportunity attacks).

        Note: Sentinel feat allows OA even against Disengage.
        """
        combatant = self.get_current_combatant()
        if not combatant:
            return ActionResult(
                success=False,
                action_type=ActionType.DISENGAGE.value,
                description="No current combatant"
            )

        if "disengaged" not in combatant.conditions:
            combatant.conditions.append("disengaged")

        # Check for adjacent enemies who might have Sentinel feat
        # Sentinel allows OA even when target takes Disengage
        combatant_pos = self.state.positions.get(combatant.id)
        sentinel_threats = []

        if combatant_pos:
            for enemy_id, enemy_pos in self.state.positions.items():
                if enemy_id == combatant.id:
                    continue
                enemy = self.state.initiative_tracker.get_combatant(enemy_id)
                if not enemy or not enemy.is_active:
                    continue
                # Check if enemy (different type = hostile)
                if enemy.combatant_type == combatant.combatant_type:
                    continue
                # Check if adjacent (within 5ft)
                dx = abs(enemy_pos[0] - combatant_pos[0])
                dy = abs(enemy_pos[1] - combatant_pos[1])
                if max(dx, dy) <= 1:
                    # This enemy could have Sentinel and make an OA
                    sentinel_threats.append(enemy_id)

        self.state.add_event(
            "disengage",
            f"{combatant.name} disengages, avoiding opportunity attacks",
            combatant_id=combatant.id
        )

        return ActionResult(
            success=True,
            action_type=ActionType.DISENGAGE.value,
            description=f"{combatant.name} disengages, avoiding opportunity attacks this turn",
            effects_applied=["disengaged"],
            extra_data={
                # Adjacent enemies who could use Sentinel to still make OA
                "sentinel_threat_ids": sentinel_threats,
                "could_trigger_sentinel": len(sentinel_threats) > 0,
            }
        )

    def _handle_dodge(self, target_id: Optional[str], **kwargs) -> ActionResult:
        """Handle a Dodge action (attacks have disadvantage)."""
        combatant = self.get_current_combatant()
        if not combatant:
            return ActionResult(
                success=False,
                action_type=ActionType.DODGE.value,
                description="No current combatant"
            )

        if "dodging" not in combatant.conditions:
            combatant.conditions.append("dodging")

        self.state.add_event(
            "dodge",
            f"{combatant.name} takes the Dodge action",
            combatant_id=combatant.id
        )

        return ActionResult(
            success=True,
            action_type=ActionType.DODGE.value,
            description=f"{combatant.name} dodges. Attacks against them have disadvantage until their next turn",
            effects_applied=["dodging"]
        )

    def _handle_help(self, target_id: Optional[str], **kwargs) -> ActionResult:
        """Handle a Help action (give advantage to ally)."""
        combatant = self.get_current_combatant()
        if not combatant:
            return ActionResult(
                success=False,
                action_type=ActionType.HELP.value,
                description="No current combatant"
            )

        desc = f"{combatant.name} helps an ally"
        if target_id:
            target = self.state.initiative_tracker.get_combatant(target_id)
            if target:
                if "helped" not in target.conditions:
                    target.conditions.append("helped")
                desc = f"{combatant.name} helps {target.name}, granting them advantage on their next check"

        self.state.add_event(
            "help",
            desc,
            combatant_id=combatant.id,
            data={"target_id": target_id}
        )

        return ActionResult(
            success=True,
            action_type=ActionType.HELP.value,
            description=desc,
            target_id=target_id,
            effects_applied=["helped"] if target_id else []
        )

    def _handle_hide(self, target_id: Optional[str], **kwargs) -> ActionResult:
        """Handle a Hide action."""
        combatant = self.get_current_combatant()
        if not combatant:
            return ActionResult(
                success=False,
                action_type=ActionType.HIDE.value,
                description="No current combatant"
            )

        # Roll Stealth check (simplified)
        stats = self.state.combatant_stats.get(combatant.id, {})
        dex_mod = stats.get("dex_mod", 0)
        stealth_roll = roll_d20(modifier=dex_mod)

        if "hidden" not in combatant.conditions:
            combatant.conditions.append("hidden")

        self.state.add_event(
            "hide",
            f"{combatant.name} attempts to hide (Stealth: {stealth_roll.total})",
            combatant_id=combatant.id,
            data={"stealth_roll": stealth_roll.total}
        )

        return ActionResult(
            success=True,
            action_type=ActionType.HIDE.value,
            description=f"{combatant.name} hides (Stealth: {stealth_roll.total})",
            effects_applied=["hidden"],
            extra_data={"stealth_roll": stealth_roll.total}
        )

    def _handle_ready(self, target_id: Optional[str], **kwargs) -> ActionResult:
        """Handle a Ready action."""
        combatant = self.get_current_combatant()
        if not combatant:
            return ActionResult(
                success=False,
                action_type=ActionType.READY.value,
                description="No current combatant"
            )

        trigger = kwargs.get("trigger", "a specified trigger")
        action = kwargs.get("readied_action", "an action")

        if "readied_action" not in combatant.conditions:
            combatant.conditions.append("readied_action")

        self.state.add_event(
            "ready",
            f"{combatant.name} readies {action} for when {trigger}",
            combatant_id=combatant.id,
            data={"trigger": trigger, "readied_action": action}
        )

        return ActionResult(
            success=True,
            action_type=ActionType.READY.value,
            description=f"{combatant.name} readies an action",
            effects_applied=["readied_action"],
            extra_data={"trigger": trigger, "readied_action": action}
        )

    def _handle_grapple(
        self,
        target_id: Optional[str],
        **kwargs
    ) -> ActionResult:
        """
        Handle a Grapple action.

        D&D 5e Rules:
        - Target must be no more than one size larger
        - Contested check: your Athletics vs target's Athletics or Acrobatics
        - On success, target gains "grappled" condition (speed becomes 0)
        - You can drag/carry grappled creature (half speed)
        """
        combatant = self.get_current_combatant()
        if not combatant:
            return ActionResult(
                success=False,
                action_type=ActionType.GRAPPLE.value,
                description="No current combatant"
            )

        if not target_id:
            return ActionResult(
                success=False,
                action_type=ActionType.GRAPPLE.value,
                description="No target specified for grapple"
            )

        target = self.state.initiative_tracker.get_combatant(target_id)
        if not target or not target.is_active:
            return ActionResult(
                success=False,
                action_type=ActionType.GRAPPLE.value,
                description="Invalid target"
            )

        # Check adjacency (must be within 5ft)
        attacker_pos = self.state.positions.get(combatant.id)
        target_pos = self.state.positions.get(target_id)
        if attacker_pos and target_pos:
            dx = abs(target_pos[0] - attacker_pos[0])
            dy = abs(target_pos[1] - attacker_pos[1])
            if max(dx, dy) > 1:
                return ActionResult(
                    success=False,
                    action_type=ActionType.GRAPPLE.value,
                    description="Target not in melee range"
                )

        attacker_stats = self.state.combatant_stats.get(combatant.id, {})
        target_stats = self.state.combatant_stats.get(target_id, {})

        # Check size - can only grapple creatures no more than one size larger
        size_order = ["tiny", "small", "medium", "large", "huge", "gargantuan"]
        attacker_size = attacker_stats.get("size", "medium").lower()
        target_size = target_stats.get("size", "medium").lower()
        attacker_size_idx = size_order.index(attacker_size) if attacker_size in size_order else 2
        target_size_idx = size_order.index(target_size) if target_size in size_order else 2

        if target_size_idx > attacker_size_idx + 1:
            return ActionResult(
                success=False,
                action_type=ActionType.GRAPPLE.value,
                description=f"{target.name} is too large to grapple"
            )

        # Contested check: Athletics vs Athletics or Acrobatics (target's choice)
        # For simplicity, use best modifier
        attacker_athletics = attacker_stats.get("athletics", attacker_stats.get("str_mod", 0))
        target_athletics = target_stats.get("athletics", target_stats.get("str_mod", 0))
        target_acrobatics = target_stats.get("acrobatics", target_stats.get("dex_mod", 0))
        target_escape_mod = max(target_athletics, target_acrobatics)

        # Roll contested checks
        attacker_roll = random.randint(1, 20) + attacker_athletics
        target_roll = random.randint(1, 20) + target_escape_mod

        if attacker_roll > target_roll:
            # Grapple succeeds
            if "grappled" not in target.conditions:
                target.conditions.append("grappled")

            # Track who is grappling whom
            if "grappling" not in attacker_stats:
                attacker_stats["grappling"] = []
            if target_id not in attacker_stats["grappling"]:
                attacker_stats["grappling"].append(target_id)
            target_stats["grappled_by"] = combatant.id

            desc = f"{combatant.name} grapples {target.name}! (Athletics {attacker_roll} vs {target_roll})"

            self.state.add_event(
                "grapple",
                desc,
                combatant_id=combatant.id,
                data={"target_id": target_id, "success": True}
            )

            return ActionResult(
                success=True,
                action_type=ActionType.GRAPPLE.value,
                description=desc,
                effects_applied=["grappled"],
                extra_data={
                    "target_id": target_id,
                    "grapple_success": True,
                    "attacker_roll": attacker_roll,
                    "target_roll": target_roll,
                }
            )
        else:
            desc = f"{combatant.name} fails to grapple {target.name} (Athletics {attacker_roll} vs {target_roll})"

            self.state.add_event(
                "grapple_failed",
                desc,
                combatant_id=combatant.id,
                data={"target_id": target_id, "success": False}
            )

            return ActionResult(
                success=True,  # Action was taken, just didn't succeed
                action_type=ActionType.GRAPPLE.value,
                description=desc,
                extra_data={
                    "target_id": target_id,
                    "grapple_success": False,
                    "attacker_roll": attacker_roll,
                    "target_roll": target_roll,
                }
            )

    def _handle_shove(
        self,
        target_id: Optional[str],
        shove_type: str = "prone",
        **kwargs
    ) -> ActionResult:
        """
        Handle a Shove action.

        D&D 5e Rules:
        - Target must be no more than one size larger
        - Contested check: your Athletics vs target's Athletics or Acrobatics
        - On success: knock target prone OR push 5ft away
        """
        combatant = self.get_current_combatant()
        if not combatant:
            return ActionResult(
                success=False,
                action_type=ActionType.SHOVE.value,
                description="No current combatant"
            )

        if not target_id:
            return ActionResult(
                success=False,
                action_type=ActionType.SHOVE.value,
                description="No target specified for shove"
            )

        target = self.state.initiative_tracker.get_combatant(target_id)
        if not target or not target.is_active:
            return ActionResult(
                success=False,
                action_type=ActionType.SHOVE.value,
                description="Invalid target"
            )

        shove_type = shove_type.lower()
        if shove_type not in ["prone", "push"]:
            return ActionResult(
                success=False,
                action_type=ActionType.SHOVE.value,
                description="shove_type must be 'prone' or 'push'"
            )

        # Check adjacency
        attacker_pos = self.state.positions.get(combatant.id)
        target_pos = self.state.positions.get(target_id)
        if attacker_pos and target_pos:
            dx = abs(target_pos[0] - attacker_pos[0])
            dy = abs(target_pos[1] - attacker_pos[1])
            if max(dx, dy) > 1:
                return ActionResult(
                    success=False,
                    action_type=ActionType.SHOVE.value,
                    description="Target not in melee range"
                )

        attacker_stats = self.state.combatant_stats.get(combatant.id, {})
        target_stats = self.state.combatant_stats.get(target_id, {})

        # Check size
        size_order = ["tiny", "small", "medium", "large", "huge", "gargantuan"]
        attacker_size = attacker_stats.get("size", "medium").lower()
        target_size = target_stats.get("size", "medium").lower()
        attacker_size_idx = size_order.index(attacker_size) if attacker_size in size_order else 2
        target_size_idx = size_order.index(target_size) if target_size in size_order else 2

        if target_size_idx > attacker_size_idx + 1:
            return ActionResult(
                success=False,
                action_type=ActionType.SHOVE.value,
                description=f"{target.name} is too large to shove"
            )

        # Contested check
        attacker_athletics = attacker_stats.get("athletics", attacker_stats.get("str_mod", 0))
        target_athletics = target_stats.get("athletics", target_stats.get("str_mod", 0))
        target_acrobatics = target_stats.get("acrobatics", target_stats.get("dex_mod", 0))
        target_resist_mod = max(target_athletics, target_acrobatics)

        attacker_roll = random.randint(1, 20) + attacker_athletics
        target_roll = random.randint(1, 20) + target_resist_mod

        if attacker_roll > target_roll:
            if shove_type == "prone":
                if "prone" not in target.conditions:
                    target.conditions.append("prone")
                desc = f"{combatant.name} shoves {target.name} prone! (Athletics {attacker_roll} vs {target_roll})"
                effects = ["prone"]
            else:
                # Push 5ft away
                # Calculate push direction
                effects = ["pushed"]
                hazard_effects = []
                hazard_damage = 0

                if attacker_pos and target_pos:
                    push_dx = 1 if target_pos[0] > attacker_pos[0] else (-1 if target_pos[0] < attacker_pos[0] else 0)
                    push_dy = 1 if target_pos[1] > attacker_pos[1] else (-1 if target_pos[1] < attacker_pos[1] else 0)
                    new_x = target_pos[0] + push_dx
                    new_y = target_pos[1] + push_dy

                    # Check if new position is valid
                    grid_size = self.state.grid.width if self.state.grid else 8
                    if 0 <= new_x < grid_size and 0 <= new_y < grid_size:
                        # ============================================================
                        # HAZARD CHECKS - BG3-style environmental interactions
                        # ============================================================

                        # Check for pit at destination
                        from app.core.falling import check_pit_fall, apply_falling_damage
                        is_pit, pit_depth = check_pit_fall(self.state.grid, new_x, new_y)
                        if is_pit and pit_depth >= 10:
                            fall_result = apply_falling_damage(
                                target, target_stats, pit_depth, self.state
                            )
                            hazard_damage += fall_result.get("damage", 0)
                            hazard_effects.append(f"fell into pit ({pit_depth}ft)")
                            if fall_result.get("applied_prone"):
                                effects.append("prone")

                        # Check for elevation drop (ledge)
                        from app.core.falling import check_fall_from_position
                        fall_distance = check_fall_from_position(
                            self.state.grid,
                            target_pos[0], target_pos[1],
                            new_x, new_y
                        )
                        if fall_distance >= 10:
                            fall_result = apply_falling_damage(
                                target, target_stats, fall_distance, self.state
                            )
                            hazard_damage += fall_result.get("damage", 0)
                            hazard_effects.append(f"fell off ledge ({fall_distance}ft)")
                            if fall_result.get("applied_prone"):
                                effects.append("prone")

                        # Check for hazardous surfaces at destination
                        if hasattr(self.state, 'surface_manager') and self.state.surface_manager:
                            surface_effects = self.state.surface_manager.process_movement_enter(
                                target_id, new_x, new_y, target_stats
                            )
                            for effect in surface_effects:
                                if effect.get("damage", 0) > 0:
                                    hazard_damage += effect["damage"]
                                    hazard_effects.append(f"{effect['surface_type']} ({effect['damage']} {effect.get('damage_type', '')} damage)")
                                    # Apply damage to target
                                    target.hp = max(0, target.hp - effect["damage"])
                                if effect.get("condition"):
                                    if effect["condition"] not in target.conditions:
                                        target.conditions.append(effect["condition"])
                                    effects.append(effect["condition"])

                        # Update position
                        self.state.positions[target_id] = (new_x, new_y)

                        # Build description
                        if hazard_effects:
                            hazard_desc = ", ".join(hazard_effects)
                            desc = f"{combatant.name} shoves {target.name} into hazard! {hazard_desc} (Athletics {attacker_roll} vs {target_roll})"
                            if hazard_damage > 0:
                                desc += f" [{hazard_damage} total damage]"
                        else:
                            desc = f"{combatant.name} shoves {target.name} back 5ft! (Athletics {attacker_roll} vs {target_roll})"
                    else:
                        desc = f"{combatant.name} shoves {target.name} but they can't be pushed further! (Athletics {attacker_roll} vs {target_roll})"
                else:
                    desc = f"{combatant.name} shoves {target.name}! (Athletics {attacker_roll} vs {target_roll})"

            self.state.add_event(
                "shove",
                desc,
                combatant_id=combatant.id,
                data={"target_id": target_id, "shove_type": shove_type, "success": True}
            )

            return ActionResult(
                success=True,
                action_type=ActionType.SHOVE.value,
                description=desc,
                effects_applied=effects,
                extra_data={
                    "target_id": target_id,
                    "shove_type": shove_type,
                    "shove_success": True,
                    "attacker_roll": attacker_roll,
                    "target_roll": target_roll,
                }
            )
        else:
            desc = f"{combatant.name} fails to shove {target.name} (Athletics {attacker_roll} vs {target_roll})"

            self.state.add_event(
                "shove_failed",
                desc,
                combatant_id=combatant.id,
                data={"target_id": target_id, "success": False}
            )

            return ActionResult(
                success=True,
                action_type=ActionType.SHOVE.value,
                description=desc,
                extra_data={
                    "target_id": target_id,
                    "shove_type": shove_type,
                    "shove_success": False,
                    "attacker_roll": attacker_roll,
                    "target_roll": target_roll,
                }
            )

    def _handle_escape_grapple(
        self,
        target_id: Optional[str],
        **kwargs
    ) -> ActionResult:
        """
        Handle escaping from a grapple.

        D&D 5e Rules:
        - Uses your action
        - Contested check: your Athletics or Acrobatics vs grappler's Athletics
        - On success, you are no longer grappled
        """
        combatant = self.get_current_combatant()
        if not combatant:
            return ActionResult(
                success=False,
                action_type=ActionType.ESCAPE_GRAPPLE.value,
                description="No current combatant"
            )

        stats = self.state.combatant_stats.get(combatant.id, {})

        # Check if actually grappled
        if "grappled" not in combatant.conditions:
            return ActionResult(
                success=False,
                action_type=ActionType.ESCAPE_GRAPPLE.value,
                description=f"{combatant.name} is not grappled"
            )

        grappler_id = stats.get("grappled_by")
        if not grappler_id:
            # Remove grappled condition if no grappler tracked
            combatant.conditions.remove("grappled")
            return ActionResult(
                success=True,
                action_type=ActionType.ESCAPE_GRAPPLE.value,
                description=f"{combatant.name} escapes the grapple"
            )

        grappler = self.state.initiative_tracker.get_combatant(grappler_id)
        grappler_stats = self.state.combatant_stats.get(grappler_id, {})

        if not grappler or not grappler.is_active:
            # Grappler is gone, auto-escape
            combatant.conditions.remove("grappled")
            stats["grappled_by"] = None
            return ActionResult(
                success=True,
                action_type=ActionType.ESCAPE_GRAPPLE.value,
                description=f"{combatant.name} escapes the grapple (grappler incapacitated)"
            )

        # Contested check
        escapee_athletics = stats.get("athletics", stats.get("str_mod", 0))
        escapee_acrobatics = stats.get("acrobatics", stats.get("dex_mod", 0))
        escapee_mod = max(escapee_athletics, escapee_acrobatics)

        grappler_athletics = grappler_stats.get("athletics", grappler_stats.get("str_mod", 0))

        escapee_roll = random.randint(1, 20) + escapee_mod
        grappler_roll = random.randint(1, 20) + grappler_athletics

        if escapee_roll > grappler_roll:
            # Escape succeeds
            combatant.conditions.remove("grappled")
            stats["grappled_by"] = None

            # Remove from grappler's grappling list
            if "grappling" in grappler_stats and combatant.id in grappler_stats["grappling"]:
                grappler_stats["grappling"].remove(combatant.id)

            desc = f"{combatant.name} escapes {grappler.name}'s grapple! ({escapee_roll} vs {grappler_roll})"

            self.state.add_event(
                "escape_grapple",
                desc,
                combatant_id=combatant.id,
                data={"grappler_id": grappler_id, "success": True}
            )

            return ActionResult(
                success=True,
                action_type=ActionType.ESCAPE_GRAPPLE.value,
                description=desc,
                extra_data={
                    "escape_success": True,
                    "escapee_roll": escapee_roll,
                    "grappler_roll": grappler_roll,
                }
            )
        else:
            desc = f"{combatant.name} fails to escape {grappler.name}'s grapple ({escapee_roll} vs {grappler_roll})"

            self.state.add_event(
                "escape_grapple_failed",
                desc,
                combatant_id=combatant.id,
                data={"grappler_id": grappler_id, "success": False}
            )

            return ActionResult(
                success=True,  # Action was taken
                action_type=ActionType.ESCAPE_GRAPPLE.value,
                description=desc,
                extra_data={
                    "escape_success": False,
                    "escapee_roll": escapee_roll,
                    "grappler_roll": grappler_roll,
                }
            )

    # =========================================================================
    # MONSTER SPECIAL ABILITIES
    # =========================================================================

    def _handle_monster_ability(
        self,
        target_id: Optional[str],
        **kwargs
    ) -> ActionResult:
        """
        Handle monster special abilities (breath weapons, etc.).

        Args:
            target_id: Primary target (or None for AOE)
            **kwargs: Should include 'ability_id' specifying which ability to use

        Returns:
            ActionResult with ability outcome
        """
        from app.core.monster_abilities import (
            parse_monster_action,
            execute_breath_weapon,
            execute_frightful_presence,
            execute_mind_blast,
            AbilityType,
        )

        combatant = self.get_current_combatant()
        if not combatant:
            return ActionResult(
                success=False,
                action_type=ActionType.MONSTER_ABILITY.value,
                description="No current combatant"
            )

        stats = self.state.combatant_stats.get(combatant.id, {})
        ability_name = kwargs.get("ability_name", "")
        ability_id = kwargs.get("ability_id", "")

        # Find the action in monster's actions array
        action_data = None
        for action in stats.get("actions", []):
            if action.get("name", "").lower() == ability_name.lower():
                action_data = action
                break
            # Also match by id if provided
            test_id = f"{combatant.id}_{action.get('name', '').lower().replace(' ', '_')}"
            if test_id == ability_id:
                action_data = action
                break

        if not action_data:
            return ActionResult(
                success=False,
                action_type=ActionType.MONSTER_ABILITY.value,
                description=f"Ability '{ability_name}' not found"
            )

        # Parse the ability
        ability = parse_monster_action(action_data, combatant.id)

        # Check if ability is available (recharge)
        recharge_state = self.state.monster_ability_recharge.get(combatant.id, {})
        if ability.recharge_type and not recharge_state.get(ability.id, True):
            return ActionResult(
                success=False,
                action_type=ActionType.MONSTER_ABILITY.value,
                description=f"{ability.name} is not recharged yet"
            )

        # Get targets in area
        targets = self._get_targets_in_ability_area(combatant.id, ability, target_id)

        # Execute based on ability type
        result = None
        total_damage = 0

        if ability.ability_type == AbilityType.BREATH_WEAPON:
            # Prepare targets with save mods and Evasion check
            save_type = ability.save_type or "dex"
            target_data = []
            for t_id in targets:
                t_stats = self.state.combatant_stats.get(t_id, {})
                save_mod = t_stats.get(f"{save_type}_save", t_stats.get(f"{save_type}_mod", 0))

                # Check for Evasion (Rogue 7+, Monk 7+)
                t_class = t_stats.get("class", "").lower()
                t_level = t_stats.get("level", 1)
                has_evasion = (t_class in ["rogue", "monk"] and t_level >= 7)

                target_data.append({
                    "id": t_id,
                    "save_mod": save_mod,
                    "has_evasion": has_evasion
                })

            result = execute_breath_weapon(ability, target_data, combatant.id)

            # Apply damage to targets
            for t_id, damage in result.damage_dealt.items():
                self._apply_damage_to_target(t_id, damage, ability.damage_type or "untyped")
                total_damage += damage

            # Mark ability on cooldown
            if combatant.id not in self.state.monster_ability_recharge:
                self.state.monster_ability_recharge[combatant.id] = {}
            self.state.monster_ability_recharge[combatant.id][ability.id] = False

        elif ability.ability_type == AbilityType.FRIGHTFUL_PRESENCE:
            save_type = ability.save_type or "wis"
            target_data = []
            for t_id in targets:
                t_stats = self.state.combatant_stats.get(t_id, {})
                save_mod = t_stats.get(f"{save_type}_save", t_stats.get(f"{save_type}_mod", 0))
                target_data.append({"id": t_id, "save_mod": save_mod})

            immune_targets = self.state.frightful_presence_immune.get(combatant.id, [])
            result = execute_frightful_presence(ability, target_data, combatant.id, immune_targets)

            # Apply frightened condition
            for t_id, conditions in result.conditions_applied.items():
                t = self.state.initiative_tracker.get_combatant(t_id)
                if t:
                    for cond in conditions:
                        if cond not in t.conditions:
                            t.conditions.append(cond)

            # Add saved targets to immune list
            if combatant.id not in self.state.frightful_presence_immune:
                self.state.frightful_presence_immune[combatant.id] = []
            for t_id in result.targets_saved:
                if t_id not in self.state.frightful_presence_immune[combatant.id]:
                    self.state.frightful_presence_immune[combatant.id].append(t_id)

        elif ability.ability_type == AbilityType.MIND_BLAST:
            save_type = ability.save_type or "int"
            target_data = []
            for t_id in targets:
                t_stats = self.state.combatant_stats.get(t_id, {})
                save_mod = t_stats.get(f"{save_type}_save", t_stats.get(f"{save_type}_mod", 0))
                target_data.append({"id": t_id, "save_mod": save_mod})

            result = execute_mind_blast(ability, target_data, combatant.id)

            # Apply damage and stun
            for t_id, damage in result.damage_dealt.items():
                self._apply_damage_to_target(t_id, damage, ability.damage_type or "psychic")
                total_damage += damage

            for t_id, conditions in result.conditions_applied.items():
                t = self.state.initiative_tracker.get_combatant(t_id)
                if t:
                    for cond in conditions:
                        if cond not in t.conditions:
                            t.conditions.append(cond)

            # Mark on cooldown
            if combatant.id not in self.state.monster_ability_recharge:
                self.state.monster_ability_recharge[combatant.id] = {}
            self.state.monster_ability_recharge[combatant.id][ability.id] = False

        else:
            # Generic AOE save ability
            if ability.save_dc and ability.damage_dice:
                from app.core.dice import roll_dice
                damage_roll = roll_dice(ability.damage_dice)
                save_type = ability.save_type or "dex"

                for t_id in targets:
                    t_stats = self.state.combatant_stats.get(t_id, {})
                    save_mod = t_stats.get(f"{save_type}_save", 0)
                    save_roll = random.randint(1, 20) + save_mod

                    if save_roll >= ability.save_dc:
                        damage = damage_roll // 2 if ability.half_on_save else 0
                    else:
                        damage = damage_roll

                    self._apply_damage_to_target(t_id, damage, ability.damage_type or "untyped")
                    total_damage += damage

        # Log the event
        self.state.add_event(
            "monster_ability",
            f"{combatant.name} uses {ability.name}!",
            combatant_id=combatant.id,
            data={
                "ability": ability.name,
                "targets": targets,
                "total_damage": total_damage,
            }
        )

        # Mark action as taken
        self.state.current_turn.action_taken = True

        return ActionResult(
            success=True,
            action_type=ActionType.MONSTER_ABILITY.value,
            description=f"{combatant.name} uses {ability.name}!",
            damage_dealt=total_damage,
            target_id=target_id,
            extra_data={
                "ability_name": ability.name,
                "targets_hit": result.targets_hit if result else targets,
                "targets_saved": result.targets_saved if result else [],
            }
        )

    def _handle_multiattack(
        self,
        target_id: Optional[str],
        **kwargs
    ) -> ActionResult:
        """
        Handle monster multiattack action.

        Executes the full multiattack pattern (e.g., bite + 2 claws).

        Args:
            target_id: Primary target for attacks
            **kwargs: Additional parameters

        Returns:
            ActionResult with combined attack outcomes
        """
        from app.core.monster_abilities import parse_monster_action, get_multiattack, AbilityType

        combatant = self.get_current_combatant()
        if not combatant:
            return ActionResult(
                success=False,
                action_type=ActionType.MULTIATTACK.value,
                description="No current combatant"
            )

        stats = self.state.combatant_stats.get(combatant.id, {})
        actions = stats.get("actions", [])

        # Find multiattack action
        multiattack_action = None
        for action in actions:
            if "multiattack" in action.get("name", "").lower():
                multiattack_action = action
                break

        if not multiattack_action:
            return ActionResult(
                success=False,
                action_type=ActionType.MULTIATTACK.value,
                description=f"{combatant.name} has no multiattack action"
            )

        # Parse the multiattack
        multiattack = parse_monster_action(multiattack_action, combatant.id)

        # Check if multiattack includes Frightful Presence
        if multiattack.includes_frightful_presence:
            # Execute frightful presence first (doesn't use action)
            self._execute_frightful_presence_as_part_of_multiattack(combatant.id, stats)

        # Build attack map from available actions
        attack_map = {}
        for action in actions:
            name = action.get("name", "").lower()
            if "attack" in action.get("description", "").lower():
                # It's an attack action
                parsed = parse_monster_action(action, combatant.id)
                if parsed.ability_type in (AbilityType.MELEE_ATTACK, AbilityType.RANGED_ATTACK):
                    attack_map[name] = parsed

        # Execute attacks based on pattern
        total_damage = 0
        attacks_made = []
        hits = 0
        misses = 0

        for attack_name in multiattack.multiattack_pattern or []:
            attack_name_lower = attack_name.lower()

            # Find matching attack
            attack = attack_map.get(attack_name_lower)
            if not attack and attack_name_lower == "attack":
                # Generic attack - use first available
                attack = next(iter(attack_map.values()), None)

            if attack:
                # Execute the attack
                attack_result = self._execute_single_monster_attack(
                    combatant, stats, attack, target_id
                )
                attacks_made.append(attack_result)

                if attack_result.get("hit"):
                    hits += 1
                    total_damage += attack_result.get("damage", 0)
                else:
                    misses += 1

        # Log combined result
        self.state.add_event(
            "multiattack",
            f"{combatant.name} uses Multiattack! {hits} hits, {misses} misses for {total_damage} total damage",
            combatant_id=combatant.id,
            data={
                "attacks": attacks_made,
                "total_damage": total_damage,
                "hits": hits,
                "misses": misses,
            }
        )

        # Mark action as taken
        self.state.current_turn.action_taken = True

        return ActionResult(
            success=True,
            action_type=ActionType.MULTIATTACK.value,
            description=f"{combatant.name} attacks multiple times! {hits} hits for {total_damage} damage",
            damage_dealt=total_damage,
            target_id=target_id,
            extra_data={
                "hits": hits,
                "misses": misses,
                "attacks": attacks_made,
            }
        )

    def _execute_single_monster_attack(
        self,
        combatant,
        stats: Dict[str, Any],
        attack,
        target_id: str
    ) -> Dict[str, Any]:
        """
        Execute a single attack from a monster's action.

        Args:
            combatant: The attacking combatant
            stats: Combatant stats
            attack: Parsed MonsterAbility for the attack
            target_id: Target of the attack

        Returns:
            Dict with attack result {hit, damage, critical, attack_roll, etc.}
        """
        from app.core.dice import roll_dice, roll_d20

        target = self.state.initiative_tracker.get_combatant(target_id)
        target_stats = self.state.combatant_stats.get(target_id, {})

        if not target:
            return {"hit": False, "damage": 0, "reason": "Invalid target"}

        # Roll attack
        attack_bonus = attack.attack_bonus or 0
        attack_roll = roll_d20(modifier=attack_bonus)
        is_crit = attack_roll.natural_roll == 20
        is_miss = attack_roll.natural_roll == 1

        # Get target AC
        target_ac = target_stats.get("armor_class", target.armor_class if hasattr(target, "armor_class") else 10)

        hit = False
        damage = 0

        if is_miss:
            hit = False
        elif is_crit or attack_roll.total >= target_ac:
            hit = True

            # Roll damage
            if attack.damage_dice:
                damage = roll_dice(attack.damage_dice)
                if is_crit:
                    damage += roll_dice(attack.damage_dice)  # Double dice on crit

            # Extra damage (like acid on dragon bite)
            if attack.extra_damage_dice:
                extra = roll_dice(attack.extra_damage_dice)
                if is_crit:
                    extra += roll_dice(attack.extra_damage_dice)
                damage += extra

            # Apply damage to target
            self._apply_damage_to_target(target_id, damage, attack.damage_type or "untyped")

        # Log individual attack
        self.state.add_event(
            "attack" if hit else "attack_miss",
            f"{combatant.name}'s {attack.name} {'hits' if hit else 'misses'} {target.name}" +
            (f" for {damage} damage!" if hit else f" (rolled {attack_roll.total} vs AC {target_ac})"),
            combatant_id=combatant.id,
            data={
                "target_id": target_id,
                "attack_roll": attack_roll.total,
                "target_ac": target_ac,
                "damage": damage if hit else 0,
                "critical": is_crit,
            }
        )

        return {
            "hit": hit,
            "damage": damage,
            "critical": is_crit,
            "attack_roll": attack_roll.total,
            "target_ac": target_ac,
            "attack_name": attack.name,
        }

    def _apply_damage_to_target(
        self,
        target_id: str,
        damage: int,
        damage_type: str
    ) -> None:
        """Apply damage to a target, respecting resistances/immunities."""
        target = self.state.initiative_tracker.get_combatant(target_id)
        target_stats = self.state.combatant_stats.get(target_id, {})

        if not target:
            return

        # Check immunities
        immunities = target_stats.get("damage_immunities", [])
        if damage_type.lower() in [i.lower() for i in immunities]:
            return  # No damage

        # Check resistances
        resistances = target_stats.get("damage_resistances", [])
        if damage_type.lower() in [r.lower() for r in resistances]:
            damage = damage // 2

        # Check vulnerabilities
        vulnerabilities = target_stats.get("damage_vulnerabilities", [])
        if damage_type.lower() in [v.lower() for v in vulnerabilities]:
            damage = damage * 2

        # Apply damage
        current_hp = target_stats.get("current_hp", target.current_hp if hasattr(target, "current_hp") else 0)
        new_hp = max(0, current_hp - damage)
        target_stats["current_hp"] = new_hp

        if hasattr(target, "current_hp"):
            target.current_hp = new_hp

    def _get_targets_in_ability_area(
        self,
        attacker_id: str,
        ability,
        primary_target_id: Optional[str]
    ) -> List[str]:
        """
        Get all valid targets within an ability's area of effect.

        Args:
            attacker_id: The monster using the ability
            ability: The MonsterAbility being used
            primary_target_id: Primary target (direction for cones/lines)

        Returns:
            List of target combatant IDs
        """
        from app.core.monster_abilities import AreaShape

        targets = []
        attacker_pos = self.state.positions.get(attacker_id, (0, 0))

        # Get all enemies of the attacker
        attacker = self.state.initiative_tracker.get_combatant(attacker_id)
        if not attacker:
            return []

        for combatant in self.state.initiative_tracker.get_active_combatants():
            if combatant.id == attacker_id:
                continue
            # Monsters target players, players target monsters
            if combatant.combatant_type == attacker.combatant_type:
                continue

            target_pos = self.state.positions.get(combatant.id, (0, 0))

            # Calculate distance
            if isinstance(attacker_pos, dict):
                ax, ay = attacker_pos.get("x", 0), attacker_pos.get("y", 0)
            else:
                ax, ay = attacker_pos

            if isinstance(target_pos, dict):
                tx, ty = target_pos.get("x", 0), target_pos.get("y", 0)
            else:
                tx, ty = target_pos

            distance = ((tx - ax) ** 2 + (ty - ay) ** 2) ** 0.5 * 5  # Grid squares to feet

            # Check if in area
            if ability.area_shape == AreaShape.SPHERE:
                if distance <= (ability.area_size or 30):
                    targets.append(combatant.id)
            elif ability.area_shape == AreaShape.CONE:
                # Simplified: targets in front within range
                if distance <= (ability.area_size or 30):
                    targets.append(combatant.id)
            elif ability.area_shape == AreaShape.LINE:
                # Simplified: targets in a line within range
                if distance <= (ability.area_size or 60):
                    targets.append(combatant.id)
            else:
                # Single target or unknown - just use primary target
                if combatant.id == primary_target_id:
                    targets.append(combatant.id)

        # If no targets found but primary target specified, use that
        if not targets and primary_target_id:
            targets = [primary_target_id]

        return targets

    def _execute_frightful_presence_as_part_of_multiattack(
        self,
        combatant_id: str,
        stats: Dict[str, Any]
    ) -> None:
        """Execute Frightful Presence as part of Multiattack (free action)."""
        from app.core.monster_abilities import parse_monster_action, execute_frightful_presence

        # Find Frightful Presence action
        for action in stats.get("actions", []):
            if "frightful presence" in action.get("name", "").lower():
                ability = parse_monster_action(action, combatant_id)

                # Get targets in range
                targets = self._get_targets_in_ability_area(combatant_id, ability, None)

                # Prepare target data
                target_data = []
                for t_id in targets:
                    t_stats = self.state.combatant_stats.get(t_id, {})
                    save_mod = t_stats.get("wis_save", t_stats.get("wis_mod", 0))
                    target_data.append({"id": t_id, "save_mod": save_mod})

                # Execute
                immune_targets = self.state.frightful_presence_immune.get(combatant_id, [])
                result = execute_frightful_presence(ability, target_data, combatant_id, immune_targets)

                # Apply conditions
                for t_id, conditions in result.conditions_applied.items():
                    t = self.state.initiative_tracker.get_combatant(t_id)
                    if t:
                        for cond in conditions:
                            if cond not in t.conditions:
                                t.conditions.append(cond)

                # Update immunity list
                if combatant_id not in self.state.frightful_presence_immune:
                    self.state.frightful_presence_immune[combatant_id] = []
                for t_id in result.targets_saved:
                    if t_id not in self.state.frightful_presence_immune[combatant_id]:
                        self.state.frightful_presence_immune[combatant_id].append(t_id)

                # Log event
                combatant = self.state.initiative_tracker.get_combatant(combatant_id)
                self.state.add_event(
                    "frightful_presence",
                    f"{combatant.name if combatant else 'Monster'} uses Frightful Presence!",
                    combatant_id=combatant_id,
                    data={
                        "targets_frightened": result.targets_hit,
                        "targets_saved": result.targets_saved,
                    }
                )
                break

    # =========================================================================
    # SPEED & ENCUMBRANCE
    # =========================================================================

    def _get_effective_speed(self, combatant_id: str, stats: Dict[str, Any] = None) -> int:
        """
        Calculate effective speed including encumbrance penalties.

        D&D 5e Variant Encumbrance Rules:
        - Weight > STR × 5: Encumbered (-10 speed)
        - Weight > STR × 10: Heavily Encumbered (-20 speed)

        Also applies:
        - "slowed" condition from weapon mastery (-10 speed)
        - Heavy armor STR requirement not met (-10 speed)

        Args:
            combatant_id: ID of the combatant
            stats: Optional pre-fetched stats dict

        Returns:
            Effective speed in feet
        """
        if stats is None:
            stats = self.state.combatant_stats.get(combatant_id, {})

        base_speed = stats.get("speed", 30)
        speed_penalty = 0

        # Get strength score for encumbrance calculation
        abilities = stats.get("abilities", {})
        strength = abilities.get("strength", 10)

        # Check equipment for encumbrance
        equipment = stats.get("equipment")
        if equipment:
            # Equipment can be a dict or CharacterEquipment object
            if hasattr(equipment, "total_weight"):
                total_weight = equipment.total_weight
            elif isinstance(equipment, dict):
                total_weight = equipment.get("total_weight", 0)
            else:
                total_weight = 0

            # Calculate encumbrance thresholds (variant encumbrance)
            encumbered_threshold = strength * 5
            heavily_threshold = strength * 10

            if total_weight > heavily_threshold:
                # Heavily encumbered: -20 speed
                speed_penalty += 20
            elif total_weight > encumbered_threshold:
                # Encumbered: -10 speed
                speed_penalty += 10

            # Check heavy armor STR requirement
            armor = None
            if hasattr(equipment, "armor") and equipment.armor:
                armor = equipment.armor
            elif isinstance(equipment, dict) and equipment.get("armor"):
                armor = equipment.get("armor")

            if armor:
                str_req = None
                if hasattr(armor, "strength_requirement"):
                    str_req = armor.strength_requirement
                elif isinstance(armor, dict):
                    str_req = armor.get("strength_requirement")

                if str_req and strength < str_req:
                    # Speed reduced by 10 if STR requirement not met
                    speed_penalty += 10

        # Check for "slowed" condition (from weapon mastery SAP)
        conditions = stats.get("conditions", [])
        if "slowed" in conditions:
            speed_penalty += 10

        # Apply condition-based speed modifications (stunned, restrained, etc.)
        condition_speed, movement_type, speed_reasons = get_condition_speed(
            base_speed=base_speed - speed_penalty,
            conditions=conditions,
        )

        # If any condition sets speed to 0, use that
        if movement_type == "zero":
            return 0

        # Ensure speed doesn't go below 0
        effective_speed = max(0, condition_speed)

        return effective_speed

    # =========================================================================
    # MOVEMENT
    # =========================================================================

    def _check_and_execute_opportunity_attacks(
        self,
        mover_id: str,
        from_pos: tuple,
        to_pos: tuple,
        mover_conditions: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Check if movement triggers opportunity attacks and execute them.

        D&D 5e Rules:
        - Opportunity attack triggers when leaving a creature's reach
        - Uses the creature's reaction (one per round)
        - Disengage action prevents opportunity attacks (unless Sentinel)
        - Can make one melee attack against the moving creature

        Args:
            mover_id: ID of the moving combatant
            from_pos: Starting position (x, y)
            to_pos: Destination position (x, y)
            mover_conditions: Conditions on the mover (for checking "disengaged")

        Returns:
            List of opportunity attack results
        """
        results = []

        # Get mover combatant
        mover = self.state.initiative_tracker.get_combatant(mover_id)
        if not mover:
            return results

        # Get all enemy combatants (opposite type from mover)
        enemy_ids = []
        enemy_data = {}
        for c in self.state.initiative_tracker.combatants:
            if c.id != mover_id and c.is_active and c.combatant_type != mover.combatant_type:
                enemy_ids.append(c.id)
                # Build enemy data for opportunity attack check
                stats = self.state.combatant_stats.get(c.id, {})
                enemy_data[c.id] = {
                    "reach": stats.get("reach", 5),
                    "sentinel": "sentinel" in stats.get("feats", []) or stats.get("sentinel", False),
                    "conditions": stats.get("conditions", getattr(c, "conditions", [])),
                }

        if not enemy_ids:
            return results

        # Build a temporary grid for position lookup
        # We need to set combatant positions on the grid
        if self.state.grid:
            grid = self.state.grid
            # Update grid with current positions
            for cid, pos in self.state.positions.items():
                cell = grid.get_cell(pos[0], pos[1])
                if cell:
                    cell.occupied_by = cid
        else:
            # Create a minimal grid if none exists
            grid = CombatGrid(width=20, height=20)
            for cid, pos in self.state.positions.items():
                cell = grid.get_cell(pos[0], pos[1])
                if cell:
                    cell.occupied_by = cid

        # Check which enemies can make opportunity attacks
        triggering_enemies = check_opportunity_attack_triggers(
            grid=grid,
            mover_id=mover_id,
            from_pos=from_pos,
            to_pos=to_pos,
            enemy_ids=enemy_ids,
            mover_conditions=mover_conditions,
            enemy_data=enemy_data,
            mover_attacked_this_turn=[]  # TODO: Track attacked enemies for Mobile feat
        )

        # Execute opportunity attacks for each triggered enemy
        for enemy_id in triggering_enemies:
            # Check if enemy has already used their reaction this round
            if self.state.reactions_used_this_round.get(enemy_id):
                continue

            enemy = self.state.initiative_tracker.get_combatant(enemy_id)
            if not enemy or not enemy.is_active:
                continue

            # Check if enemy is incapacitated
            enemy_stats = self.state.combatant_stats.get(enemy_id, {})
            enemy_conditions = enemy_stats.get("conditions", getattr(enemy, "conditions", []))
            incap, _ = is_incapacitated(enemy_conditions)
            if incap:
                continue

            # Execute the opportunity attack
            oa_result = self._execute_opportunity_attack(enemy_id, mover_id)

            # Mark reaction as used
            self.state.reactions_used_this_round[enemy_id] = True

            results.append(oa_result)

            # Log the opportunity attack
            self.state.add_event(
                "opportunity_attack",
                f"{enemy.name} makes an opportunity attack against {mover.name}!",
                combatant_id=enemy_id,
                data=oa_result
            )

            # Check if Sentinel feat stops movement
            if oa_result.get("hit") and enemy_data.get(enemy_id, {}).get("sentinel"):
                # Sentinel: On hit, target's speed becomes 0 for the rest of the turn
                # We handle this by reducing remaining movement to 0
                if self.state.current_turn and mover_id == self.state.current_turn.combatant_id:
                    mover_stats = self.state.combatant_stats.get(mover_id, {})
                    max_speed = mover_stats.get("speed", 30)
                    self.state.current_turn.movement_used = max_speed
                    self.state.add_event(
                        "sentinel_stop",
                        f"{enemy.name}'s Sentinel feat stops {mover.name}'s movement!",
                        combatant_id=enemy_id
                    )

        return results

    def _execute_opportunity_attack(
        self,
        attacker_id: str,
        target_id: str
    ) -> Dict[str, Any]:
        """
        Execute a single opportunity attack.

        Args:
            attacker_id: ID of the attacking combatant
            target_id: ID of the target combatant

        Returns:
            Dict with attack result data
        """
        attacker = self.state.initiative_tracker.get_combatant(attacker_id)
        target = self.state.initiative_tracker.get_combatant(target_id)

        if not attacker or not target:
            return {"hit": False, "damage": 0, "attacker_name": "Unknown", "error": "Combatant not found"}

        attacker_stats = self.state.combatant_stats.get(attacker_id, {})
        target_stats = self.state.combatant_stats.get(target_id, {})

        # Get attack bonus and damage from attacker stats
        attack_bonus = attacker_stats.get("attack_bonus", 0)
        if attack_bonus == 0:
            # Calculate from ability scores
            str_mod = (attacker_stats.get("ability_scores", {}).get("STR", 10) - 10) // 2
            dex_mod = (attacker_stats.get("ability_scores", {}).get("DEX", 10) - 10) // 2
            prof_bonus = attacker_stats.get("proficiency_bonus", 2)
            # Use higher of STR/DEX for melee (assumes finesse option)
            attack_bonus = max(str_mod, dex_mod) + prof_bonus

        damage_dice = attacker_stats.get("damage_dice", "1d6")
        damage_type = attacker_stats.get("damage_type", "slashing")

        # Get damage modifier
        str_mod = (attacker_stats.get("ability_scores", {}).get("STR", 10) - 10) // 2
        dex_mod = (attacker_stats.get("ability_scores", {}).get("DEX", 10) - 10) // 2
        damage_mod = max(str_mod, dex_mod)

        # Get target AC
        target_ac = target_stats.get("ac", 10)
        if target_ac == 0:
            target_ac = target.armor_class if target.armor_class else 10

        # Roll attack
        attack_roll = roll_d20()
        total_attack = attack_roll.total + attack_bonus

        # Determine hit
        is_crit = attack_roll.natural_20
        is_hit = is_crit or total_attack >= target_ac

        damage = 0
        if is_hit:
            # Roll damage
            damage_result = roll_damage(damage_dice)
            damage = damage_result.total + damage_mod

            # Double dice on crit
            if is_crit:
                crit_damage = roll_damage(damage_dice)
                damage += crit_damage.total

            # Apply damage to target
            if target.current_hp is not None:
                target.current_hp = max(0, target.current_hp - damage)

            # Update stats cache
            if target_id in self.state.combatant_stats:
                self.state.combatant_stats[target_id]["current_hp"] = target.current_hp

            # Check for concentration break
            if damage > 0:
                self._check_concentration_on_damage(target_id, damage, "opportunity attack")

        return {
            "hit": is_hit,
            "damage": damage,
            "attack_roll": attack_roll.total,
            "attack_bonus": attack_bonus,
            "total_attack": total_attack,
            "target_ac": target_ac,
            "critical": is_crit,
            "attacker_id": attacker_id,
            "attacker_name": attacker.name,
            "target_id": target_id,
            "target_name": target.name,
            "damage_type": damage_type
        }

    def move_combatant(
        self,
        combatant_id: str,
        new_x: int,
        new_y: int
    ) -> ActionResult:
        """
        Move a combatant to a new position.

        Args:
            combatant_id: ID of the combatant to move
            new_x: New X coordinate
            new_y: New Y coordinate

        Returns:
            ActionResult with the outcome
        """
        if self.state.phase != CombatPhase.COMBAT_ACTIVE:
            return ActionResult(
                success=False,
                action_type="move",
                description="Combat is not active"
            )

        combatant = self.state.initiative_tracker.get_combatant(combatant_id)
        if not combatant:
            return ActionResult(
                success=False,
                action_type="move",
                description="Combatant not found"
            )

        # Check if combatant is incapacitated (can't move)
        stats = self.state.combatant_stats.get(combatant_id, {})
        conditions = stats.get("conditions", getattr(combatant, "conditions", []))
        incap, incap_reasons = is_incapacitated(conditions)
        if incap:
            return ActionResult(
                success=False,
                action_type="move",
                description=f"Cannot move: {', '.join(incap_reasons)}"
            )

        # Get current position
        current_pos = self.state.positions.get(combatant_id, (0, 0))

        # Calculate distance (simplified - using grid distance)
        dx = abs(new_x - current_pos[0])
        dy = abs(new_y - current_pos[1])
        # Diagonal movement costs 5ft per square (simplified)
        distance = max(dx, dy) * 5

        # Check if combatant has enough movement
        stats = self.state.combatant_stats.get(combatant_id, {})
        speed = self._get_effective_speed(combatant_id, stats)

        if self.state.current_turn and combatant_id == self.state.current_turn.combatant_id:
            if not self.state.current_turn.can_move(distance, speed):
                return ActionResult(
                    success=False,
                    action_type="move",
                    description=f"Not enough movement remaining ({speed - self.state.current_turn.movement_used}ft left, need {distance}ft)"
                )
            self.state.current_turn.movement_used += distance

        # Check for opportunity attacks before updating position
        opportunity_attack_results = self._check_and_execute_opportunity_attacks(
            combatant_id, current_pos, (new_x, new_y), conditions
        )

        # Update position
        self.state.positions[combatant_id] = (new_x, new_y)

        self.state.add_event(
            "move",
            f"{combatant.name} moves to ({new_x}, {new_y})",
            combatant_id=combatant_id,
            data={
                "from": current_pos,
                "to": (new_x, new_y),
                "distance": distance
            }
        )

        # Build description including opportunity attacks
        description = f"{combatant.name} moves {distance}ft to ({new_x}, {new_y})"
        if opportunity_attack_results:
            oa_summary = ", ".join([
                f"{r['attacker_name']} {'hits' if r['hit'] else 'misses'} ({r['damage']} dmg)"
                for r in opportunity_attack_results
            ])
            description += f" [OA: {oa_summary}]"

        return ActionResult(
            success=True,
            action_type="move",
            description=description,
            extra_data={
                "from": current_pos,
                "to": (new_x, new_y),
                "distance": distance,
                "movement_remaining": speed - (self.state.current_turn.movement_used if self.state.current_turn else 0),
                "opportunity_attacks": opportunity_attack_results
            }
        )

    # =========================================================================
    # STATE QUERIES
    # =========================================================================

    def get_combat_state(self) -> Dict[str, Any]:
        """Get the full combat state for serialization/display."""
        tracker = self.state.initiative_tracker

        # Build combatants array in format frontend expects
        combatants = []
        for c in tracker.combatants:
            stats = self.state.combatant_stats.get(c.id, {})
            combatants.append({
                "id": c.id,
                "name": c.name,
                "type": stats.get("type", c.combatant_type.value if hasattr(c, 'combatant_type') else "enemy"),
                "current_hp": c.current_hp or stats.get("current_hp", stats.get("hp", 0)),
                "max_hp": c.max_hp or stats.get("max_hp", stats.get("hp", 0)),
                "ac": c.armor_class if c.armor_class is not None else stats.get("ac", 10),
                "speed": stats.get("speed", 30),
                "initiative_roll": c.initiative_roll,
                "is_active": c.is_active,
                "conditions": c.conditions or stats.get("conditions", []),
                # Include stats for frontend (class, level, abilities) - USE COMBATANT OBJECT DATA
                "stats": {
                    "class": c.character_class or stats.get("class", ""),
                    "level": c.level or stats.get("level", 1),
                    "strength": c.abilities.get("str_score", stats.get("abilities", {}).get("strength", 10)),
                    "dexterity": c.abilities.get("dex_score", stats.get("abilities", {}).get("dexterity", 10)),
                    "constitution": c.abilities.get("con_score", stats.get("abilities", {}).get("constitution", 10)),
                    "intelligence": c.abilities.get("int_score", stats.get("abilities", {}).get("intelligence", 10)),
                    "wisdom": c.abilities.get("wis_score", stats.get("abilities", {}).get("wisdom", 10)),
                    "charisma": c.abilities.get("cha_score", stats.get("abilities", {}).get("charisma", 10)),
                },
                # Include top-level character data for frontend compatibility
                "character_class": c.character_class,
                "class": c.character_class,
                "level": c.level,
                # Include full abilities dict with class features
                "abilities": c.abilities or stats.get("abilities", {}),
                # Include spellcasting data for caster classes
                "spellcasting": c.spellcasting or stats.get("spellcasting"),
                # Include equipment for weapon display
                "equipment": c.equipment or stats.get("equipment"),
                # Include weapons list
                "weapons": c.weapons or stats.get("weapons", []),
                # Include inventory for consumables (potions, scrolls, etc.)
                "inventory": stats.get("inventory", []),
            })

        # Convert positions from (x, y) tuples to {x, y} dicts
        positions_dict = {}
        for cid, pos in self.state.positions.items():
            if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                positions_dict[cid] = {"x": pos[0], "y": pos[1]}
            else:
                positions_dict[cid] = pos

        return {
            "id": self.state.id,
            "phase": self.state.phase.name,
            "round": tracker.current_round,
            "current_turn_index": tracker.current_turn_index,
            "initiative_order": tracker.get_initiative_order(),
            "current_combatant": (
                self.get_current_combatant().to_dict()
                if self.get_current_combatant()
                else None
            ),
            "current_turn": (
                {
                    "combatant_id": self.state.current_turn.combatant_id,
                    "movement_used": self.state.current_turn.movement_used,
                    "action_taken": self.state.current_turn.action_taken,
                    "bonus_action_taken": self.state.current_turn.bonus_action_taken,
                    "phase": self.state.current_turn.current_phase.name
                }
                if self.state.current_turn
                else None
            ),
            "positions": positions_dict,
            "combatants": combatants,
            "combatant_stats": self.state.combatant_stats,
            "event_count": len(self.state.event_log),
            "is_combat_over": tracker.is_combat_over(),
            "combat_result": tracker.get_combat_result()
        }

    def get_combatant_at_position(self, x: int, y: int) -> Optional[Combatant]:
        """Get the combatant at a specific grid position."""
        for cid, pos in self.state.positions.items():
            if pos == (x, y):
                return self.state.initiative_tracker.get_combatant(cid)
        return None

    def get_valid_targets(self, attacker_id: str, range_ft: int = 5) -> List[str]:
        """
        Get valid targets within range of an attacker.

        Args:
            attacker_id: ID of the attacking combatant
            range_ft: Maximum range in feet

        Returns:
            List of combatant IDs within range
        """
        attacker_pos = self.state.positions.get(attacker_id)
        if not attacker_pos:
            return []

        attacker = self.state.initiative_tracker.get_combatant(attacker_id)
        if not attacker:
            return []

        valid_targets = []
        range_squares = range_ft // 5

        for cid, pos in self.state.positions.items():
            if cid == attacker_id:
                continue

            target = self.state.initiative_tracker.get_combatant(cid)
            if not target or not target.is_active:
                continue

            # Don't target allies
            if target.combatant_type == attacker.combatant_type:
                continue

            # Check distance
            dx = abs(pos[0] - attacker_pos[0])
            dy = abs(pos[1] - attacker_pos[1])
            distance = max(dx, dy)

            if distance <= range_squares:
                valid_targets.append(cid)

        return valid_targets

    def get_recent_events(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get the most recent combat events."""
        events = self.state.event_log[-count:]
        return [
            {
                "type": e.event_type,
                "round": e.round_number,
                "combatant_id": e.combatant_id,
                "description": e.description,
                "data": e.data
            }
            for e in events
        ]

    # =========================================================================
    # SERIALIZATION
    # =========================================================================

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the combat engine state."""
        return {
            "combat_state": {
                "id": self.state.id,
                "phase": self.state.phase.name,
                "initiative_tracker": self.state.initiative_tracker.to_dict(),
                "current_turn": (
                    {
                        "combatant_id": self.state.current_turn.combatant_id,
                        "movement_used": self.state.current_turn.movement_used,
                        "action_taken": self.state.current_turn.action_taken,
                        "bonus_action_taken": self.state.current_turn.bonus_action_taken,
                        "reaction_used": self.state.current_turn.reaction_used,
                        "current_phase": self.state.current_turn.current_phase.name
                    }
                    if self.state.current_turn
                    else None
                ),
                "positions": self.state.positions,
                "combatant_stats": self.state.combatant_stats,
                "event_log": [
                    {
                        "type": e.event_type,
                        "round": e.round_number,
                        "combatant_id": e.combatant_id,
                        "description": e.description,
                        "data": e.data
                    }
                    for e in self.state.event_log
                ]
            }
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CombatEngine":
        """Deserialize a combat engine from a dictionary."""
        state_data = data.get("combat_state", {})

        state = CombatState(
            id=state_data.get("id", str(uuid.uuid4())),
            phase=CombatPhase[state_data.get("phase", "NOT_IN_COMBAT")],
            initiative_tracker=InitiativeTracker.from_dict(
                state_data.get("initiative_tracker", {})
            ),
            positions=state_data.get("positions", {}),
            combatant_stats=state_data.get("combatant_stats", {})
        )

        # Restore turn state
        turn_data = state_data.get("current_turn")
        if turn_data:
            state.current_turn = TurnState(
                combatant_id=turn_data["combatant_id"],
                movement_used=turn_data.get("movement_used", 0),
                action_taken=turn_data.get("action_taken", False),
                bonus_action_taken=turn_data.get("bonus_action_taken", False),
                reaction_used=turn_data.get("reaction_used", False),
                current_phase=TurnPhase[turn_data.get("current_phase", "START_OF_TURN")]
            )

        # Restore event log
        for event_data in state_data.get("event_log", []):
            state.event_log.append(CombatEvent(
                event_type=event_data["type"],
                round_number=event_data["round"],
                combatant_id=event_data.get("combatant_id"),
                description=event_data["description"],
                data=event_data.get("data", {})
            ))

        return cls(combat_state=state)
