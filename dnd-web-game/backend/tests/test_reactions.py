"""Tests for the reactions system."""
import pytest

from app.core.reactions import (
    ReactionType,
    ReactionTrigger,
    ReactionResult,
    ReactionOption,
    ReactionState,
    ReactionsManager,
    resolve_opportunity_attack,
    resolve_shield_spell,
    resolve_counterspell,
    resolve_absorb_elements,
    resolve_uncanny_dodge,
    resolve_hellish_rebuke,
    resolve_parry,
    check_available_reactions,
)


class TestReactionState:
    """Test ReactionState class."""

    def test_default_state(self):
        """Should have reaction available by default."""
        state = ReactionState(combatant_id="test-1")

        assert state.reaction_available is True
        assert state.readied_action is None

    def test_use_reaction(self):
        """Should mark reaction as used."""
        state = ReactionState(combatant_id="test-1")

        result = state.use_reaction()

        assert result is True
        assert state.reaction_available is False
        assert state.reaction_used_this_round is True

    def test_cannot_use_twice(self):
        """Should not be able to use reaction twice."""
        state = ReactionState(combatant_id="test-1")
        state.use_reaction()

        result = state.use_reaction()

        assert result is False

    def test_reset_for_round(self):
        """Should reset reaction availability."""
        state = ReactionState(combatant_id="test-1")
        state.use_reaction()

        state.reset_for_round()

        assert state.reaction_available is True
        assert state.reaction_used_this_round is False


class TestReactionsManager:
    """Test ReactionsManager class."""

    def test_register_combatant(self):
        """Should register combatants."""
        manager = ReactionsManager()

        manager.register_combatant("player-1")

        assert manager.get_reaction_state("player-1") is not None

    def test_remove_combatant(self):
        """Should remove combatants."""
        manager = ReactionsManager()
        manager.register_combatant("player-1")

        manager.remove_combatant("player-1")

        assert manager.get_reaction_state("player-1") is None

    def test_has_reaction_available(self):
        """Should check reaction availability."""
        manager = ReactionsManager()
        manager.register_combatant("player-1")

        assert manager.has_reaction_available("player-1") is True

    def test_use_reaction(self):
        """Should use reaction through manager."""
        manager = ReactionsManager()
        manager.register_combatant("player-1")

        result = manager.use_reaction("player-1")

        assert result is True
        assert manager.has_reaction_available("player-1") is False

    def test_reset_combatant_reaction(self):
        """Should reset combatant reaction."""
        manager = ReactionsManager()
        manager.register_combatant("player-1")
        manager.use_reaction("player-1")

        manager.reset_combatant_reaction("player-1")

        assert manager.has_reaction_available("player-1") is True

    def test_set_readied_action(self):
        """Should set readied action."""
        manager = ReactionsManager()
        manager.register_combatant("player-1")

        result = manager.set_readied_action(
            "player-1",
            action="attack",
            trigger="enemy approaches"
        )

        assert result is True
        state = manager.get_reaction_state("player-1")
        assert state.readied_action is not None
        assert state.readied_action["action"] == "attack"

    def test_clear_readied_action(self):
        """Should clear readied action."""
        manager = ReactionsManager()
        manager.register_combatant("player-1")
        manager.set_readied_action("player-1", "attack", "enemy moves")

        manager.clear_readied_action("player-1")

        state = manager.get_reaction_state("player-1")
        assert state.readied_action is None


class TestOpportunityAttack:
    """Test opportunity attack resolution."""

    def test_opportunity_attack_hit(self):
        """Should resolve opportunity attack hit."""
        # With +10 attack vs AC 10, almost always hits
        result = resolve_opportunity_attack(
            attacker_id="fighter-1",
            attacker_name="Fighter",
            target_id="goblin-1",
            target_name="Goblin",
            attack_bonus=10,
            target_ac=10,
            damage_dice="1d8",
            damage_modifier=4
        )

        assert result.success is True
        assert result.reaction_type == ReactionType.OPPORTUNITY_ATTACK.value
        assert "Fighter" in result.description
        assert "Goblin" in result.description

    def test_opportunity_attack_miss(self):
        """Should resolve opportunity attack miss."""
        # With +0 attack vs AC 25, almost always misses
        result = resolve_opportunity_attack(
            attacker_id="fighter-1",
            attacker_name="Fighter",
            target_id="enemy-1",
            target_name="Enemy",
            attack_bonus=0,
            target_ac=25,
            damage_dice="1d8"
        )

        assert result.success is True  # Reaction was used
        # Damage could be 0 if miss


