"""Tests for the dice rolling system."""
import pytest
from app.core.dice import (
    roll_die,
    roll_d20,
    roll_damage,
    parse_dice_notation,
    roll_initiative,
    D20Result,
    DamageResult,
)


class TestRollDie:
    """Tests for basic die rolling."""

    def test_roll_d20_in_range(self):
        """d20 should always be between 1 and 20."""
        for _ in range(100):
            result = roll_die(20)
            assert 1 <= result <= 20

    def test_roll_d6_in_range(self):
        """d6 should always be between 1 and 6."""
        for _ in range(100):
            result = roll_die(6)
            assert 1 <= result <= 6

    def test_invalid_die_raises_error(self):
        """Rolling a d0 or negative should raise ValueError."""
        with pytest.raises(ValueError):
            roll_die(0)
        with pytest.raises(ValueError):
            roll_die(-1)


class TestD20Roll:
    """Tests for d20 rolls with advantage/disadvantage."""

    def test_basic_roll(self):
        """Basic d20 roll should return valid result."""
        result = roll_d20()
        assert isinstance(result, D20Result)
        assert 1 <= result.total <= 20
        assert len(result.rolls) == 1

    def test_roll_with_modifier(self):
        """Modifier should be added to the roll."""
        result = roll_d20(modifier=5)
        assert result.modifier == 5
        assert result.total == result.rolls[0] + 5

    def test_advantage_rolls_twice(self):
        """Advantage should roll two dice."""
        result = roll_d20(advantage=True)
        assert len(result.rolls) == 2
        assert result.advantage is True
        assert result.base_roll == max(result.rolls)

    def test_disadvantage_rolls_twice(self):
        """Disadvantage should roll two dice."""
        result = roll_d20(disadvantage=True)
        assert len(result.rolls) == 2
        assert result.disadvantage is True
        assert result.base_roll == min(result.rolls)

    def test_advantage_and_disadvantage_cancel(self):
        """Advantage + disadvantage should cancel out."""
        result = roll_d20(advantage=True, disadvantage=True)
        assert len(result.rolls) == 1
        assert result.advantage is False
        assert result.disadvantage is False

    def test_natural_20_detected(self):
        """Natural 20 should be flagged."""
        # Run many times to eventually get a 20
        found_nat_20 = False
        for _ in range(1000):
            result = roll_d20()
            if result.rolls[0] == 20:
                assert result.natural_20 is True
                found_nat_20 = True
                break
        # Statistical: should find at least one in 1000 rolls
        assert found_nat_20, "Should have found a natural 20 in 1000 rolls"

    def test_natural_1_detected(self):
        """Natural 1 should be flagged."""
        found_nat_1 = False
        for _ in range(1000):
            result = roll_d20()
            if result.rolls[0] == 1:
                assert result.natural_1 is True
                found_nat_1 = True
                break
        assert found_nat_1, "Should have found a natural 1 in 1000 rolls"


class TestDiceNotation:
    """Tests for parsing dice notation."""

    def test_simple_notation(self):
        """Parse simple notation like '1d6'."""
        components = parse_dice_notation("1d6")
        assert components == [(1, 6, 0)]

    def test_notation_with_count(self):
        """Parse notation with dice count like '2d8'."""
        components = parse_dice_notation("2d8")
        assert components == [(2, 8, 0)]

    def test_notation_with_modifier(self):
        """Parse notation with modifier like '1d6+3'."""
        components = parse_dice_notation("1d6+3")
        assert components == [(1, 6, 3)]

    def test_notation_with_negative_modifier(self):
        """Parse notation with negative modifier like '1d6-2'."""
        components = parse_dice_notation("1d6-2")
        assert components == [(1, 6, -2)]

    def test_complex_notation(self):
        """Parse complex notation like '2d6+1d4+3'."""
        components = parse_dice_notation("2d6+1d4+3")
        assert len(components) == 2
        assert components[0] == (2, 6, 0)
        assert components[1] == (1, 4, 3)

    def test_implied_count(self):
        """Parse notation with implied 1 like 'd20'."""
        components = parse_dice_notation("d20")
        assert components == [(1, 20, 0)]

    def test_invalid_notation_raises_error(self):
        """Invalid notation should raise ValueError."""
        with pytest.raises(ValueError):
            parse_dice_notation("")
        with pytest.raises(ValueError):
            parse_dice_notation("abc")


class TestDamageRoll:
    """Tests for damage rolling."""

    def test_simple_damage(self):
        """Roll simple damage like 1d6."""
        result = roll_damage("1d6")
        assert isinstance(result, DamageResult)
        assert 1 <= result.total <= 6
        assert len(result.rolls) == 1

    def test_damage_with_modifier(self):
        """Roll damage with extra modifier."""
        result = roll_damage("1d6", modifier=3)
        assert result.modifier == 3
        assert 4 <= result.total <= 9  # 1d6 (1-6) + 3

    def test_multiple_dice(self):
        """Roll multiple dice like 2d6."""
        result = roll_damage("2d6")
        assert len(result.rolls) == 2
        assert 2 <= result.total <= 12

    def test_critical_doubles_dice(self):
        """Critical hit should double the number of dice."""
        result = roll_damage("2d6", critical=True)
        assert len(result.rolls) == 4  # 2d6 doubled = 4d6
        assert result.is_critical is True

    def test_complex_damage(self):
        """Roll complex damage like 1d8+1d6+2."""
        result = roll_damage("1d8+1d6+2")
        assert len(result.rolls) == 2  # 1d8 + 1d6
        assert 4 <= result.total <= 16  # (1-8) + (1-6) + 2

    def test_minimum_damage_is_one(self):
        """Damage should never go below 1."""
        # This tests the minimum damage rule
        result = roll_damage("1d4-10")
        assert result.total >= 1


class TestInitiative:
    """Tests for initiative rolls."""

    def test_initiative_in_range(self):
        """Initiative should be d20 + modifier."""
        result = roll_initiative(dexterity_modifier=0)
        assert 1 <= result <= 20

    def test_initiative_with_modifier(self):
        """Initiative should include DEX modifier."""
        result = roll_initiative(dexterity_modifier=3)
        assert 4 <= result <= 23  # d20 (1-20) + 3

    def test_negative_modifier(self):
        """Initiative can have negative modifier."""
        result = roll_initiative(dexterity_modifier=-2)
        assert -1 <= result <= 18  # d20 (1-20) - 2
