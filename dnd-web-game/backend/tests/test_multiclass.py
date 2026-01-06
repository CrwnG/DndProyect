"""
Tests for multiclass prerequisites and validation.
"""
import pytest
from app.core.multiclass import (
    check_multiclass_prerequisites,
    check_prerequisite,
    get_multiclass_proficiencies,
    get_eligible_multiclass_options,
    format_prerequisites,
    MULTICLASS_PREREQUISITES,
    MulticlassPrerequisite,
)


class TestMulticlassPrerequisites:
    """Test multiclass prerequisite checking."""

    def test_fighter_str_or_dex_meets_str(self):
        """Fighter can multiclass with STR 13."""
        can_mc, failures = check_multiclass_prerequisites(
            current_classes={},
            new_class="fighter",
            ability_scores={"strength": 14, "dexterity": 10}
        )
        assert can_mc is True
        assert len(failures) == 0

    def test_fighter_str_or_dex_meets_dex(self):
        """Fighter can multiclass with DEX 13."""
        can_mc, failures = check_multiclass_prerequisites(
            current_classes={},
            new_class="fighter",
            ability_scores={"strength": 10, "dexterity": 14}
        )
        assert can_mc is True
        assert len(failures) == 0

    def test_fighter_str_or_dex_fails_neither(self):
        """Fighter cannot multiclass without STR or DEX 13."""
        can_mc, failures = check_multiclass_prerequisites(
            current_classes={},
            new_class="fighter",
            ability_scores={"strength": 10, "dexterity": 10}
        )
        assert can_mc is False
        assert len(failures) > 0

    def test_monk_requires_both_dex_and_wis(self):
        """Monk requires both DEX 13 AND WIS 13."""
        # Meets both
        can_mc, failures = check_multiclass_prerequisites(
            current_classes={},
            new_class="monk",
            ability_scores={"dexterity": 14, "wisdom": 14}
        )
        assert can_mc is True

        # Only DEX
        can_mc, failures = check_multiclass_prerequisites(
            current_classes={},
            new_class="monk",
            ability_scores={"dexterity": 14, "wisdom": 10}
        )
        assert can_mc is False

        # Only WIS
        can_mc, failures = check_multiclass_prerequisites(
            current_classes={},
            new_class="monk",
            ability_scores={"dexterity": 10, "wisdom": 14}
        )
        assert can_mc is False

    def test_paladin_requires_str_and_cha(self):
        """Paladin requires STR 13 AND CHA 13."""
        can_mc, failures = check_multiclass_prerequisites(
            current_classes={},
            new_class="paladin",
            ability_scores={"strength": 14, "charisma": 14}
        )
        assert can_mc is True

        can_mc, failures = check_multiclass_prerequisites(
            current_classes={},
            new_class="paladin",
            ability_scores={"strength": 14, "charisma": 10}
        )
        assert can_mc is False

    def test_must_meet_current_class_prereqs(self):
        """Must meet prerequisites for current class too."""
        # Fighter (STR 13) trying to multiclass into Wizard (INT 13)
        # Must have BOTH STR 13 AND INT 13
        can_mc, failures = check_multiclass_prerequisites(
            current_classes={"fighter": 3},
            new_class="wizard",
            ability_scores={"strength": 14, "intelligence": 14}
        )
        assert can_mc is True

        # Has INT but not STR - fails fighter prereq
        can_mc, failures = check_multiclass_prerequisites(
            current_classes={"fighter": 3},
            new_class="wizard",
            ability_scores={"strength": 10, "intelligence": 14}
        )
        assert can_mc is False
        assert any("fighter" in f.lower() for f in failures)

    def test_multiclass_from_multiple_classes(self):
        """Must meet prereqs for all current classes."""
        # Fighter/Wizard trying to add Cleric
        can_mc, failures = check_multiclass_prerequisites(
            current_classes={"fighter": 3, "wizard": 2},
            new_class="cleric",
            ability_scores={
                "strength": 14,  # Fighter
                "intelligence": 14,  # Wizard
                "wisdom": 14,  # Cleric
            }
        )
        assert can_mc is True

        # Missing wizard INT
        can_mc, failures = check_multiclass_prerequisites(
            current_classes={"fighter": 3, "wizard": 2},
            new_class="cleric",
            ability_scores={
                "strength": 14,
                "intelligence": 10,  # Fails wizard
                "wisdom": 14,
            }
        )
        assert can_mc is False

    def test_single_ability_prereqs(self):
        """Test classes with single ability prerequisites."""
        single_prereq_classes = {
            "barbarian": ("strength", 13),
            "bard": ("charisma", 13),
            "cleric": ("wisdom", 13),
            "druid": ("wisdom", 13),
            "rogue": ("dexterity", 13),
            "sorcerer": ("charisma", 13),
            "warlock": ("charisma", 13),
            "wizard": ("intelligence", 13),
        }

        for class_name, (ability, min_score) in single_prereq_classes.items():
            # Meets requirement
            scores = {ability: min_score}
            can_mc, _ = check_multiclass_prerequisites({}, class_name, scores)
            assert can_mc is True, f"{class_name} should pass with {ability} {min_score}"

            # Fails requirement
            scores = {ability: min_score - 1}
            can_mc, _ = check_multiclass_prerequisites({}, class_name, scores)
            assert can_mc is False, f"{class_name} should fail with {ability} {min_score - 1}"