class TestShieldSpell:
    """Test Shield spell reaction."""

    def test_shield_blocks_attack(self):
        """Shield should block attack that would have hit."""
        result = resolve_shield_spell(
            caster_id="wizard-1",
            caster_name="Wizard",
            attack_roll=16,
            current_ac=13,
            has_spell_slot=True
        )

        assert result.success is True
        assert result.ac_bonus == 5
        assert result.extra_data["new_ac"] == 18
        assert result.extra_data["attack_would_miss"] is True
        assert "misses" in result.description

    def test_shield_doesnt_help_high_roll(self):
        """Shield shouldn't help against very high rolls."""
        result = resolve_shield_spell(
            caster_id="wizard-1",
            caster_name="Wizard",
            attack_roll=25,
            current_ac=13,
            has_spell_slot=True
        )

        assert result.success is True
        assert result.extra_data["attack_would_miss"] is False
        assert "still hits" in result.description

    def test_shield_no_spell_slot(self):
        """Should fail without spell slot."""
        result = resolve_shield_spell(
            caster_id="wizard-1",
            caster_name="Wizard",
            attack_roll=15,
            current_ac=13,
            has_spell_slot=False
        )

        assert result.success is False
        assert "no spell slots" in result.description


class TestCounterspell:
    """Test Counterspell reaction."""

    def test_counterspell_auto_success(self):
        """Same level slot should auto-counter."""
        result = resolve_counterspell(
            caster_id="wizard-1",
            caster_name="Wizard",
            spell_level=3,
            slot_used=3
        )

        assert result.success is True
        assert result.spell_countered is True
        assert result.extra_data["automatic"] is True

    def test_counterspell_higher_slot(self):
        """Higher slot should auto-counter lower spell."""
        result = resolve_counterspell(
            caster_id="wizard-1",
            caster_name="Wizard",
            spell_level=2,
            slot_used=5
        )

        assert result.success is True
        assert result.spell_countered is True

    def test_counterspell_lower_slot_needs_check(self):
        """Lower slot requires ability check."""
        result = resolve_counterspell(
            caster_id="wizard-1",
            caster_name="Wizard",
            spell_level=5,
            slot_used=3,
            caster_ability_mod=5,  # Good chance
            target_spell_name="Fireball"
        )

        assert result.success is True
        # May or may not counter depending on roll
        assert result.extra_data["dc"] == 15  # DC = 10 + spell level


class TestAbsorbElements:
    """Test Absorb Elements reaction."""

    def test_absorb_elements_halves_damage(self):
        """Should halve elemental damage."""
        result = resolve_absorb_elements(
            caster_id="wizard-1",
            caster_name="Wizard",
            damage_type="fire",
            damage_amount=20,
            slot_used=1
        )

        assert result.success is True
        assert result.damage_prevented == 10
        assert result.extra_data["damage_taken"] == 10
        assert result.extra_data["bonus_melee_damage"] == "1d6"

    def test_absorb_elements_upcast(self):
        """Higher slot should give more bonus damage."""
        result = resolve_absorb_elements(
            caster_id="wizard-1",
            caster_name="Wizard",
            damage_type="cold",
            damage_amount=30,
            slot_used=3
        )

        assert result.extra_data["bonus_melee_damage"] == "3d6"


class TestUncannyDodge:
    """Test Uncanny Dodge reaction."""

    def test_uncanny_dodge_halves(self):
        """Should halve damage."""
        result = resolve_uncanny_dodge(
            rogue_id="rogue-1",
            rogue_name="Rogue",
            damage_amount=20
        )

        assert result.success is True
        assert result.damage_prevented == 10
        assert result.extra_data["damage_taken"] == 10

    def test_uncanny_dodge_rounds_down(self):
        """Should round down odd damage."""
        result = resolve_uncanny_dodge(
            rogue_id="rogue-1",
            rogue_name="Rogue",
            damage_amount=15
        )

        assert result.extra_data["damage_taken"] == 7
        assert result.damage_prevented == 8


