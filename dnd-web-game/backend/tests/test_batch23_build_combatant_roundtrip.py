"""Batch 23 (Goal c): the create-character -> combatant round trip, for every class.

The root doc lists this as a REQUIRED regression test (invariant #1) that was missing
for the full set of classes: a character built through CharacterBuilder must convert
to a combatant with REAL ability mods, correct per-class HP, a real attack bonus, and
a non-fallback AC — not the 10 HP / AC 10 / +0 fallback that broke created characters.

An audit (2026-06-22) confirmed all 12 classes are healthy; this locks that in so the
invariant can't silently regress when the builder or the adapter changes.

NOTE (documented gap, not asserted here): the wizard's equipment step is a placeholder,
so a created martial gets no armor -> AC stays unarmored (10 + DEX). That's a separate
feature, tracked in the frontend notes.
"""
import pytest

from app.core.character_builder import CharacterBuilder
from app.services.character_service import builder_to_combatant_data

# d12/d10/d8/d6 hit die (max at level 1) + CON mod (+2 here).
EXPECTED_HP = {
    "barbarian": 14,
    "fighter": 12, "paladin": 12, "ranger": 12,
    "bard": 10, "cleric": 10, "druid": 10, "monk": 10, "rogue": 10, "warlock": 10,
    "sorcerer": 8, "wizard": 8,
}

# Point-buy 15/14/13/12/10/8 + a +1/+1/+1 background spread on STR/DEX/CON.
_SCORES = {"strength": 15, "dexterity": 14, "constitution": 13,
           "intelligence": 12, "wisdom": 10, "charisma": 8}


def _build_combatant(cls):
    b = CharacterBuilder()
    origin_feats = b.rules.get_origin_feats()
    ofeat = origin_feats[0]["id"] if isinstance(origin_feats[0], dict) else getattr(origin_feats[0], "id", origin_feats[0])

    build = b.create_new_build()
    b.set_species(build, "human")
    b.set_size_choice(build, "Medium")
    b.set_class(build, cls)
    b.set_ability_scores(build, dict(_SCORES))
    b.set_background(build, "soldier")
    b.set_ability_bonuses(build, {"strength": 1, "dexterity": 1, "constitution": 1})
    b.set_origin_feat(build, ofeat)
    opts, count = b._get_skill_options(b.rules.get_class(cls))
    b.set_skill_choices(build, list(opts)[:count])
    b.set_details(build, cls.title() + " Hero")

    ok, result = b.finalize_character(build)
    assert ok, f"{cls} failed to finalize: {result.get('errors') if isinstance(result, dict) else result}"
    return builder_to_combatant_data(result)


@pytest.mark.parametrize("cls", sorted(EXPECTED_HP))
def test_created_character_is_a_valid_combatant(cls):
    c = _build_combatant(cls)

    # Real ability mods, NOT the +0 fallback. STR 15 + 1 = 16 -> +3, CON 13 + 1 = 14 -> +2.
    assert c["str_mod"] == 3, f"{cls}: str_mod {c['str_mod']} (the +0 fallback?)"
    assert c["con_mod"] == 2
    assert c["dex_mod"] == 2
    assert c["abilities"]["str_score"] == 16

    # Per-class HP from the hit die + CON, not the 10 HP fallback.
    assert c["hp"] == EXPECTED_HP[cls], f"{cls}: hp {c['hp']} != {EXPECTED_HP[cls]}"
    assert c["max_hp"] == EXPECTED_HP[cls]

    # A real attack bonus (STR +3 + proficiency +2) and AC above the AC-10 fallback.
    assert c["attack_bonus"] == 5, f"{cls}: attack_bonus {c['attack_bonus']}"
    assert c["ac"] >= 12, f"{cls}: ac {c['ac']} (AC-10 fallback?)"
    # Combat lowercases class for feature checks; the stored value may be display-cased.
    assert c["class"].lower() == cls
    assert c["level"] == 1


def test_created_caster_carries_spellcasting():
    """A built full caster must come out with usable spellcasting (slots), not None."""
    c = _build_combatant("wizard")
    sc = c.get("spellcasting")
    assert sc, "wizard combatant has no spellcasting block"
    assert sc.get("spell_slots"), "wizard has no spell slots"
