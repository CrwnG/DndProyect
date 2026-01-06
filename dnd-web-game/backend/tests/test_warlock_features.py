"""
Tests for Warlock Features - Pact Boons, Invocations, Mystic Arcanum.
"""
import pytest
from app.core.warlock_features import (
    # Enums
    PactBoon,
    WarlockPatron,
    # Pact Blade
    PactBladeState,
    PACT_WEAPON_FORMS,
    summon_pact_weapon,
    dismiss_pact_weapon,
    bond_magic_weapon,
    get_pact_weapon_attack_stat,
    # Pact Chain
    PactChainState,
    CHAIN_FAMILIAR_FORMS,
    summon_chain_familiar,
    familiar_attack,
    # Pact Tome
    PactTomeState,
    set_tome_cantrips,
    add_ritual_to_tome,
    # Pact Talisman
    PactTalismanState,
    initialize_talisman_state,
    use_talisman_reroll,
    restore_talisman_uses,
    # Mystic Arcanum
    MysticArcanumState,
    get_mystic_arcanum_levels,
    set_mystic_arcanum_spell,
    cast_mystic_arcanum,
    restore_mystic_arcanum,
    # Patron Features
    PATRON_FEATURES,
    get_patron_features_at_level,
    get_new_patron_features_at_level,
    # Invocations
    ELDRITCH_INVOCATIONS,
    get_available_invocations,
    get_invocation_count,
    calculate_eldritch_blast_damage,
    get_pact_magic_slots,
    get_eldritch_blast_beams,
)


class TestPactBlade:
    """Tests for Pact of the Blade mechanics."""

    def test_pact_blade_state_defaults(self):
        """Default state has no weapon summoned."""
        state = PactBladeState()
        assert state.summoned_weapon is None
        assert state.is_summoned is False

    def test_summon_pact_weapon_success(self):
        """Can summon a valid pact weapon."""
        state = PactBladeState()

        success, msg, data = summon_pact_weapon(state, "longsword")

        assert success is True
        assert state.is_summoned is True
        assert state.summoned_weapon == "longsword"
        assert data["is_magical"] is True
        assert data["is_pact_weapon"] is True

    def test_summon_invalid_weapon(self):
        """Cannot summon invalid weapon form."""
        state = PactBladeState()

        success, msg, data = summon_pact_weapon(state, "banana")

        assert success is False
        assert "Invalid weapon form" in msg

    def test_summon_already_summoned(self):
        """Cannot summon when weapon already exists."""
        state = PactBladeState()
        summon_pact_weapon(state, "longsword")

        success, msg, data = summon_pact_weapon(state, "greatsword")

        assert success is False
        assert "already summoned" in msg.lower()

    def test_dismiss_pact_weapon(self):
        """Can dismiss summoned weapon."""
        state = PactBladeState()
        summon_pact_weapon(state, "longsword")

        dismissed = dismiss_pact_weapon(state)

        assert dismissed is True
        assert state.is_summoned is False
        assert state.summoned_weapon is None

    def test_bond_magic_weapon(self):
        """Can bond a magic weapon."""
        state = PactBladeState()
        weapon = {"name": "+1 Longsword", "is_magical": True}

        success, msg = bond_magic_weapon(state, weapon)

        assert success is True
        assert state.bonded_weapon is not None
        assert state.bonded_weapon["is_pact_weapon"] is True

    def test_bond_nonmagic_fails(self):
        """Cannot bond non-magical weapon."""
        state = PactBladeState()
        weapon = {"name": "Longsword", "is_magical": False}

        success, msg = bond_magic_weapon(state, weapon)

        assert success is False
        assert "magic" in msg.lower()

    def test_hexblade_uses_charisma(self):
        """Hexblade uses CHA for pact weapon attacks."""
        stat = get_pact_weapon_attack_stat(WarlockPatron.HEXBLADE, [])
        assert stat == "charisma"

    def test_non_hexblade_uses_strength(self):
        """Non-Hexblade uses STR for pact weapon attacks."""
        stat = get_pact_weapon_attack_stat(WarlockPatron.FIEND, [])
        assert stat == "strength"


