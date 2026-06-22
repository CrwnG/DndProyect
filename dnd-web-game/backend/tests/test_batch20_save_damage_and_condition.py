"""Batch 20: save spells that deal damage AND impose a condition do BOTH.

The save-branch dispatch in cast_spell was if-area-damage / elif-conditions /
else-standard, so a spell with both effects only got ONE:
  * single-target save+damage+condition (Phantasmal Killer 4d10, Blinding Smite,
    Prismatic Spray 12d6, Psychic Scream 14d6, …) hit the `elif conditions` path
    and dealt ZERO damage.
  * area save+damage+condition (Sunburst 12d6 + blinded, Weird, Whirlwind) hit the
    area-damage path and never applied the condition.
Both effects now resolve off the same per-target save.
"""
from app.core.spell_system import SpellRegistry, cast_spell


def _caster(spell_id, ability="intelligence"):
    return {
        "id": "c", "name": "Caster", "class": "wizard", "level": 17,
        "stats": {ability: 18},
        "spellcasting": {
            "ability": ability, "spell_save_dc": 16, "spell_attack_bonus": 8,
            "spell_slots_max": {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1, 9: 1},
            "spell_slots_used": {},
            "cantrips_known": [], "spells_known": [spell_id], "prepared_spells": [spell_id],
        },
    }


def _target(tid, save_mod):
    t = {"id": tid, "name": tid, "current_hp": 100, "max_hp": 100, "ac": 14,
         "position": {"x": 0, "y": 0}}
    for ab in ("str", "dex", "con", "int", "wis", "cha"):
        t[f"{ab}_save"] = save_mod
    return t


def test_single_target_save_spell_deals_damage_and_condition_on_fail():
    SpellRegistry.reset()
    failer = _target("f", -100)                         # always fails the save
    r = cast_spell(_caster("phantasmal_killer"), "phantasmal_killer", 4, [failer])
    assert r.success, r.description
    assert (r.damage_dealt or {}).get("f", 0) > 0, "damage was dropped"
    assert "frightened" in (r.conditions_applied or {}).get("f", [])
    SpellRegistry.reset()


def test_single_target_save_spell_saver_no_condition():
    SpellRegistry.reset()
    saver = _target("s", 100)                           # always saves
    r = cast_spell(_caster("phantasmal_killer"), "phantasmal_killer", 4, [saver])
    assert r.success, r.description
    assert "s" not in (r.conditions_applied or {})      # no condition on a save
    # Phantasmal Killer doesn't set half_damage_on_save -> a save deals NO damage.
    assert (r.damage_dealt or {}).get("s", 0) == 0
    SpellRegistry.reset()


def test_area_save_spell_deals_damage_and_condition_on_fail():
    SpellRegistry.reset()
    failer = _target("f", -100)
    r = cast_spell(_caster("sunburst"), "sunburst", 8, [failer])
    assert r.success, r.description
    assert (r.damage_dealt or {}).get("f", 0) > 0
    assert "blinded" in (r.conditions_applied or {}).get("f", [])
    SpellRegistry.reset()


def test_area_save_spell_saver_takes_no_condition():
    SpellRegistry.reset()
    saver = _target("s", 100)
    r = cast_spell(_caster("sunburst"), "sunburst", 8, [saver])
    assert r.success, r.description
    assert "s" not in (r.conditions_applied or {})
    SpellRegistry.reset()
