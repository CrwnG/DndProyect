"""Batch 18: buff spells actually apply through the cast route.

The buff machinery (apply_spell_buffs and the attack/AC/save consumers) was built
in #14/#17/#20 and unit-tested directly — but nothing connected the cast route to
it. cast_spell only populated ``result.buff_effects`` inside a branch gated on
``effect_type == BUFF``, and:
  * Bless / Mage Armor are tagged UTILITY, so they never reached it.
  * _determine_buff_effects matched "shield of faith" / "mage armor" (spaces)
    against underscore ids, so it returned nothing for them.
  * Shield of Faith reached the branch but CRASHED on ``extra_data["buff"]=`` (the
    field defaults to None).
So in real play, casting Bless / Shield of Faith / Mage Armor did nothing (or 500'd).
"""
from app.core.combat_engine import CombatEngine, CombatState
from app.core.spell_system import SpellRegistry, cast_spell


def _caster(spell_id):
    return {
        "id": "c", "name": "Caster", "class": "cleric", "level": 5,
        "stats": {"wisdom": 16, "intelligence": 16},
        "spellcasting": {
            "ability": "wisdom", "spell_save_dc": 14, "spell_attack_bonus": 6,
            "spell_slots_max": {1: 4, 2: 3, 3: 2}, "spell_slots_used": {},
            "cantrips_known": [], "spells_known": [spell_id],
            "prepared_spells": [spell_id],
        },
    }


def _target():
    return {"id": "c", "name": "Caster", "current_hp": 20, "max_hp": 20,
            "ac": 12, "dex_mod": 2}


def test_bless_populates_buff_effects_through_cast():
    SpellRegistry.reset()
    r = cast_spell(_caster("bless"), "bless", 1, [_target()])
    assert r.success, r.description
    assert r.buff_effects, "Bless produced no buff_effects -> route applies nothing"
    assert r.buff_effects.get("attack_bonus_dice") == "1d4"
    assert r.buff_effects.get("save_bonus_dice") == "1d4"
    SpellRegistry.reset()


def test_shield_of_faith_does_not_crash_and_buffs_ac():
    SpellRegistry.reset()
    r = cast_spell(_caster("shield_of_faith"), "shield_of_faith", 1, [_target()])
    assert r.success, r.description
    assert r.buff_effects and r.buff_effects.get("ac_bonus") == 2
    SpellRegistry.reset()


def test_mage_armor_populates_base_ac_buff():
    SpellRegistry.reset()
    r = cast_spell(_caster("mage_armor"), "mage_armor", 1, [_target()])
    assert r.success, r.description
    assert r.buff_effects and r.buff_effects.get("base_ac") == 13
    SpellRegistry.reset()


def test_divine_favor_not_mistagged_as_bless():
    """The old `"1d4" in description and "attack"` heuristic wrongly gave Divine
    Favor (a +radiant-damage spell) Bless's attack/save dice."""
    SpellRegistry.reset()
    from app.core.spell_system import SpellEffectResolver
    sp = SpellRegistry.get_instance().get_spell("divine_favor")
    if sp is not None:
        eff = SpellEffectResolver._determine_buff_effects(sp)
        assert "attack_bonus_dice" not in eff
        assert "save_bonus_dice" not in eff
    SpellRegistry.reset()


def test_effective_ac_honors_mage_armor_floor():
    eng = CombatEngine(combat_state=CombatState())
    player = {"id": "wiz", "name": "Wiz", "type": "player", "hp": 14, "max_hp": 14,
              "ac": 12, "speed": 30, "dex_mod": 2,
              "abilities": {"strength": 8, "dexterity": 14, "constitution": 12,
                            "intelligence": 16, "wisdom": 10, "charisma": 10},
              "class": "wizard", "level": 3, "conditions": []}
    enemy = {"id": "gob", "name": "Gob", "type": "enemy", "hp": 10, "max_hp": 10,
             "ac": 12, "speed": 30,
             "abilities": {"strength": 10, "dexterity": 10, "constitution": 10,
                           "intelligence": 8, "wisdom": 8, "charisma": 8},
             "class": "monster", "level": 1, "conditions": []}
    eng.start_combat([player], [enemy])
    stats = eng.state.combatant_stats["wiz"]
    stats["active_buffs"] = [{"base_ac": 13}]            # Mage Armor

    # Unarmored 10+DEX(2)=12 -> Mage Armor floor 13+2=15.
    assert eng._effective_ac(stats, 12) == 15
    # Already armored above the floor -> unchanged.
    assert eng._effective_ac(stats, 18) == 18
    # Mage Armor stacks with Shield of Faith (+2 on top of the floor).
    stats["active_buffs"] = [{"base_ac": 13}, {"ac_bonus": 2}]
    assert eng._effective_ac(stats, 12) == 17
