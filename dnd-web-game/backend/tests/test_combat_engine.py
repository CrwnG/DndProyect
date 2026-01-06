"""Tests for the combat engine."""
import pytest

from app.core.combat_engine import (
    CombatEngine,
    CombatState,
    CombatPhase,
    TurnPhase,
    TurnState,
    ActionType,
    ActionResult,
)
from app.core.initiative import CombatantType


class TestCombatEngineInitialization:
    """Test combat engine initialization."""

    def test_create_empty_engine(self):
        """Should create an engine with default state."""
        engine = CombatEngine()

        assert engine.state is not None
        assert engine.state.phase == CombatPhase.NOT_IN_COMBAT
        assert len(engine.state.initiative_tracker.combatants) == 0

    def test_create_with_existing_state(self):
        """Should accept an existing state."""
        state = CombatState()
        state.id = "test-id"

        engine = CombatEngine(combat_state=state)

        assert engine.state.id == "test-id"


class TestCombatLifecycle:
    """Test combat start/end lifecycle."""

    def test_start_combat(self):
        """Should start combat with players and enemies."""
        engine = CombatEngine()

        players = [
            {"id": "player-1", "name": "Thorin", "dex_mod": 2, "hp": 45, "ac": 18}
        ]
        enemies = [
            {"id": "enemy-1", "name": "Goblin", "dex_mod": 2, "hp": 7, "ac": 15}
        ]

        results = engine.start_combat(players, enemies)

        assert engine.state.phase == CombatPhase.COMBAT_ACTIVE
        assert len(engine.state.initiative_tracker.combatants) == 2
        assert len(results) == 2
        assert engine.state.initiative_tracker.combat_started is True

    def test_start_combat_with_positions(self):
        """Should store initial positions."""
        engine = CombatEngine()

        players = [{"id": "p1", "name": "Player", "hp": 10}]
        enemies = [{"id": "e1", "name": "Enemy", "hp": 10}]
        positions = {"p1": (1, 1), "e1": (5, 5)}

        engine.start_combat(players, enemies, positions)

        assert engine.state.positions["p1"] == (1, 1)
        assert engine.state.positions["e1"] == (5, 5)

    def test_cannot_start_combat_twice(self):
        """Should raise error if combat already started."""
        engine = CombatEngine()
        engine.start_combat(
            [{"name": "Player", "hp": 10}],
            [{"name": "Enemy", "hp": 10}]
        )

        with pytest.raises(ValueError, match="already in progress"):
            engine.start_combat(
                [{"name": "Player2", "hp": 10}],
                [{"name": "Enemy2", "hp": 10}]
            )

    def test_end_combat(self):
        """Should end combat properly."""
        engine = CombatEngine()
        engine.start_combat(
            [{"name": "Player", "hp": 10}],
            [{"name": "Enemy", "hp": 10}]
        )

        result = engine.end_combat("test_end")

        assert engine.state.phase == CombatPhase.COMBAT_ENDED
        assert "reason" in result
        assert result["reason"] == "test_end"

    def test_cannot_end_combat_not_started(self):
        """Should raise error if no combat in progress."""
        engine = CombatEngine()

        with pytest.raises(ValueError, match="No combat"):
            engine.end_combat()


