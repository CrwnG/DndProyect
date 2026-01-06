"""
Tests for multiclass spellcasting rules.
"""
import pytest
from app.core.class_spellcasting import (
    get_caster_level_contribution,
    get_multiclass_caster_level,
    get_multiclass_spell_slots,
    get_multiclass_pact_magic,
    get_multiclass_spellcasting_summary,
    can_cast_spell_level,
    get_max_learnable_spell_level,
    FULL_CASTER_SLOTS,
)


class TestCasterLevelContribution:
    """Test caster level contributions for different classes."""

    def test_full_caster_contribution(self):
        """Full casters contribute their full level."""
        for class_name in ["wizard", "cleric", "druid", "bard", "sorcerer"]:
            assert get_caster_level_contribution(class_name, 5) == 5
            assert get_caster_level_contribution(class_name, 10) == 10

    def test_half_caster_contribution(self):
        """Half casters contribute half their level."""
        for class_name in ["paladin", "ranger"]:
            assert get_caster_level_contribution(class_name, 4) == 2
            assert get_caster_level_contribution(class_name, 10) == 5

    def test_half_caster_before_spellcasting(self):
        """Half casters contribute 0 before gaining spellcasting."""
        # Paladin and Ranger get spellcasting at level 2
        assert get_caster_level_contribution("paladin", 1) == 0
        assert get_caster_level_contribution("ranger", 1) == 0

    def test_warlock_contributes_zero(self):
        """Warlocks don't contribute to multiclass caster level (Pact Magic is separate)."""
        assert get_caster_level_contribution("warlock", 5) == 0
        assert get_caster_level_contribution("warlock", 20) == 0

    def test_non_caster_contributes_zero(self):
        """Non-casters contribute 0."""
        assert get_caster_level_contribution("fighter", 10) == 0
        assert get_caster_level_contribution("barbarian", 20) == 0
        assert get_caster_level_contribution("rogue", 15) == 0

    def test_eldritch_knight_third_caster(self):
        """Eldritch Knight contributes 1/3 of fighter level (from level 3+)."""
        assert get_caster_level_contribution("fighter", 3, "eldritch_knight") == 1
        assert get_caster_level_contribution("fighter", 6, "eldritch_knight") == 2
        assert get_caster_level_contribution("fighter", 9, "eldritch_knight") == 3
        # Before level 3, contributes 0
        assert get_caster_level_contribution("fighter", 2, "eldritch_knight") == 0

    def test_arcane_trickster_third_caster(self):
        """Arcane Trickster contributes 1/3 of rogue level (from level 3+)."""
        assert get_caster_level_contribution("rogue", 3, "arcane_trickster") == 1
        assert get_caster_level_contribution("rogue", 6, "arcane_trickster") == 2


class TestMulticlassCasterLevel:
    """Test combined caster level calculations."""

    def test_single_full_caster(self):
        """Single full caster uses their class level."""
        assert get_multiclass_caster_level({"wizard": 5}) == 5
        assert get_multiclass_caster_level({"cleric": 10}) == 10

    def test_two_full_casters(self):
        """Two full casters add their levels together."""
        assert get_multiclass_caster_level({"wizard": 5, "cleric": 5}) == 10
        assert get_multiclass_caster_level({"wizard": 3, "bard": 2}) == 5

    def test_full_and_half_caster(self):
        """Full caster + half caster combines correctly."""
        # Wizard 5 + Paladin 4 = 5 + 2 = 7
        assert get_multiclass_caster_level({"wizard": 5, "paladin": 4}) == 7

    def test_half_casters_combined(self):
        """Two half casters combine correctly."""
        # Paladin 4 + Ranger 4 = 2 + 2 = 4
        assert get_multiclass_caster_level({"paladin": 4, "ranger": 4}) == 4

    def test_warlock_excluded(self):
        """Warlock levels don't add to caster level."""
        # Wizard 5 + Warlock 5 = 5 (warlock doesn't count)
        assert get_multiclass_caster_level({"wizard": 5, "warlock": 5}) == 5

    def test_third_caster_subclass(self):
        """Third caster subclass contributes 1/3 level."""
        # Wizard 5 + Fighter(EK) 6 = 5 + 2 = 7
        class_levels = {"wizard": 5, "fighter": 6}
        subclasses = {"fighter": "eldritch_knight"}
        assert get_multiclass_caster_level(class_levels, subclasses) == 7

    def test_non_caster_ignored(self):
        """Non-casters don't affect caster level."""
        # Wizard 5 + Fighter (no subclass) 5 = 5
        assert get_multiclass_caster_level({"wizard": 5, "fighter": 5}) == 5

    def test_rounding_down(self):
        """Caster level rounds down."""
        # Paladin 3 = 1.5 -> 1
        assert get_multiclass_caster_level({"paladin": 3}) == 1
        # Paladin 5 = 2.5 -> 2
        assert get_multiclass_caster_level({"paladin": 5}) == 2


