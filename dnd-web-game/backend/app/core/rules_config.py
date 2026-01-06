"""
Rules Configuration System.

Manages toggleable rule variants between 2014 (5e Classic/BG3) and 2024 rules.
This allows players to customize their experience with a hybrid ruleset.

Default configuration uses 2014 base with 2024 enhancements enabled.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional
import json
from pathlib import Path


class BaseRuleset(Enum):
    """The base ruleset to use."""
    RULES_2014 = "2014"  # Classic 5e, what BG3 uses
    RULES_2024 = "2024"  # Updated 2024 rules


@dataclass
class RulesConfig:
    """
    Configuration for D&D rules variants.

    Default is 2014 base (BG3 style) with 2024 enhancements enabled.
    All 2024 features can be individually toggled.
    """
    # Base ruleset
    base_ruleset: BaseRuleset = BaseRuleset.RULES_2014

    # 2024 Enhancement Toggles
    weapon_mastery_enabled: bool = True
    updated_class_features_2024: bool = True
    updated_spellcasting_2024: bool = True
    cantrip_scaling: bool = True
    ritual_casting_expanded: bool = True
    flexible_spell_preparation: bool = True

    # Combat Options
    flanking_advantage: bool = False  # Optional rule - grants advantage when flanking
    critical_damage_max_first_die: bool = False  # 2024 crit rule - max first die + roll rest

    # Character Creation Options
    point_buy_enabled: bool = True
    standard_array_enabled: bool = True
    rolled_stats_enabled: bool = True

    # DM Mode Settings (stored here for convenience)
    default_dm_mode: str = "ai"  # "ai", "human", or "ai_assisted"

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for serialization."""
        return {
            "base_ruleset": self.base_ruleset.value,
            "weapon_mastery_enabled": self.weapon_mastery_enabled,
            "updated_class_features_2024": self.updated_class_features_2024,
            "updated_spellcasting_2024": self.updated_spellcasting_2024,
            "cantrip_scaling": self.cantrip_scaling,
            "ritual_casting_expanded": self.ritual_casting_expanded,
            "flexible_spell_preparation": self.flexible_spell_preparation,
            "flanking_advantage": self.flanking_advantage,
            "critical_damage_max_first_die": self.critical_damage_max_first_die,
            "point_buy_enabled": self.point_buy_enabled,
            "standard_array_enabled": self.standard_array_enabled,
            "rolled_stats_enabled": self.rolled_stats_enabled,
            "default_dm_mode": self.default_dm_mode,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RulesConfig":
        """Create config from dictionary."""
        base_ruleset = BaseRuleset(data.get("base_ruleset", "2014"))
        return cls(
            base_ruleset=base_ruleset,
            weapon_mastery_enabled=data.get("weapon_mastery_enabled", True),
            updated_class_features_2024=data.get("updated_class_features_2024", True),
            updated_spellcasting_2024=data.get("updated_spellcasting_2024", True),
            cantrip_scaling=data.get("cantrip_scaling", True),
            ritual_casting_expanded=data.get("ritual_casting_expanded", True),
            flexible_spell_preparation=data.get("flexible_spell_preparation", True),
            flanking_advantage=data.get("flanking_advantage", False),
            critical_damage_max_first_die=data.get("critical_damage_max_first_die", False),
            point_buy_enabled=data.get("point_buy_enabled", True),
            standard_array_enabled=data.get("standard_array_enabled", True),
            rolled_stats_enabled=data.get("rolled_stats_enabled", True),
            default_dm_mode=data.get("default_dm_mode", "ai"),
        )

    def save_to_file(self, filepath: Path) -> None:
        """Save configuration to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_from_file(cls, filepath: Path) -> "RulesConfig":
        """Load configuration from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)


# Global rules configuration instance
# This can be modified at runtime or loaded from a save file
_current_config: Optional[RulesConfig] = None


def get_rules_config() -> RulesConfig:
    """Get the current rules configuration."""
    global _current_config
    if _current_config is None:
        # Default to full 2024 rules for professional D&D experience
        _current_config = PRESET_CONFIGS["full_2024"]
    return _current_config


def set_rules_config(config: RulesConfig) -> None:
    """Set the current rules configuration."""
    global _current_config
    _current_config = config


def reset_rules_config() -> None:
    """Reset to default rules configuration."""
    global _current_config
    _current_config = RulesConfig()


def is_weapon_mastery_enabled() -> bool:
    """Check if weapon mastery (2024) is enabled."""
    return get_rules_config().weapon_mastery_enabled


def is_2024_class_features_enabled() -> bool:
    """Check if 2024 class features are enabled."""
    return get_rules_config().updated_class_features_2024


def is_2024_spellcasting_enabled() -> bool:
    """Check if 2024 spellcasting rules are enabled."""
    return get_rules_config().updated_spellcasting_2024


def is_cantrip_scaling_enabled() -> bool:
    """Check if cantrip scaling is enabled."""
    return get_rules_config().cantrip_scaling


