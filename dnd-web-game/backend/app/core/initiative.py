"""
Initiative System.

Handles turn order tracking for combat encounters.
Supports initiative rolls, tiebreakers, and turn management.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any
import uuid

from app.core.dice import roll_d20


class CombatantType(Enum):
    """Type of combatant in initiative."""
    PLAYER = "player"
    ENEMY = "enemy"
    NPC = "npc"  # Allied NPCs, summons, etc.


@dataclass
class Combatant:
    """
    A participant in combat with initiative tracking.

    Attributes:
        id: Unique identifier
        name: Display name
        combatant_type: Whether player, enemy, or NPC
        dexterity_modifier: DEX mod for initiative rolls
        initiative_roll: The rolled initiative value
        has_acted: Whether they've acted this round
        is_active: Whether they're still in combat (not dead/fled)
        conditions: Active conditions affecting this combatant
    """
    id: str
    name: str
    combatant_type: CombatantType
    dexterity_modifier: int = 0
    initiative_roll: int = 0
    has_acted: bool = False
    is_active: bool = True
    conditions: List[str] = field(default_factory=list)

    # Additional data for reference
    current_hp: int = 0
    max_hp: int = 0
    armor_class: int = 10

    # Character data for display (class, level, abilities, equipment, etc.)
    character_class: str = ""
    level: int = 1
    stats: Dict[str, Any] = field(default_factory=dict)
    abilities: Dict[str, Any] = field(default_factory=dict)
    equipment: Optional[Dict[str, Any]] = None
    weapons: List[Dict[str, Any]] = field(default_factory=list)
    spellcasting: Optional[Dict[str, Any]] = None

    def roll_initiative(self) -> int:
        """Roll initiative for this combatant."""
        result = roll_d20(modifier=self.dexterity_modifier)
        self.initiative_roll = result.total
        return self.initiative_roll

    def reset_for_round(self) -> None:
        """Reset turn state for a new round."""
        self.has_acted = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        # Build stats from multiple sources, ensuring it's always populated
        stats = self.stats.copy() if self.stats else {}

        # Ensure class and level are in stats
        if not stats.get('class'):
            stats['class'] = self.character_class
        if not stats.get('level'):
            stats['level'] = self.level

        # Extract ability scores - check STATS FIRST (has 'str', 'strength', etc.)
        # Then fall back to abilities for nested format {'str': {'score': 13}}
        abilities_data = self.abilities or {}

        ability_map = {
            'strength': ['str', 'strength'],
            'dexterity': ['dex', 'dexterity'],
            'constitution': ['con', 'constitution'],
            'intelligence': ['int', 'intelligence'],
            'wisdom': ['wis', 'wisdom'],
            'charisma': ['cha', 'charisma'],
        }

        for full_name, short_names in ability_map.items():
            if not stats.get(full_name):
                # FIRST: Try to find in stats dict with short/full names
                found = False
                for short in short_names:
                    if short in stats and isinstance(stats[short], (int, float)):
                        stats[full_name] = int(stats[short])
                        found = True
                        break

                if not found:
                    # SECOND: Try to find in abilities dict
                    for short in short_names:
                        if short in abilities_data:
                            val = abilities_data[short]
                            if isinstance(val, dict):
                                stats[full_name] = val.get('score', 10)
                            else:
                                stats[full_name] = val
                            found = True
                            break

                if not found:
                    # Default to 10 if not found anywhere
                    stats[full_name] = 10

        result = {
            "id": self.id,
            "name": self.name,
            "combatant_type": self.combatant_type.value,
            "dexterity_modifier": self.dexterity_modifier,
            "initiative_roll": self.initiative_roll,
            "has_acted": self.has_acted,
            "is_active": self.is_active,
            "conditions": self.conditions,
            "current_hp": self.current_hp,
            "max_hp": self.max_hp,
            "armor_class": self.armor_class,
            # Character data for display
            "character_class": self.character_class,
            "class": self.character_class,  # Alias for frontend compatibility
            "level": self.level,
            "stats": stats,
            "abilities": self.abilities,
            "equipment": self.equipment,
            "weapons": self.weapons,
            "spellcasting": self.spellcasting,
        }
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Combatant":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            combatant_type=CombatantType(data["combatant_type"]),
            dexterity_modifier=data.get("dexterity_modifier", 0),
            initiative_roll=data.get("initiative_roll", 0),
            has_acted=data.get("has_acted", False),
            is_active=data.get("is_active", True),
            conditions=data.get("conditions", []),
            current_hp=data.get("current_hp", 0),
            max_hp=data.get("max_hp", 0),
            armor_class=data.get("armor_class", 10),
            # Character data
            character_class=data.get("character_class", data.get("class", "")),
            level=data.get("level", 1),
            stats=data.get("stats", {}),
            abilities=data.get("abilities", {}),
            equipment=data.get("equipment"),
            weapons=data.get("weapons", []),
            spellcasting=data.get("spellcasting"),
        )


@dataclass
class InitiativeResult:
    """Result of an initiative roll for display."""
    combatant_id: str
    combatant_name: str
    roll: int
    modifier: int
    total: int


@dataclass
class InitiativeTracker:
    """
    Manages initiative order for a combat encounter.

    Handles:
    - Rolling initiative for all combatants
    - Sorting by initiative (with DEX tiebreaker)
    - Tracking current turn
    - Advancing turns and rounds
    """
    combatants: List[Combatant] = field(default_factory=list)
    current_round: int = 0
    current_turn_index: int = 0
    combat_started: bool = False

    def add_combatant(
        self,
        name: str,
        combatant_type: CombatantType,
        dexterity_modifier: int = 0,
        current_hp: int = 0,
        max_hp: int = 0,
        armor_class: int = 10,
        combatant_id: Optional[str] = None,
        character_class: str = "",
        level: int = 1,
        stats: Optional[Dict[str, Any]] = None,
        abilities: Optional[Dict[str, Any]] = None,
        equipment: Optional[Dict[str, Any]] = None,
        weapons: Optional[List[Dict[str, Any]]] = None,
        spellcasting: Optional[Dict[str, Any]] = None,
    ) -> Combatant:
        """
        Add a combatant to the initiative tracker.

        Args:
            name: Display name
            combatant_type: Player, enemy, or NPC
            dexterity_modifier: DEX mod for initiative
            current_hp: Current hit points
            max_hp: Maximum hit points
            armor_class: Armor class
            combatant_id: Optional specific ID (auto-generated if not provided)
            character_class: Character class (e.g., "paladin", "fighter")
            level: Character level
            stats: Ability scores dict
            abilities: Character abilities dict
            equipment: Equipment dict
            weapons: List of weapon dicts
            spellcasting: Spellcasting info dict

        Returns:
            The created Combatant
        """
        combatant = Combatant(
            id=combatant_id or str(uuid.uuid4()),
            name=name,
            combatant_type=combatant_type,
            dexterity_modifier=dexterity_modifier,
            current_hp=current_hp,
            max_hp=max_hp,
            armor_class=armor_class,
            character_class=character_class,
            level=level,
            stats=stats or {},
            abilities=abilities or {},
            equipment=equipment,
            weapons=weapons or [],
            spellcasting=spellcasting,
        )
        self.combatants.append(combatant)
        return combatant

    def remove_combatant(self, combatant_id: str) -> bool:
        """
        Remove a combatant from combat.

        Args:
            combatant_id: ID of combatant to remove

        Returns:
            True if removed, False if not found
        """
        for i, combatant in enumerate(self.combatants):
            if combatant.id == combatant_id:
                self.combatants.pop(i)
                # Adjust current turn index if needed
                if i < self.current_turn_index:
                    self.current_turn_index -= 1
                elif i == self.current_turn_index:
                    # Current combatant was removed, don't advance
                    if self.current_turn_index >= len(self.combatants):
                        self.current_turn_index = 0
                return True
        return False

    def set_combatant_inactive(self, combatant_id: str) -> bool:
        """
        Mark a combatant as inactive (dead, fled, etc.) without removing.

        Args:
            combatant_id: ID of combatant

        Returns:
            True if found and updated, False otherwise
        """
        combatant = self.get_combatant(combatant_id)
        if combatant:
            combatant.is_active = False
            return True
        return False

    def get_combatant(self, combatant_id: str) -> Optional[Combatant]:
        """Get a combatant by ID."""
        for combatant in self.combatants:
            if combatant.id == combatant_id:
                return combatant
        return None

    def roll_all_initiative(self) -> List[InitiativeResult]:
        """
        Roll initiative for all combatants and sort by result.

        Returns:
            List of InitiativeResult for each combatant
        """
        results = []

        for combatant in self.combatants:
            # Roll for each combatant
            roll_result = roll_d20(modifier=combatant.dexterity_modifier)
            combatant.initiative_roll = roll_result.total

            results.append(InitiativeResult(
                combatant_id=combatant.id,
                combatant_name=combatant.name,
                roll=roll_result.base_roll,
                modifier=combatant.dexterity_modifier,
                total=roll_result.total,
            ))

        # Sort combatants by initiative (highest first)
        # Tiebreaker: higher DEX modifier goes first
        self._sort_by_initiative()

        # Sort results to match combatants order (CRITICAL: frontend needs sorted order)
        results.sort(key=lambda r: (r.total, r.modifier), reverse=True)

        self.combat_started = True
        self.current_round = 1
        self.current_turn_index = 0

        return results

    def set_initiative(self, combatant_id: str, initiative_value: int) -> bool:
        """
        Manually set initiative for a combatant (for DM override).

        Args:
            combatant_id: ID of combatant
            initiative_value: The initiative value to set

        Returns:
            True if found and updated, False otherwise
        """
        combatant = self.get_combatant(combatant_id)
        if combatant:
            combatant.initiative_roll = initiative_value
            self._sort_by_initiative()
            return True
        return False

    def _sort_by_initiative(self) -> None:
        """Sort combatants by initiative (highest first), with DEX tiebreaker."""
        self.combatants.sort(
            key=lambda c: (c.initiative_roll, c.dexterity_modifier),
            reverse=True
        )

    def get_current_combatant(self) -> Optional[Combatant]:
        """Get the combatant whose turn it is."""
        if not self.combat_started or not self.combatants:
            return None

        # Skip inactive combatants
        active_combatants = [c for c in self.combatants if c.is_active]
        if not active_combatants:
            return None

        # Find current active combatant
        checked = 0
        index = self.current_turn_index % len(self.combatants)

        while checked < len(self.combatants):
            combatant = self.combatants[index]
            if combatant.is_active:
                return combatant
            index = (index + 1) % len(self.combatants)
            checked += 1

        return None

    def advance_turn(self) -> Optional[Combatant]:
        """
        Advance to the next combatant's turn.

        Returns:
            The combatant whose turn it now is, or None if combat ended
        """
        if not self.combat_started or not self.combatants:
            return None

        current = self.get_current_combatant()
        if current:
            current.has_acted = True

        # Move to next combatant
        self.current_turn_index = (self.current_turn_index + 1) % len(self.combatants)

        # Check if we've completed a round
        if self.current_turn_index == 0:
            self._start_new_round()

        # Skip inactive combatants
        attempts = 0
        while attempts < len(self.combatants):
            current = self.combatants[self.current_turn_index]
            if current.is_active:
                return current
            self.current_turn_index = (self.current_turn_index + 1) % len(self.combatants)
            if self.current_turn_index == 0:
                self._start_new_round()
            attempts += 1

        return None  # No active combatants

    def _start_new_round(self) -> None:
        """Start a new combat round."""
        self.current_round += 1
        for combatant in self.combatants:
            combatant.reset_for_round()

    def get_initiative_order(self) -> List[Dict[str, Any]]:
        """
        Get the current initiative order for display.

        Returns:
            List of combatant info in initiative order
        """
        order = []
        for i, combatant in enumerate(self.combatants):
            order.append({
                "position": i + 1,
                "id": combatant.id,
                "name": combatant.name,
                "initiative": combatant.initiative_roll,
                "is_current": i == self.current_turn_index,
                "has_acted": combatant.has_acted,
                "is_active": combatant.is_active,
                "combatant_type": combatant.combatant_type.value,
                "current_hp": combatant.current_hp,
                "max_hp": combatant.max_hp,
                "conditions": combatant.conditions,
            })
        return order

    def get_active_combatants(self) -> List[Combatant]:
        """Get all active combatants."""
        return [c for c in self.combatants if c.is_active]

    def get_combatants_by_type(self, combatant_type: CombatantType) -> List[Combatant]:
        """Get all combatants of a specific type."""
        return [c for c in self.combatants if c.combatant_type == combatant_type]

    def is_combat_over(self) -> bool:
        """
        Check if combat has ended.

        Combat ends when only one side has active combatants.
        """
        if not self.combat_started:
            return False

        active_players = [
            c for c in self.combatants
            if c.is_active and c.combatant_type == CombatantType.PLAYER
        ]
        active_enemies = [
            c for c in self.combatants
            if c.is_active and c.combatant_type == CombatantType.ENEMY
        ]

        # Combat continues if both sides have active combatants
        return len(active_players) == 0 or len(active_enemies) == 0

    def get_combat_result(self) -> Optional[str]:
        """
        Get the result of combat if it's over.

        Returns:
            "victory" if players won, "defeat" if enemies won, None if ongoing
        """
        if not self.is_combat_over():
            return None

        active_players = [
            c for c in self.combatants
            if c.is_active and c.combatant_type == CombatantType.PLAYER
        ]

        return "victory" if len(active_players) > 0 else "defeat"

    def delay_turn(self, combatant_id: str, new_initiative: int) -> bool:
        """
        Allow a combatant to delay their turn by setting new initiative.

        Args:
            combatant_id: ID of combatant delaying
            new_initiative: The new initiative value (must be lower)

        Returns:
            True if successful, False otherwise
        """
        combatant = self.get_combatant(combatant_id)
        if not combatant:
            return False

        if new_initiative >= combatant.initiative_roll:
            return False  # Can only delay to lower initiative

        combatant.initiative_roll = new_initiative
        self._sort_by_initiative()
        return True

    def ready_action(self, combatant_id: str) -> bool:
        """
        Mark a combatant as having readied an action.

        Args:
            combatant_id: ID of combatant readying

        Returns:
            True if successful, False otherwise
        """
        combatant = self.get_combatant(combatant_id)
        if not combatant:
            return False

        combatant.has_acted = True  # They've used their turn to ready
        if "readied_action" not in combatant.conditions:
            combatant.conditions.append("readied_action")
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the tracker state."""
        return {
            "combatants": [c.to_dict() for c in self.combatants],
            "current_round": self.current_round,
            "current_turn_index": self.current_turn_index,
            "combat_started": self.combat_started,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InitiativeTracker":
        """Deserialize tracker state."""
        tracker = cls()
        tracker.combatants = [
            Combatant.from_dict(c) for c in data.get("combatants", [])
        ]
        tracker.current_round = data.get("current_round", 0)
        tracker.current_turn_index = data.get("current_turn_index", 0)
        tracker.combat_started = data.get("combat_started", False)
        return tracker


# Convenience functions for common operations

def create_initiative_tracker(
    players: List[Dict[str, Any]],
    enemies: List[Dict[str, Any]]
) -> InitiativeTracker:
    """
    Create a new initiative tracker with players and enemies.

    Args:
        players: List of player data dicts with name, dex_mod, hp, ac, class, level, etc.
        enemies: List of enemy data dicts with name, dex_mod, hp, ac

    Returns:
        Configured InitiativeTracker
    """
    tracker = InitiativeTracker()

    for player in players:
        # Extract character class from multiple possible locations
        char_class = (
            player.get("class") or
            player.get("character_class") or
            player.get("abilities", {}).get("class", "")
        )
        # DEBUG: Print extracted values
        print(f"[create_initiative_tracker] Player: {player.get('name')}, extracted char_class='{char_class}', player.class='{player.get('class')}', player.character_class='{player.get('character_class')}'", flush=True)
        tracker.add_combatant(
            name=player["name"],
            combatant_type=CombatantType.PLAYER,
            dexterity_modifier=player.get("dex_mod", 0),
            current_hp=player.get("current_hp", player.get("hp", 10)),
            max_hp=player.get("max_hp", player.get("hp", 10)),
            armor_class=player.get("ac", 10),
            combatant_id=player.get("id"),
            # Character data for display
            character_class=char_class,
            level=player.get("level", 1),
            stats=player.get("stats", {}),
            abilities=player.get("abilities", {}),
            equipment=player.get("equipment"),
            weapons=player.get("weapons", []),
            spellcasting=player.get("spellcasting"),
        )

    for enemy in enemies:
        tracker.add_combatant(
            name=enemy["name"],
            combatant_type=CombatantType.ENEMY,
            dexterity_modifier=enemy.get("dex_mod", 0),
            current_hp=enemy.get("current_hp", enemy.get("hp", 10)),
            max_hp=enemy.get("max_hp", enemy.get("hp", 10)),
            armor_class=enemy.get("ac", 10),
            combatant_id=enemy.get("id"),
            # Enemy data (if available)
            character_class=enemy.get("type", enemy.get("class", "")),
            level=enemy.get("cr", enemy.get("level", 1)),
            stats=enemy.get("stats", {}),
            abilities=enemy.get("abilities", {}),
            equipment=enemy.get("equipment"),
            weapons=enemy.get("weapons", []),
            spellcasting=enemy.get("spellcasting"),
        )

    return tracker


def roll_group_initiative(
    combatants: List[Dict[str, Any]]
) -> List[InitiativeResult]:
    """
    Roll initiative for a group of combatants.

    Args:
        combatants: List of combatant data dicts

    Returns:
        List of InitiativeResult sorted by initiative
    """
    results = []

    for combatant in combatants:
        dex_mod = combatant.get("dex_mod", 0)
        roll_result = roll_d20(modifier=dex_mod)

        results.append(InitiativeResult(
            combatant_id=combatant.get("id", str(uuid.uuid4())),
            combatant_name=combatant.get("name", "Unknown"),
            roll=roll_result.base_roll,
            modifier=dex_mod,
            total=roll_result.total,
        ))

    # Sort by total (highest first), with modifier as tiebreaker
    results.sort(key=lambda r: (r.total, r.modifier), reverse=True)

    return results
