"""Tests for the character builder system."""
import pytest
from unittest.mock import patch, MagicMock
import uuid

from app.core.character_builder import (
    CreationStep,
    ValidationResult,
    CharacterBuild,
    CharacterBuilder,
    get_character_builder,
)


class TestCreationStepEnum:
    """Tests for CreationStep enum."""

    def test_all_steps_defined(self):
        """All creation steps should be defined."""
        assert CreationStep.SPECIES.value == "species"
        assert CreationStep.CLASS.value == "class"
        assert CreationStep.BACKGROUND.value == "background"
        assert CreationStep.ABILITIES.value == "abilities"
        assert CreationStep.FEAT.value == "feat"
        assert CreationStep.EQUIPMENT.value == "equipment"
        assert CreationStep.DETAILS.value == "details"
        assert CreationStep.REVIEW.value == "review"

    def test_step_count(self):
        """Should have 8 creation steps."""
        assert len(CreationStep) == 8


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_valid_result(self):
        """Valid result should have no errors."""
        result = ValidationResult(valid=True)
        assert result.valid is True
        assert result.errors == []
        assert result.warnings == []
        assert result.data == {}

    def test_invalid_result_with_errors(self):
        """Invalid result should have errors."""
        result = ValidationResult(
            valid=False,
            errors=["Missing required field"],
            warnings=["Optional field empty"]
        )
        assert result.valid is False
        assert "Missing required field" in result.errors
        assert "Optional field empty" in result.warnings

    def test_result_with_data(self):
        """Result can include extra data."""
        result = ValidationResult(
            valid=True,
            data={"key": "value", "count": 5}
        )
        assert result.data["key"] == "value"
        assert result.data["count"] == 5


class TestCharacterBuild:
    """Tests for CharacterBuild dataclass."""

    def test_new_build_has_uuid(self):
        """New build should have a unique UUID."""
        build1 = CharacterBuild()
        build2 = CharacterBuild()
        assert build1.id != build2.id
        # Should be valid UUID
        uuid.UUID(build1.id)

    def test_default_ability_scores(self):
        """Default ability scores should be 8."""
        build = CharacterBuild()
        for score in build.ability_scores.values():
            assert score == 8

    def test_default_level(self):
        """Default level should be 1."""
        build = CharacterBuild()
        assert build.level == 1


class TestCharacterBuildCurrentStep:
    """Tests for CharacterBuild.get_current_step()."""

    def test_initial_step_is_species(self):
        """New build should start at species step."""
        build = CharacterBuild()
        assert build.get_current_step() == CreationStep.SPECIES

    def test_step_advances_to_class(self):
        """Should advance to class after species."""
        build = CharacterBuild(species_id="human")
        assert build.get_current_step() == CreationStep.CLASS

    def test_step_advances_to_background(self):
        """Should advance to background after class."""
        build = CharacterBuild(species_id="human", class_id="fighter")
        assert build.get_current_step() == CreationStep.BACKGROUND

    def test_step_advances_to_abilities(self):
        """Should advance to abilities after background."""
        build = CharacterBuild(
            species_id="human",
            class_id="fighter",
            background_id="soldier"
        )
        assert build.get_current_step() == CreationStep.ABILITIES

    def test_step_advances_to_feat(self):
        """Should advance to feat after abilities."""
        build = CharacterBuild(
            species_id="human",
            class_id="fighter",
            background_id="soldier",
            ability_bonuses={"strength": 2, "constitution": 1}
        )
        assert build.get_current_step() == CreationStep.FEAT

    def test_step_advances_to_equipment(self):
        """Should advance to equipment after feat."""
        build = CharacterBuild(
            species_id="human",
            class_id="fighter",
            background_id="soldier",
            ability_bonuses={"strength": 2, "constitution": 1},
            origin_feat_id="alert"
        )
        assert build.get_current_step() == CreationStep.EQUIPMENT

    def test_step_advances_to_details(self):
        """Should advance to details after equipment."""
        build = CharacterBuild(
            species_id="human",
            class_id="fighter",
            background_id="soldier",
            ability_bonuses={"strength": 2, "constitution": 1},
            origin_feat_id="alert",
            equipment_choices=[{"weapon": "longsword"}]
        )
        assert build.get_current_step() == CreationStep.DETAILS

    def test_step_advances_to_review(self):
        """Should advance to review when complete."""
        build = CharacterBuild(
            species_id="human",
            class_id="fighter",
            background_id="soldier",
            ability_bonuses={"strength": 2, "constitution": 1},
            origin_feat_id="alert",
            equipment_choices=[{"weapon": "longsword"}],
            name="Test Hero"
        )
        assert build.get_current_step() == CreationStep.REVIEW


