"""Tests for the skill check system."""
import pytest
from unittest.mock import patch

from app.core.skill_checks import (
    Skill,
    SKILL_ABILITIES,
    DifficultyClass,
    SkillCheckResult,
    GroupCheckResult,
    get_ability_modifier,
    get_proficiency_bonus,
    roll_d20,
    perform_skill_check,
    perform_ability_check,
    perform_saving_throw,
    get_dc_difficulty_label,
    get_skill_display_name,
    get_skill_modifier,
    perform_group_check,
)


class TestSkillEnum:
    """Tests for the Skill enum."""

    def test_strength_skills(self):
        """Athletics is a Strength skill."""
        assert Skill.ATHLETICS.value == "athletics"

    def test_dexterity_skills(self):
        """Dexterity skills should be defined."""
        assert Skill.ACROBATICS.value == "acrobatics"
        assert Skill.SLEIGHT_OF_HAND.value == "sleight_of_hand"
        assert Skill.STEALTH.value == "stealth"

    def test_intelligence_skills(self):
        """Intelligence skills should be defined."""
        assert Skill.ARCANA.value == "arcana"
        assert Skill.HISTORY.value == "history"
        assert Skill.INVESTIGATION.value == "investigation"
        assert Skill.NATURE.value == "nature"
        assert Skill.RELIGION.value == "religion"

    def test_wisdom_skills(self):
        """Wisdom skills should be defined."""
        assert Skill.ANIMAL_HANDLING.value == "animal_handling"
        assert Skill.INSIGHT.value == "insight"
        assert Skill.MEDICINE.value == "medicine"
        assert Skill.PERCEPTION.value == "perception"
        assert Skill.SURVIVAL.value == "survival"

    def test_charisma_skills(self):
        """Charisma skills should be defined."""
        assert Skill.DECEPTION.value == "deception"
        assert Skill.INTIMIDATION.value == "intimidation"
        assert Skill.PERFORMANCE.value == "performance"
        assert Skill.PERSUASION.value == "persuasion"


class TestSkillAbilities:
    """Tests for skill to ability score mapping."""

    def test_athletics_uses_strength(self):
        """Athletics should use Strength."""
        assert SKILL_ABILITIES[Skill.ATHLETICS] == "str"

    def test_stealth_uses_dexterity(self):
        """Stealth should use Dexterity."""
        assert SKILL_ABILITIES[Skill.STEALTH] == "dex"

    def test_perception_uses_wisdom(self):
        """Perception should use Wisdom."""
        assert SKILL_ABILITIES[Skill.PERCEPTION] == "wis"

    def test_persuasion_uses_charisma(self):
        """Persuasion should use Charisma."""
        assert SKILL_ABILITIES[Skill.PERSUASION] == "cha"

    def test_arcana_uses_intelligence(self):
        """Arcana should use Intelligence."""
        assert SKILL_ABILITIES[Skill.ARCANA] == "int"


class TestDifficultyClass:
    """Tests for difficulty class enum."""

    def test_trivial_is_5(self):
        assert DifficultyClass.TRIVIAL.value == 5

    def test_easy_is_10(self):
        assert DifficultyClass.EASY.value == 10

    def test_medium_is_15(self):
        assert DifficultyClass.MEDIUM.value == 15

    def test_hard_is_20(self):
        assert DifficultyClass.HARD.value == 20

    def test_very_hard_is_25(self):
        assert DifficultyClass.VERY_HARD.value == 25

    def test_nearly_impossible_is_30(self):
        assert DifficultyClass.NEARLY_IMPOSSIBLE.value == 30


class TestGetAbilityModifier:
    """Tests for ability modifier calculation."""

    def test_score_10_gives_modifier_0(self):
        """Score of 10 should give modifier of 0."""
        assert get_ability_modifier(10) == 0

    def test_score_11_gives_modifier_0(self):
        """Score of 11 should give modifier of 0."""
        assert get_ability_modifier(11) == 0

    def test_score_12_gives_modifier_1(self):
        """Score of 12 should give modifier of +1."""
        assert get_ability_modifier(12) == 1

    def test_score_8_gives_modifier_negative_1(self):
        """Score of 8 should give modifier of -1."""
        assert get_ability_modifier(8) == -1

    def test_score_20_gives_modifier_5(self):
        """Score of 20 should give modifier of +5."""
        assert get_ability_modifier(20) == 5

    def test_score_1_gives_modifier_negative_5(self):
        """Score of 1 should give modifier of -5."""
        assert get_ability_modifier(1) == -5

    def test_score_18_gives_modifier_4(self):
        """Score of 18 should give modifier of +4."""
        assert get_ability_modifier(18) == 4


