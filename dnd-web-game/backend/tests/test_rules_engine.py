"""Tests for the D&D 5e rules engine."""
import pytest
from app.core.rules_engine import (
    calculate_ability_modifier,
    calculate_proficiency_bonus,
    calculate_ac,
    resolve_attack,
    resolve_saving_throw,
    apply_damage,
    apply_healing,
    calculate_spell_save_dc,
    calculate_melee_attack_bonus,
    is_in_range,
    DamageType,
    AttackResult,
)


class TestAbilityModifier:
    """Tests for ability modifier calculation."""

    def test_average_score(self):
        """Score of 10 gives +0 modifier."""
        assert calculate_ability_modifier(10) == 0

    def test_high_scores(self):
        """High scores give positive modifiers."""
        assert calculate_ability_modifier(12) == 1
        assert calculate_ability_modifier(14) == 2
        assert calculate_ability_modifier(16) == 3
        assert calculate_ability_modifier(18) == 4
        assert calculate_ability_modifier(20) == 5

    def test_low_scores(self):
        """Low scores give negative modifiers."""
        assert calculate_ability_modifier(8) == -1
        assert calculate_ability_modifier(6) == -2
        assert calculate_ability_modifier(4) == -3

    def test_odd_scores(self):
        """Odd scores round down."""
        assert calculate_ability_modifier(11) == 0
        assert calculate_ability_modifier(13) == 1
        assert calculate_ability_modifier(15) == 2


class TestProficiencyBonus:
    """Tests for proficiency bonus calculation."""

    def test_low_levels(self):
        """Levels 1-4 get +2 proficiency."""
        for level in range(1, 5):
            assert calculate_proficiency_bonus(level) == 2

    def test_mid_levels(self):
        """Levels 5-8 get +3, 9-12 get +4."""
        for level in range(5, 9):
            assert calculate_proficiency_bonus(level) == 3
        for level in range(9, 13):
            assert calculate_proficiency_bonus(level) == 4

    def test_high_levels(self):
        """Levels 13-16 get +5, 17-20 get +6."""
        for level in range(13, 17):
            assert calculate_proficiency_bonus(level) == 5
        for level in range(17, 21):
            assert calculate_proficiency_bonus(level) == 6


class TestArmorClass:
    """Tests for AC calculation."""

    def test_unarmored(self):
        """Unarmored AC is 10 + DEX."""
        assert calculate_ac(base_ac=10, dex_modifier=2) == 12
        assert calculate_ac(base_ac=10, dex_modifier=-1) == 9

    def test_with_shield(self):
        """Shield adds +2 AC."""
        assert calculate_ac(base_ac=10, dex_modifier=2, shield_bonus=2) == 14

    def test_max_dex_bonus(self):
        """Medium armor limits DEX bonus."""
        # Medium armor with max DEX +2
        assert calculate_ac(base_ac=14, dex_modifier=4, max_dex_bonus=2) == 16
        # DEX +1 is less than max, so uses full DEX
        assert calculate_ac(base_ac=14, dex_modifier=1, max_dex_bonus=2) == 15


class TestAttackResolution:
    """Tests for attack resolution."""

    def test_hit_against_low_ac(self):
        """High attack bonus should hit low AC."""
        # Roll many times to ensure hits happen
        hits = 0
        for _ in range(100):
            result = resolve_attack(
                attack_bonus=10,
                target_ac=10,
                damage_dice="1d8",
                damage_modifier=3
            )
            if result.hit:
                hits += 1
        # Should hit most of the time with +10 vs AC 10
        assert hits > 80

    def test_miss_against_high_ac(self):
        """Low attack bonus should miss high AC."""
        misses = 0
        for _ in range(100):
            result = resolve_attack(
                attack_bonus=0,
                target_ac=25,
                damage_dice="1d6"
            )
            if not result.hit:
                misses += 1
        # Should miss most of the time with +0 vs AC 25
        assert misses > 80

    def test_critical_hit(self):
        """Natural 20 should be a critical hit."""
        for _ in range(1000):
            result = resolve_attack(
                attack_bonus=0,
                target_ac=30,  # Impossible to hit normally
                damage_dice="1d6"
            )
            if result.attack_roll.natural_20:
                assert result.hit is True
                assert result.critical_hit is True
                assert result.damage is not None
                assert result.damage.is_critical is True
                break

    def test_critical_miss(self):
        """Natural 1 should always miss."""
        for _ in range(1000):
            result = resolve_attack(
                attack_bonus=20,  # Very high bonus
                target_ac=1,  # Very low AC
                damage_dice="1d6"
            )
            if result.attack_roll.natural_1:
                assert result.hit is False
                assert result.critical_miss is True
                assert result.damage is None
                break

    def test_damage_type_recorded(self):
        """Damage type should be recorded on hit."""
        for _ in range(100):
            result = resolve_attack(
                attack_bonus=20,
                target_ac=10,
                damage_dice="1d8",
                damage_type=DamageType.FIRE
            )
            if result.hit:
                assert result.damage_type == DamageType.FIRE
                break


