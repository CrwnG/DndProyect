"""Tests for the death saving throw system."""
import pytest
from unittest.mock import patch
from app.core.death_saves import (
    DeathSaveState,
    DeathSaveOutcome,
    DeathSaveResult,
    roll_death_save,
    take_damage_while_dying,
    stabilize_creature,
    heal_dying_creature,
    get_death_save_status,
    attempt_medicine_check,
)


class TestDeathSaveState:
    """Tests for DeathSaveState class."""

    def test_initial_state(self):
        """New state should start with zero counts."""
        state = DeathSaveState()
        assert state.successes == 0
        assert state.failures == 0
        assert state.is_stable is False
        assert state.is_dead is False

    def test_reset(self):
        """Reset should clear counts but keep is_dead."""
        state = DeathSaveState(successes=2, failures=1, is_stable=True)
        state.reset()
        assert state.successes == 0
        assert state.failures == 0
        assert state.is_stable is False

    def test_to_dict(self):
        """to_dict should return correct dictionary."""
        state = DeathSaveState(successes=1, failures=2, is_stable=False, is_dead=False)
        d = state.to_dict()
        assert d["successes"] == 1
        assert d["failures"] == 2
        assert d["is_stable"] is False
        assert d["is_dead"] is False

    def test_from_dict(self):
        """from_dict should restore state correctly."""
        data = {"successes": 2, "failures": 1, "is_stable": True, "is_dead": False}
        state = DeathSaveState.from_dict(data)
        assert state.successes == 2
        assert state.failures == 1
        assert state.is_stable is True
        assert state.is_dead is False


class TestRollDeathSave:
    """Tests for the roll_death_save function."""

    def test_success_on_roll_10_or_higher(self):
        """Roll of 10+ should be a success."""
        state = DeathSaveState()

        with patch('app.core.death_saves.roll_d20', return_value=10):
            result = roll_death_save(state)
            assert result.success is True
            assert state.successes == 1
            assert state.failures == 0

    def test_failure_on_roll_below_10(self):
        """Roll below 10 should be a failure."""
        state = DeathSaveState()

        with patch('app.core.death_saves.roll_d20', return_value=5):
            result = roll_death_save(state)
            assert result.success is False
            assert state.successes == 0
            assert state.failures == 1

    def test_natural_20_revives(self):
        """Natural 20 should revive the character."""
        state = DeathSaveState(failures=2)  # Near death

        with patch('app.core.death_saves.roll_d20', return_value=20):
            result = roll_death_save(state)
            assert result.critical_success is True
            assert result.outcome == DeathSaveOutcome.REVIVED
            # State should be reset on revive
            assert state.successes == 0
            assert state.failures == 0
            assert state.is_stable is False

    def test_natural_1_two_failures(self):
        """Natural 1 should count as two failures."""
        state = DeathSaveState()

        with patch('app.core.death_saves.roll_d20', return_value=1):
            result = roll_death_save(state)
            assert result.critical_failure is True
            assert state.failures == 2

    def test_natural_1_causes_death_at_2_failures(self):
        """Natural 1 with 2 failures should cause death."""
        state = DeathSaveState(failures=2)

        with patch('app.core.death_saves.roll_d20', return_value=1):
            result = roll_death_save(state)
            assert result.outcome == DeathSaveOutcome.DEAD
            assert state.is_dead is True

    def test_three_successes_stabilizes(self):
        """Three successes should stabilize the character."""
        state = DeathSaveState(successes=2)

        with patch('app.core.death_saves.roll_d20', return_value=15):
            result = roll_death_save(state)
            assert result.outcome == DeathSaveOutcome.STABILIZED
            assert state.is_stable is True
            assert state.successes == 3

    def test_three_failures_kills(self):
        """Three failures should kill the character."""
        state = DeathSaveState(failures=2)

        with patch('app.core.death_saves.roll_d20', return_value=5):
            result = roll_death_save(state)
            assert result.outcome == DeathSaveOutcome.DEAD
            assert state.is_dead is True
            assert state.failures == 3

    def test_modifier_applied(self):
        """Modifier should be applied to the roll."""
        state = DeathSaveState()

        # Roll 8 with +3 modifier = 11, should succeed
        with patch('app.core.death_saves.roll_d20', return_value=8):
            result = roll_death_save(state, modifier=3)
            assert result.modified_roll == 11
            assert result.success is True

    def test_dc_is_always_10(self):
        """DC should always be 10."""
        state = DeathSaveState()

        with patch('app.core.death_saves.roll_d20', return_value=10):
            result = roll_death_save(state)
            assert result.dc == 10