class TestCharacterBuildAbilityScores:
    """Tests for ability score calculations."""

    def test_get_final_ability_scores_applies_bonuses(self):
        """Final scores should include bonuses."""
        build = CharacterBuild(
            ability_scores={"strength": 15, "dexterity": 14, "constitution": 13,
                           "intelligence": 12, "wisdom": 10, "charisma": 8},
            ability_bonuses={"strength": 2, "constitution": 1}
        )
        final = build.get_final_ability_scores()
        assert final["strength"] == 17  # 15 + 2
        assert final["constitution"] == 14  # 13 + 1
        assert final["dexterity"] == 14  # unchanged

    def test_ability_scores_capped_at_20(self):
        """Final scores should not exceed 20."""
        build = CharacterBuild(
            ability_scores={"strength": 20, "dexterity": 8, "constitution": 8,
                           "intelligence": 8, "wisdom": 8, "charisma": 8},
            ability_bonuses={"strength": 2}
        )
        final = build.get_final_ability_scores()
        assert final["strength"] == 20  # capped at 20

    def test_get_ability_modifiers(self):
        """Modifiers should be calculated correctly."""
        build = CharacterBuild(
            ability_scores={"strength": 18, "dexterity": 14, "constitution": 10,
                           "intelligence": 8, "wisdom": 12, "charisma": 16}
        )
        mods = build.get_ability_modifiers()
        assert mods["strength"] == 4   # (18-10)//2 = 4
        assert mods["dexterity"] == 2  # (14-10)//2 = 2
        assert mods["constitution"] == 0  # (10-10)//2 = 0
        assert mods["intelligence"] == -1  # (8-10)//2 = -1
        assert mods["wisdom"] == 1     # (12-10)//2 = 1
        assert mods["charisma"] == 3   # (16-10)//2 = 3


class TestCharacterBuilderManagement:
    """Tests for build management functions."""

    @patch('app.core.character_builder.get_rules_loader')
    def test_create_new_build(self, mock_rules):
        """create_new_build should return a new build."""
        mock_rules.return_value = MagicMock()
        builder = CharacterBuilder()
        build = builder.create_new_build()

        assert build is not None
        assert build.id is not None
        assert build.species_id is None

    @patch('app.core.character_builder.get_rules_loader')
    def test_get_build_returns_existing(self, mock_rules):
        """get_build should return an existing build."""
        mock_rules.return_value = MagicMock()
        builder = CharacterBuilder()
        build = builder.create_new_build()

        retrieved = builder.get_build(build.id)
        assert retrieved is build

    @patch('app.core.character_builder.get_rules_loader')
    def test_get_build_returns_none_for_missing(self, mock_rules):
        """get_build should return None for non-existent builds."""
        mock_rules.return_value = MagicMock()
        builder = CharacterBuilder()

        result = builder.get_build("nonexistent-id")
        assert result is None

    @patch('app.core.character_builder.get_rules_loader')
    def test_delete_build_removes_build(self, mock_rules):
        """delete_build should remove the build."""
        mock_rules.return_value = MagicMock()
        builder = CharacterBuilder()
        build = builder.create_new_build()

        result = builder.delete_build(build.id)
        assert result is True
        assert builder.get_build(build.id) is None

    @patch('app.core.character_builder.get_rules_loader')
    def test_delete_nonexistent_returns_false(self, mock_rules):
        """delete_build should return False for non-existent builds."""
        mock_rules.return_value = MagicMock()
        builder = CharacterBuilder()

        result = builder.delete_build("nonexistent-id")
        assert result is False