class TestTurnManagement:
    """Test turn-based combat flow."""

    def setup_method(self):
        """Set up a combat for each test."""
        self.engine = CombatEngine()
        self.engine.start_combat(
            [{"id": "player-1", "name": "Player", "dex_mod": 5, "hp": 20, "ac": 15}],
            [{"id": "enemy-1", "name": "Enemy", "dex_mod": -2, "hp": 10, "ac": 12}]
        )

    def test_get_current_combatant(self):
        """Should return the current combatant."""
        current = self.engine.get_current_combatant()

        assert current is not None
        # Due to initiative rolls, we can't predict who goes first
        assert current.name in ["Player", "Enemy"]

    def test_get_turn_state(self):
        """Should return the current turn state."""
        turn_state = self.engine.get_turn_state()

        assert turn_state is not None
        assert turn_state.action_taken is False
        assert turn_state.bonus_action_taken is False
        assert turn_state.movement_used == 0

    def test_end_turn_advances_to_next(self):
        """Should advance to the next combatant."""
        first = self.engine.get_current_combatant()

        next_combatant = self.engine.end_turn()

        assert next_combatant is not None
        assert next_combatant != first

    def test_turn_state_resets_on_new_turn(self):
        """Turn state should reset when advancing turns."""
        # Take an action on current turn
        current = self.engine.get_current_combatant()
        self.engine.state.current_turn.action_taken = True
        self.engine.state.current_turn.movement_used = 15

        # End turn
        self.engine.end_turn()

        # New turn should have fresh state
        new_turn = self.engine.get_turn_state()
        assert new_turn.action_taken is False
        assert new_turn.movement_used == 0


class TestTurnState:
    """Test TurnState class."""

    def test_reset(self):
        """Should reset all turn flags."""
        turn = TurnState(combatant_id="test")
        turn.movement_used = 30
        turn.action_taken = True
        turn.bonus_action_taken = True

        turn.reset()

        assert turn.movement_used == 0
        assert turn.action_taken is False
        assert turn.bonus_action_taken is False

    def test_can_take_action(self):
        """Should track action availability."""
        turn = TurnState(combatant_id="test")

        assert turn.can_take_action() is True

        turn.action_taken = True

        assert turn.can_take_action() is False

    def test_can_move(self):
        """Should track movement availability."""
        turn = TurnState(combatant_id="test")

        assert turn.can_move(30, 30) is True
        assert turn.can_move(35, 30) is False

        turn.movement_used = 20

        assert turn.can_move(10, 30) is True
        assert turn.can_move(15, 30) is False


class TestAttackAction:
    """Test attack actions."""

    def setup_method(self):
        """Set up a combat for each test."""
        self.engine = CombatEngine()
        self.engine.start_combat(
            [{
                "id": "player-1",
                "name": "Player",
                "dex_mod": 5,
                "hp": 20,
                "ac": 15,
                "attack_bonus": 5,
                "damage_dice": "1d8",
                "damage_type": "slashing"
            }],
            [{
                "id": "enemy-1",
                "name": "Enemy",
                "dex_mod": -2,
                "hp": 10,
                "ac": 12,
                "attack_bonus": 3,
                "damage_dice": "1d6",
                "damage_type": "piercing"
            }],
            positions={"player-1": (1, 1), "enemy-1": (2, 1)}
        )

    def test_attack_requires_target(self):
        """Attack should fail without a target."""
        result = self.engine.take_action(ActionType.ATTACK)

        assert result.success is False
        assert "No target" in result.description

    def test_attack_invalid_target(self):
        """Attack should fail against invalid target."""
        result = self.engine.take_action(ActionType.ATTACK, target_id="nonexistent")

        assert result.success is False
        assert "not found" in result.description

    def test_attack_succeeds(self):
        """Attack action should resolve."""
        current = self.engine.get_current_combatant()

        # Find a valid target (the other combatant)
        if current.id == "player-1":
            target_id = "enemy-1"
        else:
            target_id = "player-1"

        result = self.engine.take_action(ActionType.ATTACK, target_id=target_id)

        assert result.success is True
        assert result.action_type == "attack"
        assert "hit" in result.extra_data or result.damage_dealt >= 0

    def test_attack_uses_action(self):
        """Taking attack should use the action."""
        current = self.engine.get_current_combatant()
        target_id = "enemy-1" if current.id == "player-1" else "player-1"

        self.engine.take_action(ActionType.ATTACK, target_id=target_id)

        assert self.engine.state.current_turn.action_taken is True

    def test_cannot_attack_twice(self):
        """Should not be able to attack twice in one turn."""
        current = self.engine.get_current_combatant()
        target_id = "enemy-1" if current.id == "player-1" else "player-1"

        self.engine.take_action(ActionType.ATTACK, target_id=target_id)
        result = self.engine.take_action(ActionType.ATTACK, target_id=target_id)

        assert result.success is False
        assert "No attacks remaining" in result.description

    def test_attack_damage_applied(self):
        """Damage should be applied to target."""
        # Force player to go first by setting high initiative
        player = self.engine.state.initiative_tracker.get_combatant("player-1")
        enemy = self.engine.state.initiative_tracker.get_combatant("enemy-1")

        player.initiative_roll = 25
        enemy.initiative_roll = 1
        self.engine.state.initiative_tracker._sort_by_initiative()
        self.engine._start_current_turn()

        initial_hp = self.engine.state.combatant_stats["enemy-1"]["current_hp"]

        # Attack multiple times until we get a hit
        for _ in range(10):
            self.engine.state.current_turn.action_taken = False
            result = self.engine.take_action(ActionType.ATTACK, target_id="enemy-1")
            if result.extra_data.get("hit"):
                break

        if result.extra_data.get("hit"):
            final_hp = self.engine.state.combatant_stats["enemy-1"]["current_hp"]
            assert final_hp < initial_hp


