"""
Tests for Metamagic integration with spell casting.
"""
import pytest
from app.core.spell_system import (
    cast_spell_with_metamagic,
    get_available_metamagic_for_spell,
    _validate_metamagic_for_spell,
    SpellRegistry,
)
from app.core.sorcerer_features import (
    MetamagicType,
    SorceryPointState,
    METAMAGIC_OPTIONS,
)


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset spell registry before each test."""
    SpellRegistry.reset()
    yield
    SpellRegistry.reset()


@pytest.fixture
def sorcerer_caster():
    """Create a basic sorcerer caster for testing."""
    return {
        "id": "sorcerer_1",
        "name": "Test Sorcerer",
        "class": "sorcerer",
        "level": 5,
        "stats": {
            "charisma": 16,
            "constitution": 14,
        },
        "spellcasting": {
            "ability": "charisma",
            "spell_save_dc": 14,
            "spell_attack_bonus": 6,
            "spell_slots": {1: 4, 2: 3, 3: 2},
            "spell_slots_used": {},
            "cantrips_known": ["fire_bolt", "ray_of_frost"],
            "spells_known": ["magic_missile", "chromatic_orb", "hold_person", "fireball", "haste"],
            "prepared_spells": ["magic_missile", "chromatic_orb", "hold_person", "fireball", "haste"],
        },
    }


@pytest.fixture
def sorcery_state():
    """Create sorcery point state for testing."""
    return {
        "max_points": 5,
        "current_points": 5,
        "metamagic_known": [
            "twinned_spell",
            "quickened_spell",
            "subtle_spell",
            "empowered_spell",
            "heightened_spell",
        ],
    }


@pytest.fixture
def target():
    """Create a basic target for spell testing."""
    return {
        "id": "enemy_1",
        "name": "Goblin",
        "ac": 13,
        "hp": 15,
        "dexterity": 14,
        "wisdom": 10,
    }


@pytest.fixture
def second_target():
    """Create a second target for Twinned Spell testing."""
    return {
        "id": "enemy_2",
        "name": "Goblin 2",
        "ac": 13,
        "hp": 15,
        "dexterity": 14,
        "wisdom": 10,
    }


class TestCastSpellWithMetamagic:
    """Tests for cast_spell_with_metamagic function."""

    def test_cast_without_metamagic(self, sorcerer_caster, target):
        """Casting without metamagic works normally."""
        result, metamagic_info = cast_spell_with_metamagic(
            caster_data=sorcerer_caster,
            spell_id="fire_bolt",
            slot_level=None,
            targets=[target],
            metamagic_options=None,
        )

        assert result.success is True
        assert result.spell_name == "Fire Bolt"
        assert metamagic_info["applied"] == []
        assert metamagic_info["points_spent"] == 0

    def test_cast_with_quickened_spell(self, sorcerer_caster, target, sorcery_state):
        """Quickened Spell changes casting time to bonus action."""
        result, metamagic_info = cast_spell_with_metamagic(
            caster_data=sorcerer_caster,
            spell_id="fire_bolt",
            slot_level=None,
            targets=[target],
            metamagic_options=["quickened_spell"],
            sorcery_state=sorcery_state,
        )

        assert result.success is True
        assert "quickened_spell" in metamagic_info["applied"]
        assert metamagic_info["points_spent"] == 2
        # Sorcery points should be deducted
        assert sorcery_state["current_points"] == 3
        # Description should mention metamagic
        assert "Quickened" in result.description

    def test_cast_with_twinned_spell(self, sorcerer_caster, target, second_target, sorcery_state):
        """Twinned Spell targets two creatures."""
        result, metamagic_info = cast_spell_with_metamagic(
            caster_data=sorcerer_caster,
            spell_id="fire_bolt",
            slot_level=None,
            targets=[target, second_target],
            metamagic_options=["twinned_spell"],
            sorcery_state=sorcery_state,
        )

        assert result.success is True
        assert "twinned_spell" in metamagic_info["applied"]
        # Twinned costs 1 point for cantrips
        assert metamagic_info["points_spent"] == 1
        # Both targets should be affected
        assert "Twinned" in result.description
        assert sorcery_state["current_points"] == 4

    def test_twinned_spell_costs_spell_level(self, sorcerer_caster, target, second_target, sorcery_state):
        """Twinned Spell cost equals spell level."""
        result, metamagic_info = cast_spell_with_metamagic(
            caster_data=sorcerer_caster,
            spell_id="chromatic_orb",
            slot_level=1,
            targets=[target, second_target],
            metamagic_options=["twinned_spell"],
            sorcery_state=sorcery_state,
        )

        assert result.success is True
        # Twinned costs 1 point for level 1 spell
        assert metamagic_info["points_spent"] == 1

    def test_subtle_spell_removes_components(self, sorcerer_caster, target, sorcery_state):
        """Subtle Spell removes verbal and somatic components."""
        result, metamagic_info = cast_spell_with_metamagic(
            caster_data=sorcerer_caster,
            spell_id="fire_bolt",
            slot_level=None,
            targets=[target],
            metamagic_options=["subtle_spell"],
            sorcery_state=sorcery_state,
        )

        assert result.success is True
        assert "subtle_spell" in metamagic_info["applied"]
        assert metamagic_info["points_spent"] == 1
        assert result.extra_data["metamagic"]["subtle"] is True

    def test_insufficient_sorcery_points(self, sorcerer_caster, target, sorcery_state):
        """Metamagic fails when insufficient sorcery points."""
        sorcery_state["current_points"] = 1
        sorcery_state["metamagic_known"] = ["heightened_spell"]  # Costs 3

        result, metamagic_info = cast_spell_with_metamagic(
            caster_data=sorcerer_caster,
            spell_id="hold_person",
            slot_level=2,
            targets=[target],
            metamagic_options=["heightened_spell"],
            sorcery_state=sorcery_state,
        )

        # Spell still casts but metamagic wasn't applied
        assert len(metamagic_info["errors"]) > 0
        assert metamagic_info["points_spent"] == 0

    def test_unknown_metamagic_ignored(self, sorcerer_caster, target, sorcery_state):
        """Unknown metamagic options are ignored with error."""
        result, metamagic_info = cast_spell_with_metamagic(
            caster_data=sorcerer_caster,
            spell_id="fire_bolt",
            slot_level=None,
            targets=[target],
            metamagic_options=["fake_metamagic"],
            sorcery_state=sorcery_state,
        )

        assert result.success is True
        assert len(metamagic_info["errors"]) == 1
        assert "Unknown metamagic" in metamagic_info["errors"][0]


class TestValidateMetamagicForSpell:
    """Tests for _validate_metamagic_for_spell function."""

    def test_twinned_requires_single_target(self):
        """Twinned Spell only works on single-target spells."""
        registry = SpellRegistry.get_instance()
        fireball = registry.get_spell("fireball")

        valid, error = _validate_metamagic_for_spell(
            MetamagicType.TWINNED, fireball, [{"id": "1"}, {"id": "2"}]
        )

        assert valid is False
        assert "single-target" in error.lower()

    def test_twinned_requires_two_targets(self):
        """Twinned Spell requires two targets."""
        registry = SpellRegistry.get_instance()
        fire_bolt = registry.get_spell("fire_bolt")

        valid, error = _validate_metamagic_for_spell(
            MetamagicType.TWINNED, fire_bolt, [{"id": "1"}]
        )

        assert valid is False
        assert "two targets" in error.lower()

    def test_quickened_requires_action_casting_time(self):
        """Quickened Spell only works on 1 action spells."""
        registry = SpellRegistry.get_instance()
        fire_bolt = registry.get_spell("fire_bolt")

        valid, error = _validate_metamagic_for_spell(
            MetamagicType.QUICKENED, fire_bolt, []
        )

        assert valid is True

    def test_heightened_requires_saving_throw(self):
        """Heightened Spell only works on spells with saves."""
        registry = SpellRegistry.get_instance()
        magic_missile = registry.get_spell("magic_missile")

        # Magic Missile has no saving throw
        valid, error = _validate_metamagic_for_spell(
            MetamagicType.HEIGHTENED, magic_missile, [{"id": "1"}]
        )

        assert valid is False
        assert "saving throw" in error.lower()

    def test_empowered_requires_damage(self):
        """Empowered Spell only works on damage spells."""
        registry = SpellRegistry.get_instance()
        shield = registry.get_spell("shield")

        if shield:
            valid, error = _validate_metamagic_for_spell(
                MetamagicType.EMPOWERED, shield, []
            )
            assert valid is False
            assert "damage" in error.lower()

    def test_seeking_requires_attack_roll(self):
        """Seeking Spell only works on spell attacks."""
        registry = SpellRegistry.get_instance()
        hold_person = registry.get_spell("hold_person")

        if hold_person:
            valid, error = _validate_metamagic_for_spell(
                MetamagicType.SEEKING, hold_person, [{"id": "1"}]
            )
            assert valid is False
            assert "attack roll" in error.lower()

    def test_valid_metamagic_passes(self):
        """Valid metamagic combinations pass validation."""
        registry = SpellRegistry.get_instance()
        fire_bolt = registry.get_spell("fire_bolt")

        valid, error = _validate_metamagic_for_spell(
            MetamagicType.SUBTLE, fire_bolt, []
        )
        assert valid is True
        assert error == ""


class TestGetAvailableMetamagicForSpell:
    """Tests for get_available_metamagic_for_spell function."""

    def test_returns_known_metamagic(self):
        """Returns all known metamagic options."""
        sorcery_state = {
            "max_points": 5,
            "current_points": 5,
            "metamagic_known": ["twinned_spell", "quickened_spell"],
        }

        available = get_available_metamagic_for_spell("fire_bolt", sorcery_state, 0)

        assert len(available) == 2
        ids = [m["id"] for m in available]
        assert "twinned_spell" in ids
        assert "quickened_spell" in ids

    def test_marks_unusable_metamagic(self):
        """Marks metamagic that can't be used due to insufficient points."""
        sorcery_state = {
            "max_points": 5,
            "current_points": 1,
            "metamagic_known": ["quickened_spell"],  # Costs 2
        }

        available = get_available_metamagic_for_spell("fire_bolt", sorcery_state, 0)

        assert len(available) == 1
        assert available[0]["can_use"] is False
        assert "points" in available[0]["reason"].lower() or "insufficient" in available[0]["reason"].lower()

    def test_marks_invalid_for_spell(self):
        """Marks metamagic that's invalid for the specific spell."""
        sorcery_state = {
            "max_points": 5,
            "current_points": 5,
            "metamagic_known": ["heightened_spell"],  # Needs save spell
        }

        # Magic Missile doesn't have a save
        available = get_available_metamagic_for_spell("magic_missile", sorcery_state, 1)

        assert len(available) == 1
        assert available[0]["can_use"] is False

    def test_includes_cost_information(self):
        """Includes cost information for each option."""
        sorcery_state = {
            "max_points": 5,
            "current_points": 5,
            "metamagic_known": ["twinned_spell", "subtle_spell"],
        }

        available = get_available_metamagic_for_spell("fire_bolt", sorcery_state, 0)

        for option in available:
            assert "cost" in option
            assert isinstance(option["cost"], int)

    def test_twinned_cost_scales_with_level(self):
        """Twinned Spell cost scales with spell level."""
        sorcery_state = {
            "max_points": 5,
            "current_points": 5,
            "metamagic_known": ["twinned_spell"],
        }

        # Level 3 spell should cost 3
        available = get_available_metamagic_for_spell("fireball", sorcery_state, 3)

        # Fireball is AOE so Twinned won't work, but cost should be calculated
        twinned = next((m for m in available if m["id"] == "twinned_spell"), None)
        if twinned:
            assert twinned["cost"] == 3


