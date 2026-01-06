"""
Tests for Wild Shape damage integration with PartyMember.
"""
import pytest
from app.models.game_session import PartyMember
from app.core.wild_shape import (
    transform_party_member,
    revert_party_member,
    get_wild_shape_combat_stats,
    heal_wild_shape_form,
    DruidCircle,
    BEAST_FORMS,
)


class TestWildShapeDamageIntegration:
    """Test Wild Shape damage handling in PartyMember."""

    def create_druid(self, level: int = 5) -> PartyMember:
        """Create a test druid party member."""
        return PartyMember(
            id="druid-1",
            name="Test Druid",
            class_levels={"druid": level},
            primary_class="druid",
            character_class="druid",
            _level=level,
            max_hp=40,
            current_hp=40,
            temp_hp=0,
        )

    def test_damage_to_wild_shape_form(self):
        """Damage should reduce form HP first."""
        druid = self.create_druid()
        success, msg, form = transform_party_member(druid, "wolf", 5)
        assert success is True
        assert druid.is_wild_shaped is True

        # Wolf has 11 HP
        assert druid.wild_shape_form_hp == 11

        # Take 5 damage
        result = druid.take_damage(5)

        # Form should absorb the damage
        assert result["wild_shape_damage"] == 5
        assert result["damage_taken"] == 0  # No damage to druid
        assert druid.wild_shape_form_hp == 6
        assert druid.is_wild_shaped is True

    def test_form_drops_to_zero_reverts(self):
        """When form HP drops to 0, character reverts."""
        druid = self.create_druid()
        transform_party_member(druid, "wolf", 5)

        # Wolf has 11 HP, deal 11 damage
        result = druid.take_damage(11)

        assert result["wild_shape_damage"] == 11
        assert result["wild_shape_reverted"] is True
        assert result["overflow_damage"] == 0
        assert druid.is_wild_shaped is False
        assert druid.current_hp == 40  # Restored to original

    def test_overflow_damage_applies_to_druid(self):
        """Excess damage carries over to druid HP."""
        druid = self.create_druid()
        transform_party_member(druid, "wolf", 5)

        # Wolf has 11 HP, deal 15 damage (4 overflow)
        result = druid.take_damage(15)

        assert result["wild_shape_damage"] == 11
        assert result["wild_shape_reverted"] is True
        assert result["overflow_damage"] == 4
        assert result["damage_taken"] == 4  # Overflow applied to druid
        assert druid.is_wild_shaped is False
        assert druid.current_hp == 36  # 40 - 4 overflow

    def test_overflow_respects_temp_hp(self):
        """Overflow damage should go through temp HP first."""
        druid = self.create_druid()
        druid.temp_hp = 10
        transform_party_member(druid, "wolf", 5)

        # Wolf has 11 HP, deal 20 damage (9 overflow)
        result = druid.take_damage(20)

        assert result["wild_shape_damage"] == 11
        assert result["wild_shape_reverted"] is True
        assert result["overflow_damage"] == 9
        # Overflow goes through temp HP (9 absorbed by temp_hp)
        assert result["temp_hp_absorbed"] == 9
        assert result["damage_taken"] == 0
        assert druid.current_hp == 40
        assert druid.temp_hp == 1  # 10 - 9

    def test_massive_overflow_can_knock_unconscious(self):
        """Large overflow damage can knock druid unconscious."""
        druid = self.create_druid()
        druid.current_hp = 15  # Low HP before transform
        transform_party_member(druid, "wolf", 5)

        # Wolf has 11 HP, deal 30 damage (19 overflow)
        result = druid.take_damage(30)

        assert result["wild_shape_reverted"] is True
        assert result["overflow_damage"] == 19
        assert result["knocked_unconscious"] is True
        assert druid.current_hp == 0

    def test_massive_overflow_can_cause_instant_death(self):
        """Huge overflow damage can cause instant death."""
        druid = self.create_druid()
        druid.current_hp = 20  # 20 HP before transform, max_hp = 40
        transform_party_member(druid, "wolf", 5)

        # Wolf has 11 HP, deal 71 damage (60 overflow, which >= max_hp 40)
        result = druid.take_damage(71)

        assert result["wild_shape_reverted"] is True
        assert result["instant_death"] is True
        assert druid.is_dead is True

    def test_no_wild_shape_normal_damage(self):
        """Without Wild Shape, damage works normally."""
        druid = self.create_druid()

        result = druid.take_damage(10)

        assert result["damage_taken"] == 10
        assert result["wild_shape_damage"] == 0
        assert druid.current_hp == 30

    def test_form_absorbs_partial_damage(self):
        """Multiple hits with form absorbing damage."""
        druid = self.create_druid(level=8)  # Level 8 for CR 1 access
        transform_party_member(druid, "brown_bear", 8)

        # Brown bear has 34 HP
        assert druid.wild_shape_form_hp == 34

        # Take 10 damage
        result1 = druid.take_damage(10)
        assert result1["wild_shape_damage"] == 10
        assert druid.wild_shape_form_hp == 24
        assert druid.is_wild_shaped is True

        # Take 15 more damage
        result2 = druid.take_damage(15)
        assert result2["wild_shape_damage"] == 15
        assert druid.wild_shape_form_hp == 9
        assert druid.is_wild_shaped is True

        # Take 20 more damage (11 overflow)
        result3 = druid.take_damage(20)
        assert result3["wild_shape_damage"] == 9
        assert result3["wild_shape_reverted"] is True
        assert result3["overflow_damage"] == 11
        assert druid.is_wild_shaped is False


