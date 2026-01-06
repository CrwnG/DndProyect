"""Tests for the class features system."""
import pytest

from app.core.class_features import (
    ClassFeature,
    FeatureType,
    ResourceType,
    # Fighter
    use_second_wind,
    use_action_surge,
    use_tactical_mind,
    use_indomitable,
    # Rogue
    calculate_sneak_attack_dice,
    roll_sneak_attack,
    use_cunning_strike,
    use_uncanny_dodge,
    CunningStrikeEffect,
    # Wizard
    calculate_arcane_recovery_slots,
    use_arcane_recovery,
    use_modify_spell,
    # Cleric
    get_channel_divinity_uses,
    use_turn_undead,
    apply_divine_order,
    DivineOrderChoice,
    # Registry
    get_class_features,
    get_feature_by_id,
    get_weapon_mastery_count,
    get_extra_attack_count,
)
from app.core.rules_config import (
    RulesContext,
    reset_rules_config,
)


class TestFighterFeatures:
    """Test Fighter class features."""

    def setup_method(self):
        """Reset rules before each test."""
        reset_rules_config()

    def test_second_wind_heals(self):
        """Second Wind should heal 1d10 + fighter level."""
        result = use_second_wind(fighter_level=5)

        assert result.success is True
        assert result.value >= 6  # Minimum: 1 + 5
        assert result.value <= 15  # Maximum: 10 + 5
        assert "heals" in result.description.lower()

    def test_second_wind_scales_with_level(self):
        """Higher level should mean higher healing."""
        # Run multiple times to check range
        for _ in range(10):
            low_level = use_second_wind(fighter_level=1)
            high_level = use_second_wind(fighter_level=10)

            assert low_level.value >= 2  # 1 + 1
            assert low_level.value <= 11  # 10 + 1
            assert high_level.value >= 11  # 1 + 10
            assert high_level.value <= 20  # 10 + 10

    def test_action_surge_grants_action(self):
        """Action Surge should grant an extra action."""
        result = use_action_surge()

        assert result.success is True
        assert result.extra_data.get("grants_action") is True

    def test_tactical_mind_requires_2024_rules(self):
        """Tactical Mind should only work with 2024 rules."""
        with RulesContext(updated_class_features_2024=False):
            result = use_tactical_mind(
                original_roll=12,
                check_dc=15,
                proficiency_bonus=2
            )
            assert result.success is False
            assert "2024" in result.description

    def test_tactical_mind_adds_d10(self):
        """Tactical Mind should add 1d10 to the roll."""
        with RulesContext(updated_class_features_2024=True):
            result = use_tactical_mind(
                original_roll=10,
                check_dc=15,
                proficiency_bonus=2
            )
            # Check that a bonus was added
            assert result.extra_data.get("bonus") >= 1
            assert result.extra_data.get("bonus") <= 10
            assert result.value == 10 + result.extra_data["bonus"]

    def test_indomitable_rerolls_save(self):
        """Indomitable should allow a reroll."""
        result = use_indomitable(save_result=8, save_dc=15)

        assert result.value >= 1  # New roll exists
        assert "Indomitable" in result.description
        assert result.extra_data.get("original") == 8


