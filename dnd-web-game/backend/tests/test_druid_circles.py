"""
Tests for Druid Circle Features - Moon, Land, Sea, and Stars.
"""
import pytest
from app.core.wild_shape import (
    # Enums
    DruidCircle,
    LandType,
    StarryFormType,
    # State classes
    CircleLandState,
    CircleSeaState,
    StarryFormState,
    # Circle of the Moon
    get_moon_lunar_form_bonuses,
    get_moon_druid_cr_at_level,
    can_cast_beast_spells,
    is_archdruid,
    get_moon_druid_temp_hp,
    get_moon_druid_form_ac,
    # Circle of the Land
    LAND_CIRCLE_SPELLS,
    initialize_land_circle_state,
    get_land_circle_spells,
    use_natural_recovery,
    restore_natural_recovery,
    get_land_circle_features,
    # Circle of the Sea
    initialize_sea_circle_state,
    activate_wrath_of_sea,
    deactivate_wrath_of_sea,
    get_wrath_of_sea_damage,
    restore_wrath_of_sea,
    get_sea_circle_features,
    # Circle of the Stars
    initialize_starry_form_state,
    activate_starry_form,
    get_starry_form_effects,
    change_starry_constellation,
    check_starry_form_expiration,
    deactivate_starry_form,
    restore_starry_form,
    get_stars_circle_features,
    # Utility
    get_druid_circle_features,
    get_circle_always_prepared_spells,
)


class TestCircleOfTheMoon:
    """Tests for Circle of the Moon features."""

    def test_cr_at_level_2(self):
        """Level 2 Moon Druids can transform into CR 1 beasts."""
        assert get_moon_druid_cr_at_level(2) == 1

    def test_cr_at_level_6(self):
        """Level 6 Moon Druids use level / 3 for CR."""
        assert get_moon_druid_cr_at_level(6) == 2

    def test_cr_at_level_9(self):
        """Level 9 Moon Druids can reach CR 3."""
        assert get_moon_druid_cr_at_level(9) == 3

    def test_cr_at_level_18(self):
        """Level 18 Moon Druids reach CR 6."""
        assert get_moon_druid_cr_at_level(18) == 6

    def test_temp_hp_on_transform(self):
        """Moon Druids gain 3 × level temp HP."""
        assert get_moon_druid_temp_hp(2) == 6
        assert get_moon_druid_temp_hp(5) == 15
        assert get_moon_druid_temp_hp(10) == 30
        assert get_moon_druid_temp_hp(20) == 60

    def test_form_ac_override(self):
        """Moon Druids can use 13 + WIS for AC."""
        assert get_moon_druid_form_ac(0) == 13
        assert get_moon_druid_form_ac(3) == 16
        assert get_moon_druid_form_ac(5) == 18

    def test_lunar_form_bonuses_level_2(self):
        """Level 2 Moon Druids get basic bonuses."""
        bonuses = get_moon_lunar_form_bonuses(2)
        assert bonuses["temp_hp_on_transform"] == 6
        assert bonuses["bonus_action_transform"] is True
        assert "moonlight_step" not in bonuses

    def test_lunar_form_bonuses_level_10(self):
        """Level 10 Moon Druids gain Moonlight Step."""
        bonuses = get_moon_lunar_form_bonuses(10)
        assert bonuses["moonlight_step"] is True
        assert bonuses["moonlight_step_distance"] == 30

    def test_lunar_form_bonuses_level_14(self):
        """Level 14 Moon Druids gain Lunar Form resistance."""
        bonuses = get_moon_lunar_form_bonuses(14)
        assert "bludgeoning" in bonuses["lunar_form_resistance"]
        assert bonuses["lunar_radiance_damage"] == "2d10"

    def test_beast_spells(self):
        """Beast Spells unlocks at level 18."""
        assert can_cast_beast_spells(17) is False
        assert can_cast_beast_spells(18) is True

    def test_archdruid(self):
        """Archdruid unlocks at level 20."""
        assert is_archdruid(19) is False
        assert is_archdruid(20) is True