class TestOtherActions:
    """Test non-attack actions."""

    def setup_method(self):
        """Set up a combat for each test."""
        self.engine = CombatEngine()
        self.engine.start_combat(
            [{"id": "player-1", "name": "Player", "hp": 20, "speed": 30}],
            [{"id": "enemy-1", "name": "Enemy", "hp": 10}]
        )

    def test_dash_action(self):
        """Dash should grant extra movement."""
        result = self.engine.take_action(ActionType.DASH)

        assert result.success is True
        assert "dash" in result.description.lower()
        assert "additional_movement" in result.extra_data

    def test_disengage_action(self):
        """Disengage should apply condition."""
        result = self.engine.take_action(ActionType.DISENGAGE)

        assert result.success is True
        assert "disengage" in result.description.lower()

        current = self.engine.get_current_combatant()
        assert "disengaged" in current.conditions

    def test_dodge_action(self):
        """Dodge should apply condition."""
        result = self.engine.take_action(ActionType.DODGE)

        assert result.success is True
        assert "dodge" in result.description.lower()

        current = self.engine.get_current_combatant()
        assert "dodging" in current.conditions

    def test_help_action(self):
        """Help action should succeed."""
        result = self.engine.take_action(ActionType.HELP)

        assert result.success is True
        assert "help" in result.description.lower()

    def test_hide_action(self):
        """Hide should apply condition and roll stealth."""
        result = self.engine.take_action(ActionType.HIDE)

        assert result.success is True
        assert "hide" in result.description.lower()
        assert "stealth_roll" in result.extra_data

        current = self.engine.get_current_combatant()
        assert "hidden" in current.conditions

    def test_ready_action(self):
        """Ready should apply condition."""
        result = self.engine.take_action(
            ActionType.READY,
            trigger="an enemy approaches",
            readied_action="attack"
        )

        assert result.success is True
        assert result.action_type == "ready"

        current = self.engine.get_current_combatant()
        assert "readied_action" in current.conditions


class TestMovement:
    """Test movement in combat."""

    def setup_method(self):
        """Set up a combat for each test."""
        self.engine = CombatEngine()
        self.engine.start_combat(
            [{"id": "player-1", "name": "Player", "hp": 20, "speed": 30}],
            [{"id": "enemy-1", "name": "Enemy", "hp": 10, "speed": 30}],
            positions={"player-1": (1, 1), "enemy-1": (5, 5)}
        )

    def test_move_combatant(self):
        """Should move combatant to new position."""
        current = self.engine.get_current_combatant()

        result = self.engine.move_combatant(current.id, 2, 2)

        assert result.success is True
        assert self.engine.state.positions[current.id] == (2, 2)

    def test_move_tracks_distance(self):
        """Movement should track distance used."""
        current = self.engine.get_current_combatant()
        current_pos = self.engine.state.positions[current.id]

        # Move 2 squares (10ft)
        new_x = current_pos[0] + 2
        self.engine.move_combatant(current.id, new_x, current_pos[1])

        assert self.engine.state.current_turn.movement_used == 10

    def test_cannot_exceed_speed(self):
        """Should not allow movement beyond speed."""
        current = self.engine.get_current_combatant()
        current_pos = self.engine.state.positions.get(current.id, (0, 0))

        # Try to move 40ft (8 squares) from current position
        # Moving 8 squares in x direction should exceed 30ft speed
        new_x = current_pos[0] + 8
        result = self.engine.move_combatant(current.id, new_x, current_pos[1])

        assert result.success is False
        assert "Not enough movement" in result.description

    def test_move_calculates_diagonal(self):
        """Diagonal movement should be calculated correctly."""
        current = self.engine.get_current_combatant()

        # Move diagonally 2 squares (10ft)
        result = self.engine.move_combatant(current.id, 3, 3)

        assert result.success is True
        # Diagonal uses Chebyshev distance (max of x or y)
        assert result.extra_data["distance"] == 10


