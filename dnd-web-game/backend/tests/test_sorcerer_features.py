"""
Tests for Sorcerer Features - Innate Sorcery and Origin Features.
"""
import pytest
from app.core.sorcerer_features import (
    # Innate Sorcery
    InnateSorceryState,
    initialize_innate_sorcery,
    activate_innate_sorcery,
    check_innate_sorcery_expiration,
    deactivate_innate_sorcery,
    restore_innate_sorcery,
    get_innate_sorcery_uses,
    get_innate_sorcery_modifiers,
    # Origins
    SorcerousOrigin,
    ORIGIN_FEATURES,
    get_origin_features_at_level,
    get_new_origin_features_at_level,
    # Core
    SorceryPointState,
    MetamagicType,
    get_max_sorcery_points,
    get_metamagic_known_count,
    get_cantrips_known,
    get_spells_known,
    initialize_sorcery_state,
    restore_sorcery_points,
)


class TestInnateSorceryState:
    """Tests for InnateSorceryState dataclass."""

    def test_default_values(self):
        """Default state has 2 max uses and is inactive."""
        state = InnateSorceryState()
        assert state.max_uses == 2
        assert state.uses_remaining == 2
        assert state.is_active is False
        assert state.active_until_round is None

    def test_to_dict(self):
        """State serializes to dict correctly."""
        state = InnateSorceryState(
            max_uses=3,
            uses_remaining=2,
            is_active=True,
            active_until_round=15,
        )
        data = state.to_dict()
        assert data["max_uses"] == 3
        assert data["uses_remaining"] == 2
        assert data["is_active"] is True
        assert data["active_until_round"] == 15

    def test_from_dict(self):
        """State deserializes from dict correctly."""
        data = {
            "max_uses": 4,
            "uses_remaining": 1,
            "is_active": True,
            "active_until_round": 20,
        }
        state = InnateSorceryState.from_dict(data)
        assert state.max_uses == 4
        assert state.uses_remaining == 1
        assert state.is_active is True
        assert state.active_until_round == 20


class TestInnateSorceryFunctions:
    """Tests for Innate Sorcery functions."""

    def test_get_uses_scales_with_proficiency(self):
        """Uses scale with proficiency bonus."""
        assert get_innate_sorcery_uses(1) == 2  # Prof +2
        assert get_innate_sorcery_uses(4) == 2  # Prof +2
        assert get_innate_sorcery_uses(5) == 3  # Prof +3
        assert get_innate_sorcery_uses(8) == 3  # Prof +3
        assert get_innate_sorcery_uses(9) == 4  # Prof +4
        assert get_innate_sorcery_uses(13) == 5  # Prof +5
        assert get_innate_sorcery_uses(17) == 6  # Prof +6

    def test_initialize_innate_sorcery(self):
        """Initialize creates correct state for level."""
        state = initialize_innate_sorcery(5)
        assert state.max_uses == 3
        assert state.uses_remaining == 3
        assert state.is_active is False

    def test_activate_success(self):
        """Activation uses a charge and sets active."""
        state = initialize_innate_sorcery(5)

        success, msg, data = activate_innate_sorcery(state, current_round=5)

        assert success is True
        assert state.uses_remaining == 2
        assert state.is_active is True
        assert state.active_until_round == 15  # 5 + 10 rounds
        assert "activated" in msg.lower()
        assert data["effects"]["spell_attack_advantage"] is True
        assert data["effects"]["spell_save_dc_bonus"] == 1

    def test_activate_already_active(self):
        """Cannot activate when already active."""
        state = initialize_innate_sorcery(5)
        activate_innate_sorcery(state, current_round=1)

        success, msg, data = activate_innate_sorcery(state, current_round=2)

        assert success is False
        assert "already active" in msg.lower()

    def test_activate_no_uses(self):
        """Cannot activate with no uses remaining."""
        state = initialize_innate_sorcery(1)
        state.uses_remaining = 0

        success, msg, data = activate_innate_sorcery(state, current_round=1)

        assert success is False
        assert "no uses" in msg.lower()

    def test_expiration_check_expires(self):
        """Expiration check correctly ends effect."""
        state = initialize_innate_sorcery(5)
        activate_innate_sorcery(state, current_round=1)
        # Should expire at round 11 (1 + 10)

        expired = check_innate_sorcery_expiration(state, current_round=10)
        assert expired is False
        assert state.is_active is True

        expired = check_innate_sorcery_expiration(state, current_round=11)
        assert expired is True
        assert state.is_active is False
        assert state.active_until_round is None

    def test_expiration_check_inactive(self):
        """Expiration check on inactive returns False."""
        state = initialize_innate_sorcery(5)

        expired = check_innate_sorcery_expiration(state, current_round=100)
        assert expired is False

    def test_deactivate(self):
        """Manual deactivation works."""
        state = initialize_innate_sorcery(5)
        activate_innate_sorcery(state, current_round=1)

        deactivated = deactivate_innate_sorcery(state)

        assert deactivated is True
        assert state.is_active is False
        assert state.active_until_round is None

    def test_deactivate_when_inactive(self):
        """Deactivating inactive state returns False."""
        state = initialize_innate_sorcery(5)

        deactivated = deactivate_innate_sorcery(state)

        assert deactivated is False

    def test_restore_on_long_rest(self):
        """Long rest restores all uses."""
        state = initialize_innate_sorcery(5)
        activate_innate_sorcery(state, current_round=1)
        # Expire the first use
        check_innate_sorcery_expiration(state, current_round=12)
        # Activate second time
        activate_innate_sorcery(state, current_round=15)
        state.is_active = False
        # Now at 1 use remaining

        restored = restore_innate_sorcery(state, level=5)

        assert state.uses_remaining == 3
        assert state.is_active is False
        assert restored == 2  # Was at 1, now at 3

    def test_get_modifiers_when_active(self):
        """Modifiers returned when active."""
        state = initialize_innate_sorcery(5)
        activate_innate_sorcery(state, current_round=1)

        mods = get_innate_sorcery_modifiers(state)

        assert mods["spell_attack_advantage"] is True
        assert mods["spell_save_dc_bonus"] == 1

    def test_get_modifiers_when_inactive(self):
        """No modifiers when inactive."""
        state = initialize_innate_sorcery(5)

        mods = get_innate_sorcery_modifiers(state)

        assert mods == {}