class TestGetProficiencyBonus:
    """Tests for proficiency bonus by level."""

    def test_level_1_gives_bonus_2(self):
        """Level 1-4 should have +2 proficiency."""
        assert get_proficiency_bonus(1) == 2
        assert get_proficiency_bonus(4) == 2

    def test_level_5_gives_bonus_3(self):
        """Level 5-8 should have +3 proficiency."""
        assert get_proficiency_bonus(5) == 3
        assert get_proficiency_bonus(8) == 3

    def test_level_9_gives_bonus_4(self):
        """Level 9-12 should have +4 proficiency."""
        assert get_proficiency_bonus(9) == 4
        assert get_proficiency_bonus(12) == 4

    def test_level_13_gives_bonus_5(self):
        """Level 13-16 should have +5 proficiency."""
        assert get_proficiency_bonus(13) == 5
        assert get_proficiency_bonus(16) == 5

    def test_level_17_gives_bonus_6(self):
        """Level 17-20 should have +6 proficiency."""
        assert get_proficiency_bonus(17) == 6
        assert get_proficiency_bonus(20) == 6


class TestRollD20:
    """Tests for d20 rolling mechanics."""

    def test_normal_roll_returns_single_die(self):
        """Normal roll should return one die result."""
        result, rolls = roll_d20()
        assert 1 <= result <= 20
        assert len(rolls) == 1
        assert rolls[0] == result

    @patch('app.core.skill_checks.random.randint')
    def test_advantage_takes_higher(self, mock_randint):
        """Advantage should take higher of two rolls."""
        mock_randint.side_effect = [5, 15]
        result, rolls = roll_d20(advantage=True)
        assert result == 15
        assert len(rolls) == 2
        assert 5 in rolls and 15 in rolls

    @patch('app.core.skill_checks.random.randint')
    def test_disadvantage_takes_lower(self, mock_randint):
        """Disadvantage should take lower of two rolls."""
        mock_randint.side_effect = [15, 5]
        result, rolls = roll_d20(disadvantage=True)
        assert result == 5
        assert len(rolls) == 2

    @patch('app.core.skill_checks.random.randint')
    def test_advantage_and_disadvantage_cancel(self, mock_randint):
        """Advantage and disadvantage should cancel out."""
        mock_randint.return_value = 10
        result, rolls = roll_d20(advantage=True, disadvantage=True)
        assert len(rolls) == 1  # Only one roll when they cancel


class TestPerformSkillCheck:
    """Tests for skill check execution."""

    @patch('app.core.skill_checks.roll_d20')
    def test_basic_skill_check(self, mock_roll):
        """Basic skill check should work."""
        mock_roll.return_value = (15, [15])
        stats = {"dex": 14, "level": 1}  # +2 modifier

        result = perform_skill_check("stealth", 15, stats)

        assert result.skill == "stealth"
        assert result.ability == "dex"
        assert result.roll == 15
        assert result.total == 17  # 15 + 2
        assert result.success is True

    @patch('app.core.skill_checks.roll_d20')
    def test_skill_check_with_proficiency(self, mock_roll):
        """Skill check with proficiency should add bonus."""
        mock_roll.return_value = (10, [10])
        stats = {
            "dex": 10,  # +0 modifier
            "level": 1,  # +2 proficiency
            "skill_proficiencies": ["stealth"],
        }

        result = perform_skill_check("stealth", 12, stats)

        assert result.modifier == 2  # +0 ability + 2 proficiency
        assert result.total == 12  # 10 + 2
        assert result.success is True

    @patch('app.core.skill_checks.roll_d20')
    def test_skill_check_with_expertise(self, mock_roll):
        """Expertise should double proficiency bonus."""
        mock_roll.return_value = (10, [10])
        stats = {
            "dex": 10,  # +0 modifier
            "level": 1,  # +2 proficiency
            "skill_proficiencies": ["stealth"],
        }

        result = perform_skill_check("stealth", 15, stats, proficient=True, expertise=True)

        assert result.modifier == 4  # +0 ability + 4 (doubled proficiency)
        assert result.total == 14  # 10 + 4

    @patch('app.core.skill_checks.roll_d20')
    def test_critical_success_on_nat_20(self, mock_roll):
        """Natural 20 should be marked as critical success."""
        mock_roll.return_value = (20, [20])
        stats = {"dex": 10, "level": 1}

        result = perform_skill_check("stealth", 25, stats)

        assert result.critical_success is True
        assert result.roll == 20

    @patch('app.core.skill_checks.roll_d20')
    def test_critical_failure_on_nat_1(self, mock_roll):
        """Natural 1 should be marked as critical failure."""
        mock_roll.return_value = (1, [1])
        stats = {"dex": 20, "level": 20}  # Even with high modifier

        result = perform_skill_check("stealth", 5, stats)

        assert result.critical_failure is True
        assert result.roll == 1

    @patch('app.core.skill_checks.roll_d20')
    def test_unknown_skill_defaults_to_ability(self, mock_roll):
        """Unknown skill should default to raw ability check."""
        mock_roll.return_value = (10, [10])
        stats = {"str": 16, "level": 1}  # +3 modifier

        result = perform_skill_check("strength", 13, stats)

        assert result.ability == "str"
        assert result.modifier == 3
        assert result.success is True


