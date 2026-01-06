"""Tests for the rules configuration system."""
import pytest
from pathlib import Path
import tempfile

from app.core.rules_config import (
    RulesConfig,
    BaseRuleset,
    get_rules_config,
    set_rules_config,
    reset_rules_config,
    is_weapon_mastery_enabled,
    is_2024_class_features_enabled,
    is_cantrip_scaling_enabled,
    is_flanking_enabled,
    apply_preset,
    get_rules_summary,
    RulesContext,
    PRESET_CONFIGS,
)


class TestRulesConfig:
    """Test the RulesConfig dataclass."""

    def setup_method(self):
        """Reset config before each test."""
        reset_rules_config()

    def test_default_config(self):
        """Default config should be 2014 base with 2024 enhancements."""
        config = RulesConfig()

        assert config.base_ruleset == BaseRuleset.RULES_2014
        assert config.weapon_mastery_enabled is True
        assert config.updated_class_features_2024 is True
        assert config.updated_spellcasting_2024 is True
        assert config.cantrip_scaling is True
        assert config.flanking_advantage is False

    def test_config_to_dict(self):
        """Config should serialize to dictionary correctly."""
        config = RulesConfig()
        data = config.to_dict()

        assert data["base_ruleset"] == "2014"
        assert data["weapon_mastery_enabled"] is True
        assert data["default_dm_mode"] == "ai"

    def test_config_from_dict(self):
        """Config should deserialize from dictionary correctly."""
        data = {
            "base_ruleset": "2024",
            "weapon_mastery_enabled": False,
            "flanking_advantage": True,
        }
        config = RulesConfig.from_dict(data)

        assert config.base_ruleset == BaseRuleset.RULES_2024
        assert config.weapon_mastery_enabled is False
        assert config.flanking_advantage is True
        # Should have defaults for missing values
        assert config.cantrip_scaling is True

    def test_config_save_and_load(self):
        """Config should save to and load from file correctly."""
        config = RulesConfig(
            weapon_mastery_enabled=False,
            flanking_advantage=True,
        )

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            filepath = Path(f.name)

        try:
            config.save_to_file(filepath)
            loaded_config = RulesConfig.load_from_file(filepath)

            assert loaded_config.weapon_mastery_enabled is False
            assert loaded_config.flanking_advantage is True
            assert loaded_config.base_ruleset == BaseRuleset.RULES_2014
        finally:
            filepath.unlink()


class TestGlobalConfig:
    """Test global configuration functions."""

    def setup_method(self):
        """Reset config before each test."""
        reset_rules_config()

    def test_get_rules_config_returns_default(self):
        """Should return default config when none set."""
        config = get_rules_config()
        assert isinstance(config, RulesConfig)
        assert config.weapon_mastery_enabled is True

    def test_set_rules_config(self):
        """Should update global config."""
        new_config = RulesConfig(weapon_mastery_enabled=False)
        set_rules_config(new_config)

        assert get_rules_config().weapon_mastery_enabled is False

    def test_reset_rules_config(self):
        """Should reset to default config."""
        set_rules_config(RulesConfig(weapon_mastery_enabled=False))
        reset_rules_config()

        assert get_rules_config().weapon_mastery_enabled is True


class TestConvenienceFunctions:
    """Test convenience check functions."""

    def setup_method(self):
        """Reset config before each test."""
        reset_rules_config()

    def test_is_weapon_mastery_enabled(self):
        """Should check weapon mastery setting."""
        assert is_weapon_mastery_enabled() is True

        set_rules_config(RulesConfig(weapon_mastery_enabled=False))
        assert is_weapon_mastery_enabled() is False

    def test_is_2024_class_features_enabled(self):
        """Should check 2024 class features setting."""
        assert is_2024_class_features_enabled() is True

        set_rules_config(RulesConfig(updated_class_features_2024=False))
        assert is_2024_class_features_enabled() is False

    def test_is_cantrip_scaling_enabled(self):
        """Should check cantrip scaling setting."""
        assert is_cantrip_scaling_enabled() is True

    def test_is_flanking_enabled(self):
        """Should check flanking setting (default off)."""
        assert is_flanking_enabled() is False

        set_rules_config(RulesConfig(flanking_advantage=True))
        assert is_flanking_enabled() is True