class TestCircleOfTheLand:
    """Tests for Circle of the Land features."""

    def test_all_land_types_have_spells(self):
        """Each land type has circle spells defined."""
        for land_type in LandType:
            assert land_type in LAND_CIRCLE_SPELLS
            assert len(LAND_CIRCLE_SPELLS[land_type]) >= 4

    def test_initialize_state(self):
        """Initialize creates correct state."""
        state = initialize_land_circle_state(LandType.FOREST)
        assert state.land_type == LandType.FOREST
        assert state.natural_recovery_used is False

    def test_state_serialization(self):
        """State serializes and deserializes correctly."""
        state = CircleLandState(land_type=LandType.ARCTIC, natural_recovery_used=True)
        data = state.to_dict()
        restored = CircleLandState.from_dict(data)
        assert restored.land_type == LandType.ARCTIC
        assert restored.natural_recovery_used is True

    def test_get_circle_spells_level_3(self):
        """Level 3 druids get only first set of circle spells."""
        spells = get_land_circle_spells(LandType.FOREST, 3)
        assert "barkskin" in spells
        assert "spider_climb" in spells
        assert "call_lightning" not in spells  # Level 5 spell

    def test_get_circle_spells_level_9(self):
        """Level 9 druids get all circle spells."""
        spells = get_land_circle_spells(LandType.FOREST, 9)
        assert "barkskin" in spells
        assert "spider_climb" in spells
        assert "call_lightning" in spells
        assert "tree_stride" in spells

    def test_natural_recovery_success(self):
        """Natural Recovery works correctly."""
        state = initialize_land_circle_state(LandType.FOREST)

        # Level 6 druid can recover 3 levels worth
        success, msg, levels = use_natural_recovery(state, 6, [(1, 2), (1, 1)])
        assert success is True
        assert levels == 3
        assert state.natural_recovery_used is True

    def test_natural_recovery_too_many_levels(self):
        """Natural Recovery fails if requesting too many levels."""
        state = initialize_land_circle_state(LandType.FOREST)

        # Level 4 druid can only recover 2 levels
        success, msg, levels = use_natural_recovery(state, 4, [(2, 2)])  # 4 levels
        assert success is False
        assert "Cannot recover 4 levels" in msg

    def test_natural_recovery_no_6th_level(self):
        """Cannot recover slots above 5th level."""
        state = initialize_land_circle_state(LandType.FOREST)

        success, msg, levels = use_natural_recovery(state, 20, [(6, 1)])
        assert success is False
        assert "5th level" in msg

    def test_natural_recovery_only_once(self):
        """Natural Recovery can only be used once per long rest."""
        state = initialize_land_circle_state(LandType.FOREST)

        use_natural_recovery(state, 6, [(1, 1)])
        success, msg, levels = use_natural_recovery(state, 6, [(1, 1)])
        assert success is False
        assert "already used" in msg.lower()

    def test_restore_natural_recovery(self):
        """Long rest restores Natural Recovery."""
        state = initialize_land_circle_state(LandType.FOREST)
        use_natural_recovery(state, 6, [(1, 1)])

        restore_natural_recovery(state)
        assert state.natural_recovery_used is False

    def test_land_features_level_2(self):
        """Level 2 Land Druids get basic features."""
        features = get_land_circle_features(2)
        assert features["circle_spells"] is True
        assert features["natural_recovery"] is True
        assert "lands_stride" not in features

    def test_land_features_level_6(self):
        """Level 6 Land Druids gain Land's Stride."""
        features = get_land_circle_features(6)
        assert features["lands_stride"] is True
        assert features["ignore_difficult_terrain"] is True

    def test_land_features_level_10(self):
        """Level 10 Land Druids gain Nature's Ward."""
        features = get_land_circle_features(10)
        assert features["natures_ward"] is True
        assert features["immune_to_poison"] is True
        assert features["immune_to_disease"] is True

    def test_land_features_level_14(self):
        """Level 14 Land Druids gain Nature's Sanctuary."""
        features = get_land_circle_features(14)
        assert features["natures_sanctuary"] is True


