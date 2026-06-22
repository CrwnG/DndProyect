"""Batch 17: stop prose-extraction from applying conditions a spell doesn't impose.

`_parse_combat_data` flags any condition WORD that appears in a spell's description
(`[c for c in conditions if c in description]`). That produces harmful false
positives:
  * Faerie Fire's text ("can't benefit from being Invisible") made it apply the
    `invisible` condition to enemies — making them HARDER to hit, the opposite of
    the spell.
  * Cure/prevent spells (Heal, Lesser/Greater Restoration, Freedom of Movement,
    Protection from Poison, …) mention the conditions they REMOVE, so they were
    applying blinded/poisoned/etc. to the very ally they target.

These are corrected per-spell so the genuine cases (Hold Person → paralyzed, Web →
restrained, real Invisibility → invisible) are untouched.
"""
from app.core.spell_system import SpellRegistry


def _spell(sid):
    sp = SpellRegistry.get_instance().get_spell(sid)
    assert sp is not None, f"{sid} not found"
    return sp


def test_cure_and_prevent_spells_impose_no_conditions():
    for sid in ["heal", "mass_heal", "lesser_restoration", "greater_restoration",
                "power_word_heal", "freedom_of_movement", "protection_from_poison",
                "mind_blank", "aura_of_purity", "heroes_feast",
                "protection_from_evil_and_good", "calm_emotions",
                "dispel_evil_and_good"]:
        assert _spell(sid).conditions_applied == [], \
            f"{sid} should impose nothing, got {_spell(sid).conditions_applied}"


def test_mention_only_spells_do_not_apply_invisible():
    for sid in ["faerie_fire", "branding_smite", "starry_wisp", "shield",
                "wall_of_force", "antimagic_field", "see_invisibility",
                "arcane_eye", "clairvoyance", "faithful_hound", "forcecage",
                "rope_trick", "scrying", "unseen_servant",
                "drawmijs_instant_summons"]:
        assert "invisible" not in (_spell(sid).conditions_applied or []), sid


def test_genuine_condition_spells_are_untouched():
    assert "paralyzed" in _spell("hold_person").conditions_applied
    assert "paralyzed" in _spell("hold_monster").conditions_applied
    assert "restrained" in _spell("web").conditions_applied
    assert "restrained" in _spell("entangle").conditions_applied
    assert "frightened" in _spell("fear").conditions_applied
    assert "charmed" in _spell("charm_person").conditions_applied
    assert "poisoned" in _spell("contagion").conditions_applied       # Contagion really poisons
    assert "blinded" in _spell("blindness_deafness").conditions_applied
    # Real invisibility still grants the invisible state (it's a self/ally buff).
    assert "invisible" in _spell("invisibility").conditions_applied
    assert "invisible" in _spell("greater_invisibility").conditions_applied