class TestHellishRebuke:
    """Test Hellish Rebuke reaction."""

    def test_hellish_rebuke_fails_save(self):
        """Target failing save should take full damage."""
        result = resolve_hellish_rebuke(
            caster_id="warlock-1",
            caster_name="Warlock",
            target_id="enemy-1",
            target_name="Enemy",
            target_dex_mod=-2,  # Low DEX
            slot_used=1,
            spell_dc=15
        )

        assert result.success is True
        assert result.damage_dealt > 0
        # With -2 mod vs DC 15, likely fails

    def test_hellish_rebuke_upcast(self):
        """Higher slot should roll more dice."""
        # Just verify it runs with higher slot
        result = resolve_hellish_rebuke(
            caster_id="warlock-1",
            caster_name="Warlock",
            target_id="enemy-1",
            target_name="Enemy",
            target_dex_mod=0,
            slot_used=3,
            spell_dc=13
        )

        assert result.success is True
        assert result.extra_data["slot_used"] == 3


class TestParry:
    """Test Parry (Defensive Duelist) reaction."""

    def test_parry_blocks_attack(self):
        """Parry should block attack that would have hit."""
        result = resolve_parry(
            defender_id="fighter-1",
            defender_name="Fighter",
            proficiency_bonus=4,
            attack_roll=18,
            current_ac=16
        )

        assert result.success is True
        assert result.ac_bonus == 4
        assert result.extra_data["new_ac"] == 20
        assert result.extra_data["attack_would_miss"] is True

    def test_parry_doesnt_help_high_roll(self):
        """Parry shouldn't help against very high rolls."""
        result = resolve_parry(
            defender_id="fighter-1",
            defender_name="Fighter",
            proficiency_bonus=3,
            attack_roll=25,
            current_ac=15
        )

        assert result.extra_data["attack_would_miss"] is False