class TestRogueFeatures:
    """Test Rogue class features."""

    def setup_method(self):
        """Reset rules before each test."""
        reset_rules_config()

    def test_sneak_attack_dice_scaling(self):
        """Sneak Attack dice should scale with level."""
        assert calculate_sneak_attack_dice(1) == "1d6"
        assert calculate_sneak_attack_dice(2) == "1d6"
        assert calculate_sneak_attack_dice(3) == "2d6"
        assert calculate_sneak_attack_dice(5) == "3d6"
        assert calculate_sneak_attack_dice(7) == "4d6"
        assert calculate_sneak_attack_dice(19) == "10d6"
        assert calculate_sneak_attack_dice(20) == "10d6"

    def test_roll_sneak_attack(self):
        """Sneak Attack should roll appropriate dice."""
        result = roll_sneak_attack(rogue_level=5)

        assert result.success is True
        assert result.value >= 3  # Minimum: 3 dice, each 1
        assert result.value <= 18  # Maximum: 3 dice, each 6
        assert result.extra_data.get("dice") == "3d6"

    def test_uncanny_dodge_halves_damage(self):
        """Uncanny Dodge should halve incoming damage."""
        result = use_uncanny_dodge(incoming_damage=20)

        assert result.success is True
        assert result.value == 10
        assert result.extra_data.get("original_damage") == 20

    def test_uncanny_dodge_rounds_down(self):
        """Odd damage should round down."""
        result = use_uncanny_dodge(incoming_damage=15)
        assert result.value == 7  # 15 // 2 = 7

    def test_cunning_strike_requires_2024(self):
        """Cunning Strike requires 2024 rules."""
        with RulesContext(updated_class_features_2024=False):
            result = use_cunning_strike(
                rogue_level=5,
                effect=CunningStrikeEffect.TRIP
            )
            assert result.success is False

    def test_cunning_strike_requires_level_5(self):
        """Cunning Strike requires level 5."""
        with RulesContext(updated_class_features_2024=True):
            result = use_cunning_strike(
                rogue_level=4,
                effect=CunningStrikeEffect.TRIP
            )
            assert result.success is False
            assert "level 5" in result.description

    def test_cunning_strike_trip(self):
        """Trip effect should knock target prone."""
        with RulesContext(updated_class_features_2024=True):
            result = use_cunning_strike(
                rogue_level=5,
                effect=CunningStrikeEffect.TRIP
            )
            assert result.success is True
            assert result.extra_data.get("condition") == "prone"

    def test_cunning_strike_withdraw(self):
        """Withdraw effect should grant safe movement."""
        with RulesContext(updated_class_features_2024=True):
            result = use_cunning_strike(
                rogue_level=5,
                effect=CunningStrikeEffect.WITHDRAW
            )
            assert result.success is True
            assert "movement" in result.extra_data


class TestWizardFeatures:
    """Test Wizard class features."""

    def setup_method(self):
        """Reset rules before each test."""
        reset_rules_config()

    def test_arcane_recovery_slot_calculation(self):
        """Arcane Recovery slots should scale with level."""
        assert calculate_arcane_recovery_slots(1) == 1
        assert calculate_arcane_recovery_slots(2) == 1
        assert calculate_arcane_recovery_slots(4) == 2
        assert calculate_arcane_recovery_slots(10) == 5
        assert calculate_arcane_recovery_slots(20) == 10

    def test_arcane_recovery_success(self):
        """Valid slot recovery should succeed."""
        result = use_arcane_recovery(
            wizard_level=4,
            slots_to_recover={1: 2}  # 2 first-level slots = 2 levels
        )

        assert result.success is True
        assert result.extra_data.get("total_levels") == 2

    def test_arcane_recovery_over_limit(self):
        """Cannot recover more slots than allowed."""
        result = use_arcane_recovery(
            wizard_level=4,
            slots_to_recover={2: 2}  # 2 second-level = 4 levels, but max is 2
        )

        assert result.success is False
        assert "Cannot recover more than" in result.description

    def test_arcane_recovery_no_high_slots(self):
        """Cannot recover 6th level or higher slots."""
        result = use_arcane_recovery(
            wizard_level=20,
            slots_to_recover={6: 1}
        )

        assert result.success is False
        assert "6th level or higher" in result.description

    def test_modify_spell_requires_2024(self):
        """Modify Spell requires 2024 rules."""
        with RulesContext(updated_class_features_2024=False):
            result = use_modify_spell("fire", "cold")
            assert result.success is False

    def test_modify_spell_changes_type(self):
        """Modify Spell should change damage type."""
        with RulesContext(updated_class_features_2024=True):
            result = use_modify_spell("fire", "cold")

            assert result.success is True
            assert result.extra_data.get("original_type") == "fire"
            assert result.extra_data.get("new_type") == "cold"

    def test_modify_spell_invalid_type(self):
        """Invalid damage types should fail."""
        with RulesContext(updated_class_features_2024=True):
            result = use_modify_spell("fire", "banana")
            assert result.success is False


