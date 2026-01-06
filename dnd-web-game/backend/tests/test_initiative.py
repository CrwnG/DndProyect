"""Tests for the initiative system."""
import pytest

from app.core.initiative import (
    CombatantType,
    Combatant,
    InitiativeResult,
    InitiativeTracker,
    create_initiative_tracker,
    roll_group_initiative,
)


class TestCombatant:
    """Test the Combatant class."""

    def test_create_combatant(self):
        """Should create a combatant with default values."""
        combatant = Combatant(
            id="test-1",
            name="Test Fighter",
            combatant_type=CombatantType.PLAYER,
        )

        assert combatant.id == "test-1"
        assert combatant.name == "Test Fighter"
        assert combatant.combatant_type == CombatantType.PLAYER
        assert combatant.dexterity_modifier == 0
        assert combatant.initiative_roll == 0
        assert combatant.has_acted is False
        assert combatant.is_active is True
        assert combatant.conditions == []

    def test_combatant_with_stats(self):
        """Should create a combatant with full stats."""
        combatant = Combatant(
            id="fighter-1",
            name="Thorin",
            combatant_type=CombatantType.PLAYER,
            dexterity_modifier=2,
            current_hp=45,
            max_hp=45,
            armor_class=18,
        )

        assert combatant.dexterity_modifier == 2
        assert combatant.current_hp == 45
        assert combatant.max_hp == 45
        assert combatant.armor_class == 18

    def test_roll_initiative(self):
        """Combatant should be able to roll initiative."""
        combatant = Combatant(
            id="test-1",
            name="Test",
            combatant_type=CombatantType.PLAYER,
            dexterity_modifier=3,
        )

        result = combatant.roll_initiative()

        # With +3 DEX, result should be between 4 and 23
        assert result >= 4
        assert result <= 23
        assert combatant.initiative_roll == result

    def test_reset_for_round(self):
        """Should reset turn state for a new round."""
        combatant = Combatant(
            id="test-1",
            name="Test",
            combatant_type=CombatantType.PLAYER,
        )
        combatant.has_acted = True

        combatant.reset_for_round()

        assert combatant.has_acted is False

    def test_to_dict(self):
        """Should serialize to dictionary."""
        combatant = Combatant(
            id="test-1",
            name="Test Fighter",
            combatant_type=CombatantType.PLAYER,
            dexterity_modifier=2,
            initiative_roll=15,
            current_hp=30,
            max_hp=45,
            armor_class=18,
            conditions=["poisoned"],
        )

        data = combatant.to_dict()

        assert data["id"] == "test-1"
        assert data["name"] == "Test Fighter"
        assert data["combatant_type"] == "player"
        assert data["dexterity_modifier"] == 2
        assert data["initiative_roll"] == 15
        assert data["current_hp"] == 30
        assert data["max_hp"] == 45
        assert data["armor_class"] == 18
        assert data["conditions"] == ["poisoned"]

    def test_from_dict(self):
        """Should deserialize from dictionary."""
        data = {
            "id": "test-1",
            "name": "Test Fighter",
            "combatant_type": "player",
            "dexterity_modifier": 2,
            "initiative_roll": 15,
            "current_hp": 30,
            "max_hp": 45,
            "armor_class": 18,
            "conditions": ["poisoned"],
        }

        combatant = Combatant.from_dict(data)

        assert combatant.id == "test-1"
        assert combatant.name == "Test Fighter"
        assert combatant.combatant_type == CombatantType.PLAYER
        assert combatant.dexterity_modifier == 2
        assert combatant.initiative_roll == 15
        assert combatant.conditions == ["poisoned"]