class TestCircleOfTheSea:
    """Tests for Circle of the Sea features."""

    def test_initialize_state(self):
        """Initialize creates correct state."""
        state = initialize_sea_circle_state(wisdom_modifier=3)
        assert state.wrath_of_sea_uses == 3
        assert state.max_wrath_uses == 3
        assert state.wrath_of_sea_active is False

    def test_initialize_state_min_1(self):
        """Minimum 1 use even with negative WIS."""
        state = initialize_sea_circle_state(wisdom_modifier=-1)
        assert state.wrath_of_sea_uses == 1

    def test_state_serialization(self):
        """State serializes and deserializes correctly."""
        state = CircleSeaState(wrath_of_sea_active=True, wrath_of_sea_uses=2, max_wrath_uses=3)
        data = state.to_dict()
        restored = CircleSeaState.from_dict(data)
        assert restored.wrath_of_sea_active is True
        assert restored.wrath_of_sea_uses == 2
        assert restored.max_wrath_uses == 3

    def test_activate_wrath_success(self):
        """Wrath of the Sea activates successfully."""
        state = initialize_sea_circle_state(3)

        success, msg, data = activate_wrath_of_sea(state, current_round=1)
        assert success is True
        assert "activated" in msg.lower()
        assert state.wrath_of_sea_active is True
        assert state.wrath_of_sea_uses == 2
        assert data["aura_radius"] == 10
        assert data["damage_type"] == "cold"

    def test_activate_wrath_already_active(self):
        """Cannot activate if already active."""
        state = initialize_sea_circle_state(3)
        activate_wrath_of_sea(state, 1)

        success, msg, data = activate_wrath_of_sea(state, 2)
        assert success is False
        assert "already active" in msg.lower()

    def test_activate_wrath_no_uses(self):
        """Cannot activate with no uses remaining."""
        state = initialize_sea_circle_state(1)
        activate_wrath_of_sea(state, 1)
        state.wrath_of_sea_active = False

        success, msg, data = activate_wrath_of_sea(state, 2)
        assert success is False
        assert "no uses" in msg.lower()

    def test_deactivate_wrath(self):
        """Wrath deactivates correctly."""
        state = initialize_sea_circle_state(3)
        activate_wrath_of_sea(state, 1)

        result = deactivate_wrath_of_sea(state)
        assert result is True
        assert state.wrath_of_sea_active is False

    def test_deactivate_wrath_when_inactive(self):
        """Deactivating inactive returns False."""
        state = initialize_sea_circle_state(3)

        result = deactivate_wrath_of_sea(state)
        assert result is False

    def test_wrath_damage_scaling(self):
        """Wrath damage scales with level."""
        assert get_wrath_of_sea_damage(2) == "1d6"
        assert get_wrath_of_sea_damage(5) == "2d6"
        assert get_wrath_of_sea_damage(11) == "3d6"
        assert get_wrath_of_sea_damage(17) == "4d6"

    def test_restore_wrath(self):
        """Long rest restores uses."""
        state = initialize_sea_circle_state(3)
        activate_wrath_of_sea(state, 1)

        restored = restore_wrath_of_sea(state, 3)
        assert restored == 1
        assert state.wrath_of_sea_uses == 3
        assert state.wrath_of_sea_active is False

    def test_sea_features_level_2(self):
        """Level 2 Sea Druids get basic features."""
        features = get_sea_circle_features(2)
        assert features["wrath_of_the_sea"] is True
        assert features["aquatic_affinity"] is True
        assert features["swim_speed"] is True

    def test_sea_features_level_6(self):
        """Level 6 Sea Druids gain water breathing."""
        features = get_sea_circle_features(6)
        assert features["water_breathing"] is True
        assert features["underwater_spellcasting"] is True

    def test_sea_features_level_10(self):
        """Level 10 Sea Druids gain Stormborn."""
        features = get_sea_circle_features(10)
        assert features["stormborn"] is True
        assert features["fly_speed_outdoor"] == 60
        assert features["resistance_lightning"] is True

    def test_sea_features_level_14(self):
        """Level 14 Sea Druids gain Oceanic Gift."""
        features = get_sea_circle_features(14)
        assert features["oceanic_gift"] is True
        assert features["wrath_of_sea_bonus_action_teleport"] == 30