class TestTakeDamageWhileDying:
    """Tests for taking damage at 0 HP."""

    def test_damage_adds_one_failure(self):
        """Normal damage should add one failure."""
        state = DeathSaveState()
        result = take_damage_while_dying(state, damage=5)
        assert state.failures == 1
        assert result["failures_added"] == 1

    def test_critical_hit_adds_two_failures(self):
        """Critical hit should add two failures."""
        state = DeathSaveState()
        result = take_damage_while_dying(state, damage=10, was_critical=True)
        assert state.failures == 2
        assert result["failures_added"] == 2

    def test_damage_causes_death_at_two_failures(self):
        """Damage with 2 failures should cause death."""
        state = DeathSaveState(failures=2)
        result = take_damage_while_dying(state, damage=5)
        assert state.is_dead is True
        assert result["died"] is True

    def test_critical_causes_death_at_one_failure(self):
        """Critical hit with 1 failure should cause death."""
        state = DeathSaveState(failures=1)
        result = take_damage_while_dying(state, damage=10, was_critical=True)
        assert state.is_dead is True
        assert result["died"] is True


class TestStabilizeCreature:
    """Tests for stabilization mechanics."""

    def test_spare_the_dying_auto_stabilizes(self):
        """Spare the Dying should automatically stabilize."""
        state = DeathSaveState(failures=2, successes=1)
        result = stabilize_creature(state, method="spare_the_dying")
        assert result.success is True
        assert state.is_stable is True
        assert state.successes == 0
        assert state.failures == 0

    def test_healer_kit_auto_stabilizes(self):
        """Healer's Kit should automatically stabilize."""
        state = DeathSaveState(failures=1)
        result = stabilize_creature(state, method="healer_kit")
        assert result.success is True
        assert state.is_stable is True

    def test_medicine_check_success(self):
        """Successful medicine check should stabilize."""
        state = DeathSaveState(failures=1)
        check_result = (True, 15, 18)  # success, roll, total
        result = stabilize_creature(state, method="medicine", medicine_check_result=check_result)
        assert result.success is True
        assert state.is_stable is True

    def test_medicine_check_failure(self):
        """Failed medicine check should not stabilize."""
        state = DeathSaveState(failures=1)
        check_result = (False, 5, 7)  # failure, roll, total
        result = stabilize_creature(state, method="medicine", medicine_check_result=check_result)
        assert result.success is False
        assert state.is_stable is False

    def test_cannot_stabilize_dead(self):
        """Cannot stabilize a dead creature."""
        state = DeathSaveState(is_dead=True)
        result = stabilize_creature(state, method="spare_the_dying")
        assert result.success is False

    def test_already_stable_returns_success(self):
        """Stabilizing already stable creature returns success."""
        state = DeathSaveState(is_stable=True)
        result = stabilize_creature(state, method="spare_the_dying")
        assert result.success is True


class TestHealDyingCreature:
    """Tests for healing at 0 HP."""

    def test_healing_revives(self):
        """Any healing should bring creature to consciousness."""
        state = DeathSaveState(failures=2, successes=1)
        result = heal_dying_creature(state, hp_healed=5)
        assert result["success"] is True
        assert result["regained_consciousness"] is True
        # Death saves should be reset
        assert state.successes == 0
        assert state.failures == 0

    def test_cannot_heal_dead(self):
        """Cannot heal dead creature (needs resurrection)."""
        state = DeathSaveState(is_dead=True)
        result = heal_dying_creature(state, hp_healed=10)
        assert result["success"] is False
        assert result["regained_consciousness"] is False


class TestGetDeathSaveStatus:
    """Tests for status formatting."""

    def test_dead_status(self):
        """Dead state should show dead status."""
        state = DeathSaveState(is_dead=True)
        status = get_death_save_status(state)
        assert status["status"] == "dead"

    def test_stable_status(self):
        """Stable state should show stable status."""
        state = DeathSaveState(is_stable=True)
        status = get_death_save_status(state)
        assert status["status"] == "stable"

    def test_dying_status(self):
        """Dying state should show counts."""
        state = DeathSaveState(successes=1, failures=2)
        status = get_death_save_status(state)
        assert status["status"] == "dying"
        assert "1 successes" in status["description"]
        assert "2 failures" in status["description"]

    def test_marker_formatting(self):
        """Status markers should be correct."""
        state = DeathSaveState(successes=2, failures=1)
        status = get_death_save_status(state)
        assert status["success_markers"] == "●●○"
        assert status["failure_markers"] == "●○○"


class TestMedicineCheck:
    """Tests for medicine check rolling."""

    def test_success_on_10_or_higher(self):
        """Roll of 10+ (with modifier) should succeed."""
        with patch('app.core.death_saves.roll_d20', return_value=10):
            success, roll, total = attempt_medicine_check(wisdom_modifier=0)
            assert success is True
            assert total >= 10

    def test_proficiency_bonus_applied(self):
        """Proficiency should be added when proficient."""
        with patch('app.core.death_saves.roll_d20', return_value=5):
            success, roll, total = attempt_medicine_check(
                wisdom_modifier=2,
                proficiency_bonus=3,
                is_proficient=True
            )
            assert total == 5 + 2 + 3  # roll + wis + prof