class TestSpeciesSelection:
    """Tests for species selection."""

    @patch('app.core.character_builder.get_rules_loader')
    def test_set_valid_species(self, mock_rules):
        """Setting a valid species should succeed."""
        mock_loader = MagicMock()
        mock_loader.get_species.return_value = {
            "id": "human",
            "name": "Human",
            "size": "Medium",
            "speed": 30,
            "traits": [{"name": "Resourceful", "description": "Extra skill"}],
            "languages": ["Common"]
        }
        mock_rules.return_value = mock_loader

        builder = CharacterBuilder()
        build = builder.create_new_build()
        result = builder.set_species(build, "human")

        assert result.valid is True
        assert build.species_id == "human"
        assert build.size == "Medium"

    @patch('app.core.character_builder.get_rules_loader')
    def test_set_invalid_species(self, mock_rules):
        """Setting an invalid species should fail."""
        mock_loader = MagicMock()
        mock_loader.get_species.return_value = None
        mock_rules.return_value = mock_loader

        builder = CharacterBuilder()
        build = builder.create_new_build()
        result = builder.set_species(build, "unknown")

        assert result.valid is False
        assert "Unknown species" in result.errors[0]

    @patch('app.core.character_builder.get_rules_loader')
    def test_size_choice_required_for_flexible_species(self, mock_rules):
        """Species with flexible size should require choice."""
        mock_loader = MagicMock()
        mock_loader.get_species.return_value = {
            "id": "human",
            "name": "Human",
            "size": "Small or Medium",
            "speed": 30
        }
        mock_rules.return_value = mock_loader

        builder = CharacterBuilder()
        build = builder.create_new_build()
        result = builder.set_species(build, "human")

        assert result.valid is True
        assert result.data["size_choice_required"] is True
        assert build.size is None  # Not set yet

    @patch('app.core.character_builder.get_rules_loader')
    def test_set_size_choice_valid(self, mock_rules):
        """Setting a valid size choice should succeed."""
        mock_rules.return_value = MagicMock()
        builder = CharacterBuilder()
        build = builder.create_new_build()

        result = builder.set_size_choice(build, "Small")
        assert result.valid is True
        assert build.size == "Small"

    @patch('app.core.character_builder.get_rules_loader')
    def test_set_size_choice_invalid(self, mock_rules):
        """Setting an invalid size choice should fail."""
        mock_rules.return_value = MagicMock()
        builder = CharacterBuilder()
        build = builder.create_new_build()

        result = builder.set_size_choice(build, "Large")
        assert result.valid is False
        assert "Small" in result.errors[0] or "Medium" in result.errors[0]


class TestClassSelection:
    """Tests for class selection."""

    @patch('app.core.character_builder.get_rules_loader')
    def test_set_valid_class(self, mock_rules):
        """Setting a valid class should succeed."""
        mock_loader = MagicMock()
        mock_loader.get_class.return_value = {
            "id": "fighter",
            "name": "Fighter",
            "hit_die": "d10",
            "skill_choices": {"options": ["athletics", "acrobatics"], "count": 2},
            "armor_proficiencies": ["all armor", "shields"],
            "weapon_proficiencies": ["simple", "martial"]
        }
        mock_loader.get_class_features_at_level.return_value = []
        mock_loader.get_class_equipment_choices.return_value = []
        mock_rules.return_value = mock_loader

        builder = CharacterBuilder()
        build = builder.create_new_build()
        result = builder.set_class(build, "fighter")

        assert result.valid is True
        assert build.class_id == "fighter"
        assert result.data["hit_die"] == "d10"

    @patch('app.core.character_builder.get_rules_loader')
    def test_set_invalid_class(self, mock_rules):
        """Setting an invalid class should fail."""
        mock_loader = MagicMock()
        mock_loader.get_class.return_value = None
        mock_rules.return_value = mock_loader

        builder = CharacterBuilder()
        build = builder.create_new_build()
        result = builder.set_class(build, "unknown")

        assert result.valid is False
        assert "Unknown class" in result.errors[0]


class TestSkillProficiencies:
    """Tests for skill proficiency selection."""

    @patch('app.core.character_builder.get_rules_loader')
    def test_set_valid_skills(self, mock_rules):
        """Setting valid skills should succeed."""
        mock_loader = MagicMock()
        mock_loader.get_class.return_value = {
            "skill_choices": {
                "options": ["athletics", "acrobatics", "perception", "stealth"],
                "count": 2
            }
        }
        mock_rules.return_value = mock_loader

        builder = CharacterBuilder()
        build = CharacterBuild(class_id="fighter")
        builder._builds[build.id] = build

        result = builder.set_skill_choices(build, ["athletics", "perception"])

        assert result.valid is True
        assert build.skill_choices == ["athletics", "perception"]

    @patch('app.core.character_builder.get_rules_loader')
    def test_set_skills_wrong_count(self, mock_rules):
        """Setting wrong number of skills should fail."""
        mock_loader = MagicMock()
        mock_loader.get_class.return_value = {
            "skill_choices": {"options": ["athletics", "acrobatics"], "count": 2}
        }
        mock_rules.return_value = mock_loader

        builder = CharacterBuilder()
        build = CharacterBuild(class_id="fighter")

        result = builder.set_skill_choices(build, ["athletics"])

        assert result.valid is False
        assert "exactly 2" in result.errors[0]

    @patch('app.core.character_builder.get_rules_loader')
    def test_set_skills_invalid_option(self, mock_rules):
        """Setting invalid skill should fail."""
        mock_loader = MagicMock()
        mock_loader.get_class.return_value = {
            "skill_choices": {"options": ["athletics", "acrobatics"], "count": 2}
        }
        mock_rules.return_value = mock_loader

        builder = CharacterBuilder()
        build = CharacterBuild(class_id="fighter")

        result = builder.set_skill_choices(build, ["athletics", "arcana"])

        assert result.valid is False
        assert "arcana" in result.errors[0]

    @patch('app.core.character_builder.get_rules_loader')
    def test_set_skills_duplicate(self, mock_rules):
        """Setting duplicate skills should fail."""
        mock_loader = MagicMock()
        mock_loader.get_class.return_value = {
            "skill_choices": {"options": ["athletics", "acrobatics"], "count": 2}
        }
        mock_rules.return_value = mock_loader

        builder = CharacterBuilder()
        build = CharacterBuild(class_id="fighter")

        result = builder.set_skill_choices(build, ["athletics", "athletics"])

        assert result.valid is False
        assert "same skill twice" in result.errors[0]

    @patch('app.core.character_builder.get_rules_loader')
    def test_set_skills_no_class(self, mock_rules):
        """Setting skills without class should fail."""
        mock_rules.return_value = MagicMock()
        builder = CharacterBuilder()
        build = CharacterBuild()

        result = builder.set_skill_choices(build, ["athletics"])

        assert result.valid is False
        assert "class first" in result.errors[0]