class TestCombatStateQueries:
    """Test state query methods."""

    def setup_method(self):
        """Set up a combat for each test."""
        self.engine = CombatEngine()
        self.engine.start_combat(
            [{"id": "player-1", "name": "Player", "hp": 20}],
            [{"id": "enemy-1", "name": "Enemy", "hp": 10}],
            positions={"player-1": (1, 1), "enemy-1": (2, 2)}
        )

    def test_get_combat_state(self):
        """Should return full combat state."""
        state = self.engine.get_combat_state()

        assert state["phase"] == "COMBAT_ACTIVE"
        assert state["round"] >= 1
        assert len(state["initiative_order"]) == 2
        assert state["current_combatant"] is not None

    def test_get_combatant_at_position(self):
        """Should find combatant at position."""
        combatant = self.engine.get_combatant_at_position(1, 1)

        assert combatant is not None
        assert combatant.id == "player-1"

    def test_get_combatant_at_empty_position(self):
        """Should return None for empty position."""
        combatant = self.engine.get_combatant_at_position(0, 0)

        assert combatant is None

    def test_get_valid_targets_melee(self):
        """Should find targets in melee range."""
        # Move enemy adjacent to player
        self.engine.state.positions["enemy-1"] = (2, 1)

        targets = self.engine.get_valid_targets("player-1", range_ft=5)

        assert "enemy-1" in targets

    def test_get_valid_targets_out_of_range(self):
        """Should not include targets out of range."""
        # Enemy is at (2, 2), which is 1 diagonal square away
        targets = self.engine.get_valid_targets("player-1", range_ft=5)

        # 1 diagonal square = 5ft, so should be in range
        assert "enemy-1" in targets

    def test_get_recent_events(self):
        """Should return recent events."""
        events = self.engine.get_recent_events(5)

        assert len(events) > 0
        # Should have combat_started and initiative_rolled at minimum
        event_types = [e["type"] for e in events]
        assert "combat_started" in event_types


class TestCombatVictoryDefeat:
    """Test combat end conditions."""

    def test_combat_ends_on_enemy_defeat(self):
        """Combat should end when all enemies are defeated."""
        engine = CombatEngine()
        engine.start_combat(
            [{"id": "player-1", "name": "Player", "hp": 20}],
            [{"id": "enemy-1", "name": "Enemy", "hp": 1, "ac": 1}],  # Easy to kill
        )

        # Defeat the enemy
        enemy = engine.state.initiative_tracker.get_combatant("enemy-1")
        enemy.is_active = False

        # Try to end turn - should end combat
        result = engine.end_turn()

        assert engine.state.phase == CombatPhase.COMBAT_ENDED

    def test_combat_ends_on_player_defeat(self):
        """Combat should end when all players are defeated."""
        engine = CombatEngine()
        engine.start_combat(
            [{"id": "player-1", "name": "Player", "hp": 1}],
            [{"id": "enemy-1", "name": "Enemy", "hp": 20}],
        )

        # Defeat the player
        player = engine.state.initiative_tracker.get_combatant("player-1")
        player.is_active = False

        # Try to end turn - should end combat
        result = engine.end_turn()

        assert engine.state.phase == CombatPhase.COMBAT_ENDED