class TestCircleOfTheStars:
    """Tests for Circle of the Stars features."""

    def test_initialize_state(self):
        """Initialize creates correct state with proficiency bonus uses."""
        state = initialize_starry_form_state(druid_level=5)  # Prof +3
        assert state.uses_remaining == 3
        assert state.max_uses == 3
        assert state.is_active is False
        assert state.free_guiding_bolt_used is False

    def test_state_serialization(self):
        """State serializes and deserializes correctly."""
        state = StarryFormState(
            is_active=True,
            constellation=StarryFormType.ARCHER,
            uses_remaining=2,
            max_uses=3,
            active_until_round=50,
            free_guiding_bolt_used=True,
        )
        data = state.to_dict()
        restored = StarryFormState.from_dict(data)
        assert restored.is_active is True
        assert restored.constellation == StarryFormType.ARCHER
        assert restored.uses_remaining == 2
        assert restored.active_until_round == 50
        assert restored.free_guiding_bolt_used is True

    def test_activate_archer(self):
        """Activating Archer constellation works."""
        state = initialize_starry_form_state(5)

        success, msg, effects = activate_starry_form(
            state, StarryFormType.ARCHER, current_round=1
        )

        assert success is True
        assert state.is_active is True
        assert state.constellation == StarryFormType.ARCHER
        assert state.uses_remaining == 2
        assert effects["bonus_action_attack"] is True
        assert effects["damage"] == "1d8+WIS radiant"

    def test_activate_chalice(self):
        """Activating Chalice constellation works."""
        state = initialize_starry_form_state(5)

        success, msg, effects = activate_starry_form(
            state, StarryFormType.CHALICE, current_round=1
        )

        assert success is True
        assert effects["healing_bonus"] is True
        assert effects["bonus_healing"] == "1d8+WIS"

    def test_activate_dragon(self):
        """Activating Dragon constellation works."""
        state = initialize_starry_form_state(5)

        success, msg, effects = activate_starry_form(
            state, StarryFormType.DRAGON, current_round=1
        )

        assert success is True
        assert effects["concentration_minimum"] == 10

    def test_activate_already_active(self):
        """Cannot activate if already in Starry Form."""
        state = initialize_starry_form_state(5)
        activate_starry_form(state, StarryFormType.ARCHER, 1)

        success, msg, effects = activate_starry_form(
            state, StarryFormType.CHALICE, current_round=2
        )
        assert success is False
        assert "already active" in msg.lower()

    def test_activate_no_uses(self):
        """Cannot activate with no uses remaining."""
        state = initialize_starry_form_state(2)  # Prof +2
        activate_starry_form(state, StarryFormType.ARCHER, 1)
        state.is_active = False
        activate_starry_form(state, StarryFormType.CHALICE, 2)
        state.is_active = False

        success, msg, effects = activate_starry_form(
            state, StarryFormType.DRAGON, current_round=3
        )
        assert success is False
        assert "no uses" in msg.lower()

    def test_change_constellation_level_10(self):
        """Level 10+ druids can change constellation."""
        state = initialize_starry_form_state(10)
        activate_starry_form(state, StarryFormType.ARCHER, 1)

        success, msg = change_starry_constellation(
            state, StarryFormType.DRAGON, druid_level=10
        )
        assert success is True
        assert state.constellation == StarryFormType.DRAGON

    def test_change_constellation_below_level_10(self):
        """Below level 10, cannot change constellation."""
        state = initialize_starry_form_state(9)
        activate_starry_form(state, StarryFormType.ARCHER, 1)

        success, msg = change_starry_constellation(
            state, StarryFormType.DRAGON, druid_level=9
        )
        assert success is False
        assert "level 10+" in msg.lower()

    def test_change_constellation_not_active(self):
        """Cannot change constellation if not in Starry Form."""
        state = initialize_starry_form_state(10)

        success, msg = change_starry_constellation(
            state, StarryFormType.DRAGON, druid_level=10
        )
        assert success is False

    def test_expiration_check(self):
        """Starry Form expires correctly."""
        state = initialize_starry_form_state(5)
        activate_starry_form(state, StarryFormType.ARCHER, current_round=1)
        # Active until round 101

        expired = check_starry_form_expiration(state, current_round=50)
        assert expired is False
        assert state.is_active is True

        expired = check_starry_form_expiration(state, current_round=101)
        assert expired is True
        assert state.is_active is False

    def test_deactivate(self):
        """Manual deactivation works."""
        state = initialize_starry_form_state(5)
        activate_starry_form(state, StarryFormType.ARCHER, 1)

        result = deactivate_starry_form(state)
        assert result is True
        assert state.is_active is False
        assert state.constellation is None

    def test_restore_on_long_rest(self):
        """Long rest restores uses and resets guiding bolt."""
        state = initialize_starry_form_state(5)
        activate_starry_form(state, StarryFormType.ARCHER, 1)
        state.is_active = False
        state.free_guiding_bolt_used = True

        restored = restore_starry_form(state, druid_level=5)
        assert restored == 1
        assert state.uses_remaining == 3
        assert state.free_guiding_bolt_used is False

    def test_stars_features_level_2(self):
        """Level 2 Stars Druids get basic features."""
        features = get_stars_circle_features(2)
        assert features["star_map"] is True
        assert features["free_guiding_bolt"] is True
        assert features["starry_form"] is True

    def test_stars_features_level_6(self):
        """Level 6 Stars Druids gain Cosmic Omen."""
        features = get_stars_circle_features(6)
        assert features["cosmic_omen"] is True
        assert features["weal_or_woe_bonus"] == "1d6"

    def test_stars_features_level_10(self):
        """Level 10 Stars Druids gain Twinkling Constellations."""
        features = get_stars_circle_features(10)
        assert features["twinkling_constellations"] is True
        assert features["change_constellation"] is True
        assert features["dragon_fly_speed"] == 20

    def test_stars_features_level_14(self):
        """Level 14 Stars Druids gain Full of Stars."""
        features = get_stars_circle_features(14)
        assert features["full_of_stars"] is True
        assert "bludgeoning" in features["starry_form_resistance"]