class TestMulticlassSpellSlots:
    """Test multiclass spell slot calculations."""

    def test_single_class_matches_base(self):
        """Single full caster gets same slots as base table."""
        slots = get_multiclass_spell_slots({"wizard": 5})
        assert slots == FULL_CASTER_SLOTS[5]

    def test_combined_caster_level(self):
        """Multiclass uses combined caster level for slots."""
        # Wizard 3 + Cleric 2 = caster level 5
        slots = get_multiclass_spell_slots({"wizard": 3, "cleric": 2})
        assert slots == FULL_CASTER_SLOTS[5]
        # Should have 3rd level slots
        assert 3 in slots

    def test_no_slots_for_non_casters(self):
        """Non-casters get no spell slots."""
        slots = get_multiclass_spell_slots({"fighter": 10, "barbarian": 5})
        assert slots == {}

    def test_warlock_only_no_regular_slots(self):
        """Pure warlock gets no multiclass spell slots."""
        slots = get_multiclass_spell_slots({"warlock": 10})
        assert slots == {}


class TestPactMagic:
    """Test Warlock Pact Magic handling."""

    def test_no_pact_magic_without_warlock(self):
        """No Pact Magic without warlock levels."""
        pact = get_multiclass_pact_magic({"wizard": 10})
        assert pact == {}

    def test_pact_magic_with_warlock(self):
        """Warlock levels grant Pact Magic."""
        pact = get_multiclass_pact_magic({"warlock": 5})
        assert pact["slots"] == 2
        assert pact["slot_level"] == 3

    def test_pact_magic_independent_of_other_classes(self):
        """Pact Magic is independent of other class levels."""
        # Wizard 10 + Warlock 5 - warlock still has level 5 pact magic
        pact = get_multiclass_pact_magic({"wizard": 10, "warlock": 5})
        assert pact["slots"] == 2
        assert pact["slot_level"] == 3


class TestMulticlassSpellcastingSummary:
    """Test the complete multiclass spellcasting summary."""

    def test_single_class_summary(self):
        """Single class summary works correctly."""
        summary = get_multiclass_spellcasting_summary(
            class_levels={"wizard": 5},
            ability_scores={"intelligence": 16}
        )
        assert summary["has_spellcasting"] is True
        assert summary["caster_level"] == 5
        assert summary["is_multiclass"] is False
        assert "wizard" in summary["spellcasting_abilities"]
        assert summary["spellcasting_abilities"]["wizard"] == "intelligence"

    def test_multiclass_summary(self):
        """Multiclass summary combines correctly."""
        summary = get_multiclass_spellcasting_summary(
            class_levels={"wizard": 3, "cleric": 2},
            ability_scores={"intelligence": 16, "wisdom": 14}
        )
        assert summary["has_spellcasting"] is True
        assert summary["caster_level"] == 5
        assert summary["is_multiclass"] is True
        assert "wizard" in summary["spellcasting_abilities"]
        assert "cleric" in summary["spellcasting_abilities"]
        # Wizard uses INT, Cleric uses WIS
        assert summary["spell_save_dcs"]["wizard"] != summary["spell_save_dcs"]["cleric"]

    def test_summary_with_pact_magic(self):
        """Summary includes Pact Magic for warlocks."""
        summary = get_multiclass_spellcasting_summary(
            class_levels={"wizard": 5, "warlock": 3},
            ability_scores={"intelligence": 16, "charisma": 14}
        )
        assert summary["has_pact_magic"] is True
        assert "pact_magic" in summary
        assert summary["pact_magic"]["slots"] == 2
        # Regular spell slots from wizard 5
        assert summary["caster_level"] == 5

    def test_summary_cantrips_by_class(self):
        """Cantrips are tracked per class."""
        summary = get_multiclass_spellcasting_summary(
            class_levels={"wizard": 3, "cleric": 2},
            ability_scores={"intelligence": 16, "wisdom": 14}
        )
        assert "cantrips_by_class" in summary
        # Both classes should have cantrips
        assert summary["total_cantrips"] > 0