class TestSavingThrow:
    """Tests for saving throw resolution."""

    def test_high_modifier_vs_low_dc(self):
        """High modifier should usually succeed against low DC."""
        successes = 0
        for _ in range(100):
            result = resolve_saving_throw(save_modifier=10, dc=10)
            if result.success:
                successes += 1
        assert successes > 80

    def test_low_modifier_vs_high_dc(self):
        """Low modifier should usually fail against high DC."""
        failures = 0
        for _ in range(100):
            result = resolve_saving_throw(save_modifier=0, dc=20)
            if not result.success:
                failures += 1
        assert failures > 70

    def test_auto_fail(self):
        """Auto-fail should always fail regardless of roll."""
        result = resolve_saving_throw(save_modifier=20, dc=1, auto_fail=True)
        assert result.success is False

    def test_auto_succeed(self):
        """Auto-succeed should always succeed regardless of roll."""
        result = resolve_saving_throw(save_modifier=-10, dc=30, auto_succeed=True)
        assert result.success is True


class TestDamageApplication:
    """Tests for damage and healing application."""

    def test_normal_damage(self):
        """Normal damage reduces HP."""
        new_hp, actual, unconscious = apply_damage(
            current_hp=20, max_hp=20, damage=5
        )
        assert new_hp == 15
        assert actual == 5
        assert unconscious is False

    def test_resistance(self):
        """Resistance halves damage."""
        new_hp, actual, unconscious = apply_damage(
            current_hp=20, max_hp=20, damage=10, resistance=True
        )
        assert new_hp == 15  # 10 // 2 = 5 damage
        assert actual == 5

    def test_vulnerability(self):
        """Vulnerability doubles damage."""
        new_hp, actual, unconscious = apply_damage(
            current_hp=20, max_hp=20, damage=5, vulnerability=True
        )
        assert new_hp == 10  # 5 * 2 = 10 damage
        assert actual == 10

    def test_immunity(self):
        """Immunity negates all damage."""
        new_hp, actual, unconscious = apply_damage(
            current_hp=20, max_hp=20, damage=100, immunity=True
        )
        assert new_hp == 20
        assert actual == 0

    def test_unconscious_at_zero(self):
        """Creature is unconscious at 0 HP."""
        new_hp, actual, unconscious = apply_damage(
            current_hp=5, max_hp=20, damage=10
        )
        assert new_hp == 0  # Can't go negative
        assert unconscious is True

    def test_healing(self):
        """Healing restores HP."""
        new_hp, actual = apply_healing(current_hp=10, max_hp=20, healing=5)
        assert new_hp == 15
        assert actual == 5

    def test_healing_cap(self):
        """Healing can't exceed max HP."""
        new_hp, actual = apply_healing(current_hp=18, max_hp=20, healing=10)
        assert new_hp == 20
        assert actual == 2


class TestSpellDC:
    """Tests for spell save DC calculation."""

    def test_basic_dc(self):
        """DC = 8 + proficiency + ability modifier."""
        dc = calculate_spell_save_dc(
            spellcasting_ability_modifier=3,
            proficiency_bonus=2
        )
        assert dc == 13  # 8 + 2 + 3


class TestMeleeAttackBonus:
    """Tests for melee attack bonus calculation."""

    def test_basic_bonus(self):
        """Bonus = STR + proficiency."""
        bonus = calculate_melee_attack_bonus(
            strength_modifier=3,
            proficiency_bonus=2,
            is_proficient=True
        )
        assert bonus == 5

    def test_not_proficient(self):
        """No proficiency bonus if not proficient."""
        bonus = calculate_melee_attack_bonus(
            strength_modifier=3,
            proficiency_bonus=2,
            is_proficient=False
        )
        assert bonus == 3

    def test_finesse_uses_higher(self):
        """Finesse weapon uses higher of STR or DEX."""
        # DEX higher
        bonus = calculate_melee_attack_bonus(
            strength_modifier=1,
            proficiency_bonus=2,
            is_finesse=True,
            dexterity_modifier=4
        )
        assert bonus == 6  # Uses DEX (4) + prof (2)

        # STR higher
        bonus = calculate_melee_attack_bonus(
            strength_modifier=5,
            proficiency_bonus=2,
            is_finesse=True,
            dexterity_modifier=2
        )
        assert bonus == 7  # Uses STR (5) + prof (2)


class TestRange:
    """Tests for range checking."""

    def test_adjacent_melee(self):
        """Adjacent targets are in melee range."""
        in_range, in_long = is_in_range(0, 0, 1, 0, weapon_range=5)
        assert in_range is True

    def test_diagonal_melee(self):
        """Diagonal adjacent is also 5ft in D&D."""
        in_range, in_long = is_in_range(0, 0, 1, 1, weapon_range=5)
        assert in_range is True

    def test_out_of_melee_range(self):
        """Two squares away is out of melee range."""
        in_range, in_long = is_in_range(0, 0, 2, 0, weapon_range=5)
        assert in_range is False

    def test_ranged_in_range(self):
        """Ranged weapon range check."""
        in_range, in_long = is_in_range(0, 0, 4, 4, weapon_range=80)
        # 4 squares diagonal = 20ft, within 80ft
        assert in_range is True