class TestBackgroundSelection:
    """Tests for background selection."""

    @patch('app.core.character_builder.get_rules_loader')
    def test_set_valid_background(self, mock_rules):
        """Setting a valid background should succeed."""
        mock_loader = MagicMock()
        mock_loader.get_background.return_value = {
            "id": "soldier",
            "name": "Soldier",
            "skill_proficiencies": ["athletics", "intimidation"],
            "origin_feat": "savage_attacker",
            "ability_score_increases": {
                "options": ["strength", "constitution"]
            }
        }
        mock_rules.return_value = mock_loader

        builder = CharacterBuilder()
        build = builder.create_new_build()
        result = builder.set_background(build, "soldier")

        assert result.valid is True
        assert build.background_id == "soldier"

    @patch('app.core.character_builder.get_rules_loader')
    def test_set_invalid_background(self, mock_rules):
        """Setting an invalid background should fail."""
        mock_loader = MagicMock()
        mock_loader.get_background.return_value = None
        mock_rules.return_value = mock_loader

        builder = CharacterBuilder()
        build = builder.create_new_build()
        result = builder.set_background(build, "unknown")

        assert result.valid is False
        assert "Unknown background" in result.errors[0]


class TestAbilityScores:
    """Tests for ability score setting."""

    @patch('app.core.character_builder.get_rules_loader')
    def test_set_point_buy_valid(self, mock_rules):
        """Valid point buy should succeed."""
        mock_loader = MagicMock()
        mock_loader.validate_point_buy.return_value = {
            "valid": True,
            "total_cost": 27,
            "points_remaining": 0
        }
        mock_rules.return_value = mock_loader

        builder = CharacterBuilder()
        build = builder.create_new_build()
        scores = {
            "strength": 15, "dexterity": 14, "constitution": 13,
            "intelligence": 12, "wisdom": 10, "charisma": 8
        }
        result = builder.set_ability_scores(build, scores, "point_buy")

        assert result.valid is True
        assert build.ability_scores == scores
        assert build.ability_method == "point_buy"

    @patch('app.core.character_builder.get_rules_loader')
    def test_set_point_buy_invalid(self, mock_rules):
        """Invalid point buy should fail."""
        mock_loader = MagicMock()
        mock_loader.validate_point_buy.return_value = {
            "valid": False,
            "errors": ["Point buy exceeds 27 points"]
        }
        mock_rules.return_value = mock_loader

        builder = CharacterBuilder()
        build = builder.create_new_build()
        scores = {
            "strength": 15, "dexterity": 15, "constitution": 15,
            "intelligence": 15, "wisdom": 15, "charisma": 15
        }
        result = builder.set_ability_scores(build, scores, "point_buy")

        assert result.valid is False

    @patch('app.core.character_builder.get_rules_loader')
    def test_set_standard_array_valid(self, mock_rules):
        """Valid standard array should succeed."""
        mock_loader = MagicMock()
        mock_loader.get_standard_array.return_value = [15, 14, 13, 12, 10, 8]
        mock_rules.return_value = mock_loader

        builder = CharacterBuilder()
        build = builder.create_new_build()
        scores = {
            "strength": 15, "dexterity": 14, "constitution": 13,
            "intelligence": 12, "wisdom": 10, "charisma": 8
        }
        result = builder.set_ability_scores(build, scores, "standard_array")

        assert result.valid is True
        assert build.ability_method == "standard_array"

    @patch('app.core.character_builder.get_rules_loader')
    def test_set_standard_array_invalid(self, mock_rules):
        """Invalid standard array should fail."""
        mock_loader = MagicMock()
        mock_loader.get_standard_array.return_value = [15, 14, 13, 12, 10, 8]
        mock_rules.return_value = mock_loader

        builder = CharacterBuilder()
        build = builder.create_new_build()
        scores = {
            "strength": 18, "dexterity": 14, "constitution": 13,
            "intelligence": 12, "wisdom": 10, "charisma": 8
        }
        result = builder.set_ability_scores(build, scores, "standard_array")

        assert result.valid is False

    @patch('app.core.character_builder.get_rules_loader')
    def test_set_ability_scores_missing_ability(self, mock_rules):
        """Missing ability should fail."""
        mock_rules.return_value = MagicMock()
        builder = CharacterBuilder()
        build = builder.create_new_build()
        scores = {"strength": 15, "dexterity": 14}  # Missing others

        result = builder.set_ability_scores(build, scores, "point_buy")

        assert result.valid is False
        assert "Missing" in result.errors[0]