class TestPactChain:
    """Tests for Pact of the Chain mechanics."""

    def test_summon_chain_familiar(self):
        """Can summon a chain familiar."""
        state = PactChainState()

        success, msg, data = summon_chain_familiar(state, "imp")

        assert success is True
        assert state.familiar_form == "imp"
        assert state.familiar_active is True
        assert data["hp"] == 10
        assert data["ac"] == 13

    def test_all_familiar_forms_valid(self):
        """All 4 special familiar forms work."""
        for form in ["imp", "pseudodragon", "quasit", "sprite"]:
            state = PactChainState()
            success, msg, data = summon_chain_familiar(state, form)
            assert success is True, f"Failed to summon {form}"

    def test_invalid_familiar_form(self):
        """Invalid familiar form fails."""
        state = PactChainState()

        success, msg, data = summon_chain_familiar(state, "cat")

        assert success is False
        assert "Invalid familiar form" in msg

    def test_familiar_attack_basic(self):
        """Familiar can attack using its stats."""
        state = PactChainState()
        summon_chain_familiar(state, "imp")

        attack = familiar_attack(state, [])

        assert attack["attack_bonus"] == 5
        assert attack["action_type"] == "bonus_action"

    def test_familiar_attack_with_investment(self):
        """Investment of the Chain Master uses warlock's stats."""
        state = PactChainState()
        summon_chain_familiar(state, "imp")

        attack = familiar_attack(
            state,
            invocations=["investment_of_the_chain_master"],
            warlock_spell_attack=8
        )

        assert attack["attack_bonus"] == 8


class TestPactTome:
    """Tests for Pact of the Tome mechanics."""

    def test_set_tome_cantrips(self):
        """Can set 3 cantrips for Book of Shadows."""
        state = PactTomeState()
        cantrips = ["light", "mage_hand", "guidance"]

        success, msg = set_tome_cantrips(state, cantrips)

        assert success is True
        assert len(state.extra_cantrips) == 3

    def test_must_have_exactly_three_cantrips(self):
        """Must choose exactly 3 cantrips."""
        state = PactTomeState()

        success, msg = set_tome_cantrips(state, ["light", "mage_hand"])
        assert success is False
        assert "exactly 3" in msg

    def test_add_ritual_without_invocation(self):
        """Cannot add ritual without Book of Ancient Secrets."""
        state = PactTomeState()

        success, msg = add_ritual_to_tome(state, "detect_magic", has_book_of_ancient_secrets=False)

        assert success is False
        assert "Ancient Secrets" in msg

    def test_add_ritual_with_invocation(self):
        """Can add ritual with Book of Ancient Secrets."""
        state = PactTomeState()

        success, msg = add_ritual_to_tome(state, "detect_magic", has_book_of_ancient_secrets=True)

        assert success is True
        assert "detect_magic" in state.ritual_spells


class TestPactTalisman:
    """Tests for Pact of the Talisman mechanics."""

    def test_initialize_talisman_state(self):
        """Initialize with proficiency bonus uses."""
        state = initialize_talisman_state(level=5)
        assert state.max_uses == 3  # +3 proficiency at level 5

    def test_use_talisman_reroll(self):
        """Can use talisman to add d4."""
        state = initialize_talisman_state(level=5)

        success, msg, roll = use_talisman_reroll(state)

        assert success is True
        assert 1 <= roll <= 4
        assert state.uses_remaining == 2

    def test_talisman_no_uses(self):
        """Cannot use talisman with no uses remaining."""
        state = initialize_talisman_state(level=1)
        state.uses_remaining = 0

        success, msg, roll = use_talisman_reroll(state)

        assert success is False
        assert "No talisman uses" in msg

    def test_restore_talisman_uses(self):
        """Long rest restores talisman uses."""
        state = initialize_talisman_state(level=5)
        state.uses_remaining = 0

        restored = restore_talisman_uses(state, level=5)

        assert restored == 3
        assert state.uses_remaining == 3


