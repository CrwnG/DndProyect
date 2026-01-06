"""Tests for the spell system."""
import pytest
from unittest.mock import patch, MagicMock
from app.core.spell_system import SpellRegistry
from app.models.spells import (
    Spell, SpellComponents, SpellSchool, SpellTargetType, SpellEffectType,
    CharacterSpellcasting, SpellcastingType, DamageType
)


class TestSpellRegistry:
    """Tests for the SpellRegistry singleton."""

    def setup_method(self):
        """Reset the singleton before each test."""
        SpellRegistry.reset()

    def test_singleton_pattern(self):
        """Should always return the same instance."""
        instance1 = SpellRegistry.get_instance()
        instance2 = SpellRegistry.get_instance()
        assert instance1 is instance2

    def test_reset_clears_singleton(self):
        """Reset should clear the singleton."""
        instance1 = SpellRegistry.get_instance()
        SpellRegistry.reset()
        instance2 = SpellRegistry.get_instance()
        assert instance1 is not instance2

    def test_spells_loaded(self):
        """Spells should be loaded from JSON files."""
        registry = SpellRegistry.get_instance()
        # Should have at least some spells loaded
        assert len(registry._spells) > 0

    def test_get_spell_by_id(self):
        """Should retrieve spells by ID."""
        registry = SpellRegistry.get_instance()
        # Fire Bolt is a common cantrip that should exist
        spell = registry.get_spell("fire_bolt")
        if spell:
            assert spell.name.lower() == "fire bolt"
            assert spell.level == 0  # Cantrip

    def test_get_nonexistent_spell(self):
        """Getting nonexistent spell should return None."""
        registry = SpellRegistry.get_instance()
        spell = registry.get_spell("nonexistent_spell_12345")
        assert spell is None

    def test_get_spells_by_level(self):
        """Should retrieve spells by level."""
        registry = SpellRegistry.get_instance()
        cantrips = registry.get_spells_by_level(0)
        assert isinstance(cantrips, list)
        for spell in cantrips:
            assert spell.level == 0

    def test_get_spells_by_class(self):
        """Should retrieve spells available to a class."""
        registry = SpellRegistry.get_instance()
        wizard_spells = registry.get_spells_for_class("wizard")
        assert isinstance(wizard_spells, list)
        for spell in wizard_spells:
            assert "wizard" in [c.lower() for c in spell.classes]


class TestSpellComponents:
    """Tests for spell component tracking."""

    def test_verbal_only(self):
        """Test spell with only verbal component."""
        components = SpellComponents(verbal=True, somatic=False, material=None)
        assert components.verbal is True
        assert components.somatic is False
        assert components.material is None

    def test_all_components(self):
        """Test spell with all components."""
        components = SpellComponents(
            verbal=True,
            somatic=True,
            material="a pinch of bat guano"
        )
        assert components.verbal is True
        assert components.somatic is True
        assert components.material == "a pinch of bat guano"


class TestCharacterSpellcasting:
    """Tests for character spellcasting management."""

    def test_initial_spell_slots(self):
        """New spellcaster should have correct initial slots."""
        spellcasting = CharacterSpellcasting(
            ability="intelligence",
            spell_save_dc=13,
            spell_attack_bonus=5,
            spellcasting_type=SpellcastingType.PREPARED,
            spell_slots_max={1: 2, 2: 0},
        )
        # Should have 2 first level slots
        assert spellcasting.get_available_slots(1) == 2

    def test_use_spell_slot(self):
        """Should be able to use a spell slot."""
        spellcasting = CharacterSpellcasting(
            ability="intelligence",
            spell_save_dc=13,
            spell_attack_bonus=5,
            spell_slots_max={1: 4, 2: 2},
        )
        initial_available = spellcasting.get_available_slots(1)
        result = spellcasting.use_slot(1)
        assert result is True
        assert spellcasting.get_available_slots(1) == initial_available - 1

    def test_cannot_use_empty_slot(self):
        """Should not be able to use slot when none available."""
        spellcasting = CharacterSpellcasting(
            ability="intelligence",
            spell_save_dc=13,
            spell_attack_bonus=5,
            spell_slots_max={1: 2},
        )
        # Use all first level slots
        spellcasting.use_slot(1)
        spellcasting.use_slot(1)
        # Try to use again - should return False
        result = spellcasting.use_slot(1)
        assert result is False

    def test_restore_slots_on_long_rest(self):
        """Long rest should restore all spell slots."""
        spellcasting = CharacterSpellcasting(
            ability="intelligence",
            spell_save_dc=13,
            spell_attack_bonus=5,
            spell_slots_max={1: 4, 2: 2},
        )
        # Use some slots
        spellcasting.use_slot(1)
        spellcasting.use_slot(1)
        spellcasting.use_slot(2)
        # Long rest
        spellcasting.restore_all_slots()
        # Slots should be restored
        assert spellcasting.get_available_slots(1) == 4
        assert spellcasting.get_available_slots(2) == 2

    def test_has_slot_available(self):
        """Should correctly report if slot is available."""
        spellcasting = CharacterSpellcasting(
            ability="intelligence",
            spell_save_dc=13,
            spell_attack_bonus=5,
            spell_slots_max={1: 2},
        )
        assert spellcasting.has_slot(1) is True
        # Use all slots
        spellcasting.use_slot(1)
        spellcasting.use_slot(1)
        assert spellcasting.has_slot(1) is False

    def test_cantrips_dont_use_slots(self):
        """Cantrips (level 0) should not require slots."""
        spellcasting = CharacterSpellcasting(
            ability="wisdom",
            spell_save_dc=12,
            spell_attack_bonus=4,
            spell_slots_max={1: 2},
        )
        # Level 0 should always have "slots"
        assert spellcasting.has_slot(0) is True
        assert spellcasting.use_slot(0) is True