class TestMetamagicPointDeduction:
    """Tests for proper sorcery point deduction."""

    def test_points_deducted_after_cast(self, sorcerer_caster, target, sorcery_state):
        """Sorcery points are properly deducted."""
        initial_points = sorcery_state["current_points"]

        cast_spell_with_metamagic(
            caster_data=sorcerer_caster,
            spell_id="fire_bolt",
            slot_level=None,
            targets=[target],
            metamagic_options=["subtle_spell"],  # Costs 1
            sorcery_state=sorcery_state,
        )

        assert sorcery_state["current_points"] == initial_points - 1

    def test_multiple_metamagic_stack_cost(self, sorcerer_caster, target, sorcery_state):
        """Multiple metamagic options stack their costs."""
        sorcery_state["metamagic_known"].append("subtle_spell")
        sorcery_state["current_points"] = 10

        result, metamagic_info = cast_spell_with_metamagic(
            caster_data=sorcerer_caster,
            spell_id="fire_bolt",
            slot_level=None,
            targets=[target],
            metamagic_options=["quickened_spell", "subtle_spell"],
            sorcery_state=sorcery_state,
        )

        # Quickened (2) + Subtle (1) = 3
        assert metamagic_info["points_spent"] == 3
        assert sorcery_state["current_points"] == 7

    def test_failed_metamagic_no_deduction(self, sorcerer_caster, target, sorcery_state):
        """Failed metamagic doesn't deduct points."""
        sorcery_state["current_points"] = 10
        sorcery_state["metamagic_known"] = ["heightened_spell"]

        # Fire bolt doesn't force a save, so Heightened fails
        result, metamagic_info = cast_spell_with_metamagic(
            caster_data=sorcerer_caster,
            spell_id="fire_bolt",
            slot_level=None,
            targets=[target],
            metamagic_options=["heightened_spell"],
            sorcery_state=sorcery_state,
        )

        # No points deducted for failed metamagic
        assert sorcery_state["current_points"] == 10
        assert len(metamagic_info["errors"]) > 0
