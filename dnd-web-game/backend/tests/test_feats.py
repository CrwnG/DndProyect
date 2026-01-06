"""
Tests for Feat System - General Feats and Epic Boons.
"""
import pytest
from app.core.feats import (
    # Enums and classes
    FeatCategory,
    FeatPrerequisiteType,
    FeatPrerequisite,
    FeatBenefit,
    Feat,
    # Registries
    GENERAL_FEATS,
    EPIC_BOONS,
    ALL_FEATS,
    # Functions
    get_feat,
    get_all_feats,
    get_feats_by_category,
    get_general_feats,
    get_epic_boons,
    check_feat_prerequisites,
    get_available_feats,
    apply_feat_benefits,
    get_feat_choices,
)


class TestFeatRegistry:
    """Tests for feat registry and lookup."""

    def test_general_feats_count(self):
        """Should have 30+ general feats defined."""
        assert len(GENERAL_FEATS) >= 30

    def test_epic_boons_count(self):
        """Should have 8 epic boons defined."""
        assert len(EPIC_BOONS) == 8

    def test_all_feats_combined(self):
        """ALL_FEATS should contain all general feats and epic boons."""
        assert len(ALL_FEATS) == len(GENERAL_FEATS) + len(EPIC_BOONS)

    def test_get_feat_exists(self):
        """get_feat returns feat for valid ID."""
        feat = get_feat("alert")
        assert feat is not None
        assert feat.name == "Alert"

    def test_get_feat_not_exists(self):
        """get_feat returns None for invalid ID."""
        assert get_feat("nonexistent_feat") is None

    def test_get_all_feats(self):
        """get_all_feats returns all feats."""
        feats = get_all_feats()
        assert len(feats) == len(ALL_FEATS)

    def test_get_feats_by_category_general(self):
        """get_feats_by_category filters correctly."""
        general = get_feats_by_category(FeatCategory.GENERAL)
        assert len(general) == len(GENERAL_FEATS)
        for feat in general:
            assert feat.category == FeatCategory.GENERAL

    def test_get_feats_by_category_epic(self):
        """get_feats_by_category returns epic boons."""
        epic = get_feats_by_category(FeatCategory.EPIC_BOON)
        assert len(epic) == len(EPIC_BOONS)
        for feat in epic:
            assert feat.category == FeatCategory.EPIC_BOON

    def test_get_general_feats(self):
        """get_general_feats returns all general feats."""
        feats = get_general_feats()
        assert len(feats) == len(GENERAL_FEATS)

    def test_get_epic_boons(self):
        """get_epic_boons returns all epic boons."""
        boons = get_epic_boons()
        assert len(boons) == len(EPIC_BOONS)


class TestFeatDefinitions:
    """Tests for individual feat definitions."""

    def test_alert_feat(self):
        """Alert feat is defined correctly."""
        alert = get_feat("alert")
        assert alert is not None
        assert "alert_initiative" in alert.benefits.special_abilities
        assert "cannot_be_surprised" in alert.benefits.special_abilities

    def test_tough_feat(self):
        """Tough feat has HP bonus per level."""
        tough = get_feat("tough")
        assert tough is not None
        assert tough.benefits.hp_bonus_per_level == 2

    def test_mobile_feat(self):
        """Mobile feat has speed bonus."""
        mobile = get_feat("mobile")
        assert mobile is not None
        assert mobile.benefits.speed_bonus == 10

    def test_dual_wielder_feat(self):
        """Dual Wielder has AC bonus."""
        dual = get_feat("dual_wielder")
        assert dual is not None
        assert dual.benefits.ac_bonus == 1

    def test_great_weapon_master_feat(self):
        """Great Weapon Master has power attack."""
        gwm = get_feat("great_weapon_master")
        assert gwm is not None
        assert "gwm_power_attack" in gwm.benefits.special_abilities
        assert "gwm_bonus_attack_on_crit_kill" in gwm.benefits.special_abilities

    def test_sharpshooter_feat(self):
        """Sharpshooter ignores cover and long range."""
        sharp = get_feat("sharpshooter")
        assert sharp is not None
        assert "ignore_cover" in sharp.benefits.special_abilities
        assert "sharpshooter_power_attack" in sharp.benefits.special_abilities

    def test_sentinel_feat(self):
        """Sentinel has reaction attack ability."""
        sentinel = get_feat("sentinel")
        assert sentinel is not None
        assert sentinel.benefits.reaction_attack is True
        assert "sentinel_stop_movement" in sentinel.benefits.special_abilities

    def test_war_caster_feat(self):
        """War Caster requires spellcasting."""
        war_caster = get_feat("war_caster")
        assert war_caster is not None
        assert len(war_caster.prerequisites) > 0
        assert any(p.type == FeatPrerequisiteType.SPELLCASTING for p in war_caster.prerequisites)

    def test_skilled_repeatable(self):
        """Skilled feat is repeatable."""
        skilled = get_feat("skilled")
        assert skilled is not None
        assert skilled.repeatable is True

    def test_resilient_has_ability_choice(self):
        """Resilient feat has ability choice."""
        resilient = get_feat("resilient")
        assert resilient is not None
        assert resilient.benefits.ability_choice is not None
        assert len(resilient.benefits.ability_choice) == 6