class TestClericFeatures:
    """Test Cleric class features."""

    def setup_method(self):
        """Reset rules before each test."""
        reset_rules_config()

    def test_channel_divinity_uses_scaling(self):
        """Channel Divinity uses should scale with level."""
        assert get_channel_divinity_uses(1) == 0
        assert get_channel_divinity_uses(2) == 1
        assert get_channel_divinity_uses(5) == 1
        assert get_channel_divinity_uses(6) == 2
        assert get_channel_divinity_uses(17) == 2
        assert get_channel_divinity_uses(18) == 3

    def test_turn_undead_turns_enemies(self):
        """Turn Undead should turn undead that fail saves."""
        undead = [
            {"id": "zombie1", "wis_save_mod": -2},
            {"id": "zombie2", "wis_save_mod": -2},
        ]

        # With +3 WIS and +2 prof, DC = 8 + 2 + 3 = 13
        # With -2 mod, zombies need to roll 15+ to resist
        result = use_turn_undead(
            cleric_wisdom_mod=3,
            cleric_proficiency=2,
            undead_targets=undead
        )

        assert result.extra_data.get("dc") == 13
        assert len(result.extra_data.get("turned", [])) + len(result.extra_data.get("resisted", [])) == 2

    def test_divine_order_requires_2024(self):
        """Divine Order requires 2024 rules."""
        with RulesContext(updated_class_features_2024=False):
            result = apply_divine_order(DivineOrderChoice.PROTECTOR)
            assert result.success is False

    def test_divine_order_protector(self):
        """Protector should grant martial proficiencies."""
        with RulesContext(updated_class_features_2024=True):
            result = apply_divine_order(DivineOrderChoice.PROTECTOR)

            assert result.success is True
            assert "martial_weapons" in result.extra_data.get("proficiencies", [])
            assert "heavy_armor" in result.extra_data.get("proficiencies", [])

    def test_divine_order_thaumaturge(self):
        """Thaumaturge should grant extra cantrip."""
        with RulesContext(updated_class_features_2024=True):
            result = apply_divine_order(DivineOrderChoice.THAUMATURGE)

            assert result.success is True
            assert result.extra_data.get("extra_cantrips") == 1
            assert result.extra_data.get("enhanced_cantrips") is True


class TestFeatureRegistry:
    """Test the feature registry functions."""

    def setup_method(self):
        """Reset rules before each test."""
        reset_rules_config()

    def test_get_class_features_by_level(self):
        """Should return features available at level."""
        level_1_features = get_class_features("fighter", 1)
        level_5_features = get_class_features("fighter", 5)

        # Level 1 should have Fighting Style, Second Wind
        feature_ids = [f.id for f in level_1_features]
        assert "fighting_style" in feature_ids
        # Should have second_wind or second_wind_2024 depending on rules

        # Level 5 should also have Extra Attack
        level_5_ids = [f.id for f in level_5_features]
        assert "extra_attack" in level_5_ids

    def test_get_class_features_replaces_2014_with_2024(self):
        """2024 features should replace their 2014 counterparts."""
        with RulesContext(updated_class_features_2024=True):
            features = get_class_features("fighter", 1)
            feature_ids = [f.id for f in features]

            # Should have enhanced version, not original
            assert "second_wind_2024" in feature_ids
            assert "second_wind" not in feature_ids

    def test_get_class_features_unknown_class(self):
        """Unknown class should return empty list."""
        features = get_class_features("unknown_class", 5)
        assert features == []

    def test_get_feature_by_id(self):
        """Should return specific feature."""
        feature = get_feature_by_id("rogue", "sneak_attack")

        assert feature is not None
        assert feature.name == "Sneak Attack"
        assert feature.min_level == 1

    def test_get_weapon_mastery_count(self):
        """Should return correct mastery count."""
        # Fighter gets the most
        assert get_weapon_mastery_count("fighter", 1) == 3
        assert get_weapon_mastery_count("fighter", 4) == 4
        assert get_weapon_mastery_count("fighter", 10) == 5
        assert get_weapon_mastery_count("fighter", 16) == 6

        # Rogue gets fewer
        assert get_weapon_mastery_count("rogue", 1) == 2
        assert get_weapon_mastery_count("rogue", 4) == 3

        # Wizard gets none
        assert get_weapon_mastery_count("wizard", 5) == 0

    def test_get_weapon_mastery_disabled(self):
        """Should return 0 when weapon mastery is disabled."""
        with RulesContext(weapon_mastery_enabled=False):
            assert get_weapon_mastery_count("fighter", 10) == 0

    def test_get_extra_attack_count(self):
        """Should return correct extra attack count."""
        # Fighter gets the most
        assert get_extra_attack_count("fighter", 4) == 0
        assert get_extra_attack_count("fighter", 5) == 1
        assert get_extra_attack_count("fighter", 11) == 2
        assert get_extra_attack_count("fighter", 20) == 3

        # Other martials get one
        assert get_extra_attack_count("paladin", 5) == 1
        assert get_extra_attack_count("ranger", 5) == 1

        # Rogue doesn't get extra attack
        assert get_extra_attack_count("rogue", 20) == 0

        # Casters don't get extra attack
        assert get_extra_attack_count("wizard", 20) == 0
        assert get_extra_attack_count("cleric", 20) == 0
