"""
Tests for Subclass Registry System.

Tests subclass loading, feature availability, and combat implementations.
"""
import pytest
from unittest.mock import patch, MagicMock

from app.core.subclass_registry import (
    SubclassRegistry,
    SubclassResource,
    SubclassResourceType,
    get_subclass_registry,
    get_critical_range,
    get_superiority_dice_info,
    get_psionic_dice_info,
    execute_maneuver,
    execute_psionic_power,
    assassinate_bonus,
    get_combat_modifiers,
    process_subclass_attack_modifiers,
)


class TestSubclassRegistry:
    """Test the SubclassRegistry singleton."""

    def test_registry_loads_fighter_subclasses(self):
        """Registry should load all fighter subclasses."""
        registry = get_subclass_registry()
        subclasses = registry.get_subclasses_for_class("fighter")

        assert len(subclasses) >= 4
        subclass_ids = [s.get("id") for s in subclasses]
        assert "champion" in subclass_ids
        assert "battle_master" in subclass_ids

    def test_get_champion_subclass(self):
        """Should retrieve Champion subclass data."""
        registry = get_subclass_registry()
        champion = registry.get_subclass("fighter", "champion")

        assert champion is not None
        assert champion["name"] == "Champion"
        assert "features" in champion

    def test_get_battle_master_subclass(self):
        """Should retrieve Battle Master subclass data."""
        registry = get_subclass_registry()
        bm = registry.get_subclass("fighter", "battle_master")

        assert bm is not None
        assert bm["name"] == "Battle Master"
        assert "maneuvers" in bm

    def test_get_nonexistent_subclass(self):
        """Should return None for nonexistent subclass."""
        registry = get_subclass_registry()
        result = registry.get_subclass("fighter", "nonexistent")
        assert result is None


class TestSubclassFeatures:
    """Test subclass feature availability by level."""

    def test_champion_improved_critical_at_level_3(self):
        """Champion gets Improved Critical at level 3."""
        registry = get_subclass_registry()
        features = registry.get_subclass_features("fighter", "champion", 3)

        feature_ids = [f.get("id") for f in features]
        assert "improved_critical" in feature_ids

    def test_champion_superior_critical_at_level_15(self):
        """Champion gets Superior Critical at level 15."""
        registry = get_subclass_registry()
        features = registry.get_subclass_features("fighter", "champion", 15)

        feature_ids = [f.get("id") for f in features]
        assert "superior_critical" in feature_ids

    def test_champion_no_superior_critical_at_level_10(self):
        """Champion doesn't have Superior Critical at level 10."""
        registry = get_subclass_registry()
        features = registry.get_subclass_features("fighter", "champion", 10)

        feature_ids = [f.get("id") for f in features]
        assert "superior_critical" not in feature_ids

    def test_has_feature_returns_true(self):
        """has_feature should return True for available feature."""
        registry = get_subclass_registry()
        assert registry.has_feature("fighter", "champion", "improved_critical", 3)

    def test_has_feature_returns_false_low_level(self):
        """has_feature should return False if level too low."""
        registry = get_subclass_registry()
        assert not registry.has_feature("fighter", "champion", "superior_critical", 10)


class TestCriticalRange:
    """Test Champion critical hit range expansion."""

    def test_default_crit_range(self):
        """Non-champion should have crit range of 20."""
        assert get_critical_range("battle_master", 20) == 20

    def test_champion_improved_critical(self):
        """Champion at level 3+ crits on 19-20."""
        assert get_critical_range("champion", 3) == 19
        assert get_critical_range("champion", 10) == 19

    def test_champion_superior_critical(self):
        """Champion at level 15+ crits on 18-20."""
        assert get_critical_range("champion", 15) == 18
        assert get_critical_range("champion", 20) == 18


class TestSuperiorityDice:
    """Test Battle Master superiority dice progression."""

    def test_level_3_dice(self):
        """Level 3 Battle Master has 4d8."""
        count, size = get_superiority_dice_info(3)
        assert count == 4
        assert size == 8

    def test_level_7_dice(self):
        """Level 7 Battle Master has 5d8."""
        count, size = get_superiority_dice_info(7)
        assert count == 5
        assert size == 8

    def test_level_10_dice(self):
        """Level 10 Battle Master has 5d10."""
        count, size = get_superiority_dice_info(10)
        assert count == 5
        assert size == 10

    def test_level_15_dice(self):
        """Level 15 Battle Master has 6d10."""
        count, size = get_superiority_dice_info(15)
        assert count == 6
        assert size == 10

    def test_level_18_dice(self):
        """Level 18 Battle Master has 6d12."""
        count, size = get_superiority_dice_info(18)
        assert count == 6
        assert size == 12