class TestEpicBoons:
    """Tests for Epic Boon definitions."""

    def test_all_boons_require_level_19(self):
        """All epic boons require level 19+."""
        for boon in EPIC_BOONS.values():
            level_prereqs = [p for p in boon.prerequisites if p.type == FeatPrerequisiteType.LEVEL]
            assert len(level_prereqs) > 0
            assert level_prereqs[0].value >= 19

    def test_all_boons_have_ability_choice(self):
        """All epic boons grant an ability score increase."""
        for boon in EPIC_BOONS.values():
            assert boon.benefits.ability_choice is not None
            assert len(boon.benefits.ability_choice) == 6

    def test_boon_of_speed(self):
        """Boon of Speed grants +30 speed."""
        boon = get_feat("boon_of_speed")
        assert boon is not None
        assert boon.benefits.speed_bonus == 30

    def test_boon_of_spell_recall_requires_spellcasting(self):
        """Boon of Spell Recall requires spellcasting."""
        boon = get_feat("boon_of_spell_recall")
        assert boon is not None
        spell_prereqs = [p for p in boon.prerequisites if p.type == FeatPrerequisiteType.SPELLCASTING]
        assert len(spell_prereqs) > 0

    def test_boon_of_combat_prowess(self):
        """Boon of Combat Prowess has miss-to-hit ability."""
        boon = get_feat("boon_of_combat_prowess")
        assert boon is not None
        assert "epic_miss_becomes_20" in boon.benefits.special_abilities

    def test_boon_of_irresistible_offense(self):
        """Boon of Irresistible Offense ignores resistance."""
        boon = get_feat("boon_of_irresistible_offense")
        assert boon is not None
        assert "epic_ignore_resistance" in boon.benefits.special_abilities


class TestFeatPrerequisites:
    """Tests for prerequisite checking."""

    def test_no_prerequisites_pass(self):
        """Feats with no prerequisites always pass."""
        alert = get_feat("alert")
        meets, unmet = check_feat_prerequisites(
            alert,
            character_level=1,
            ability_scores={"strength": 8, "dexterity": 8, "constitution": 8, "intelligence": 8, "wisdom": 8, "charisma": 8},
            proficiencies=[],
            has_spellcasting=False,
        )
        assert meets is True
        assert len(unmet) == 0

    def test_ability_score_prereq_met(self):
        """Ability score prerequisite passes when met."""
        defensive_duelist = get_feat("defensive_duelist")
        meets, unmet = check_feat_prerequisites(
            defensive_duelist,
            character_level=1,
            ability_scores={"dexterity": 13},
            proficiencies=[],
            has_spellcasting=False,
        )
        assert meets is True

    def test_ability_score_prereq_not_met(self):
        """Ability score prerequisite fails when not met."""
        defensive_duelist = get_feat("defensive_duelist")
        meets, unmet = check_feat_prerequisites(
            defensive_duelist,
            character_level=1,
            ability_scores={"dexterity": 12},
            proficiencies=[],
            has_spellcasting=False,
        )
        assert meets is False
        assert any("Dexterity 13" in u for u in unmet)

    def test_proficiency_prereq_met(self):
        """Proficiency prerequisite passes when met."""
        heavy_armor_master = get_feat("heavy_armor_master")
        meets, unmet = check_feat_prerequisites(
            heavy_armor_master,
            character_level=1,
            ability_scores={},
            proficiencies=["heavy_armor"],
            has_spellcasting=False,
        )
        assert meets is True

    def test_proficiency_prereq_not_met(self):
        """Proficiency prerequisite fails when not met."""
        heavy_armor_master = get_feat("heavy_armor_master")
        meets, unmet = check_feat_prerequisites(
            heavy_armor_master,
            character_level=1,
            ability_scores={},
            proficiencies=[],
            has_spellcasting=False,
        )
        assert meets is False
        assert any("heavy_armor" in u for u in unmet)

    def test_level_prereq_met(self):
        """Level prerequisite passes when met."""
        boon = get_feat("boon_of_speed")
        meets, unmet = check_feat_prerequisites(
            boon,
            character_level=19,
            ability_scores={},
            proficiencies=[],
            has_spellcasting=False,
        )
        assert meets is True

    def test_level_prereq_not_met(self):
        """Level prerequisite fails when not met."""
        boon = get_feat("boon_of_speed")
        meets, unmet = check_feat_prerequisites(
            boon,
            character_level=18,
            ability_scores={},
            proficiencies=[],
            has_spellcasting=False,
        )
        assert meets is False
        assert any("Level 19" in u for u in unmet)

    def test_spellcasting_prereq_met(self):
        """Spellcasting prerequisite passes when met."""
        war_caster = get_feat("war_caster")
        meets, unmet = check_feat_prerequisites(
            war_caster,
            character_level=1,
            ability_scores={},
            proficiencies=[],
            has_spellcasting=True,
        )
        assert meets is True

    def test_spellcasting_prereq_not_met(self):
        """Spellcasting prerequisite fails when not met."""
        war_caster = get_feat("war_caster")
        meets, unmet = check_feat_prerequisites(
            war_caster,
            character_level=1,
            ability_scores={},
            proficiencies=[],
            has_spellcasting=False,
        )
        assert meets is False
        assert any("spell" in u.lower() for u in unmet)


