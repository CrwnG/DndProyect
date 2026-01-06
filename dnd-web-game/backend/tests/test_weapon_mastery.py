"""
Tests for Weapon Mastery System (2024 D&D Rules).

Tests all 8 weapon masteries:
- Cleave: Damage adjacent enemy on hit
- Graze: Deal ability mod damage on miss
- Nick: Extra attack with light weapon
- Push: Push target 10ft on hit (STR save)
- Sap: Target disadvantage on next attack
- Slow: Reduce target speed by 10ft
- Topple: STR save or prone
- Vex: Advantage on next attack vs same target
"""
import pytest
from unittest.mock import patch

from app.core.weapon_mastery import (
    MasteryType,
    MasteryEffect,
    WEAPON_MASTERY_MAP,
    get_weapon_mastery,
    apply_cleave,
    apply_graze,
    apply_nick,
    apply_push,
    apply_sap,
    apply_slow,
    apply_topple,
    apply_vex,
    apply_weapon_mastery,
    get_mastery_description,
    get_class_mastery_count,
)


class TestMasteryTypeEnum:
    """Test the MasteryType enum is complete."""

    def test_all_eight_masteries_defined(self):
        """All 8 weapon masteries should be defined."""
        expected = {"cleave", "graze", "nick", "push", "sap", "slow", "topple", "vex"}
        actual = {m.value for m in MasteryType}
        assert actual == expected

    def test_mastery_count(self):
        """Should have exactly 8 masteries."""
        assert len(MasteryType) == 8


class TestWeaponMasteryMap:
    """Test weapon to mastery mappings."""

    def test_longsword_has_sap(self):
        """Longsword should have SAP mastery."""
        assert WEAPON_MASTERY_MAP["longsword"] == MasteryType.SAP

    def test_greataxe_has_cleave(self):
        """Greataxe should have CLEAVE mastery."""
        assert WEAPON_MASTERY_MAP["greataxe"] == MasteryType.CLEAVE

    def test_greatsword_has_graze(self):
        """Greatsword should have GRAZE mastery."""
        assert WEAPON_MASTERY_MAP["greatsword"] == MasteryType.GRAZE

    def test_dagger_has_nick(self):
        """Dagger should have NICK mastery."""
        assert WEAPON_MASTERY_MAP["dagger"] == MasteryType.NICK

    def test_rapier_has_vex(self):
        """Rapier should have VEX mastery."""
        assert WEAPON_MASTERY_MAP["rapier"] == MasteryType.VEX

    def test_quarterstaff_has_topple(self):
        """Quarterstaff should have TOPPLE mastery."""
        assert WEAPON_MASTERY_MAP["quarterstaff"] == MasteryType.TOPPLE

    def test_warhammer_has_push(self):
        """Warhammer should have PUSH mastery."""
        assert WEAPON_MASTERY_MAP["warhammer"] == MasteryType.PUSH

    def test_club_has_slow(self):
        """Club should have SLOW mastery."""
        assert WEAPON_MASTERY_MAP["club"] == MasteryType.SLOW

    def test_all_weapons_have_valid_mastery(self):
        """All mapped weapons should have a valid MasteryType."""
        for weapon, mastery in WEAPON_MASTERY_MAP.items():
            assert isinstance(mastery, MasteryType), f"{weapon} has invalid mastery"


class TestGetWeaponMastery:
    """Test weapon mastery lookup function."""

    def test_get_known_weapon(self):
        """Should return mastery for known weapon."""
        assert get_weapon_mastery("longsword") == MasteryType.SAP

    def test_get_unknown_weapon_returns_none(self):
        """Should return None for unknown weapon."""
        assert get_weapon_mastery("banana") is None

    def test_case_insensitive(self):
        """Should handle case insensitively."""
        assert get_weapon_mastery("LONGSWORD") == MasteryType.SAP
        assert get_weapon_mastery("LongSword") == MasteryType.SAP

    def test_handles_spaces(self):
        """Should handle spaces in weapon names."""
        assert get_weapon_mastery("light hammer") == MasteryType.NICK
        assert get_weapon_mastery("light_hammer") == MasteryType.NICK