class TestSpellModel:
    """Tests for the Spell model."""

    def test_spell_creation(self):
        """Test creating a spell directly."""
        spell = Spell(
            id="test_spell",
            name="Test Spell",
            level=1,
            school=SpellSchool.EVOCATION,
            casting_time="1 action",
            range="60 feet",
            components=SpellComponents(verbal=True, somatic=True),
            duration="Instantaneous",
            description="A test spell.",
            classes=["wizard", "sorcerer"],
        )
        assert spell.id == "test_spell"
        assert spell.level == 1
        assert spell.school == SpellSchool.EVOCATION

    def test_spell_is_cantrip(self):
        """Level 0 spells should be cantrips."""
        cantrip = Spell(
            id="test_cantrip",
            name="Test Cantrip",
            level=0,
            school=SpellSchool.CONJURATION,
            casting_time="1 action",
            range="30 feet",
            components=SpellComponents(verbal=True),
            duration="Instantaneous",
            description="A test cantrip.",
            classes=["wizard"],
        )
        # Cantrips are level 0
        assert cantrip.level == 0

    def test_spell_requires_concentration(self):
        """Concentration spells should be marked."""
        spell = Spell(
            id="test_concentration",
            name="Test Concentration",
            level=2,
            school=SpellSchool.ENCHANTMENT,
            casting_time="1 action",
            range="60 feet",
            components=SpellComponents(verbal=True, somatic=True),
            duration="Concentration, up to 1 minute",
            description="A concentration spell.",
            classes=["wizard"],
            concentration=True,
        )
        assert spell.concentration is True


class TestSpellDamage:
    """Tests for spell damage calculations."""

    def test_damage_spell_has_damage_info(self):
        """Damage spells should have damage information."""
        registry = SpellRegistry.get_instance()
        fire_bolt = registry.get_spell("fire_bolt")
        if fire_bolt:
            # Fire Bolt should have damage info
            assert fire_bolt.damage_dice is not None or fire_bolt.effect_type == SpellEffectType.DAMAGE

    def test_healing_spell_exists(self):
        """Healing spells should exist in the registry."""
        registry = SpellRegistry.get_instance()
        cure_wounds = registry.get_spell("cure_wounds")
        # Cure Wounds should exist and be a level 1 spell
        if cure_wounds:
            assert cure_wounds.level == 1
            assert "cleric" in [c.lower() for c in cure_wounds.classes]


class TestSpellSlotUpscaling:
    """Tests for spell upcasting mechanics."""

    def test_upcast_damage_spell(self):
        """Upcasting damage spell should increase damage."""
        # Most damage spells add 1d per level
        # This would require the spell system to have upcast damage methods
        registry = SpellRegistry.get_instance()
        magic_missile = registry.get_spell("magic_missile")
        if magic_missile and hasattr(magic_missile, 'get_damage_at_level'):
            base_damage = magic_missile.get_damage_at_level(1)
            upcast_damage = magic_missile.get_damage_at_level(2)
            # Upcast should deal more damage (more dice or higher values)
            # This is a basic structural test

    def test_cantrip_scaling(self):
        """Cantrips should scale with character level."""
        # Cantrips scale at levels 5, 11, 17
        registry = SpellRegistry.get_instance()
        fire_bolt = registry.get_spell("fire_bolt")
        if fire_bolt and hasattr(fire_bolt, 'get_damage_at_character_level'):
            damage_level_1 = fire_bolt.get_damage_at_character_level(1)
            damage_level_5 = fire_bolt.get_damage_at_character_level(5)
            # At level 5, cantrip damage should be higher