class TestCanCastSpellLevel:
    """Test spell level capability checking."""

    def test_can_cast_available_level(self):
        """Can cast when slots are available."""
        assert can_cast_spell_level({"wizard": 5}, 3) is True
        assert can_cast_spell_level({"wizard": 5}, 1) is True

    def test_cannot_cast_too_high_level(self):
        """Cannot cast when no slots of that level."""
        assert can_cast_spell_level({"wizard": 5}, 4) is False
        assert can_cast_spell_level({"wizard": 3}, 3) is False

    def test_can_cast_with_pact_magic(self):
        """Can cast using Pact Magic slots."""
        # Warlock 5 has 3rd level pact slots
        assert can_cast_spell_level({"warlock": 5}, 3) is True
        assert can_cast_spell_level({"warlock": 5}, 1) is True  # Can cast lower too
        assert can_cast_spell_level({"warlock": 5}, 4) is False


class TestMaxLearnableSpellLevel:
    """Test maximum learnable spell level per class."""

    def test_full_caster_learns_by_class_level(self):
        """Full casters learn based on individual class level."""
        assert get_max_learnable_spell_level("wizard", 5) == 3
        assert get_max_learnable_spell_level("wizard", 9) == 5

    def test_half_caster_learns_by_class_level(self):
        """Half casters learn based on individual class level."""
        assert get_max_learnable_spell_level("paladin", 5) == 2
        assert get_max_learnable_spell_level("paladin", 9) == 3

    def test_third_caster_learns_by_subclass(self):
        """Third casters learn limited spell levels."""
        assert get_max_learnable_spell_level("fighter", 3, "eldritch_knight") == 1
        assert get_max_learnable_spell_level("fighter", 7, "eldritch_knight") == 2
        assert get_max_learnable_spell_level("fighter", 13, "eldritch_knight") == 3
        assert get_max_learnable_spell_level("fighter", 19, "eldritch_knight") == 4

    def test_non_caster_learns_nothing(self):
        """Non-casters can't learn spells."""
        assert get_max_learnable_spell_level("fighter", 20) == 0
        assert get_max_learnable_spell_level("barbarian", 20) == 0


class TestMulticlassScenarios:
    """Test realistic multiclass scenarios."""

    def test_fighter_wizard_multiclass(self):
        """Fighter 10 / Wizard 10 multiclass."""
        class_levels = {"fighter": 10, "wizard": 10}
        # Caster level = 10 (wizard only)
        assert get_multiclass_caster_level(class_levels) == 10
        slots = get_multiclass_spell_slots(class_levels)
        # Should have up to 5th level slots
        assert 5 in slots

    def test_eldritch_knight_wizard(self):
        """Eldritch Knight 7 / Wizard 3."""
        class_levels = {"fighter": 7, "wizard": 3}
        subclasses = {"fighter": "eldritch_knight"}
        # Caster level = 2 (EK) + 3 (Wizard) = 5
        assert get_multiclass_caster_level(class_levels, subclasses) == 5
        slots = get_multiclass_spell_slots(class_levels, subclasses)
        assert 3 in slots

    def test_paladin_warlock_multiclass(self):
        """Paladin 6 / Warlock 6."""
        class_levels = {"paladin": 6, "warlock": 6}
        # Caster level = 3 (paladin only, warlock excluded)
        assert get_multiclass_caster_level(class_levels) == 3
        slots = get_multiclass_spell_slots(class_levels)
        # 2nd level slots from paladin
        assert 2 in slots

        # Plus separate Pact Magic
        pact = get_multiclass_pact_magic(class_levels)
        assert pact["slots"] == 2
        assert pact["slot_level"] == 3

    def test_triple_class_casters(self):
        """Wizard 5 / Cleric 5 / Sorcerer 5."""
        class_levels = {"wizard": 5, "cleric": 5, "sorcerer": 5}
        # Caster level = 15
        assert get_multiclass_caster_level(class_levels) == 15
        slots = get_multiclass_spell_slots(class_levels)
        # 8th level slots at caster level 15
        assert 8 in slots