class TestPsionicDice:
    """Test Psi Warrior psionic energy dice progression."""

    def test_level_3_dice(self):
        """Level 3 Psi Warrior has 4d6."""
        count, size = get_psionic_dice_info(3)
        assert count == 4  # 2 * proficiency (2)
        assert size == 6

    def test_level_5_dice(self):
        """Level 5 Psi Warrior has 6d8."""
        count, size = get_psionic_dice_info(5)
        assert count == 6  # 2 * proficiency (3)
        assert size == 8

    def test_level_11_dice(self):
        """Level 11 Psi Warrior has 8d10."""
        count, size = get_psionic_dice_info(11)
        assert count == 8  # 2 * proficiency (4)
        assert size == 10

    def test_level_17_dice(self):
        """Level 17 Psi Warrior has 12d12."""
        count, size = get_psionic_dice_info(17)
        assert count == 12  # 2 * proficiency (6)
        assert size == 12


class TestSubclassResource:
    """Test SubclassResource tracking."""

    def test_use_resource(self):
        """Should decrement uses when using resource."""
        resource = SubclassResource(
            resource_type=SubclassResourceType.SUPERIORITY_DICE,
            max_uses=4,
            current_uses=4,
            dice_size=8
        )

        assert resource.use(1)
        assert resource.current_uses == 3

    def test_use_resource_fails_when_empty(self):
        """Should fail when no uses remaining."""
        resource = SubclassResource(
            resource_type=SubclassResourceType.SUPERIORITY_DICE,
            max_uses=4,
            current_uses=0,
            dice_size=8
        )

        assert not resource.use(1)
        assert resource.current_uses == 0

    def test_regain_resource(self):
        """Should regain uses up to max."""
        resource = SubclassResource(
            resource_type=SubclassResourceType.SUPERIORITY_DICE,
            max_uses=4,
            current_uses=2,
            dice_size=8
        )

        resource.regain(1)
        assert resource.current_uses == 3

    def test_regain_capped_at_max(self):
        """Regain should not exceed max."""
        resource = SubclassResource(
            resource_type=SubclassResourceType.SUPERIORITY_DICE,
            max_uses=4,
            current_uses=4,
            dice_size=8
        )

        resource.regain(2)
        assert resource.current_uses == 4

    def test_reset_resource(self):
        """Reset should restore to full."""
        resource = SubclassResource(
            resource_type=SubclassResourceType.SUPERIORITY_DICE,
            max_uses=4,
            current_uses=1,
            dice_size=8
        )

        resource.reset()
        assert resource.current_uses == 4

    def test_roll_resource_die(self):
        """Roll should return value within dice range."""
        resource = SubclassResource(
            resource_type=SubclassResourceType.SUPERIORITY_DICE,
            max_uses=4,
            current_uses=4,
            dice_size=8
        )

        for _ in range(20):
            roll = resource.roll()
            assert 1 <= roll <= 8


class TestManeuverExecution:
    """Test Battle Master maneuver execution."""

    def test_precision_attack_adds_to_roll(self):
        """Precision Attack should add die to attack roll."""
        resource = SubclassResource(
            resource_type=SubclassResourceType.SUPERIORITY_DICE,
            max_uses=4,
            current_uses=4,
            dice_size=8
        )
        attacker = {"ability_scores": {"STR": 16, "DEX": 14}, "proficiency_bonus": 2}

        result = execute_maneuver("precision_attack", resource, attacker)

        assert result.success
        assert result.bonus > 0
        assert resource.current_uses == 3

    def test_trip_attack_with_target(self):
        """Trip Attack should attempt to knock target prone."""
        resource = SubclassResource(
            resource_type=SubclassResourceType.SUPERIORITY_DICE,
            max_uses=4,
            current_uses=4,
            dice_size=8
        )
        attacker = {"ability_scores": {"STR": 16, "DEX": 14}, "proficiency_bonus": 2}
        target = {"ability_scores": {"STR": 10}}

        result = execute_maneuver("trip_attack", resource, attacker, target)

        assert result.success
        assert result.damage > 0

    def test_maneuver_fails_without_dice(self):
        """Maneuver should fail with no dice remaining."""
        resource = SubclassResource(
            resource_type=SubclassResourceType.SUPERIORITY_DICE,
            max_uses=4,
            current_uses=0,
            dice_size=8
        )
        attacker = {"ability_scores": {"STR": 16, "DEX": 14}, "proficiency_bonus": 2}

        result = execute_maneuver("precision_attack", resource, attacker)

        assert not result.success
        assert "No superiority dice" in result.description

    @patch('app.core.subclass_registry.roll_d20')
    def test_menacing_attack_frightens(self, mock_roll):
        """Menacing Attack should frighten target on failed save."""
        mock_roll.return_value = MagicMock(total=5)  # Low roll = failed save

        resource = SubclassResource(
            resource_type=SubclassResourceType.SUPERIORITY_DICE,
            max_uses=4,
            current_uses=4,
            dice_size=8
        )
        attacker = {"ability_scores": {"STR": 16, "DEX": 14}, "proficiency_bonus": 2}
        target = {"ability_scores": {"WIS": 10}}

        result = execute_maneuver("menacing_attack", resource, attacker, target)

        assert result.success
        assert result.condition_applied == "frightened"