def is_flanking_enabled() -> bool:
    """Check if flanking advantage is enabled."""
    return get_rules_config().flanking_advantage


def get_base_ruleset() -> BaseRuleset:
    """Get the base ruleset being used."""
    return get_rules_config().base_ruleset


def use_2024_critical_damage() -> bool:
    """Check if 2024 critical damage rules are enabled."""
    return get_rules_config().critical_damage_max_first_die


def is_player_only_crits() -> bool:
    """
    Check if 2024 player-only critical hits rule is enabled.

    In 2024 rules, only PLAYERS deal extra damage on critical hits.
    Monsters still hit on nat 20, but deal normal damage.
    """
    config = get_rules_config()
    return config.base_ruleset == BaseRuleset.RULES_2024


# Preset configurations for quick setup
PRESET_CONFIGS = {
    "bg3_style": RulesConfig(
        base_ruleset=BaseRuleset.RULES_2014,
        weapon_mastery_enabled=True,
        updated_class_features_2024=True,
        updated_spellcasting_2024=True,
        cantrip_scaling=True,
        ritual_casting_expanded=True,
        flexible_spell_preparation=True,
        flanking_advantage=False,
        critical_damage_max_first_die=False,
    ),
    "classic_2014": RulesConfig(
        base_ruleset=BaseRuleset.RULES_2014,
        weapon_mastery_enabled=False,
        updated_class_features_2024=False,
        updated_spellcasting_2024=False,
        cantrip_scaling=True,  # This was always in 2014
        ritual_casting_expanded=False,
        flexible_spell_preparation=False,
        flanking_advantage=False,
        critical_damage_max_first_die=False,
    ),
    "full_2024": RulesConfig(
        base_ruleset=BaseRuleset.RULES_2024,
        weapon_mastery_enabled=True,
        updated_class_features_2024=True,
        updated_spellcasting_2024=True,
        cantrip_scaling=True,
        ritual_casting_expanded=True,
        flexible_spell_preparation=True,
        flanking_advantage=False,
        critical_damage_max_first_die=True,
    ),
}


def apply_preset(preset_name: str) -> bool:
    """
    Apply a preset configuration.

    Args:
        preset_name: One of "bg3_style", "classic_2014", or "full_2024"

    Returns:
        True if preset was applied, False if preset name is invalid
    """
    if preset_name not in PRESET_CONFIGS:
        return False

    set_rules_config(PRESET_CONFIGS[preset_name])
    return True


def get_rules_summary() -> Dict[str, Any]:
    """
    Get a human-readable summary of the current rules configuration.

    Returns:
        Dictionary with readable descriptions of enabled rules
    """
    config = get_rules_config()

    summary = {
        "base_ruleset": f"D&D {config.base_ruleset.value}",
        "enabled_2024_features": [],
        "optional_rules": [],
        "character_creation_methods": [],
    }

    # 2024 Features
    if config.weapon_mastery_enabled:
        summary["enabled_2024_features"].append("Weapon Mastery")
    if config.updated_class_features_2024:
        summary["enabled_2024_features"].append("Updated Class Features")
    if config.updated_spellcasting_2024:
        summary["enabled_2024_features"].append("Updated Spellcasting")
    if config.cantrip_scaling:
        summary["enabled_2024_features"].append("Cantrip Scaling")
    if config.ritual_casting_expanded:
        summary["enabled_2024_features"].append("Expanded Ritual Casting")
    if config.flexible_spell_preparation:
        summary["enabled_2024_features"].append("Flexible Spell Preparation")

    # Optional Rules
    if config.flanking_advantage:
        summary["optional_rules"].append("Flanking Advantage")
    if config.critical_damage_max_first_die:
        summary["optional_rules"].append("2024 Critical Damage (Max First Die)")

    # Character Creation
    if config.point_buy_enabled:
        summary["character_creation_methods"].append("Point Buy")
    if config.standard_array_enabled:
        summary["character_creation_methods"].append("Standard Array")
    if config.rolled_stats_enabled:
        summary["character_creation_methods"].append("Rolled Stats")

    return summary


class RulesContext:
    """
    Context manager for temporarily changing rules configuration.

    Useful for testing or temporary rule changes.

    Example:
        with RulesContext(weapon_mastery_enabled=False):
            # Weapon mastery is disabled here
            pass
        # Original config is restored
    """

    def __init__(self, **kwargs):
        self.overrides = kwargs
        self.original_config = None

    def __enter__(self):
        self.original_config = get_rules_config()

        # Create new config with overrides
        new_config_dict = self.original_config.to_dict()
        new_config_dict.update(self.overrides)

        # Handle base_ruleset specially if it's a string
        if "base_ruleset" in self.overrides and isinstance(self.overrides["base_ruleset"], str):
            new_config_dict["base_ruleset"] = self.overrides["base_ruleset"]

        set_rules_config(RulesConfig.from_dict(new_config_dict))
        return get_rules_config()

    def __exit__(self, exc_type, exc_val, exc_tb):
        set_rules_config(self.original_config)
        return False