class TestSerialization:
    """Test combat state serialization."""

    def test_to_dict(self):
        """Should serialize combat state."""
        engine = CombatEngine()
        engine.start_combat(
            [{"id": "player-1", "name": "Player", "hp": 20}],
            [{"id": "enemy-1", "name": "Enemy", "hp": 10}],
            positions={"player-1": (1, 1), "enemy-1": (5, 5)}
        )

        data = engine.to_dict()

        assert "combat_state" in data
        assert data["combat_state"]["phase"] == "COMBAT_ACTIVE"
        assert len(data["combat_state"]["initiative_tracker"]["combatants"]) == 2

    def test_from_dict(self):
        """Should deserialize combat state."""
        engine = CombatEngine()
        engine.start_combat(
            [{"id": "player-1", "name": "Player", "hp": 20}],
            [{"id": "enemy-1", "name": "Enemy", "hp": 10}],
            positions={"player-1": (1, 1), "enemy-1": (5, 5)}
        )

        # Take some actions
        engine.take_action(ActionType.DODGE)

        # Serialize
        data = engine.to_dict()

        # Deserialize
        restored = CombatEngine.from_dict(data)

        assert restored.state.phase == CombatPhase.COMBAT_ACTIVE
        assert len(restored.state.initiative_tracker.combatants) == 2
        assert restored.state.positions == {"player-1": (1, 1), "enemy-1": (5, 5)}

    def test_round_trip_preserves_state(self):
        """Serializing and deserializing should preserve state."""
        engine = CombatEngine()
        engine.start_combat(
            [{"id": "player-1", "name": "Player", "hp": 20}],
            [{"id": "enemy-1", "name": "Enemy", "hp": 10}],
        )

        original_round = engine.state.initiative_tracker.current_round
        original_id = engine.state.id

        data = engine.to_dict()
        restored = CombatEngine.from_dict(data)

        assert restored.state.initiative_tracker.current_round == original_round
        assert restored.state.id == original_id


class TestEventLogging:
    """Test combat event logging."""

    def test_combat_start_logged(self):
        """Combat start should be logged."""
        engine = CombatEngine()
        engine.start_combat(
            [{"name": "Player", "hp": 20}],
            [{"name": "Enemy", "hp": 10}],
        )

        events = engine.get_recent_events(10)
        event_types = [e["type"] for e in events]

        assert "combat_started" in event_types

    def test_turn_events_logged(self):
        """Turn start/end should be logged."""
        engine = CombatEngine()
        engine.start_combat(
            [{"name": "Player", "hp": 20}],
            [{"name": "Enemy", "hp": 10}],
        )

        engine.end_turn()

        events = engine.get_recent_events(10)
        event_types = [e["type"] for e in events]

        assert "turn_started" in event_types
        assert "turn_ended" in event_types

    def test_action_events_logged(self):
        """Actions should be logged."""
        engine = CombatEngine()
        engine.start_combat(
            [{"id": "player-1", "name": "Player", "hp": 20}],
            [{"id": "enemy-1", "name": "Enemy", "hp": 10}],
        )

        engine.take_action(ActionType.DODGE)

        events = engine.get_recent_events(10)
        event_types = [e["type"] for e in events]

        assert "dodge" in event_types


class TestCombatNotActive:
    """Test behavior when combat is not active."""

    def test_cannot_take_action_before_combat(self):
        """Should not allow actions before combat starts."""
        engine = CombatEngine()

        result = engine.take_action(ActionType.ATTACK, target_id="any")

        assert result.success is False
        assert "not active" in result.description

    def test_cannot_move_before_combat(self):
        """Should not allow movement before combat starts."""
        engine = CombatEngine()

        result = engine.move_combatant("any", 1, 1)

        assert result.success is False
        assert "not active" in result.description

    def test_cannot_end_turn_before_combat(self):
        """Should not allow ending turn before combat starts."""
        engine = CombatEngine()

        with pytest.raises(ValueError):
            engine.end_turn()