class TestPsionicPowerExecution:
    """Test Psi Warrior psionic power execution."""

    def test_psionic_strike_deals_force_damage(self):
        """Psionic Strike should deal force damage."""
        resource = SubclassResource(
            resource_type=SubclassResourceType.PSIONIC_DICE,
            max_uses=4,
            current_uses=4,
            dice_size=6
        )
        attacker = {"ability_scores": {"INT": 16}, "proficiency_bonus": 2}

        result = execute_psionic_power("psionic_strike", resource, attacker)

        assert result.success
        assert result.damage > 0
        assert result.extra_data.get("damage_type") == "force"

    def test_protective_field_reduces_damage(self):
        """Protective Field should reduce damage taken."""
        resource = SubclassResource(
            resource_type=SubclassResourceType.PSIONIC_DICE,
            max_uses=4,
            current_uses=4,
            dice_size=6
        )
        attacker = {"ability_scores": {"INT": 16}, "proficiency_bonus": 2}

        result = execute_psionic_power("protective_field", resource, attacker)

        assert result.success
        assert "damage_reduction" in result.extra_data.get("type", "")


class TestAssassinFeatures:
    """Test Assassin subclass features."""

    def test_assassinate_surprised_target(self):
        """Assassinate against surprised target is auto-crit."""
        result = assassinate_bonus(target_surprised=True, attacker_first=True)

        assert result["advantage"]
        assert result["auto_crit"]

    def test_assassinate_first_in_combat(self):
        """Assassinate grants advantage when acting first."""
        result = assassinate_bonus(target_surprised=False, attacker_first=True)

        assert result["advantage"]
        assert not result["auto_crit"]

    def test_no_assassinate_bonus(self):
        """No bonus when conditions not met."""
        result = assassinate_bonus(target_surprised=False, attacker_first=False)

        assert not result["advantage"]
        assert not result["auto_crit"]


class TestCombatModifiers:
    """Test combat modifier helpers."""

    def test_champion_crit_range_modifier(self):
        """Champion should have expanded crit range in modifiers."""
        modifiers = get_combat_modifiers("fighter", "champion", 3)
        assert modifiers.get("crit_range") == 19

    def test_champion_level_15_crit_range(self):
        """Champion at 15 should have 18-20 crit range."""
        modifiers = get_combat_modifiers("fighter", "champion", 15)
        assert modifiers.get("crit_range") == 18

    def test_assassin_modifier(self):
        """Assassin should have assassinate modifier."""
        modifiers = get_combat_modifiers("rogue", "assassin", 3)
        assert modifiers.get("assassinate") is True


class TestAttackRollProcessing:
    """Test subclass attack roll processing."""

    def test_champion_19_is_crit_at_level_3(self):
        """Champion's 19 should be crit at level 3+."""
        roll, is_crit = process_subclass_attack_modifiers(
            "fighter", "champion", 3, 19, False
        )
        assert is_crit

    def test_champion_18_not_crit_at_level_3(self):
        """Champion's 18 should not be crit at level 3."""
        roll, is_crit = process_subclass_attack_modifiers(
            "fighter", "champion", 3, 18, False
        )
        assert not is_crit

    def test_champion_18_is_crit_at_level_15(self):
        """Champion's 18 should be crit at level 15+."""
        roll, is_crit = process_subclass_attack_modifiers(
            "fighter", "champion", 15, 18, False
        )
        assert is_crit


class TestResourcePoolCreation:
    """Test creating resource pools for subclasses."""

    def test_create_battle_master_resource(self):
        """Should create superiority dice pool for Battle Master."""
        registry = get_subclass_registry()
        resource = registry.create_resource_pool("fighter", "battle_master", 3)

        assert resource is not None
        assert resource.resource_type == SubclassResourceType.SUPERIORITY_DICE
        assert resource.max_uses == 4
        assert resource.dice_size == 8

    def test_create_psi_warrior_resource(self):
        """Should create psionic dice pool for Psi Warrior."""
        registry = get_subclass_registry()
        resource = registry.create_resource_pool("fighter", "psi_warrior", 5)

        assert resource is not None
        assert resource.resource_type == SubclassResourceType.PSIONIC_DICE
        assert resource.dice_size == 8

    def test_champion_no_resource_pool(self):
        """Champion doesn't need a resource pool."""
        registry = get_subclass_registry()
        resource = registry.create_resource_pool("fighter", "champion", 3)
        assert resource is None