class TestPresets:
    """Test preset configurations."""

    def setup_method(self):
        """Reset config before each test."""
        reset_rules_config()

    def test_bg3_style_preset(self):
        """BG3 style should be 2014 base with 2024 enhancements."""
        preset = PRESET_CONFIGS["bg3_style"]

        assert preset.base_ruleset == BaseRuleset.RULES_2014
        assert preset.weapon_mastery_enabled is True
        assert preset.updated_class_features_2024 is True
        assert preset.flanking_advantage is False

    def test_classic_2014_preset(self):
        """Classic 2014 should disable 2024 features."""
        preset = PRESET_CONFIGS["classic_2014"]

        assert preset.base_ruleset == BaseRuleset.RULES_2014
        assert preset.weapon_mastery_enabled is False
        assert preset.updated_class_features_2024 is False
        assert preset.cantrip_scaling is True  # This was always in 2014

    def test_full_2024_preset(self):
        """Full 2024 should enable all 2024 features."""
        preset = PRESET_CONFIGS["full_2024"]

        assert preset.base_ruleset == BaseRuleset.RULES_2024
        assert preset.weapon_mastery_enabled is True
        assert preset.updated_class_features_2024 is True
        assert preset.critical_damage_max_first_die is True

    def test_apply_preset(self):
        """Should apply preset to global config."""
        assert apply_preset("classic_2014") is True
        assert is_weapon_mastery_enabled() is False

    def test_apply_invalid_preset(self):
        """Should return False for invalid preset."""
        assert apply_preset("invalid_preset") is False


class TestRulesSummary:
    """Test rules summary generation."""

    def setup_method(self):
        """Reset config before each test."""
        reset_rules_config()

    def test_summary_includes_enabled_features(self):
        """Summary should list enabled 2024 features."""
        summary = get_rules_summary()

        assert summary["base_ruleset"] == "D&D 2014"
        assert "Weapon Mastery" in summary["enabled_2024_features"]
        assert "Updated Class Features" in summary["enabled_2024_features"]
        assert "Cantrip Scaling" in summary["enabled_2024_features"]

    def test_summary_shows_optional_rules(self):
        """Summary should show optional rules when enabled."""
        set_rules_config(RulesConfig(flanking_advantage=True))
        summary = get_rules_summary()

        assert "Flanking Advantage" in summary["optional_rules"]

    def test_summary_shows_character_creation_methods(self):
        """Summary should list available character creation methods."""
        summary = get_rules_summary()

        assert "Point Buy" in summary["character_creation_methods"]
        assert "Standard Array" in summary["character_creation_methods"]
        assert "Rolled Stats" in summary["character_creation_methods"]


class TestRulesContext:
    """Test the RulesContext context manager."""

    def setup_method(self):
        """Reset config before each test."""
        reset_rules_config()

    def test_context_temporarily_changes_config(self):
        """Context should change config temporarily."""
        assert is_weapon_mastery_enabled() is True

        with RulesContext(weapon_mastery_enabled=False):
            assert is_weapon_mastery_enabled() is False

        assert is_weapon_mastery_enabled() is True

    def test_context_restores_on_exception(self):
        """Context should restore config even on exception."""
        assert is_weapon_mastery_enabled() is True

        try:
            with RulesContext(weapon_mastery_enabled=False):
                assert is_weapon_mastery_enabled() is False
                raise ValueError("Test exception")
        except ValueError:
            pass

        assert is_weapon_mastery_enabled() is True

    def test_context_can_change_multiple_settings(self):
        """Context can change multiple settings at once."""
        with RulesContext(
            weapon_mastery_enabled=False,
            flanking_advantage=True,
            cantrip_scaling=False
        ):
            assert is_weapon_mastery_enabled() is False
            assert is_flanking_enabled() is True
            assert is_cantrip_scaling_enabled() is False