class TestGetAvailableFeats:
    """Tests for getting available feats."""

    def test_level_1_no_spellcasting(self):
        """Level 1 non-caster has limited options."""
        available = get_available_feats(
            character_level=1,
            ability_scores={"strength": 10, "dexterity": 10, "constitution": 10, "intelligence": 10, "wisdom": 10, "charisma": 10},
            proficiencies=[],
            has_spellcasting=False,
            current_feats=[],
        )
        # Should have some but not spellcasting feats
        assert len(available) > 0
        feat_ids = [f.id for f in available]
        assert "alert" in feat_ids
        assert "war_caster" not in feat_ids  # Requires spellcasting

    def test_level_1_with_spellcasting(self):
        """Level 1 caster can take spellcasting feats."""
        available = get_available_feats(
            character_level=1,
            ability_scores={"strength": 10, "dexterity": 10, "constitution": 10, "intelligence": 13, "wisdom": 10, "charisma": 10},
            proficiencies=[],
            has_spellcasting=True,
            current_feats=[],
        )
        feat_ids = [f.id for f in available]
        assert "war_caster" in feat_ids
        assert "ritual_caster" in feat_ids

    def test_level_19_gets_epic_boons(self):
        """Level 19+ characters can take epic boons."""
        available = get_available_feats(
            character_level=19,
            ability_scores={"strength": 10, "dexterity": 10, "constitution": 10, "intelligence": 10, "wisdom": 10, "charisma": 10},
            proficiencies=[],
            has_spellcasting=False,
            current_feats=[],
            include_epic_boons=True,
        )
        feat_ids = [f.id for f in available]
        assert "boon_of_speed" in feat_ids
        assert "boon_of_fortitude" in feat_ids
        # But not spellcasting boon
        assert "boon_of_spell_recall" not in feat_ids

    def test_level_18_no_epic_boons(self):
        """Level 18 characters cannot take epic boons."""
        available = get_available_feats(
            character_level=18,
            ability_scores={"strength": 10, "dexterity": 10, "constitution": 10, "intelligence": 10, "wisdom": 10, "charisma": 10},
            proficiencies=[],
            has_spellcasting=False,
            current_feats=[],
            include_epic_boons=True,
        )
        feat_ids = [f.id for f in available]
        assert "boon_of_speed" not in feat_ids

    def test_already_has_feat_excluded(self):
        """Feats already taken are excluded."""
        available = get_available_feats(
            character_level=4,
            ability_scores={"strength": 10, "dexterity": 10, "constitution": 10, "intelligence": 10, "wisdom": 10, "charisma": 10},
            proficiencies=[],
            has_spellcasting=False,
            current_feats=["alert"],
        )
        feat_ids = [f.id for f in available]
        assert "alert" not in feat_ids

    def test_repeatable_feat_still_available(self):
        """Repeatable feats can be taken again."""
        available = get_available_feats(
            character_level=4,
            ability_scores={"strength": 10, "dexterity": 10, "constitution": 10, "intelligence": 10, "wisdom": 10, "charisma": 10},
            proficiencies=[],
            has_spellcasting=False,
            current_feats=["skilled"],
        )
        feat_ids = [f.id for f in available]
        assert "skilled" in feat_ids