class TestPerformAbilityCheck:
    """Tests for raw ability checks."""

    @patch('app.core.skill_checks.roll_d20')
    def test_strength_check(self, mock_roll):
        """Strength ability check should work."""
        mock_roll.return_value = (12, [12])
        stats = {"str": 16}  # +3 modifier

        result = perform_ability_check("strength", 15, stats)

        # perform_ability_check returns the full ability name
        assert result.ability == "strength"
        assert result.modifier == 3
        assert result.total == 15
        assert result.success is True


class TestPerformSavingThrow:
    """Tests for saving throws."""

    @patch('app.core.skill_checks.roll_d20')
    def test_dexterity_save(self, mock_roll):
        """Dexterity saving throw should work."""
        mock_roll.return_value = (10, [10])
        stats = {"dex": 14, "level": 1}

        result = perform_saving_throw("dex", 12, stats)

        assert result.skill == "dex_save"
        assert result.ability == "dex"
        assert result.modifier == 2  # No proficiency
        assert result.success is True

    @patch('app.core.skill_checks.roll_d20')
    def test_save_with_proficiency(self, mock_roll):
        """Proficient save should add proficiency bonus."""
        mock_roll.return_value = (10, [10])
        stats = {
            "dex": 10,
            "level": 1,
            "saving_throw_proficiencies": ["dex"],
        }

        result = perform_saving_throw("dex", 12, stats)

        assert result.modifier == 2  # +2 proficiency
        assert result.total == 12
        assert result.success is True


class TestGetDcDifficultyLabel:
    """Tests for DC difficulty labels."""

    def test_trivial_dc(self):
        assert get_dc_difficulty_label(5) == "Trivial"

    def test_easy_dc(self):
        assert get_dc_difficulty_label(10) == "Easy"

    def test_medium_dc(self):
        assert get_dc_difficulty_label(15) == "Medium"

    def test_hard_dc(self):
        assert get_dc_difficulty_label(20) == "Hard"

    def test_very_hard_dc(self):
        assert get_dc_difficulty_label(25) == "Very Hard"

    def test_nearly_impossible_dc(self):
        assert get_dc_difficulty_label(30) == "Nearly Impossible"

    def test_in_between_values(self):
        """Values in between should use the lower category."""
        assert get_dc_difficulty_label(8) == "Easy"  # 6-10 is Easy
        assert get_dc_difficulty_label(12) == "Medium"  # 11-15 is Medium


class TestGetSkillDisplayName:
    """Tests for skill display name formatting."""

    def test_single_word_skill(self):
        assert get_skill_display_name("stealth") == "Stealth"

    def test_multi_word_skill(self):
        assert get_skill_display_name("animal_handling") == "Animal Handling"

    def test_sleight_of_hand(self):
        assert get_skill_display_name("sleight_of_hand") == "Sleight Of Hand"


class TestGetSkillModifier:
    """Tests for calculating skill modifiers."""

    def test_basic_modifier(self):
        """Should return ability modifier without proficiency."""
        stats = {"dex": 14, "level": 1}
        modifier = get_skill_modifier(stats, "stealth")
        assert modifier == 2

    def test_modifier_with_proficiency(self):
        """Should add proficiency bonus when proficient."""
        stats = {
            "dex": 14,
            "level": 5,  # +3 proficiency
            "skill_proficiencies": ["stealth"],
        }
        modifier = get_skill_modifier(stats, "stealth")
        assert modifier == 5  # +2 Dex + 3 proficiency