class TestAbilityBonuses:
    """Tests for ability bonus assignment."""

    @patch('app.core.character_builder.get_rules_loader')
    def test_set_bonuses_two_plus_one(self, mock_rules):
        """Setting +2/+1 pattern should succeed."""
        mock_loader = MagicMock()
        mock_loader.get_background.return_value = {
            "ability_score_increases": {"options": ["strength", "constitution"]}
        }
        mock_rules.return_value = mock_loader

        builder = CharacterBuilder()
        build = CharacterBuild(background_id="soldier")

        result = builder.set_ability_bonuses(build, {"strength": 2, "constitution": 1})

        assert result.valid is True
        assert build.ability_bonuses == {"strength": 2, "constitution": 1}

    @patch('app.core.character_builder.get_rules_loader')
    def test_set_bonuses_three_plus_one(self, mock_rules):
        """Setting +1/+1/+1 pattern should succeed."""
        mock_loader = MagicMock()
        mock_loader.get_background.return_value = {
            "ability_score_increases": {"options": ["any"]}
        }
        mock_rules.return_value = mock_loader

        builder = CharacterBuilder()
        build = CharacterBuild(background_id="soldier")

        result = builder.set_ability_bonuses(
            build,
            {"strength": 1, "dexterity": 1, "constitution": 1}
        )

        assert result.valid is True

    @patch('app.core.character_builder.get_rules_loader')
    def test_set_bonuses_invalid_pattern(self, mock_rules):
        """Invalid bonus pattern should fail."""
        mock_loader = MagicMock()
        mock_loader.get_background.return_value = {
            "ability_score_increases": {"options": ["any"]}
        }
        mock_rules.return_value = mock_loader

        builder = CharacterBuilder()
        build = CharacterBuild(background_id="soldier")

        result = builder.set_ability_bonuses(build, {"strength": 3})

        assert result.valid is False
        assert "Invalid ability bonus pattern" in result.errors[0]

    @patch('app.core.character_builder.get_rules_loader')
    def test_set_bonuses_invalid_ability(self, mock_rules):
        """Invalid ability name should fail."""
        mock_loader = MagicMock()
        mock_loader.get_background.return_value = {
            "ability_score_increases": {"options": ["any"]}
        }
        mock_rules.return_value = mock_loader

        builder = CharacterBuilder()
        build = CharacterBuild(background_id="soldier")

        result = builder.set_ability_bonuses(build, {"power": 2, "speed": 1})

        assert result.valid is False
        assert "Invalid ability" in result.errors[0]

    @patch('app.core.character_builder.get_rules_loader')
    def test_set_bonuses_no_background(self, mock_rules):
        """Setting bonuses without background should fail."""
        mock_rules.return_value = MagicMock()
        builder = CharacterBuilder()
        build = CharacterBuild()

        result = builder.set_ability_bonuses(build, {"strength": 2, "dexterity": 1})

        assert result.valid is False
        assert "background first" in result.errors[0]


class TestOriginFeat:
    """Tests for origin feat selection."""

    @patch('app.core.character_builder.get_rules_loader')
    def test_set_valid_origin_feat(self, mock_rules):
        """Setting a valid origin feat should succeed."""
        mock_loader = MagicMock()
        mock_loader.get_feat.return_value = {
            "id": "alert",
            "name": "Alert",
            "category": "origin",
            "description": "+2 to initiative"
        }
        mock_rules.return_value = mock_loader

        builder = CharacterBuilder()
        build = builder.create_new_build()
        result = builder.set_origin_feat(build, "alert")

        assert result.valid is True
        assert build.origin_feat_id == "alert"

    @patch('app.core.character_builder.get_rules_loader')
    def test_set_non_origin_feat_fails(self, mock_rules):
        """Setting a non-origin feat should fail."""
        mock_loader = MagicMock()
        mock_loader.get_feat.return_value = {
            "id": "great_weapon_master",
            "name": "Great Weapon Master",
            "category": "general"
        }
        mock_rules.return_value = mock_loader

        builder = CharacterBuilder()
        build = builder.create_new_build()
        result = builder.set_origin_feat(build, "great_weapon_master")

        assert result.valid is False
        assert "not an Origin feat" in result.errors[0]

    @patch('app.core.character_builder.get_rules_loader')
    def test_set_invalid_feat(self, mock_rules):
        """Setting an invalid feat should fail."""
        mock_loader = MagicMock()
        mock_loader.get_feat.return_value = None
        mock_rules.return_value = mock_loader

        builder = CharacterBuilder()
        build = builder.create_new_build()
        result = builder.set_origin_feat(build, "unknown_feat")

        assert result.valid is False
        assert "Unknown feat" in result.errors[0]