class TestMysticArcanum:
    """Tests for Mystic Arcanum system."""

    def test_arcanum_levels_by_warlock_level(self):
        """Arcanum levels unlock at correct warlock levels."""
        assert get_mystic_arcanum_levels(10) == []
        assert get_mystic_arcanum_levels(11) == [6]
        assert get_mystic_arcanum_levels(13) == [6, 7]
        assert get_mystic_arcanum_levels(15) == [6, 7, 8]
        assert get_mystic_arcanum_levels(17) == [6, 7, 8, 9]

    def test_set_mystic_arcanum_spell(self):
        """Can set arcanum spell at available level."""
        state = MysticArcanumState()

        success, msg = set_mystic_arcanum_spell(state, 6, "mass_suggestion", warlock_level=11)

        assert success is True
        assert state.spells_chosen[6] == "mass_suggestion"

    def test_set_unavailable_arcanum_level(self):
        """Cannot set arcanum for unavailable level."""
        state = MysticArcanumState()

        success, msg = set_mystic_arcanum_spell(state, 7, "finger_of_death", warlock_level=11)

        assert success is False
        assert "not available" in msg.lower()

    def test_cast_mystic_arcanum(self):
        """Can cast arcanum spell once per rest."""
        state = MysticArcanumState()
        state.spells_chosen[6] = "mass_suggestion"

        success, msg, spell_id = cast_mystic_arcanum(state, 6)

        assert success is True
        assert spell_id == "mass_suggestion"
        assert 6 in state.used_this_rest

    def test_cannot_cast_arcanum_twice(self):
        """Cannot cast same arcanum twice before rest."""
        state = MysticArcanumState()
        state.spells_chosen[6] = "mass_suggestion"
        cast_mystic_arcanum(state, 6)

        success, msg, spell_id = cast_mystic_arcanum(state, 6)

        assert success is False
        assert "Already used" in msg

    def test_restore_mystic_arcanum(self):
        """Long rest restores all arcanum uses."""
        state = MysticArcanumState()
        state.spells_chosen = {6: "spell1", 7: "spell2"}
        state.used_this_rest = {6, 7}

        restored = restore_mystic_arcanum(state)

        assert restored == 2
        assert len(state.used_this_rest) == 0


class TestPatronFeatures:
    """Tests for Warlock Patron features."""

    def test_all_patrons_have_features(self):
        """All main patrons have features defined."""
        patrons_with_features = [
            WarlockPatron.FIEND,
            WarlockPatron.ARCHFEY,
            WarlockPatron.GREAT_OLD_ONE,
            WarlockPatron.CELESTIAL,
            WarlockPatron.HEXBLADE,
        ]
        for patron in patrons_with_features:
            assert patron in PATRON_FEATURES
            assert len(PATRON_FEATURES[patron]) >= 4

    def test_get_patron_features_at_level(self):
        """Features are filtered by level."""
        features = get_patron_features_at_level(WarlockPatron.FIEND, 10)
        feature_names = [f.name for f in features]

        assert "Dark One's Blessing" in feature_names  # Level 1
        assert "Dark One's Own Luck" in feature_names  # Level 6
        assert "Fiendish Resilience" in feature_names  # Level 10
        assert "Hurl Through Hell" not in feature_names  # Level 14

    def test_get_new_patron_features(self):
        """Only features at exact level returned."""
        features = get_new_patron_features_at_level(WarlockPatron.FIEND, 6)

        assert len(features) == 1
        assert features[0].name == "Dark One's Own Luck"


