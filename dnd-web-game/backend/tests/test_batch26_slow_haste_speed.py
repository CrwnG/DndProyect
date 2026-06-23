"""Batch 26: Slow becomes a real debuff, and movement honors speed multipliers.

Slow (a 2024 control spell) cast successfully but did NOTHING — it has a DEX save,
no damage, no condition, so it fell through to the standard-save branch and produced
no effect. It's now a debuff (reusing the Bane failed-save path): -2 AC and HALF
speed on a failed save. The speed half/double is honored by a shared
``_speed_multiplier`` in ``_get_effective_speed``, which also finally makes Haste's
stored ``speed_multiplier`` (x2 movement) take effect.
"""
from app.core.combat_engine import CombatEngine, CombatState
from app.core.spell_system import SpellRegistry, SpellEffectResolver, cast_spell


def _engine():
    player = {"id": "hero", "name": "Hero", "type": "player", "hp": 24, "max_hp": 24,
              "ac": 15, "speed": 30, "str_mod": 3, "attack_bonus": 5,
              "abilities": {"strength": 16, "dexterity": 12, "constitution": 14,
                            "intelligence": 10, "wisdom": 10, "charisma": 10},
              "class": "fighter", "level": 3, "conditions": []}
    enemy = {"id": "ogre", "name": "Ogre", "type": "enemy", "hp": 30, "max_hp": 30,
             "ac": 13, "speed": 30,
             "abilities": {"strength": 16, "dexterity": 8, "constitution": 16,
                           "intelligence": 6, "wisdom": 7, "charisma": 7},
             "class": "monster", "level": 2, "conditions": []}
    eng = CombatEngine(combat_state=CombatState())
    eng.start_combat([player], [enemy])
    return eng


def test_speed_multiplier_combines_active_buffs_and_gates_on_concentration():
    eng = _engine()
    stats = eng.state.combatant_stats["hero"]
    assert eng._speed_multiplier(stats) == 1.0                     # no buffs

    stats["active_buffs"] = [{"speed_multiplier": 2}]              # Haste (untagged)
    assert eng._speed_multiplier(stats) == 2.0
    stats["active_buffs"] = [{"speed_multiplier": 0.5}]            # Slow
    assert eng._speed_multiplier(stats) == 0.5
    stats["active_buffs"] = [{"speed_multiplier": 2}, {"speed_multiplier": 0.5}]
    assert eng._speed_multiplier(stats) == 1.0                     # net out

    # Concentration-gated: a tagged multiplier only counts while the caster holds it.
    stats["spellcasting"] = {"concentrating_on": None}
    stats["active_buffs"] = [{"source": "x", "spell_id": "haste", "speed_multiplier": 2}]
    assert eng._speed_multiplier(stats) == 1.0                     # caster not concentrating


def test_effective_speed_doubles_for_haste_and_halves_for_slow():
    eng = _engine()
    stats = eng.state.combatant_stats["hero"]
    base = eng._get_effective_speed("hero", stats)
    assert base == 30

    stats["active_buffs"] = [{"speed_multiplier": 2}]
    assert eng._get_effective_speed("hero", stats) == 60          # Haste
    stats["active_buffs"] = [{"speed_multiplier": 0.5}]
    assert eng._get_effective_speed("hero", stats) == 15          # Slow


def test_slow_is_a_debuff():
    sp = SpellRegistry.get_instance().get_spell("slow")
    eff = SpellEffectResolver._determine_debuff_effects(sp)
    assert eff == {"ac_bonus": -2, "speed_multiplier": 0.5}


def test_slow_uses_a_wisdom_save():
    """RAW Slow is a WISDOM save (the prose extractor used to grab 'Dexterity saving
    throws' from the -2 penalty text before the real 'Wisdom saving throw')."""
    assert SpellRegistry.get_instance().get_spell("slow").save_type == "wisdom"


def test_casting_slow_debuffs_failed_save_targets():
    SpellRegistry.reset()
    caster = {"id": "wiz", "name": "Wiz", "class": "wizard", "level": 9,
              "stats": {"intelligence": 18},
              "spellcasting": {"ability": "intelligence", "spell_save_dc": 16,
                               "spell_attack_bonus": 8, "spell_slots_max": {3: 3},
                               "spell_slots_used": {}, "cantrips_known": [],
                               "spells_known": ["slow"], "prepared_spells": ["slow"]}}
    # WIS save (the real ability); a big penalty makes the failed-save path deterministic.
    failer = {"id": "f", "name": "Failer", "current_hp": 30, "max_hp": 30, "ac": 13,
              "wis_save": -100}
    r = cast_spell(caster, "slow", 3, [failer])
    assert r.success, r.description
    assert r.debuffs_applied and "f" in r.debuffs_applied
    assert r.debuffs_applied["f"]["speed_multiplier"] == 0.5
    assert r.debuffs_applied["f"]["ac_bonus"] == -2
    SpellRegistry.reset()


def test_slowed_enemy_is_easier_to_hit_and_at_half_speed():
    """End-to-end: a Slow debuff applied to an enemy lowers its effective AC by 2 and
    halves its movement speed (gated on the caster's concentration)."""
    eng = _engine()
    eng.apply_spell_buffs("hero", {"ac_bonus": -2, "speed_multiplier": 0.5},
                          ["ogre"], spell_id="slow")
    eng.state.combatant_stats["hero"]["spellcasting"] = {"concentrating_on": "slow"}
    og = eng.state.combatant_stats["ogre"]

    assert eng._effective_ac(og, 13) == 11                        # 13 - 2
    assert eng._get_effective_speed("ogre", og) == 15             # 30 / 2

    # Caster loses concentration -> Slow lifts.
    eng.state.combatant_stats["hero"]["spellcasting"]["concentrating_on"] = None
    assert eng._effective_ac(og, 13) == 13
    assert eng._get_effective_speed("ogre", og) == 30