class TestInitiativeTracker:
    """Test the InitiativeTracker class."""

    def test_add_combatant(self):
        """Should add a combatant to the tracker."""
        tracker = InitiativeTracker()

        combatant = tracker.add_combatant(
            name="Thorin",
            combatant_type=CombatantType.PLAYER,
            dexterity_modifier=2,
            current_hp=45,
            max_hp=45,
            armor_class=18,
        )

        assert len(tracker.combatants) == 1
        assert combatant.name == "Thorin"
        assert combatant.id is not None

    def test_add_combatant_with_id(self):
        """Should use provided ID if given."""
        tracker = InitiativeTracker()

        combatant = tracker.add_combatant(
            name="Thorin",
            combatant_type=CombatantType.PLAYER,
            combatant_id="custom-id-123",
        )

        assert combatant.id == "custom-id-123"

    def test_remove_combatant(self):
        """Should remove a combatant from the tracker."""
        tracker = InitiativeTracker()
        combatant = tracker.add_combatant(
            name="Goblin",
            combatant_type=CombatantType.ENEMY,
        )

        result = tracker.remove_combatant(combatant.id)

        assert result is True
        assert len(tracker.combatants) == 0

    def test_remove_combatant_not_found(self):
        """Should return False if combatant not found."""
        tracker = InitiativeTracker()

        result = tracker.remove_combatant("nonexistent-id")

        assert result is False

    def test_remove_adjusts_turn_index(self):
        """Removing combatant before current should adjust index."""
        tracker = InitiativeTracker()
        tracker.add_combatant(name="A", combatant_type=CombatantType.PLAYER)
        b = tracker.add_combatant(name="B", combatant_type=CombatantType.PLAYER)
        tracker.add_combatant(name="C", combatant_type=CombatantType.PLAYER)

        tracker.current_turn_index = 2  # C's turn

        tracker.remove_combatant(b.id)  # Remove B

        # Index should adjust since we removed someone before current
        assert tracker.current_turn_index == 1

    def test_set_combatant_inactive(self):
        """Should mark combatant as inactive."""
        tracker = InitiativeTracker()
        combatant = tracker.add_combatant(
            name="Goblin",
            combatant_type=CombatantType.ENEMY,
        )

        result = tracker.set_combatant_inactive(combatant.id)

        assert result is True
        assert combatant.is_active is False

    def test_get_combatant(self):
        """Should get combatant by ID."""
        tracker = InitiativeTracker()
        combatant = tracker.add_combatant(
            name="Thorin",
            combatant_type=CombatantType.PLAYER,
        )

        found = tracker.get_combatant(combatant.id)

        assert found is combatant

    def test_get_combatant_not_found(self):
        """Should return None if combatant not found."""
        tracker = InitiativeTracker()

        found = tracker.get_combatant("nonexistent")

        assert found is None

    def test_roll_all_initiative(self):
        """Should roll initiative for all combatants."""
        tracker = InitiativeTracker()
        tracker.add_combatant(
            name="Thorin",
            combatant_type=CombatantType.PLAYER,
            dexterity_modifier=2,
        )
        tracker.add_combatant(
            name="Goblin",
            combatant_type=CombatantType.ENEMY,
            dexterity_modifier=-1,
        )

        results = tracker.roll_all_initiative()

        assert len(results) == 2
        assert tracker.combat_started is True
        assert tracker.current_round == 1
        assert tracker.current_turn_index == 0

        # Check that combatants are sorted
        for i in range(len(tracker.combatants) - 1):
            current = tracker.combatants[i]
            next_c = tracker.combatants[i + 1]
            assert current.initiative_roll >= next_c.initiative_roll

    def test_initiative_results_have_data(self):
        """Initiative results should contain roll data."""
        tracker = InitiativeTracker()
        tracker.add_combatant(
            name="Thorin",
            combatant_type=CombatantType.PLAYER,
            dexterity_modifier=3,
        )

        results = tracker.roll_all_initiative()

        assert results[0].combatant_name == "Thorin"
        assert results[0].modifier == 3
        assert results[0].roll >= 1
        assert results[0].roll <= 20
        assert results[0].total == results[0].roll + results[0].modifier

    def test_set_initiative_manually(self):
        """Should allow manual initiative override."""
        tracker = InitiativeTracker()
        combatant = tracker.add_combatant(
            name="Thorin",
            combatant_type=CombatantType.PLAYER,
        )

        result = tracker.set_initiative(combatant.id, 20)

        assert result is True
        assert combatant.initiative_roll == 20

    def test_get_current_combatant(self):
        """Should return current combatant."""
        tracker = InitiativeTracker()
        tracker.add_combatant(
            name="Thorin",
            combatant_type=CombatantType.PLAYER,
            dexterity_modifier=5,  # High DEX to likely go first
        )
        tracker.add_combatant(
            name="Goblin",
            combatant_type=CombatantType.ENEMY,
            dexterity_modifier=-2,
        )

        tracker.roll_all_initiative()
        current = tracker.get_current_combatant()

        assert current is not None
        assert current == tracker.combatants[0]

    def test_get_current_combatant_not_started(self):
        """Should return None if combat not started."""
        tracker = InitiativeTracker()
        tracker.add_combatant(
            name="Thorin",
            combatant_type=CombatantType.PLAYER,
        )

        current = tracker.get_current_combatant()

        assert current is None

    def test_get_current_combatant_skips_inactive(self):
        """Should skip inactive combatants."""
        tracker = InitiativeTracker()
        tracker.add_combatant(
            name="A",
            combatant_type=CombatantType.PLAYER,
        )
        tracker.add_combatant(
            name="B",
            combatant_type=CombatantType.PLAYER,
        )

        tracker.roll_all_initiative()
        # Make first combatant inactive
        tracker.combatants[0].is_active = False

        current = tracker.get_current_combatant()

        assert current == tracker.combatants[1]

    def test_advance_turn(self):
        """Should advance to next combatant."""
        tracker = InitiativeTracker()
        tracker.add_combatant(name="A", combatant_type=CombatantType.PLAYER)
        tracker.add_combatant(name="B", combatant_type=CombatantType.PLAYER)

        tracker.roll_all_initiative()
        first = tracker.get_current_combatant()

        next_combatant = tracker.advance_turn()

        assert next_combatant is not None
        assert next_combatant != first
        assert first.has_acted is True

    def test_advance_turn_wraps_around(self):
        """Should wrap to round 2 after all combatants act."""
        tracker = InitiativeTracker()
        tracker.add_combatant(name="A", combatant_type=CombatantType.PLAYER)
        tracker.add_combatant(name="B", combatant_type=CombatantType.ENEMY)

        tracker.roll_all_initiative()
        assert tracker.current_round == 1

        tracker.advance_turn()  # A acts, B's turn
        tracker.advance_turn()  # B acts, back to A, round 2

        assert tracker.current_round == 2
        # Both should have has_acted reset
        for c in tracker.combatants:
            assert c.has_acted is False

    def test_advance_turn_skips_inactive(self):
        """Should skip inactive combatants when advancing."""
        tracker = InitiativeTracker()
        a = tracker.add_combatant(name="A", combatant_type=CombatantType.PLAYER)
        b = tracker.add_combatant(name="B", combatant_type=CombatantType.PLAYER)
        c = tracker.add_combatant(name="C", combatant_type=CombatantType.PLAYER)

        tracker.roll_all_initiative()
        # Manually set order for predictable test
        a.initiative_roll = 20
        b.initiative_roll = 15
        c.initiative_roll = 10
        tracker._sort_by_initiative()

        # Mark B as inactive
        b.is_active = False

        tracker.advance_turn()  # A's turn ends

        current = tracker.get_current_combatant()
        assert current == c  # Should skip B

    def test_get_initiative_order(self):
        """Should return ordered list for display."""
        tracker = InitiativeTracker()
        tracker.add_combatant(
            name="Thorin",
            combatant_type=CombatantType.PLAYER,
            current_hp=45,
            max_hp=45,
        )
        tracker.add_combatant(
            name="Goblin",
            combatant_type=CombatantType.ENEMY,
            current_hp=7,
            max_hp=7,
        )

        tracker.roll_all_initiative()
        order = tracker.get_initiative_order()

        assert len(order) == 2
        assert order[0]["position"] == 1
        assert order[0]["is_current"] is True
        assert order[1]["position"] == 2
        assert order[1]["is_current"] is False

        # Check all expected fields
        for entry in order:
            assert "id" in entry
            assert "name" in entry
            assert "initiative" in entry
            assert "has_acted" in entry
            assert "is_active" in entry
            assert "combatant_type" in entry
            assert "current_hp" in entry
            assert "max_hp" in entry
            assert "conditions" in entry

    def test_get_active_combatants(self):
        """Should return only active combatants."""
        tracker = InitiativeTracker()
        a = tracker.add_combatant(name="A", combatant_type=CombatantType.PLAYER)
        b = tracker.add_combatant(name="B", combatant_type=CombatantType.PLAYER)

        b.is_active = False

        active = tracker.get_active_combatants()

        assert len(active) == 1
        assert active[0] == a

    def test_get_combatants_by_type(self):
        """Should filter by combatant type."""
        tracker = InitiativeTracker()
        tracker.add_combatant(name="Player1", combatant_type=CombatantType.PLAYER)
        tracker.add_combatant(name="Player2", combatant_type=CombatantType.PLAYER)
        tracker.add_combatant(name="Goblin", combatant_type=CombatantType.ENEMY)

        players = tracker.get_combatants_by_type(CombatantType.PLAYER)
        enemies = tracker.get_combatants_by_type(CombatantType.ENEMY)

        assert len(players) == 2
        assert len(enemies) == 1

    def test_is_combat_over_players_win(self):
        """Combat ends when no enemies remain active."""
        tracker = InitiativeTracker()
        tracker.add_combatant(name="Player", combatant_type=CombatantType.PLAYER)
        goblin = tracker.add_combatant(name="Goblin", combatant_type=CombatantType.ENEMY)

        tracker.roll_all_initiative()
        assert tracker.is_combat_over() is False

        goblin.is_active = False

        assert tracker.is_combat_over() is True

    def test_is_combat_over_enemies_win(self):
        """Combat ends when no players remain active."""
        tracker = InitiativeTracker()
        player = tracker.add_combatant(name="Player", combatant_type=CombatantType.PLAYER)
        tracker.add_combatant(name="Goblin", combatant_type=CombatantType.ENEMY)

        tracker.roll_all_initiative()
        player.is_active = False

        assert tracker.is_combat_over() is True

    def test_get_combat_result_victory(self):
        """Should return victory when players win."""
        tracker = InitiativeTracker()
        tracker.add_combatant(name="Player", combatant_type=CombatantType.PLAYER)
        goblin = tracker.add_combatant(name="Goblin", combatant_type=CombatantType.ENEMY)

        tracker.roll_all_initiative()
        goblin.is_active = False

        assert tracker.get_combat_result() == "victory"

    def test_get_combat_result_defeat(self):
        """Should return defeat when enemies win."""
        tracker = InitiativeTracker()
        player = tracker.add_combatant(name="Player", combatant_type=CombatantType.PLAYER)
        tracker.add_combatant(name="Goblin", combatant_type=CombatantType.ENEMY)

        tracker.roll_all_initiative()
        player.is_active = False

        assert tracker.get_combat_result() == "defeat"

    def test_get_combat_result_ongoing(self):
        """Should return None if combat is ongoing."""
        tracker = InitiativeTracker()
        tracker.add_combatant(name="Player", combatant_type=CombatantType.PLAYER)
        tracker.add_combatant(name="Goblin", combatant_type=CombatantType.ENEMY)

        tracker.roll_all_initiative()

        assert tracker.get_combat_result() is None

    def test_delay_turn(self):
        """Should allow delaying to lower initiative."""
        tracker = InitiativeTracker()
        combatant = tracker.add_combatant(
            name="Thorin",
            combatant_type=CombatantType.PLAYER,
        )
        combatant.initiative_roll = 20

        result = tracker.delay_turn(combatant.id, 10)

        assert result is True
        assert combatant.initiative_roll == 10

    def test_delay_turn_cannot_increase(self):
        """Should not allow delaying to higher initiative."""
        tracker = InitiativeTracker()
        combatant = tracker.add_combatant(
            name="Thorin",
            combatant_type=CombatantType.PLAYER,
        )
        combatant.initiative_roll = 10

        result = tracker.delay_turn(combatant.id, 15)

        assert result is False
        assert combatant.initiative_roll == 10  # Unchanged

    def test_ready_action(self):
        """Should mark combatant as having readied action."""
        tracker = InitiativeTracker()
        combatant = tracker.add_combatant(
            name="Thorin",
            combatant_type=CombatantType.PLAYER,
        )

        result = tracker.ready_action(combatant.id)

        assert result is True
        assert combatant.has_acted is True
        assert "readied_action" in combatant.conditions

    def test_serialization(self):
        """Should serialize and deserialize tracker state."""
        tracker = InitiativeTracker()
        tracker.add_combatant(
            name="Thorin",
            combatant_type=CombatantType.PLAYER,
            current_hp=45,
            max_hp=45,
        )
        tracker.add_combatant(
            name="Goblin",
            combatant_type=CombatantType.ENEMY,
            current_hp=7,
            max_hp=7,
        )

        tracker.roll_all_initiative()
        tracker.advance_turn()

        # Serialize
        data = tracker.to_dict()

        # Deserialize
        restored = InitiativeTracker.from_dict(data)

        assert len(restored.combatants) == 2
        assert restored.current_round == tracker.current_round
        assert restored.current_turn_index == tracker.current_turn_index
        assert restored.combat_started is True


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_create_initiative_tracker(self):
        """Should create tracker with players and enemies."""
        players = [
            {"name": "Thorin", "dex_mod": 2, "hp": 45, "ac": 18},
            {"name": "Lyra", "dex_mod": 4, "hp": 28, "ac": 14},
        ]
        enemies = [
            {"name": "Goblin 1", "dex_mod": 2, "hp": 7, "ac": 15},
            {"name": "Goblin 2", "dex_mod": 2, "hp": 7, "ac": 15},
        ]

        tracker = create_initiative_tracker(players, enemies)

        assert len(tracker.combatants) == 4

        player_combatants = tracker.get_combatants_by_type(CombatantType.PLAYER)
        enemy_combatants = tracker.get_combatants_by_type(CombatantType.ENEMY)

        assert len(player_combatants) == 2
        assert len(enemy_combatants) == 2

    def test_create_initiative_tracker_with_ids(self):
        """Should use provided IDs."""
        players = [
            {"id": "player-1", "name": "Thorin", "dex_mod": 2, "hp": 45},
        ]
        enemies = [
            {"id": "enemy-1", "name": "Goblin", "dex_mod": 2, "hp": 7},
        ]

        tracker = create_initiative_tracker(players, enemies)

        assert tracker.get_combatant("player-1") is not None
        assert tracker.get_combatant("enemy-1") is not None

    def test_roll_group_initiative(self):
        """Should roll and sort initiative for a group."""
        combatants = [
            {"id": "1", "name": "Fighter", "dex_mod": 2},
            {"id": "2", "name": "Wizard", "dex_mod": 1},
            {"id": "3", "name": "Rogue", "dex_mod": 4},
        ]

        results = roll_group_initiative(combatants)

        assert len(results) == 3

        # Should be sorted highest to lowest
        for i in range(len(results) - 1):
            assert results[i].total >= results[i + 1].total

    def test_roll_group_initiative_includes_modifiers(self):
        """Results should include modifier in total."""
        combatants = [
            {"id": "1", "name": "High DEX", "dex_mod": 5},
        ]

        results = roll_group_initiative(combatants)

        assert results[0].modifier == 5
        assert results[0].total == results[0].roll + 5