class TestSkillCheckResult:
    """Tests for SkillCheckResult dataclass."""

    def test_to_dict(self):
        """to_dict should return complete result dict."""
        result = SkillCheckResult(
            skill="stealth",
            ability="dex",
            roll=15,
            modifier=4,
            total=19,
            dc=15,
            success=True,
            critical_success=False,
            critical_failure=False,
            advantage=True,
            disadvantage=False,
            rolls=[10, 15],
        )

        d = result.to_dict()

        assert d["skill"] == "stealth"
        assert d["ability"] == "dex"
        assert d["roll"] == 15
        assert d["modifier"] == 4
        assert d["total"] == 19
        assert d["dc"] == 15
        assert d["success"] is True
        assert d["rolls"] == [10, 15]


class TestGroupCheckResult:
    """Tests for GroupCheckResult dataclass."""

    def test_to_dict(self):
        """to_dict should serialize group check results."""
        individual = SkillCheckResult(
            skill="stealth",
            ability="dex",
            roll=15,
            modifier=2,
            total=17,
            dc=15,
            success=True,
            critical_success=False,
            critical_failure=False,
        )

        result = GroupCheckResult(
            skill="stealth",
            dc=15,
            individual_results=[individual],
            successes=1,
            failures=0,
            needed_successes=1,
            success=True,
        )

        d = result.to_dict()

        assert d["skill"] == "stealth"
        assert d["dc"] == 15
        assert d["successes"] == 1
        assert d["failures"] == 0
        assert d["success"] is True
        assert len(d["individual_results"]) == 1


class TestPerformGroupCheck:
    """Tests for group skill checks."""

    @patch('app.core.skill_checks.roll_d20')
    def test_group_check_half_success(self, mock_roll):
        """Group check should succeed if at least half succeed."""
        # All roll 15
        mock_roll.return_value = (15, [15])

        party = [
            {"id": "p1", "name": "Fighter", "dexterity": 14, "level": 1},
            {"id": "p2", "name": "Wizard", "dexterity": 10, "level": 1},
        ]

        result = perform_group_check("stealth", 15, party)

        assert result.skill == "stealth"
        assert result.dc == 15
        assert len(result.individual_results) == 2
        # Both should succeed (15 + modifiers >= 15)
        assert result.successes >= 1
        assert result.success is True  # Need at least 1 of 2

    @patch('app.core.skill_checks.roll_d20')
    def test_group_check_majority_failure(self, mock_roll):
        """Group check should fail if less than half succeed."""
        mock_roll.return_value = (5, [5])  # Everyone rolls low

        party = [
            {"id": "p1", "name": "Fighter", "dexterity": 10, "level": 1},
            {"id": "p2", "name": "Wizard", "dexterity": 8, "level": 1},
            {"id": "p3", "name": "Cleric", "dexterity": 10, "level": 1},
        ]

        result = perform_group_check("stealth", 15, party)

        # All should fail (5 + small modifiers < 15)
        assert result.failures == 3
        assert result.success is False

    @patch('app.core.skill_checks.roll_d20')
    def test_group_check_with_advantage(self, mock_roll):
        """Group check with advantage should pass to all members."""
        mock_roll.return_value = (18, [10, 18])

        party = [{"id": "p1", "name": "Fighter", "dexterity": 10, "level": 1}]

        result = perform_group_check("stealth", 15, party, advantage=True)

        # Should have rolled with advantage
        individual = result.individual_results[0]
        assert individual.advantage is True

    def test_needed_successes_calculation(self):
        """Needed successes should be at least half (rounded up)."""
        with patch('app.core.skill_checks.roll_d20') as mock_roll:
            mock_roll.return_value = (10, [10])

            # 3 members need 2 successes (ceil(3/2) = 2)
            party = [
                {"id": "p1", "name": "A", "dexterity": 10},
                {"id": "p2", "name": "B", "dexterity": 10},
                {"id": "p3", "name": "C", "dexterity": 10},
            ]

            result = perform_group_check("stealth", 10, party)
            assert result.needed_successes == 2

            # 4 members need 2 successes (ceil(4/2) = 2)
            party.append({"id": "p4", "name": "D", "dexterity": 10})
            result = perform_group_check("stealth", 10, party)
            assert result.needed_successes == 2

            # 5 members need 3 successes (ceil(5/2) = 3)
            party.append({"id": "p5", "name": "E", "dexterity": 10})
            result = perform_group_check("stealth", 10, party)
            assert result.needed_successes == 3
