"""Batch 32: spell ATTACK rolls honor condition-based advantage/disadvantage.

`resolve_attack_spell` rolled a plain d20 — it ignored advantage/disadvantage from ANY
source, so Fire Bolt / Eldritch Blast / Guiding Bolt etc. never got advantage against a
prone / restrained / stunned / paralyzed target, and a frightened/poisoned caster's
spell attack never took disadvantage. cast_spell now computes the condition modifiers
(via the shared get_attack_modifiers, off the conditions already on the caster + target
dicts) and passes them through. Faerie Fire (a concentration-gated buff, not a standard
condition) on spell attacks remains a separate follow-up.
"""
import app.core.spell_system as spell_system
from app.core.dice import D20Result
from app.core.spell_system import SpellRegistry, SpellEffectResolver, cast_spell


def _cap(cap):
    def fake(modifier=0, advantage=False, disadvantage=False):
        cap["advantage"] = advantage
        cap["disadvantage"] = disadvantage
        return D20Result(rolls=[15], modifier=modifier, total=15 + modifier)
    return fake


def _caster(*spells, conditions=None):
    return {"id": "wiz", "name": "Wiz", "class": "wizard", "level": 5,
            "conditions": conditions or [],
            "stats": {"intelligence": 18},
            "spellcasting": {"ability": "intelligence", "spell_save_dc": 15,
                             "spell_attack_bonus": 7, "spell_slots_max": {i: 3 for i in range(1, 6)},
                             "spell_slots_used": {}, "cantrips_known": list(spells),
                             "spells_known": list(spells), "prepared_spells": list(spells)}}


def _target(*conditions):
    return {"id": "ogre", "name": "Ogre", "current_hp": 40, "max_hp": 40, "ac": 13,
            "hp": 40, "conditions": list(conditions)}


def test_resolve_attack_spell_honors_advantage_param(monkeypatch):
    cap = {}
    monkeypatch.setattr(spell_system, "roll_d20", _cap(cap))
    sp = SpellRegistry.get_instance().get_spell("fire_bolt")
    SpellEffectResolver.resolve_attack_spell(sp, 7, 12, advantage=True)
    assert cap["advantage"] is True


def test_spell_attack_no_conditions_is_straight(monkeypatch):
    cap = {}
    monkeypatch.setattr(spell_system, "roll_d20", _cap(cap))
    cast_spell(_caster("fire_bolt"), "fire_bolt", 0, [_target()])
    assert cap["advantage"] is False and cap["disadvantage"] is False


def test_ranged_spell_attack_vs_restrained_target_has_advantage(monkeypatch):
    cap = {}
    monkeypatch.setattr(spell_system, "roll_d20", _cap(cap))
    cast_spell(_caster("fire_bolt"), "fire_bolt", 0, [_target("restrained")])
    assert cap["advantage"] is True


def test_ranged_spell_attack_vs_prone_target_has_disadvantage(monkeypatch):
    """Prone grants RANGED attackers disadvantage (melee would be advantage)."""
    cap = {}
    monkeypatch.setattr(spell_system, "roll_d20", _cap(cap))
    cast_spell(_caster("fire_bolt"), "fire_bolt", 0, [_target("prone")])
    assert cap["disadvantage"] is True and cap["advantage"] is False


def test_melee_spell_attack_vs_prone_target_has_advantage(monkeypatch):
    cap = {}
    monkeypatch.setattr(spell_system, "roll_d20", _cap(cap))
    cast_spell(_caster("shocking_grasp"), "shocking_grasp", 0, [_target("prone")])
    assert cap["advantage"] is True


def test_frightened_caster_spell_attack_has_disadvantage(monkeypatch):
    cap = {}
    monkeypatch.setattr(spell_system, "roll_d20", _cap(cap))
    cast_spell(_caster("fire_bolt", conditions=["frightened"]), "fire_bolt", 0, [_target()])
    assert cap["disadvantage"] is True


def test_spell_attack_with_none_conditions_does_not_crash(monkeypatch):
    """A conditions key explicitly set to None must not crash the attack (the get(...) or [])."""
    cap = {}
    monkeypatch.setattr(spell_system, "roll_d20", _cap(cap))
    caster = _caster("fire_bolt")
    caster["conditions"] = None
    target = _target()
    target["conditions"] = None
    r = cast_spell(caster, "fire_bolt", 0, [target])
    assert r.success
    assert cap["advantage"] is False and cap["disadvantage"] is False


def test_melee_spell_attack_vs_paralyzed_target_is_a_crit(monkeypatch):
    """A hit on a paralyzed target within 5 ft (melee spell attack) is a critical hit."""
    cap = {}
    monkeypatch.setattr(spell_system, "roll_d20", _cap(cap))     # total 15 + 7 = 22 hits AC 13
    r = cast_spell(_caster("shocking_grasp"), "shocking_grasp", 0, [_target("paralyzed")])
    assert r.hit is True and r.critical is True