class TestWildShapeTransformRevert:
    """Test transform and revert functions."""

    def create_druid(self, level: int = 5) -> PartyMember:
        return PartyMember(
            id="druid-1",
            name="Test Druid",
            class_levels={"druid": level},
            primary_class="druid",
            character_class="druid",
            _level=level,
            max_hp=40,
            current_hp=35,
            temp_hp=5,
        )

    def test_transform_stores_original_hp(self):
        """Transform should store original HP values."""
        druid = self.create_druid()
        success, msg, form = transform_party_member(druid, "wolf", 5)

        assert success is True
        assert druid.wild_shape_state["original_hp"] == 35
        assert druid.wild_shape_state["original_temp_hp"] == 5

    def test_revert_restores_original_hp(self):
        """Revert should restore original HP values."""
        druid = self.create_druid()
        druid.current_hp = 35
        druid.temp_hp = 5

        transform_party_member(druid, "wolf", 5)

        # Manually set different HP to confirm restore
        druid.current_hp = 0
        druid.temp_hp = 0

        success, msg = revert_party_member(druid)

        assert success is True
        assert druid.current_hp == 35
        assert druid.temp_hp == 5

    def test_transform_checks_cr_limit(self):
        """Transform should check CR restrictions."""
        druid = self.create_druid(level=2)  # Level 2 = CR 1/4 max

        # Wolf is CR 1/4, should work
        success, msg, form = transform_party_member(druid, "wolf", 2)
        assert success is True

        revert_party_member(druid)
        druid.wild_shape_state["uses_remaining"] = 2

        # Brown bear is CR 1, should fail
        success, msg, form = transform_party_member(druid, "brown_bear", 2)
        assert success is False
        assert "CR" in msg

    def test_moon_druid_higher_cr(self):
        """Moon druid should have higher CR limit."""
        druid = self.create_druid(level=2)

        # Brown bear (CR 1) should work for Moon druid at level 2
        success, msg, form = transform_party_member(
            druid, "brown_bear", 2, DruidCircle.MOON
        )
        assert success is True

    def test_transform_uses_uses(self):
        """Transform should decrement uses."""
        druid = self.create_druid()
        druid.init_wild_shape_state(5)

        initial_uses = druid.wild_shape_state["uses_remaining"]
        transform_party_member(druid, "wolf", 5)

        assert druid.wild_shape_state["uses_remaining"] == initial_uses - 1

    def test_no_uses_remaining_fails(self):
        """Should fail if no uses remaining."""
        druid = self.create_druid()
        druid.init_wild_shape_state(5)
        druid.wild_shape_state["uses_remaining"] = 0

        success, msg, form = transform_party_member(druid, "wolf", 5)

        assert success is False
        assert "No Wild Shape uses" in msg


