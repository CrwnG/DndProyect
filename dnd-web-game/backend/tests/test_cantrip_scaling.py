"""Tests for the cantrip scaling system."""
import pytest

from app.core.cantrip_scaling import (
    get_cantrip_scaling_tier,
    get_cantrip_die_count,
    parse_base_damage,
    scale_cantrip_damage,
    roll_scaled_cantrip_damage,
    get_cantrip_definition,
    get_scaled_cantrip_info,
    get_eldritch_blast_beams,
    get_toll_the_dead_damage,
    format_cantrip_scaling_description,
    DAMAGE_CANTRIPS,
)
from app.core.rules_config import RulesContext, reset_rules_config


class TestScalingTiers:
    """Test scaling tier calculations."""

    def test_tier_0_levels_1_to_4(self):
        """Levels 1-4 should be tier 0."""
        for level in range(1, 5):
            assert get_cantrip_scaling_tier(level) == 0

    def test_tier_1_levels_5_to_10(self):
        """Levels 5-10 should be tier 1."""
        for level in range(5, 11):
            assert get_cantrip_scaling_tier(level) == 1

    def test_tier_2_levels_11_to_16(self):
        """Levels 11-16 should be tier 2."""
        for level in range(11, 17):
            assert get_cantrip_scaling_tier(level) == 2

    def test_tier_3_levels_17_to_20(self):
        """Levels 17-20 should be tier 3."""
        for level in range(17, 21):
            assert get_cantrip_scaling_tier(level) == 3

    def test_die_count_matches_tier(self):
        """Die count should be tier + 1."""
        assert get_cantrip_die_count(1) == 1
        assert get_cantrip_die_count(5) == 2
        assert get_cantrip_die_count(11) == 3
        assert get_cantrip_die_count(17) == 4


class TestDamageParsing:
    """Test damage dice parsing."""

    def test_parse_simple_dice(self):
        """Parse simple dice like 1d10."""
        count, size, mod = parse_base_damage("1d10")
        assert count == 1
        assert size == 10
        assert mod == 0

    def test_parse_multiple_dice(self):
        """Parse multiple dice like 2d6."""
        count, size, mod = parse_base_damage("2d6")
        assert count == 2
        assert size == 6
        assert mod == 0

    def test_parse_with_positive_modifier(self):
        """Parse dice with positive modifier."""
        count, size, mod = parse_base_damage("1d8+3")
        assert count == 1
        assert size == 8
        assert mod == 3

    def test_parse_with_negative_modifier(self):
        """Parse dice with negative modifier."""
        count, size, mod = parse_base_damage("1d6-1")
        assert count == 1
        assert size == 6
        assert mod == -1

    def test_parse_invalid_format_raises(self):
        """Invalid format should raise ValueError."""
        with pytest.raises(ValueError):
            parse_base_damage("invalid")

        with pytest.raises(ValueError):
            parse_base_damage("d20")  # Missing count


class TestCantripScaling:
    """Test cantrip damage scaling."""

    def setup_method(self):
        """Reset rules before each test."""
        reset_rules_config()

    def test_scale_fire_bolt_level_1(self):
        """Fire Bolt at level 1 should be 1d10."""
        scaled = scale_cantrip_damage("1d10", 1)

        assert scaled.base_dice == "1d10"
        assert scaled.scaled_dice == "1d10"
        assert scaled.die_count == 1
        assert scaled.scaling_tier == 0

    def test_scale_fire_bolt_level_5(self):
        """Fire Bolt at level 5 should be 2d10."""
        scaled = scale_cantrip_damage("1d10", 5)

        assert scaled.scaled_dice == "2d10"
        assert scaled.die_count == 2
        assert scaled.scaling_tier == 1

    def test_scale_fire_bolt_level_11(self):
        """Fire Bolt at level 11 should be 3d10."""
        scaled = scale_cantrip_damage("1d10", 11)

        assert scaled.scaled_dice == "3d10"
        assert scaled.die_count == 3
        assert scaled.scaling_tier == 2

    def test_scale_fire_bolt_level_17(self):
        """Fire Bolt at level 17 should be 4d10."""
        scaled = scale_cantrip_damage("1d10", 17)

        assert scaled.scaled_dice == "4d10"
        assert scaled.die_count == 4
        assert scaled.scaling_tier == 3

    def test_scale_with_modifier(self):
        """Modifiers should be preserved in scaling."""
        scaled = scale_cantrip_damage("1d8+3", 11)

        assert scaled.scaled_dice == "3d8+3"
        assert scaled.modifier == 3

    def test_scale_with_negative_modifier(self):
        """Negative modifiers should be preserved."""
        scaled = scale_cantrip_damage("1d6-1", 5)

        assert scaled.scaled_dice == "2d6-1"
        assert scaled.modifier == -1

    def test_scaling_disabled_returns_base(self):
        """When scaling is disabled, return base damage."""
        with RulesContext(cantrip_scaling=False):
            scaled = scale_cantrip_damage("1d10", 17, ignore_toggle=False)

            assert scaled.scaled_dice == "1d10"
            assert scaled.scaling_tier == 0

    def test_ignore_toggle_forces_scaling(self):
        """ignore_toggle should bypass the rules check."""
        with RulesContext(cantrip_scaling=False):
            scaled = scale_cantrip_damage("1d10", 17, ignore_toggle=True)

            assert scaled.scaled_dice == "4d10"