class TestApplyCleave:
    """Test CLEAVE mastery: On hit, damage adjacent enemy."""

    def test_cleave_damages_adjacent(self):
        """Cleave should deal STR mod damage to adjacent enemy."""
        result = apply_cleave(
            attacker_strength_mod=3,
            adjacent_enemy_ids=["goblin_2", "goblin_3"],
            original_target_id="goblin_1"
        )
        assert result.success is True
        assert result.mastery_type == MasteryType.CLEAVE
        assert result.extra_damage == 3
        assert "goblin_2" in result.affected_entity_ids

    def test_cleave_minimum_damage_one(self):
        """Cleave damage should be at least 1."""
        result = apply_cleave(
            attacker_strength_mod=-1,
            adjacent_enemy_ids=["enemy"],
            original_target_id="target"
        )
        assert result.extra_damage == 1

    def test_cleave_no_adjacent_fails(self):
        """Cleave should fail if no adjacent enemies."""
        result = apply_cleave(
            attacker_strength_mod=3,
            adjacent_enemy_ids=[],
            original_target_id="target"
        )
        assert result.success is False
        assert result.extra_damage == 0

    def test_cleave_hits_first_adjacent(self):
        """Cleave should hit the first adjacent enemy."""
        result = apply_cleave(
            attacker_strength_mod=3,
            adjacent_enemy_ids=["first", "second", "third"],
            original_target_id="target"
        )
        assert result.affected_entity_ids == ["first"]


class TestApplyGraze:
    """Test GRAZE mastery: On miss, deal ability mod damage."""

    def test_graze_deals_str_mod_damage(self):
        """Graze should deal STR mod damage on miss."""
        result = apply_graze(attacker_ability_mod=4)
        assert result.success is True
        assert result.mastery_type == MasteryType.GRAZE
        assert result.extra_damage == 4

    def test_graze_minimum_damage_one(self):
        """Graze damage should be at least 1."""
        result = apply_graze(attacker_ability_mod=-2)
        assert result.extra_damage == 1

    def test_graze_finesse_uses_higher_mod(self):
        """Graze with finesse weapon should use higher of STR/DEX."""
        result = apply_graze(
            attacker_ability_mod=2,  # STR
            weapon_is_finesse=True,
            attacker_dex_mod=4  # DEX is higher
        )
        assert result.extra_damage == 4

    def test_graze_finesse_still_uses_str_if_higher(self):
        """Graze with finesse weapon uses STR if higher than DEX."""
        result = apply_graze(
            attacker_ability_mod=5,  # STR is higher
            weapon_is_finesse=True,
            attacker_dex_mod=3
        )
        assert result.extra_damage == 5


class TestApplyNick:
    """Test NICK mastery: Extra attack with light weapon."""

    def test_nick_grants_extra_attack(self):
        """Nick should grant an extra attack."""
        result = apply_nick()
        assert result.success is True
        assert result.mastery_type == MasteryType.NICK
        assert result.target_condition == "extra_light_weapon_attack"


class TestApplyPush:
    """Test PUSH mastery: Push target 10ft on hit (STR save)."""

    @patch("app.core.weapon_mastery.roll_d20")
    def test_push_succeeds_on_failed_save(self, mock_roll):
        """Push should succeed when target fails STR save."""
        mock_roll.return_value = type("Roll", (), {"total": 8})()  # Low roll
        result = apply_push(
            target_strength_save_mod=0,
            attacker_dc=12
        )
        assert result.success is True
        assert result.mastery_type == MasteryType.PUSH
        assert result.push_distance == 10

    @patch("app.core.weapon_mastery.roll_d20")
    def test_push_fails_on_successful_save(self, mock_roll):
        """Push should fail when target succeeds STR save."""
        mock_roll.return_value = type("Roll", (), {"total": 15})()  # High roll
        result = apply_push(
            target_strength_save_mod=0,
            attacker_dc=12
        )
        assert result.success is False
        assert result.push_distance == 0


class TestApplySap:
    """Test SAP mastery: Target disadvantage on next attack."""

    def test_sap_applies_disadvantage(self):
        """Sap should apply disadvantage condition."""
        result = apply_sap()
        assert result.success is True
        assert result.mastery_type == MasteryType.SAP
        assert result.target_condition == "sapped"


class TestApplySlow:
    """Test SLOW mastery: Reduce target speed by 10ft."""

    def test_slow_reduces_speed(self):
        """Slow should apply slowed condition."""
        result = apply_slow()
        assert result.success is True
        assert result.mastery_type == MasteryType.SLOW
        assert result.target_condition == "slowed"


class TestApplyTopple:
    """Test TOPPLE mastery: STR save or fall prone."""

    @patch("app.core.weapon_mastery.roll_d20")
    def test_topple_causes_prone_on_failed_save(self, mock_roll):
        """Topple should cause prone on failed save."""
        mock_roll.return_value = type("Roll", (), {"total": 5})()
        result = apply_topple(
            target_strength_save_mod=0,
            attacker_dc=12
        )
        assert result.success is True
        assert result.mastery_type == MasteryType.TOPPLE
        assert result.target_condition == "prone"

    @patch("app.core.weapon_mastery.roll_d20")
    def test_topple_fails_on_successful_save(self, mock_roll):
        """Topple should fail on successful save."""
        mock_roll.return_value = type("Roll", (), {"total": 18})()
        result = apply_topple(
            target_strength_save_mod=0,
            attacker_dc=12
        )
        assert result.success is False
        assert result.target_condition is None


