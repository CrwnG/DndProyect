"""Batch 31: spells that GRANT temporary HP (the producer side of Batch 30).

Batch 30 made temp HP a real damage buffer but nothing in play granted it. This wires
the grant: a structured `temp_hp` spell field -> cast_spell computes the amount (with
+5/slot scaling) -> result.temp_hp_granted -> the cast routes call grant_temp_hp. Proven
end-to-end via False Life (pure temp HP) and Armor of Agathys (its temp-HP buffer).
"""
from app.core.spell_system import SpellRegistry, cast_spell
from app.core.combat_engine import CombatEngine, CombatState


def _caster(*spells, level=5):
    return {"id": "wiz", "name": "Wiz", "class": "wizard", "level": level,
            "stats": {"intelligence": 18, "constitution": 14},
            "spellcasting": {"ability": "intelligence", "spell_save_dc": 15,
                             "spell_attack_bonus": 7, "spell_slots_max": {i: 3 for i in range(1, 6)},
                             "spell_slots_used": {}, "cantrips_known": [],
                             "spells_known": list(spells), "prepared_spells": list(spells)}}


def _self():
    return {"id": "wiz", "name": "Wiz", "current_hp": 20, "max_hp": 20, "ac": 12, "hp": 20}


def test_spell_model_parses_temp_hp():
    reg = SpellRegistry.get_instance()
    assert reg.get_spell("false_life").temp_hp == "2d4+4"
    assert reg.get_spell("armor_of_agathys").temp_hp == "5"


def test_false_life_grants_temp_hp():
    SpellRegistry.reset()
    r = cast_spell(_caster("false_life"), "false_life", 1, [_self()])
    assert r.success, r.description
    assert 6 <= r.temp_hp_granted["wiz"] <= 12                 # 2d4 + 4
    SpellRegistry.reset()


def test_false_life_upcast_scales_by_5_per_slot():
    SpellRegistry.reset()
    r = cast_spell(_caster("false_life"), "false_life", 3, [_self()])
    assert 16 <= r.temp_hp_granted["wiz"] <= 22                # +5/slot * 2 = +10
    SpellRegistry.reset()


def test_armor_of_agathys_grants_flat_temp_hp():
    SpellRegistry.reset()
    r = cast_spell(_caster("armor_of_agathys"), "armor_of_agathys", 1, [_self()])
    assert r.temp_hp_granted["wiz"] == 5
    SpellRegistry.reset()


def test_armor_of_agathys_upcast_scales():
    SpellRegistry.reset()
    r = cast_spell(_caster("armor_of_agathys"), "armor_of_agathys", 3, [_self()])
    assert r.temp_hp_granted["wiz"] == 15                      # 5 + 5*2
    SpellRegistry.reset()


def test_self_range_grant_always_targets_the_caster():
    """False Life is range Self: even if a different target is passed, the caster is buffed."""
    SpellRegistry.reset()
    other = {"id": "ally", "name": "Ally", "current_hp": 20, "max_hp": 20, "ac": 12, "hp": 20}
    r = cast_spell(_caster("false_life"), "false_life", 1, [other])
    assert "wiz" in r.temp_hp_granted and "ally" not in r.temp_hp_granted
    SpellRegistry.reset()


def test_temp_hp_grant_absorbs_damage_end_to_end():
    """Producer -> consumer: cast False Life, apply the grant like the route does, then
    damage must deplete temp HP before real HP (Batch 30 pipeline)."""
    SpellRegistry.reset()
    eng = CombatEngine(combat_state=CombatState())
    player = {"id": "wiz", "name": "Wiz", "type": "player", "hp": 20, "max_hp": 20, "ac": 12,
              "speed": 30, "abilities": {"strength": 8, "dexterity": 12, "constitution": 14,
                                         "intelligence": 18, "wisdom": 10, "charisma": 10},
              "class": "wizard", "level": 5, "conditions": []}
    enemy = {"id": "ogre", "name": "Ogre", "type": "enemy", "hp": 30, "max_hp": 30, "ac": 13,
             "speed": 30, "abilities": {"strength": 16, "dexterity": 8, "constitution": 16,
                                        "intelligence": 6, "wisdom": 7, "charisma": 7},
             "class": "monster", "level": 2, "conditions": []}
    eng.start_combat([player], [enemy])

    r = cast_spell(_caster("false_life"), "false_life", 1, [_self()])
    for tid, amt in (r.temp_hp_granted or {}).items():
        eng.grant_temp_hp(tid, amt)
    temp = eng.state.combatant_stats["wiz"]["temp_hp"]
    assert temp >= 6                                           # the grant landed

    eng.apply_spell_damage("wiz", 3)
    assert eng.state.combatant_stats["wiz"]["temp_hp"] == temp - 3   # depletes temp first
    assert eng.state.combatant_stats["wiz"]["current_hp"] == 20      # real HP untouched
    SpellRegistry.reset()