class TestCheckAvailableReactions:
    """Test checking available reactions."""

    def setup_method(self):
        """Set up a reactions manager for tests."""
        self.manager = ReactionsManager()
        self.manager.register_combatant("player-1")

    def test_opportunity_attack_available(self):
        """Should show OA when enemy leaves reach."""
        options = check_available_reactions(
            combatant_id="player-1",
            trigger=ReactionTrigger.ENEMY_LEAVES_REACH,
            trigger_source_id="enemy-1",
            reactions_manager=self.manager,
            combatant_abilities={"can_opportunity_attack": True}
        )

        assert len(options) >= 1
        oa_option = next(
            (o for o in options if o.reaction_type == ReactionType.OPPORTUNITY_ATTACK),
            None
        )
        assert oa_option is not None

    def test_shield_available_with_slot(self):
        """Should show Shield when being attacked with slot."""
        options = check_available_reactions(
            combatant_id="player-1",
            trigger=ReactionTrigger.BEING_ATTACKED,
            trigger_source_id="enemy-1",
            reactions_manager=self.manager,
            combatant_abilities={
                "knows_shield": True,
                "spell_slots_1st": 2
            }
        )

        shield_option = next(
            (o for o in options if o.reaction_type == ReactionType.SHIELD),
            None
        )
        assert shield_option is not None
        assert shield_option.can_use is True

    def test_shield_unavailable_no_slot(self):
        """Shield should be unavailable without slot."""
        options = check_available_reactions(
            combatant_id="player-1",
            trigger=ReactionTrigger.BEING_ATTACKED,
            trigger_source_id="enemy-1",
            reactions_manager=self.manager,
            combatant_abilities={
                "knows_shield": True,
                "spell_slots_1st": 0
            }
        )

        shield_option = next(
            (o for o in options if o.reaction_type == ReactionType.SHIELD),
            None
        )
        assert shield_option is not None
        assert shield_option.can_use is False

    def test_uncanny_dodge_on_hit(self):
        """Should show Uncanny Dodge when hit."""
        options = check_available_reactions(
            combatant_id="player-1",
            trigger=ReactionTrigger.BEING_HIT,
            trigger_source_id="enemy-1",
            reactions_manager=self.manager,
            combatant_abilities={"uncanny_dodge": True}
        )

        ud_option = next(
            (o for o in options if o.reaction_type == ReactionType.UNCANNY_DODGE),
            None
        )
        assert ud_option is not None

    def test_no_reactions_when_used(self):
        """Should show no options when reaction already used."""
        self.manager.use_reaction("player-1")

        options = check_available_reactions(
            combatant_id="player-1",
            trigger=ReactionTrigger.ENEMY_LEAVES_REACH,
            trigger_source_id="enemy-1",
            reactions_manager=self.manager,
            combatant_abilities={"can_opportunity_attack": True}
        )

        assert len(options) == 0

    def test_absorb_elements_on_elemental_damage(self):
        """Should show Absorb Elements for elemental damage."""
        options = check_available_reactions(
            combatant_id="player-1",
            trigger=ReactionTrigger.TAKING_DAMAGE,
            trigger_source_id="enemy-1",
            reactions_manager=self.manager,
            combatant_abilities={
                "knows_absorb_elements": True,
                "spell_slots_1st": 1
            },
            context={"damage_type": "fire"}
        )

        ae_option = next(
            (o for o in options if o.reaction_type == ReactionType.ABSORB_ELEMENTS),
            None
        )
        assert ae_option is not None

    def test_absorb_elements_not_for_physical(self):
        """Should not show Absorb Elements for physical damage."""
        options = check_available_reactions(
            combatant_id="player-1",
            trigger=ReactionTrigger.TAKING_DAMAGE,
            trigger_source_id="enemy-1",
            reactions_manager=self.manager,
            combatant_abilities={
                "knows_absorb_elements": True,
                "spell_slots_1st": 1
            },
            context={"damage_type": "slashing"}
        )

        ae_option = next(
            (o for o in options if o.reaction_type == ReactionType.ABSORB_ELEMENTS),
            None
        )
        assert ae_option is None

    def test_counterspell_on_enemy_spell(self):
        """Should show Counterspell when enemy casts."""
        options = check_available_reactions(
            combatant_id="player-1",
            trigger=ReactionTrigger.ENEMY_CASTS_SPELL,
            trigger_source_id="enemy-1",
            reactions_manager=self.manager,
            combatant_abilities={
                "knows_counterspell": True,
                "spell_slots_3": 1
            }
        )

        cs_option = next(
            (o for o in options if o.reaction_type == ReactionType.COUNTERSPELL),
            None
        )
        assert cs_option is not None

    def test_readied_action_available(self):
        """Should show readied action when trigger matches."""
        self.manager.set_readied_action(
            "player-1",
            action="attack",
            trigger="enemy moves"
        )

        options = check_available_reactions(
            combatant_id="player-1",
            trigger=ReactionTrigger.CUSTOM,
            trigger_source_id="enemy-1",
            reactions_manager=self.manager,
            combatant_abilities={}
        )

        ready_option = next(
            (o for o in options if o.reaction_type == ReactionType.READIED_ACTION),
            None
        )
        assert ready_option is not None


class TestMultipleReactionOptions:
    """Test scenarios with multiple reaction options."""

    def test_multiple_options_available(self):
        """Should show all applicable reactions."""
        manager = ReactionsManager()
        manager.register_combatant("player-1")

        options = check_available_reactions(
            combatant_id="player-1",
            trigger=ReactionTrigger.BEING_ATTACKED,
            trigger_source_id="enemy-1",
            reactions_manager=manager,
            combatant_abilities={
                "knows_shield": True,
                "spell_slots_1st": 2,
                "defensive_duelist": True
            }
        )

        # Should have both Shield and Parry
        reaction_types = [o.reaction_type for o in options]
        assert ReactionType.SHIELD in reaction_types
        assert ReactionType.PARRY in reaction_types