class TestSorcerousOrigins:
    """Tests for Sorcerous Origin features."""

    def test_all_origins_defined(self):
        """All 7 origins have features defined."""
        expected_origins = {
            SorcerousOrigin.DRACONIC,
            SorcerousOrigin.WILD_MAGIC,
            SorcerousOrigin.DIVINE_SOUL,
            SorcerousOrigin.SHADOW,
            SorcerousOrigin.STORM,
            SorcerousOrigin.ABERRANT,
            SorcerousOrigin.CLOCKWORK,
        }
        assert set(ORIGIN_FEATURES.keys()) == expected_origins

    def test_each_origin_has_level_1_feature(self):
        """Each origin has at least one level 1 feature."""
        for origin in SorcerousOrigin:
            features = get_origin_features_at_level(origin, 1)
            assert len(features) >= 1, f"{origin} has no level 1 features"

    def test_draconic_features(self):
        """Draconic Bloodline has correct features."""
        features = get_origin_features_at_level(SorcerousOrigin.DRACONIC, 20)
        feature_names = [f.name for f in features]

        assert "Dragon Ancestor" in feature_names
        assert "Draconic Resilience" in feature_names
        assert "Elemental Affinity" in feature_names
        assert "Dragon Wings" in feature_names
        assert "Draconic Presence" in feature_names

    def test_wild_magic_features(self):
        """Wild Magic has correct features."""
        features = get_origin_features_at_level(SorcerousOrigin.WILD_MAGIC, 20)
        feature_names = [f.name for f in features]

        assert "Wild Magic Surge" in feature_names
        assert "Tides of Chaos" in feature_names
        assert "Bend Luck" in feature_names
        assert "Controlled Chaos" in feature_names
        assert "Spell Bombardment" in feature_names

    def test_divine_soul_features(self):
        """Divine Soul has correct features."""
        features = get_origin_features_at_level(SorcerousOrigin.DIVINE_SOUL, 20)
        feature_names = [f.name for f in features]

        assert "Divine Magic" in feature_names
        assert "Favored by the Gods" in feature_names
        assert "Empowered Healing" in feature_names
        assert "Otherworldly Wings" in feature_names
        assert "Unearthly Recovery" in feature_names

    def test_shadow_magic_features(self):
        """Shadow Magic has correct features."""
        features = get_origin_features_at_level(SorcerousOrigin.SHADOW, 20)
        feature_names = [f.name for f in features]

        assert "Eyes of the Dark" in feature_names
        assert "Strength of the Grave" in feature_names
        assert "Hound of Ill Omen" in feature_names
        assert "Shadow Walk" in feature_names
        assert "Umbral Form" in feature_names

    def test_storm_sorcery_features(self):
        """Storm Sorcery has correct features."""
        features = get_origin_features_at_level(SorcerousOrigin.STORM, 20)
        feature_names = [f.name for f in features]

        assert "Wind Speaker" in feature_names
        assert "Tempestuous Magic" in feature_names
        assert "Heart of the Storm" in feature_names
        assert "Storm's Fury" in feature_names
        assert "Wind Soul" in feature_names

    def test_aberrant_mind_features(self):
        """Aberrant Mind has correct features."""
        features = get_origin_features_at_level(SorcerousOrigin.ABERRANT, 20)
        feature_names = [f.name for f in features]

        assert "Psionic Spells" in feature_names
        assert "Telepathic Speech" in feature_names
        assert "Psionic Sorcery" in feature_names
        assert "Psychic Defenses" in feature_names
        assert "Revelation in Flesh" in feature_names
        assert "Warping Implosion" in feature_names

    def test_clockwork_soul_features(self):
        """Clockwork Soul has correct features."""
        features = get_origin_features_at_level(SorcerousOrigin.CLOCKWORK, 20)
        feature_names = [f.name for f in features]

        assert "Clockwork Magic" in feature_names
        assert "Restore Balance" in feature_names
        assert "Bastion of Law" in feature_names
        assert "Trance of Order" in feature_names
        assert "Clockwork Cavalcade" in feature_names

    def test_get_new_features_at_level(self):
        """Get only features gained at specific level."""
        # Level 6 for Draconic should only return Elemental Affinity
        new_features = get_new_origin_features_at_level(SorcerousOrigin.DRACONIC, 6)
        assert len(new_features) == 1
        assert new_features[0].name == "Elemental Affinity"

    def test_features_have_required_fields(self):
        """All features have required fields."""
        for origin, features in ORIGIN_FEATURES.items():
            for feature in features:
                assert feature.id, f"{origin} feature missing id"
                assert feature.name, f"{origin} feature missing name"
                assert feature.level > 0, f"{origin} feature has invalid level"
                assert feature.description, f"{origin} feature missing description"