class TestEquipment:
    """Tests for equipment selection."""

    @patch('app.core.character_builder.get_rules_loader')
    def test_set_equipment_choices(self, mock_rules):
        """Setting equipment choices should succeed."""
        mock_rules.return_value = MagicMock()
        builder = CharacterBuilder()
        build = CharacterBuild(class_id="fighter")

        choices = [{"weapon": "longsword"}, {"armor": "chain_mail"}]
        result = builder.set_equipment_choices(build, choices)

        assert result.valid is True
        assert build.equipment_choices == choices

    @patch('app.core.character_builder.get_rules_loader')
    def test_set_equipment_no_class(self, mock_rules):
        """Setting equipment without class should fail."""
        mock_rules.return_value = MagicMock()
        builder = CharacterBuilder()
        build = CharacterBuild()

        result = builder.set_equipment_choices(build, [{"weapon": "dagger"}])

        assert result.valid is False
        assert "class first" in result.errors[0]


class TestCharacterDetails:
    """Tests for character details."""

    @patch('app.core.character_builder.get_rules_loader')
    def test_set_valid_details(self, mock_rules):
        """Setting valid details should succeed."""
        mock_rules.return_value = MagicMock()
        builder = CharacterBuilder()
        build = builder.create_new_build()

        result = builder.set_details(
            build,
            name="Test Hero",
            appearance="Tall and strong",
            personality="Brave but reckless",
            backstory="Born in a small village"
        )

        assert result.valid is True
        assert build.name == "Test Hero"
        assert build.appearance == "Tall and strong"

    @patch('app.core.character_builder.get_rules_loader')
    def test_set_empty_name_fails(self, mock_rules):
        """Setting empty name should fail."""
        mock_rules.return_value = MagicMock()
        builder = CharacterBuilder()
        build = builder.create_new_build()

        result = builder.set_details(build, name="")

        assert result.valid is False
        assert "required" in result.errors[0]

    @patch('app.core.character_builder.get_rules_loader')
    def test_set_whitespace_name_fails(self, mock_rules):
        """Setting whitespace-only name should fail."""
        mock_rules.return_value = MagicMock()
        builder = CharacterBuilder()
        build = builder.create_new_build()

        result = builder.set_details(build, name="   ")

        assert result.valid is False

    @patch('app.core.character_builder.get_rules_loader')
    def test_name_is_trimmed(self, mock_rules):
        """Name should be trimmed."""
        mock_rules.return_value = MagicMock()
        builder = CharacterBuilder()
        build = builder.create_new_build()

        result = builder.set_details(build, name="  Test Hero  ")

        assert result.valid is True
        assert build.name == "Test Hero"


class TestLevelManagement:
    """Tests for level setting."""

    @patch('app.core.character_builder.get_rules_loader')
    def test_set_valid_level(self, mock_rules):
        """Setting valid level should succeed."""
        mock_rules.return_value = MagicMock()
        builder = CharacterBuilder()
        build = builder.create_new_build()

        result = builder.set_level(build, 5)

        assert result.valid is True
        assert build.level == 5

    @patch('app.core.character_builder.get_rules_loader')
    def test_set_level_below_1(self, mock_rules):
        """Setting level below 1 should fail."""
        mock_rules.return_value = MagicMock()
        builder = CharacterBuilder()
        build = builder.create_new_build()

        result = builder.set_level(build, 0)

        assert result.valid is False
        assert "between 1 and 20" in result.errors[0]

    @patch('app.core.character_builder.get_rules_loader')
    def test_set_level_above_20(self, mock_rules):
        """Setting level above 20 should fail."""
        mock_rules.return_value = MagicMock()
        builder = CharacterBuilder()
        build = builder.create_new_build()

        result = builder.set_level(build, 21)

        assert result.valid is False
        assert "between 1 and 20" in result.errors[0]