class TestApplyFeatBenefits:
    """Tests for applying feat benefits."""

    def test_apply_ability_increase(self):
        """Applying feat with ability increase works."""
        durable = get_feat("durable")
        char_data = {"ability_scores": {"constitution": 14}}

        result = apply_feat_benefits(durable, char_data)

        assert result["ability_scores"]["constitution"] == 15

    def test_apply_ability_choice(self):
        """Applying feat with ability choice works."""
        athlete = get_feat("athlete")
        char_data = {"ability_scores": {"strength": 14, "dexterity": 12}}

        result = apply_feat_benefits(athlete, char_data, {"ability_choice": "strength"})

        assert result["ability_scores"]["strength"] == 15
        assert result["ability_scores"]["dexterity"] == 12

    def test_apply_speed_bonus(self):
        """Applying feat with speed bonus works."""
        mobile = get_feat("mobile")
        char_data = {}

        result = apply_feat_benefits(mobile, char_data)

        assert result["feat_speed_bonus"] == 10

    def test_apply_hp_per_level(self):
        """Applying Tough feat calculates HP correctly."""
        tough = get_feat("tough")
        char_data = {"level": 10}

        result = apply_feat_benefits(tough, char_data)

        assert result["feat_hp_bonus"] == 20  # 2 * 10 levels

    def test_apply_proficiencies(self):
        """Applying feat grants proficiencies."""
        heavily_armored = get_feat("heavily_armored")
        char_data = {"ability_scores": {"strength": 12}, "proficiencies": ["medium_armor"]}

        result = apply_feat_benefits(heavily_armored, char_data)

        assert "heavy_armor" in result["proficiencies"]
        assert result["ability_scores"]["strength"] == 13

    def test_apply_special_abilities(self):
        """Applying feat adds special abilities."""
        alert = get_feat("alert")
        char_data = {}

        result = apply_feat_benefits(alert, char_data)

        assert "alert_initiative" in result["feat_abilities"]
        assert "cannot_be_surprised" in result["feat_abilities"]

    def test_apply_tracks_feat(self):
        """Applying feat adds feat ID to character."""
        alert = get_feat("alert")
        char_data = {"feats": []}

        result = apply_feat_benefits(alert, char_data)

        assert "alert" in result["feats"]


class TestFeatChoices:
    """Tests for feat choice requirements."""

    def test_feat_with_ability_choice(self):
        """Feats with ability choice return choice info."""
        athlete = get_feat("athlete")
        choices = get_feat_choices(athlete)

        assert "ability_choice" in choices
        assert choices["ability_choice"]["type"] == "select_one"
        assert "strength" in choices["ability_choice"]["options"]
        assert "dexterity" in choices["ability_choice"]["options"]

    def test_feat_with_no_choices(self):
        """Feats with no choices return empty dict."""
        alert = get_feat("alert")
        choices = get_feat_choices(alert)

        assert "ability_choice" not in choices

    def test_resilient_has_save_choice(self):
        """Resilient has saving throw choice linked to ability."""
        resilient = get_feat("resilient")
        choices = get_feat_choices(resilient)

        assert "ability_choice" in choices
        assert "saving_throw" in choices

    def test_skilled_has_proficiency_choices(self):
        """Skilled has proficiency choices."""
        skilled = get_feat("skilled")
        choices = get_feat_choices(skilled)

        assert "proficiency_choices" in choices
        assert choices["proficiency_choices"]["count"] == 3


class TestFeatSerialization:
    """Tests for feat serialization."""

    def test_feat_to_dict(self):
        """Feat serializes to dict correctly."""
        alert = get_feat("alert")
        data = alert.to_dict()

        assert data["id"] == "alert"
        assert data["name"] == "Alert"
        assert data["category"] == "general"
        assert "benefits" in data

    def test_prereq_to_dict(self):
        """Prerequisite serializes correctly."""
        prereq = FeatPrerequisite(FeatPrerequisiteType.ABILITY_SCORE, 13, "dexterity")
        data = prereq.to_dict()

        assert data["type"] == "ability_score"
        assert data["value"] == 13
        assert data["ability"] == "dexterity"

    def test_benefit_to_dict(self):
        """FeatBenefit serializes correctly."""
        benefit = FeatBenefit(
            description="Test",
            speed_bonus=10,
            special_abilities=["test_ability"],
        )
        data = benefit.to_dict()

        assert data["speed_bonus"] == 10
        assert "test_ability" in data["special_abilities"]