class TestSorcererProgression:
    """Tests for sorcerer progression functions."""

    def test_sorcery_points_scale_with_level(self):
        """Sorcery points equal level (from level 2)."""
        assert get_max_sorcery_points(1) == 0  # No points at level 1
        assert get_max_sorcery_points(2) == 2
        assert get_max_sorcery_points(5) == 5
        assert get_max_sorcery_points(10) == 10
        assert get_max_sorcery_points(20) == 20

    def test_metamagic_known_count(self):
        """Metamagic known scales correctly."""
        assert get_metamagic_known_count(1) == 0
        assert get_metamagic_known_count(2) == 0
        assert get_metamagic_known_count(3) == 2
        assert get_metamagic_known_count(9) == 2
        assert get_metamagic_known_count(10) == 3
        assert get_metamagic_known_count(16) == 3
        assert get_metamagic_known_count(17) == 4

    def test_cantrips_known(self):
        """Cantrips known scales correctly."""
        assert get_cantrips_known(1) == 4
        assert get_cantrips_known(3) == 4
        assert get_cantrips_known(4) == 5
        assert get_cantrips_known(9) == 5
        assert get_cantrips_known(10) == 6

    def test_spells_known(self):
        """Spells known scales correctly."""
        assert get_spells_known(1) == 2
        assert get_spells_known(5) == 6
        assert get_spells_known(10) == 11
        assert get_spells_known(11) == 12
        assert get_spells_known(17) == 15

    def test_initialize_sorcery_state(self):
        """Initialize sorcery state works correctly."""
        state = initialize_sorcery_state(
            level=5,
            metamagic_choices=[MetamagicType.QUICKENED, MetamagicType.TWINNED]
        )
        assert state.max_points == 5
        assert state.current_points == 5
        assert MetamagicType.QUICKENED in state.metamagic_known
        assert MetamagicType.TWINNED in state.metamagic_known

    def test_restore_sorcery_points_long_rest(self):
        """Long rest restores all sorcery points."""
        state = initialize_sorcery_state(level=10)
        state.current_points = 3

        restored = restore_sorcery_points(state, is_long_rest=True)

        assert state.current_points == 10
        assert restored == 7

    def test_restore_sorcery_points_short_rest(self):
        """Short rest does not restore sorcery points."""
        state = initialize_sorcery_state(level=10)
        state.current_points = 3

        restored = restore_sorcery_points(state, is_long_rest=False)

        assert state.current_points == 3
        assert restored == 0