class TestApplyVex:
    """Test VEX mastery: Advantage on next attack vs same target."""

    def test_vex_grants_advantage(self):
        """Vex should grant advantage on next attack."""
        result = apply_vex()
        assert result.success is True
        assert result.mastery_type == MasteryType.VEX
        assert result.grants_advantage is True


class TestApplyWeaponMastery:
    """Test the main apply_weapon_mastery function."""

    def test_graze_only_applies_on_miss(self):
        """Graze should only apply when attack misses."""
        # On hit - graze should return None
        result = apply_weapon_mastery(
            mastery_type=MasteryType.GRAZE,
            hit=True,
            attacker_data={"str_mod": 3},
            target_data={},
            combat_context={}
        )
        assert result is None

        # On miss - graze should apply
        result = apply_weapon_mastery(
            mastery_type=MasteryType.GRAZE,
            hit=False,
            attacker_data={"str_mod": 3},
            target_data={},
            combat_context={}
        )
        assert result is not None
        assert result.mastery_type == MasteryType.GRAZE

    def test_other_masteries_only_apply_on_hit(self):
        """Non-graze masteries should only apply on hit."""
        for mastery in [MasteryType.SAP, MasteryType.SLOW, MasteryType.VEX, MasteryType.NICK]:
            result = apply_weapon_mastery(
                mastery_type=mastery,
                hit=False,
                attacker_data={},
                target_data={},
                combat_context={}
            )
            assert result is None, f"{mastery.value} should not apply on miss"

    def test_sap_on_hit(self):
        """SAP should apply on hit."""
        result = apply_weapon_mastery(
            mastery_type=MasteryType.SAP,
            hit=True,
            attacker_data={},
            target_data={},
            combat_context={}
        )
        assert result is not None
        assert result.target_condition == "sapped"


class TestGetMasteryDescription:
    """Test mastery description lookup."""

    def test_all_masteries_have_descriptions(self):
        """All masteries should have descriptions."""
        for mastery in MasteryType:
            desc = get_mastery_description(mastery)
            assert desc is not None
            assert len(desc) > 10  # Should be meaningful text


class TestGetClassMasteryCount:
    """Test class mastery count progression."""

    def test_fighter_gets_most_masteries(self):
        """Fighter should get the most masteries."""
        assert get_class_mastery_count("fighter", 1) == 3
        assert get_class_mastery_count("fighter", 4) == 4
        assert get_class_mastery_count("fighter", 10) == 5
        assert get_class_mastery_count("fighter", 16) == 6

    def test_rogue_gets_masteries(self):
        """Rogue should get weapon masteries."""
        assert get_class_mastery_count("rogue", 1) == 2
        assert get_class_mastery_count("rogue", 4) == 3

    def test_barbarian_gets_masteries(self):
        """Barbarian should get weapon masteries."""
        assert get_class_mastery_count("barbarian", 1) == 2
        assert get_class_mastery_count("barbarian", 4) == 3

    def test_paladin_gets_masteries(self):
        """Paladin should get weapon masteries."""
        assert get_class_mastery_count("paladin", 1) == 2
        assert get_class_mastery_count("paladin", 4) == 3

    def test_ranger_gets_masteries(self):
        """Ranger should get weapon masteries."""
        assert get_class_mastery_count("ranger", 1) == 2
        assert get_class_mastery_count("ranger", 4) == 3

    def test_wizard_gets_no_masteries(self):
        """Wizard should not get weapon masteries."""
        assert get_class_mastery_count("wizard", 1) == 0
        assert get_class_mastery_count("wizard", 20) == 0

    def test_case_insensitive(self):
        """Class lookup should be case insensitive."""
        assert get_class_mastery_count("FIGHTER", 1) == 3
        assert get_class_mastery_count("Fighter", 1) == 3


class TestMasteryEffect:
    """Test MasteryEffect dataclass."""

    def test_default_values(self):
        """MasteryEffect should have sensible defaults."""
        effect = MasteryEffect(
            mastery_type=MasteryType.VEX,
            success=True,
            description="Test"
        )
        assert effect.extra_damage == 0
        assert effect.target_condition is None
        assert effect.affected_entity_ids == []
        assert effect.grants_advantage is False
        assert effect.push_distance == 0