class TestWildShapeCombatStats:
    """Test getting combat stats for Wild Shape form."""

    def test_get_combat_stats(self):
        """Should return form stats when transformed."""
        druid = PartyMember(
            id="druid-1",
            name="Test Druid",
            class_levels={"druid": 8},  # Level 8 for CR 1 access
            primary_class="druid",
            character_class="druid",
            _level=8,
            max_hp=40,
            current_hp=40,
        )

        transform_party_member(druid, "dire_wolf", 8)
        stats = get_wild_shape_combat_stats(druid)

        assert stats is not None
        assert stats["form_name"] == "Dire Wolf"
        assert stats["ac"] == 14
        assert stats["speed"] == 50
        assert stats["strength"] == 17
        assert len(stats["attacks"]) > 0

    def test_no_stats_when_not_transformed(self):
        """Should return None when not transformed."""
        druid = PartyMember(
            id="druid-1",
            name="Test Druid",
            class_levels={"druid": 5},
            primary_class="druid",
            character_class="druid",
            _level=5,
            max_hp=40,
            current_hp=40,
        )

        stats = get_wild_shape_combat_stats(druid)
        assert stats is None


class TestMoonDruidBonuses:
    """Test Circle of the Moon specific bonuses."""

    def test_moon_druid_temp_hp_on_transform(self):
        """Moon Druid gets temp HP when transforming."""
        druid = PartyMember(
            id="druid-1",
            name="Moon Druid",
            class_levels={"druid": 5},
            primary_class="druid",
            character_class="druid",
            _level=5,
            max_hp=40,
            current_hp=40,
            wisdom=16,  # +3 modifier
        )

        # Brown bear (CR 1) is available to Moon Druid at level 2+
        success, msg, form = transform_party_member(
            druid, "brown_bear", 5, DruidCircle.MOON
        )

        assert success is True
        # Brown bear has 34 HP + (3 × 5 = 15) temp HP = 49
        assert druid.wild_shape_form_hp == 49
        assert druid.wild_shape_state["form_base_hp"] == 34
        assert druid.wild_shape_state["form_temp_hp_bonus"] == 15
        assert "+15 temp HP" in msg

    def test_moon_druid_ac_override(self):
        """Moon Druid AC should be max of form AC or 13 + WIS."""
        from app.core.wild_shape import get_effective_wild_shape_ac, BEAST_FORMS

        # Wolf has AC 13
        wolf = BEAST_FORMS["wolf"]

        # Without Moon Circle, use form AC
        ac_normal = get_effective_wild_shape_ac(wolf, None, 3)
        assert ac_normal == 13  # Wolf's base AC

        # Moon druid with WIS +3: 13 + 3 = 16 > 13
        ac_moon = get_effective_wild_shape_ac(wolf, DruidCircle.MOON, 3)
        assert ac_moon == 16  # Moon override (13 + 3)

        # Moon druid with WIS +0: 13 + 0 = 13 = 13 (tie, use override)
        ac_moon_low = get_effective_wild_shape_ac(wolf, DruidCircle.MOON, 0)
        assert ac_moon_low == 13  # Same as form

        # Dire wolf has AC 14
        dire_wolf = BEAST_FORMS["dire_wolf"]
        # Moon druid with WIS +0: 13 + 0 = 13 < 14
        ac_moon_dire = get_effective_wild_shape_ac(dire_wolf, DruidCircle.MOON, 0)
        assert ac_moon_dire == 14  # Form AC is higher

    def test_moon_druid_ac_in_combat_stats(self):
        """Combat stats should use effective AC for Moon Druid."""
        druid = PartyMember(
            id="druid-1",
            name="Moon Druid",
            class_levels={"druid": 5},
            primary_class="druid",
            character_class="druid",
            _level=5,
            max_hp=40,
            current_hp=40,
            wisdom=18,  # +4 modifier
        )

        # Transform as Moon Druid with WIS +4
        transform_party_member(druid, "brown_bear", 5, DruidCircle.MOON, 4)
        stats = get_wild_shape_combat_stats(druid)

        # Brown bear has AC 11, Moon druid gets 13 + 4 = 17
        assert stats["ac"] == 17
        assert stats["base_ac"] == 11
        assert stats["circle"] == "moon"

    def test_moon_druid_bonus_action_check(self):
        """Moon Druids can Wild Shape as bonus action."""
        from app.core.wild_shape import can_wild_shape_as_bonus_action

        assert can_wild_shape_as_bonus_action(None) is False
        assert can_wild_shape_as_bonus_action(DruidCircle.LAND) is False
        assert can_wild_shape_as_bonus_action(DruidCircle.MOON) is True

    def test_moon_druid_higher_cr_forms(self):
        """Moon Druid should access higher CR forms earlier."""
        druid = PartyMember(
            id="druid-1",
            name="Moon Druid",
            class_levels={"druid": 2},
            primary_class="druid",
            character_class="druid",
            _level=2,
            max_hp=18,
            current_hp=18,
        )

        # At level 2, normal druid max CR = 1/4
        # Moon druid max CR = 1
        # Brown bear is CR 1

        # Normal druid should fail
        druid.wild_shape_state = None
        success, msg, _ = transform_party_member(druid, "brown_bear", 2, None)
        assert success is False
        assert "CR" in msg

        # Moon druid should succeed
        druid.wild_shape_state = None
        success, msg, _ = transform_party_member(druid, "brown_bear", 2, DruidCircle.MOON)
        assert success is True