class TestRollingScaledDamage:
    """Test rolling scaled cantrip damage."""

    def setup_method(self):
        """Reset rules before each test."""
        reset_rules_config()

    def test_roll_level_1_fire_bolt(self):
        """Rolling Fire Bolt at level 1."""
        result = roll_scaled_cantrip_damage("1d10", 1)

        assert result.total >= 1
        assert result.total <= 10
        assert len(result.rolls) == 1

    def test_roll_level_11_fire_bolt(self):
        """Rolling Fire Bolt at level 11 should roll 3 dice."""
        result = roll_scaled_cantrip_damage("1d10", 11)

        assert result.total >= 3  # Minimum: 1+1+1
        assert result.total <= 30  # Maximum: 10+10+10
        assert len(result.rolls) == 3

    def test_roll_with_additional_modifier(self):
        """Additional modifiers should be added."""
        # Multiple rolls to verify modifier is always added
        for _ in range(5):
            result = roll_scaled_cantrip_damage("1d4", 1, additional_modifier=5)
            assert result.total >= 6  # 1 + 5
            assert result.total <= 9  # 4 + 5


class TestCantripDefinitions:
    """Test cantrip definition lookup."""

    def test_get_fire_bolt(self):
        """Should retrieve Fire Bolt definition."""
        cantrip = get_cantrip_definition("fire_bolt")

        assert cantrip is not None
        assert cantrip.name == "Fire Bolt"
        assert cantrip.base_damage == "1d10"
        assert cantrip.damage_type == "fire"
        assert cantrip.range == 120

    def test_get_sacred_flame(self):
        """Should retrieve Sacred Flame definition."""
        cantrip = get_cantrip_definition("sacred_flame")

        assert cantrip is not None
        assert cantrip.attack_type == "save"
        assert cantrip.save_type == "dexterity"

    def test_get_unknown_cantrip(self):
        """Unknown cantrip should return None."""
        cantrip = get_cantrip_definition("not_a_cantrip")
        assert cantrip is None

    def test_case_insensitive_lookup(self):
        """Lookup should be case insensitive."""
        cantrip = get_cantrip_definition("FIRE_BOLT")
        assert cantrip is not None

    def test_all_cantrips_have_required_fields(self):
        """All defined cantrips should have required fields."""
        for cantrip_id, cantrip in DAMAGE_CANTRIPS.items():
            assert cantrip.id == cantrip_id
            assert cantrip.name
            assert cantrip.base_damage
            assert cantrip.damage_type
            assert cantrip.attack_type


class TestScaledCantripInfo:
    """Test getting full scaled cantrip info."""

    def setup_method(self):
        """Reset rules before each test."""
        reset_rules_config()

    def test_get_scaled_fire_bolt_info(self):
        """Should get complete scaled Fire Bolt info."""
        info = get_scaled_cantrip_info("fire_bolt", 11)

        assert info is not None
        assert info["name"] == "Fire Bolt"
        assert info["base_damage"] == "1d10"
        assert info["scaled_damage"] == "3d10"
        assert info["damage_type"] == "fire"
        assert info["character_level"] == 11
        assert info["scaling_tier"] == 2

    def test_get_unknown_cantrip_info(self):
        """Unknown cantrip should return None."""
        info = get_scaled_cantrip_info("not_a_cantrip", 5)
        assert info is None


class TestSpecialCantrips:
    """Test special cantrip handling."""

    def setup_method(self):
        """Reset rules before each test."""
        reset_rules_config()

    def test_eldritch_blast_beams(self):
        """Eldritch Blast should fire more beams at higher levels."""
        assert get_eldritch_blast_beams(1) == 1
        assert get_eldritch_blast_beams(5) == 2
        assert get_eldritch_blast_beams(11) == 3
        assert get_eldritch_blast_beams(17) == 4

    def test_toll_the_dead_undamaged(self):
        """Toll the Dead deals d8 to undamaged targets."""
        damage = get_toll_the_dead_damage(5, target_is_damaged=False)
        assert damage == "2d8"

    def test_toll_the_dead_damaged(self):
        """Toll the Dead deals d12 to damaged targets."""
        damage = get_toll_the_dead_damage(5, target_is_damaged=True)
        assert damage == "2d12"

    def test_toll_the_dead_scaling(self):
        """Toll the Dead should scale at higher levels."""
        damage = get_toll_the_dead_damage(17, target_is_damaged=True)
        assert damage == "4d12"


class TestScalingDescriptions:
    """Test scaling description formatting."""

    def setup_method(self):
        """Reset rules before each test."""
        reset_rules_config()

    def test_base_description(self):
        """Level 1 description should show base damage."""
        desc = format_cantrip_scaling_description("fire_bolt", 1)

        assert "Fire Bolt" in desc
        assert "1d10" in desc
        assert "fire" in desc

    def test_scaled_description(self):
        """Higher level should show scaling info."""
        desc = format_cantrip_scaling_description("fire_bolt", 11)

        assert "3d10" in desc
        assert "11th level" in desc

    def test_eldritch_blast_description(self):
        """Eldritch Blast should mention beams."""
        desc = format_cantrip_scaling_description("eldritch_blast", 11)

        assert "3 beam" in desc
        assert "1d10" in desc  # Per-beam damage

    def test_unknown_cantrip_description(self):
        """Unknown cantrip should return error message."""
        desc = format_cantrip_scaling_description("not_a_cantrip", 5)
        assert "Unknown" in desc
