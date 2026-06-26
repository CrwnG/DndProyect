"""Batch 36: Faerie Fire grants advantage to SPELL attacks too (not just weapon attacks).

Weapon attacks honor the Faerie Fire "attacks against an outlined target have advantage"
buff (Batch 25), and spell attacks honor CONDITION-based advantage (Batch 32) — but the
Faerie Fire BUFF (a concentration-gated active_buff, not a standard condition) didn't reach
spell attacks, because cast_spell is pure and can't gate on the caster's concentration.
The route now pre-stamps a `_grants_attack_advantage` flag (engine-gated, like
stamp_save_buff) onto the target dict, and cast_spell's attack branch honors it — and, like
weapon attacks, suppresses the target's Invisible benefit while outlined.
"""
import app.core.spell_system as spell_system
from app.core.dice import D20Result
from app.core.combat_engine import CombatEngine, CombatState
from app.core.spell_system import SpellRegistry, cast_spell


def _cap(cap):
    def fake(modifier=0, advantage=False, disadvantage=False):
        cap["advantage"] = advantage
        cap["disadvantage"] = disadvantage
        return D20Result(rolls=[15], modifier=modifier, total=15 + modifier)
    return fake


def _caster(*spells):
    return {"id": "wiz", "name": "Wiz", "class": "wizard", "level": 5, "conditions": [],
            "stats": {"intelligence": 18},
            "spellcasting": {"ability": "intelligence", "spell_save_dc": 15,
                             "spell_attack_bonus": 7, "spell_slots_max": {i: 3 for i in range(1, 6)},
                             "spell_slots_used": {}, "cantrips_known": list(spells),
                             "spells_known": list(spells), "prepared_spells": list(spells)}}


def _target(*conditions, outlined=False):
    t = {"id": "ogre", "name": "Ogre", "current_hp": 40, "max_hp": 40, "ac": 13, "hp": 40,
         "conditions": list(conditions)}
    if outlined:
        t["_grants_attack_advantage"] = True
    return t


# ----------------------------- the stamp (engine, concentration-gated) ------

def _engine_with_faerie_fired_ogre():
    caster = {"id": "bard", "name": "Bard", "type": "player", "hp": 24, "max_hp": 24,
              "ac": 14, "speed": 30, "conditions": [],
              "abilities": {"strength": 10, "dexterity": 14, "constitution": 12,
                            "intelligence": 10, "wisdom": 10, "charisma": 16},
              "class": "bard", "level": 5}
    ogre = {"id": "ogre", "name": "Ogre", "type": "enemy", "hp": 40, "max_hp": 40, "ac": 13,
            "speed": 30, "conditions": [],
            "abilities": {"strength": 16, "dexterity": 8, "constitution": 16,
                          "intelligence": 6, "wisdom": 7, "charisma": 7},
            "class": "monster", "level": 3}
    eng = CombatEngine(combat_state=CombatState())
    eng.start_combat([caster], [ogre])
    eng.apply_spell_buffs("bard", {"attacks_against_advantage": True}, ["ogre"],
                          spell_id="faerie_fire")
    eng.state.combatant_stats["bard"]["spellcasting"] = {"concentrating_on": "faerie_fire"}
    return eng


def test_stamp_attack_advantage_when_outlined_and_concentrating():
    eng = _engine_with_faerie_fired_ogre()
    td = dict(eng.state.combatant_stats["ogre"])
    eng.stamp_attack_advantage(td)
    assert td.get("_grants_attack_advantage") is True


def test_stamp_attack_advantage_lifts_when_concentration_drops():
    eng = _engine_with_faerie_fired_ogre()
    eng.state.combatant_stats["bard"]["spellcasting"]["concentrating_on"] = None
    td = dict(eng.state.combatant_stats["ogre"])
    eng.stamp_attack_advantage(td)
    assert not td.get("_grants_attack_advantage")


# ----------------------------- cast_spell honors the flag -------------------

def test_spell_attack_vs_outlined_target_has_advantage(monkeypatch):
    cap = {}
    monkeypatch.setattr(spell_system, "roll_d20", _cap(cap))
    cast_spell(_caster("fire_bolt"), "fire_bolt", 0, [_target(outlined=True)])
    assert cap["advantage"] is True


def test_spell_attack_vs_normal_target_has_no_advantage(monkeypatch):
    cap = {}
    monkeypatch.setattr(spell_system, "roll_d20", _cap(cap))
    cast_spell(_caster("fire_bolt"), "fire_bolt", 0, [_target()])
    assert cap["advantage"] is False


def test_spell_attack_vs_outlined_invisible_target_suppresses_invisibility(monkeypatch):
    """An outlined target can't benefit from Invisible: the spell attacker no longer takes
    disadvantage, and Faerie Fire's advantage applies."""
    cap = {}
    monkeypatch.setattr(spell_system, "roll_d20", _cap(cap))
    cast_spell(_caster("fire_bolt"), "fire_bolt", 0, [_target("invisible", outlined=True)])
    assert cap["advantage"] is True
    assert cap["disadvantage"] is False