class TestCircleUtilityFunctions:
    """Tests for circle utility functions."""

    def test_get_circle_features_moon(self):
        """Get Moon circle features."""
        features = get_druid_circle_features(DruidCircle.MOON, 10)
        assert features["temp_hp_on_transform"] == 30
        assert features["moonlight_step"] is True

    def test_get_circle_features_land(self):
        """Get Land circle features."""
        features = get_druid_circle_features(DruidCircle.LAND, 10)
        assert features["natures_ward"] is True

    def test_get_circle_features_sea(self):
        """Get Sea circle features."""
        features = get_druid_circle_features(DruidCircle.SEA, 10)
        assert features["stormborn"] is True

    def test_get_circle_features_stars(self):
        """Get Stars circle features."""
        features = get_druid_circle_features(DruidCircle.STARS, 10)
        assert features["twinkling_constellations"] is True

    def test_always_prepared_spells_land(self):
        """Land druids get terrain-specific prepared spells."""
        spells = get_circle_always_prepared_spells(
            DruidCircle.LAND, 5, LandType.FOREST
        )
        assert "barkskin" in spells
        assert "call_lightning" in spells

    def test_always_prepared_spells_stars(self):
        """Stars druids get guiding bolt prepared."""
        spells = get_circle_always_prepared_spells(DruidCircle.STARS, 5)
        assert "guiding_bolt" in spells

    def test_always_prepared_spells_moon(self):
        """Moon druids get no always-prepared circle spells."""
        spells = get_circle_always_prepared_spells(DruidCircle.MOON, 5)
        assert len(spells) == 0