class TestInvocations:
    """Tests for Eldritch Invocations."""

    def test_invocations_defined(self):
        """Many invocations are defined."""
        assert len(ELDRITCH_INVOCATIONS) >= 30

    def test_invocation_count_scales(self):
        """Invocation count scales with level."""
        assert get_invocation_count(1) == 0
        assert get_invocation_count(2) == 2
        assert get_invocation_count(5) == 3
        assert get_invocation_count(9) == 5
        assert get_invocation_count(17) == 8

    def test_available_invocations_basic(self):
        """Can get invocations without prerequisites."""
        available = get_available_invocations(level=2)

        inv_ids = [i.id for i in available]
        # No-prerequisite invocations should be available
        assert "armor_of_shadows" in inv_ids
        assert "eldritch_sight" in inv_ids
        assert "devils_sight" in inv_ids

    def test_invocations_require_cantrip(self):
        """Agonizing Blast requires eldritch_blast cantrip."""
        available = get_available_invocations(
            level=5,
            cantrips_known=["fire_bolt"]
        )
        inv_ids = [i.id for i in available]
        assert "agonizing_blast" not in inv_ids

        # With eldritch_blast
        available = get_available_invocations(
            level=5,
            cantrips_known=["eldritch_blast"]
        )
        inv_ids = [i.id for i in available]
        assert "agonizing_blast" in inv_ids

    def test_invocations_require_pact(self):
        """Thirsting Blade requires Pact of the Blade."""
        available = get_available_invocations(
            level=5,
            pact_boon=None
        )
        inv_ids = [i.id for i in available]
        assert "thirsting_blade" not in inv_ids

        available = get_available_invocations(
            level=5,
            pact_boon=PactBoon.BLADE
        )
        inv_ids = [i.id for i in available]
        assert "thirsting_blade" in inv_ids

    def test_invocations_require_level(self):
        """Level-gated invocations require minimum level."""
        available = get_available_invocations(level=4)
        inv_ids = [i.id for i in available]
        assert "mire_the_mind" not in inv_ids  # Level 5

        available = get_available_invocations(level=5)
        inv_ids = [i.id for i in available]
        assert "mire_the_mind" in inv_ids


class TestPactMagic:
    """Tests for Pact Magic slot system."""

    def test_pact_magic_slots(self):
        """Pact Magic slots scale correctly."""
        assert get_pact_magic_slots(1) == {"slots": 1, "slot_level": 1}
        assert get_pact_magic_slots(2) == {"slots": 1, "slot_level": 1}
        assert get_pact_magic_slots(3) == {"slots": 2, "slot_level": 2}
        assert get_pact_magic_slots(5) == {"slots": 2, "slot_level": 3}
        assert get_pact_magic_slots(11) == {"slots": 3, "slot_level": 5}
        assert get_pact_magic_slots(17) == {"slots": 4, "slot_level": 5}


class TestEldritchBlast:
    """Tests for Eldritch Blast calculations."""

    def test_eldritch_blast_beams(self):
        """Eldritch Blast beams scale with level."""
        assert get_eldritch_blast_beams(1) == 1
        assert get_eldritch_blast_beams(5) == 2
        assert get_eldritch_blast_beams(11) == 3
        assert get_eldritch_blast_beams(17) == 4

    def test_eldritch_blast_damage_basic(self):
        """Basic Eldritch Blast damage calculation."""
        damage = calculate_eldritch_blast_damage(
            level=5,
            charisma_mod=3,
            invocations=[]
        )

        assert damage["beams"] == 2
        assert damage["damage_per_beam"] == "1d10"
        assert damage["bonus_damage"] == 0
        assert damage["range"] == 120

    def test_eldritch_blast_with_agonizing(self):
        """Agonizing Blast adds CHA to damage."""
        damage = calculate_eldritch_blast_damage(
            level=5,
            charisma_mod=4,
            invocations=["agonizing_blast"]
        )

        assert damage["bonus_damage"] == 4
        assert "8" in damage["total_potential"]  # 2d10 + 8

    def test_eldritch_blast_with_spear(self):
        """Eldritch Spear increases range."""
        damage = calculate_eldritch_blast_damage(
            level=5,
            charisma_mod=3,
            invocations=["eldritch_spear"]
        )

        assert damage["range"] == 300

    def test_eldritch_blast_effects(self):
        """Invocations add movement effects."""
        damage = calculate_eldritch_blast_damage(
            level=5,
            charisma_mod=3,
            invocations=["repelling_blast", "lance_of_lethargy"]
        )

        assert "Push 10 ft." in damage["effects"]
        assert "Speed -10 ft." in damage["effects"]