class TestInitiativeTiebreaker:
    """Test that DEX modifier is used as tiebreaker."""

    def test_dex_tiebreaker(self):
        """Higher DEX should win ties."""
        tracker = InitiativeTracker()

        # Create two combatants with same initiative but different DEX
        low_dex = tracker.add_combatant(
            name="Low DEX",
            combatant_type=CombatantType.PLAYER,
            dexterity_modifier=0,
        )
        high_dex = tracker.add_combatant(
            name="High DEX",
            combatant_type=CombatantType.PLAYER,
            dexterity_modifier=5,
        )

        # Manually set same initiative
        low_dex.initiative_roll = 15
        high_dex.initiative_roll = 15

        tracker._sort_by_initiative()

        # High DEX should come first
        assert tracker.combatants[0] == high_dex
        assert tracker.combatants[1] == low_dex


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_tracker(self):
        """Empty tracker should handle operations gracefully."""
        tracker = InitiativeTracker()

        assert tracker.get_current_combatant() is None
        assert tracker.advance_turn() is None
        assert tracker.is_combat_over() is False
        assert tracker.get_combat_result() is None
        assert tracker.get_initiative_order() == []

    def test_all_combatants_inactive(self):
        """Should handle all combatants being inactive."""
        tracker = InitiativeTracker()
        a = tracker.add_combatant(name="A", combatant_type=CombatantType.PLAYER)
        b = tracker.add_combatant(name="B", combatant_type=CombatantType.ENEMY)

        tracker.roll_all_initiative()

        a.is_active = False
        b.is_active = False

        assert tracker.get_current_combatant() is None
        assert tracker.advance_turn() is None

    def test_single_combatant(self):
        """Should handle single combatant."""
        tracker = InitiativeTracker()
        tracker.add_combatant(name="Solo", combatant_type=CombatantType.PLAYER)

        tracker.roll_all_initiative()

        current = tracker.get_current_combatant()
        assert current is not None
        assert current.name == "Solo"

    def test_npc_combatant_type(self):
        """NPCs should work as combatants."""
        tracker = InitiativeTracker()
        tracker.add_combatant(name="Ally", combatant_type=CombatantType.NPC)

        npcs = tracker.get_combatants_by_type(CombatantType.NPC)

        assert len(npcs) == 1
        assert npcs[0].name == "Ally"

    def test_combat_with_only_players(self):
        """Combat with only players should be 'over' immediately."""
        tracker = InitiativeTracker()
        tracker.add_combatant(name="Player1", combatant_type=CombatantType.PLAYER)
        tracker.add_combatant(name="Player2", combatant_type=CombatantType.PLAYER)

        tracker.roll_all_initiative()

        # No enemies means combat is "over" with victory
        assert tracker.is_combat_over() is True
        assert tracker.get_combat_result() == "victory"