class TestWildShapeHealing:
    """Test healing while in Wild Shape."""

    def test_heal_form(self):
        """Healing should increase form HP."""
        druid = PartyMember(
            id="druid-1",
            name="Test Druid",
            class_levels={"druid": 8},  # Level 8 for CR 1 access
            primary_class="druid",
            character_class="druid",
            _level=8,
            max_hp=40,
            current_hp=40,
        )

        transform_party_member(druid, "brown_bear", 8)

        # Take some damage first
        druid.take_damage(10)
        assert druid.wild_shape_form_hp == 24  # 34 - 10

        # Heal
        healed = heal_wild_shape_form(druid, 5)

        assert healed == 5
        assert druid.wild_shape_form_hp == 29

    def test_heal_form_caps_at_max(self):
        """Healing should not exceed form max HP."""
        druid = PartyMember(
            id="druid-1",
            name="Test Druid",
            class_levels={"druid": 8},  # Level 8 for CR 1 access
            primary_class="druid",
            character_class="druid",
            _level=8,
            max_hp=40,
            current_hp=40,
        )

        transform_party_member(druid, "brown_bear", 8)

        # Take small damage
        druid.take_damage(5)
        assert druid.wild_shape_form_hp == 29

        # Try to heal more than missing
        healed = heal_wild_shape_form(druid, 20)

        assert healed == 5  # Only 5 was missing
        assert druid.wild_shape_form_hp == 34  # At max

    def test_no_heal_when_not_transformed(self):
        """Healing form should do nothing when not transformed."""
        druid = PartyMember(
            id="druid-1",
            name="Test Druid",
            class_levels={"druid": 5},
            primary_class="druid",
            character_class="druid",
            _level=5,
            max_hp=40,
            current_hp=30,
        )

        healed = heal_wild_shape_form(druid, 10)
        assert healed == 0
        assert druid.current_hp == 30  # Unchanged