class TestBuildValidation:
    """Tests for build validation."""

    @patch('app.core.character_builder.get_rules_loader')
    def test_validate_complete_build(self, mock_rules):
        """Complete build should validate."""
        mock_loader = MagicMock()
        mock_loader.get_species.return_value = {"size": "Medium"}
        mock_loader.get_class.return_value = {"skill_choices": {"count": 0}}
        mock_rules.return_value = mock_loader

        builder = CharacterBuilder()
        build = CharacterBuild(
            species_id="human",
            class_id="fighter",
            background_id="soldier",
            ability_bonuses={"strength": 2, "constitution": 1},
            origin_feat_id="alert",
            name="Test Hero"
        )

        result = builder.validate_build(build)

        assert result.valid is True

    @patch('app.core.character_builder.get_rules_loader')
    def test_validate_missing_species(self, mock_rules):
        """Build without species should fail."""
        mock_rules.return_value = MagicMock()
        builder = CharacterBuilder()
        build = CharacterBuild()

        result = builder.validate_build(build)

        assert result.valid is False
        assert any("Species" in e for e in result.errors)

    @patch('app.core.character_builder.get_rules_loader')
    def test_validate_missing_class(self, mock_rules):
        """Build without class should fail."""
        mock_rules.return_value = MagicMock()
        builder = CharacterBuilder()
        build = CharacterBuild(species_id="human")

        result = builder.validate_build(build)

        assert result.valid is False
        assert any("Class" in e for e in result.errors)

    @patch('app.core.character_builder.get_rules_loader')
    def test_validate_missing_name(self, mock_rules):
        """Build without name should fail."""
        mock_loader = MagicMock()
        mock_loader.get_species.return_value = {"size": "Medium"}
        mock_loader.get_class.return_value = {"skill_choices": {"count": 0}}
        mock_rules.return_value = mock_loader

        builder = CharacterBuilder()
        build = CharacterBuild(
            species_id="human",
            class_id="fighter",
            background_id="soldier",
            ability_bonuses={"strength": 2, "constitution": 1},
            origin_feat_id="alert"
        )

        result = builder.validate_build(build)

        assert result.valid is False
        assert any("name" in e.lower() for e in result.errors)


class TestCharacterFinalization:
    """Tests for character finalization."""

    @patch('app.core.character_builder.get_rules_loader')
    def test_finalize_valid_build(self, mock_rules):
        """Finalizing valid build should succeed."""
        mock_loader = MagicMock()
        mock_loader.get_species.return_value = {
            "name": "Human",
            "size": "Medium",
            "speed": 30,
            "traits": [],
            "languages": ["Common"]
        }
        mock_loader.get_class.return_value = {
            "name": "Fighter",
            "hit_die": "d10",
            "skill_choices": {"count": 0},
            "saving_throw_proficiencies": ["strength", "constitution"],
            "armor_proficiencies": ["all armor"],
            "weapon_proficiencies": ["simple", "martial"]
        }
        mock_loader.get_background.return_value = {
            "name": "Soldier",
            "skill_proficiencies": ["athletics"],
            "starting_equipment": {"gold": 10}
        }
        mock_loader.get_feat.return_value = {
            "name": "Alert",
            "description": "+2 to initiative"
        }
        mock_loader.get_class_features_at_level.return_value = []
        mock_loader.get_proficiency_bonus.return_value = 2
        mock_rules.return_value = mock_loader

        builder = CharacterBuilder()
        build = CharacterBuild(
            species_id="human",
            class_id="fighter",
            background_id="soldier",
            ability_scores={
                "strength": 16, "dexterity": 14, "constitution": 14,
                "intelligence": 10, "wisdom": 12, "charisma": 8
            },
            ability_bonuses={"strength": 2, "constitution": 1},
            origin_feat_id="alert",
            name="Test Hero"
        )
        builder._builds[build.id] = build

        success, character = builder.finalize_character(build)

        assert success is True
        assert character["name"] == "Test Hero"
        assert character["species"] == "Human"
        assert character["class"] == "Fighter"
        assert character["hit_die"] == "d10"

    @patch('app.core.character_builder.get_rules_loader')
    def test_finalize_calculates_hp(self, mock_rules):
        """HP should be calculated correctly."""
        mock_loader = MagicMock()
        mock_loader.get_species.return_value = {"size": "Medium", "speed": 30, "traits": [], "languages": []}
        mock_loader.get_class.return_value = {
            "hit_die": "d10",
            "skill_choices": {"count": 0},
            "saving_throw_proficiencies": [],
            "armor_proficiencies": [],
            "weapon_proficiencies": []
        }
        mock_loader.get_background.return_value = {"skill_proficiencies": [], "starting_equipment": {}}
        mock_loader.get_feat.return_value = {"name": "Alert", "description": ""}
        mock_loader.get_class_features_at_level.return_value = []
        mock_loader.get_proficiency_bonus.return_value = 2
        mock_rules.return_value = mock_loader

        builder = CharacterBuilder()
        build = CharacterBuild(
            species_id="human",
            class_id="fighter",
            background_id="soldier",
            ability_scores={
                "strength": 10, "dexterity": 10, "constitution": 16,  # +3 CON
                "intelligence": 10, "wisdom": 10, "charisma": 10
            },
            ability_bonuses={"strength": 2, "constitution": 1},
            origin_feat_id="alert",
            name="Test"
        )
        builder._builds[build.id] = build

        success, character = builder.finalize_character(build)

        assert success is True
        # HP = d10 max (10) + CON mod (16+1=17 -> +3) = 13
        assert character["hit_points"] == 13

    @patch('app.core.character_builder.get_rules_loader')
    def test_finalize_invalid_build(self, mock_rules):
        """Finalizing invalid build should fail."""
        mock_rules.return_value = MagicMock()
        builder = CharacterBuilder()
        build = CharacterBuild()  # Empty build

        success, result = builder.finalize_character(build)

        assert success is False
        assert "errors" in result