class TestMulticlassProficiencies:
    """Test multiclass proficiency grants."""

    def test_fighter_grants_armor_and_weapons(self):
        """Fighter multiclass grants armor, shields, and weapons."""
        profs = get_multiclass_proficiencies("fighter")
        assert "light armor" in profs["armor"]
        assert "medium armor" in profs["armor"]
        assert "shields" in profs["armor"]
        assert "martial weapons" in profs["weapons"]

    def test_wizard_grants_nothing(self):
        """Wizard multiclass grants no proficiencies."""
        profs = get_multiclass_proficiencies("wizard")
        assert profs["armor"] == []
        assert profs["weapons"] == []
        assert profs["skills"] == []

    def test_rogue_grants_light_armor_and_skill(self):
        """Rogue multiclass grants light armor and one skill."""
        profs = get_multiclass_proficiencies("rogue")
        assert "light armor" in profs["armor"]
        assert len(profs["skills"]) > 0  # One skill choice

    def test_unknown_class_returns_empty(self):
        """Unknown class returns empty proficiencies."""
        profs = get_multiclass_proficiencies("unknown_class")
        assert profs["armor"] == []
        assert profs["weapons"] == []
        assert profs["skills"] == []


class TestEligibleOptions:
    """Test getting eligible multiclass options."""

    def test_all_options_returned(self):
        """All 12 classes should be in options."""
        options = get_eligible_multiclass_options(
            current_classes={},
            ability_scores={"strength": 10}
        )
        assert len(options) == 12

    def test_marks_ineligible_correctly(self):
        """Low stats should mark classes ineligible."""
        options = get_eligible_multiclass_options(
            current_classes={},
            ability_scores={
                "strength": 10,
                "dexterity": 10,
                "constitution": 10,
                "intelligence": 10,
                "wisdom": 10,
                "charisma": 10,
            }
        )

        # All classes should be ineligible with 10s
        for class_name, info in options.items():
            assert info["eligible"] is False, f"{class_name} should be ineligible"
            assert len(info["reasons"]) > 0

    def test_marks_existing_class(self):
        """Should mark if character already has class."""
        options = get_eligible_multiclass_options(
            current_classes={"fighter": 5},
            ability_scores={"strength": 14, "dexterity": 14}
        )

        assert options["fighter"]["already_has"] is True
        assert options["wizard"]["already_has"] is False


class TestFormatPrerequisites:
    """Test prerequisite formatting."""

    def test_format_single_prereq(self):
        """Single prerequisite formats correctly."""
        result = format_prerequisites("wizard")
        assert "Intelligence 13" in result

    def test_format_or_prereq(self):
        """OR prerequisite formats correctly."""
        result = format_prerequisites("fighter")
        assert "or" in result.lower()
        assert "Strength" in result
        assert "Dexterity" in result

    def test_format_and_prereq(self):
        """AND prerequisite formats correctly."""
        result = format_prerequisites("monk")
        assert "and" in result.lower()
        assert "Dexterity" in result
        assert "Wisdom" in result

    def test_format_unknown_class(self):
        """Unknown class returns default message."""
        result = format_prerequisites("unknown")
        assert "No prerequisites" in result


class TestPrerequisiteDataIntegrity:
    """Test that all prerequisite data is correct."""

    def test_all_12_classes_defined(self):
        """All 12 PHB classes have prerequisites defined."""
        expected_classes = {
            "barbarian", "bard", "cleric", "druid",
            "fighter", "monk", "paladin", "ranger",
            "rogue", "sorcerer", "warlock", "wizard"
        }
        assert set(MULTICLASS_PREREQUISITES.keys()) == expected_classes

    def test_all_scores_are_13(self):
        """All multiclass requirements use 13 as the minimum."""
        for class_name, prereq in MULTICLASS_PREREQUISITES.items():
            for ability, score in prereq.requirements:
                assert score == 13, f"{class_name} has score {score} for {ability}"

    def test_valid_ability_names(self):
        """All ability names are valid."""
        valid_abilities = {"strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"}
        for class_name, prereq in MULTICLASS_PREREQUISITES.items():
            for ability, _ in prereq.requirements:
                assert ability in valid_abilities, f"{class_name} has invalid ability {ability}"