class TestSpellcasting:
    """Tests for spellcasting finalization."""

    @patch('app.core.character_builder.get_rules_loader')
    def test_wizard_gets_spellcasting(self, mock_rules):
        """Wizard should have spellcasting data."""
        mock_loader = MagicMock()
        mock_loader.get_species.return_value = {"size": "Medium", "speed": 30, "traits": [], "languages": []}
        mock_loader.get_class.return_value = {
            "hit_die": "d6",
            "skill_choices": {"count": 0},
            "saving_throw_proficiencies": [],
            "armor_proficiencies": [],
            "weapon_proficiencies": []
        }
        mock_loader.get_background.return_value = {"skill_proficiencies": [], "starting_equipment": {}}
        mock_loader.get_feat.return_value = {"name": "Alert", "description": ""}
        mock_loader.get_class_features_at_level.return_value = []
        mock_loader.get_proficiency_bonus.return_value = 2
        mock_rules.return_value = mock_loader

        builder = CharacterBuilder()
        build = CharacterBuild(
            species_id="human",
            class_id="wizard",
            background_id="sage",
            ability_scores={
                "strength": 8, "dexterity": 14, "constitution": 12,
                "intelligence": 14, "wisdom": 10, "charisma": 10
            },
            ability_bonuses={"intelligence": 2, "dexterity": 1},
            origin_feat_id="alert",
            name="Test Wizard"
        )
        builder._builds[build.id] = build

        success, character = builder.finalize_character(build)

        assert success is True
        assert character["spellcasting"] is not None
        assert character["spellcasting"]["ability"] == "intelligence"
        # DC = 8 + prof (2) + INT mod (14+2=16 -> +3) = 13
        assert character["spellcasting"]["spell_save_dc"] == 13

    @patch('app.core.character_builder.get_rules_loader')
    def test_fighter_no_spellcasting(self, mock_rules):
        """Fighter should not have spellcasting."""
        mock_loader = MagicMock()
        mock_loader.get_species.return_value = {"size": "Medium", "speed": 30, "traits": [], "languages": []}
        mock_loader.get_class.return_value = {
            "hit_die": "d10",
            "skill_choices": {"count": 0},
            "saving_throw_proficiencies": [],
            "armor_proficiencies": [],
            "weapon_proficiencies": []
        }
        mock_loader.get_background.return_value = {"skill_proficiencies": [], "starting_equipment": {}}
        mock_loader.get_feat.return_value = {"name": "Alert", "description": ""}
        mock_loader.get_class_features_at_level.return_value = []
        mock_loader.get_proficiency_bonus.return_value = 2
        mock_rules.return_value = mock_loader

        builder = CharacterBuilder()
        build = CharacterBuild(
            species_id="human",
            class_id="fighter",
            background_id="soldier",
            ability_scores={
                "strength": 14, "dexterity": 14, "constitution": 13,
                "intelligence": 10, "wisdom": 10, "charisma": 10
            },
            ability_bonuses={"strength": 2, "constitution": 1},
            origin_feat_id="alert",
            name="Test Fighter"
        )
        builder._builds[build.id] = build

        success, character = builder.finalize_character(build)

        assert success is True
        assert character["spellcasting"] is None


class TestGetCharacterBuilder:
    """Tests for the convenience function."""

    @patch('app.core.character_builder.get_rules_loader')
    def test_returns_builder_instance(self, mock_rules):
        """get_character_builder should return a CharacterBuilder."""
        mock_rules.return_value = MagicMock()
        builder = get_character_builder()
        assert isinstance(builder, CharacterBuilder)
