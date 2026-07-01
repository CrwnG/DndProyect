"""Batch 56 (A2b-lite): Flaming Sphere rides the active_summons scaffolding.

Unlike Spiritual Weapon (melee spell attack), the sphere is save-based: a creature
ending its turn within 5 ft makes a Dex save (2d6 fire, half on success; +1d6 per slot
level above 2), and the caster's bonus action moves it up to 30 ft — ramming a creature
within 5 ft of its new position forces the same save. It makes NO on-cast attack.
"""
from app.core.combat_engine import (
    CombatEngine, CombatState, CombatPhase, TurnState, BonusActionType,
)
from app.core.spell_system import SpellRegistry, SpellEffectResolver


def _mk(cid, ctype, **over):
    base = {"id": cid, "name": cid, "type": ctype, "hp": 30, "max_hp": 30, "ac": 12,
            "speed": 30, "abilities": {"strength": 12, "dexterity": 12, "constitution": 14,
                                       "intelligence": 10, "wisdom": 16, "charisma": 10},
            "class": "druid", "level": 5, "conditions": []}
    base.update(over)
    return base


def _engine():
    eng = CombatEngine(combat_state=CombatState())
    eng.start_combat([_mk("dru", "player")], [_mk("gob", "enemy")],
                     positions={"dru": (0, 0), "gob": (1, 0)})
    eng.state.phase = CombatPhase.COMBAT_ACTIVE
    eng.state.current_turn = TurnState(combatant_id="dru")
    eng.state.combatant_stats["dru"]["spellcasting"] = {
        "ability": "wisdom", "spell_save_dc": 14, "spell_attack_bonus": 6,
        "spell_slots": {"2": 3}, "prepared_spells": ["flaming_sphere"],
        "concentrating_on": "flaming_sphere",
    }
    return eng


def _sphere(eng, pos):
    eng.apply_spell_summon(
        "dru",
        {"summon_id": "flaming_sphere", "damage": "2d6", "damage_type": "fire",
         "move_speed": 30, "save": "dex", "aura": 5},
        pos, spell_id="flaming_sphere",
    )


def test_determine_summon_recognizes_flaming_sphere_with_upcast():
    reg = SpellRegistry.get_instance()
    spell = reg.get_spell("flaming_sphere")
    s2 = SpellEffectResolver._determine_summon_created(spell, 2)
    assert s2 and s2["summon_id"] == "flaming_sphere"
    assert s2["damage"] == "2d6" and s2["save"] == "dex" and s2["damage_type"] == "fire"
    assert not s2.get("on_cast_attack")     # appears in an unoccupied space: no cast attack
    s4 = SpellEffectResolver._determine_summon_created(spell, 4)
    assert s4["damage"] == "4d6"            # +1d6 per slot level above 2


def test_spiritual_weapon_still_flags_on_cast_attack():
    reg = SpellRegistry.get_instance()
    sw = SpellEffectResolver._determine_summon_created(reg.get_spell("spiritual_weapon"), 2)
    assert sw.get("on_cast_attack") is True


def test_ram_forces_save_damage_and_failed_save_hurts_more():
    eng = _engine()
    _sphere(eng, (5, 0))
    eng.state.combatant_stats["gob"]["dex_save"] = -30    # always fails -> full damage

    hp0 = eng.state.combatant_stats["gob"]["current_hp"]
    result = eng.summon_attack("dru", "flaming_sphere", "gob", move_to=(2, 0))
    assert result.success
    full = hp0 - eng.state.combatant_stats["gob"]["current_hp"]
    assert full >= 2                                       # 2d6 full damage

    eng2 = _engine()
    _sphere(eng2, (2, 0))
    eng2.state.combatant_stats["gob"]["dex_save"] = 30     # always saves -> half
    hp0 = eng2.state.combatant_stats["gob"]["current_hp"]
    result2 = eng2.summon_attack("dru", "flaming_sphere", "gob")
    assert result2.success
    half = hp0 - eng2.state.combatant_stats["gob"]["current_hp"]
    assert half <= 6                                       # at most half of max 12


def test_ending_turn_next_to_sphere_burns():
    eng = _engine()
    _sphere(eng, (2, 0))                                   # gob at (1,0): within 5 ft
    eng.state.combatant_stats["gob"]["dex_save"] = -30
    eng.state.current_turn = TurnState(combatant_id="gob")
    eng.state.initiative_tracker.current_turn_index = next(
        i for i, c in enumerate(eng.state.initiative_tracker.combatants) if c.id == "gob")

    hp0 = eng.state.combatant_stats["gob"]["current_hp"]
    eng.end_turn()
    assert eng.state.combatant_stats["gob"]["current_hp"] < hp0


def test_ending_turn_far_from_sphere_is_safe():
    eng = _engine()
    _sphere(eng, (6, 6))                                   # far from gob at (1,0)
    eng.state.current_turn = TurnState(combatant_id="gob")
    eng.state.initiative_tracker.current_turn_index = next(
        i for i, c in enumerate(eng.state.initiative_tracker.combatants) if c.id == "gob")

    hp0 = eng.state.combatant_stats["gob"]["current_hp"]
    eng.end_turn()
    assert eng.state.combatant_stats["gob"]["current_hp"] == hp0


def test_aura_gated_by_concentration():
    eng = _engine()
    _sphere(eng, (2, 0))
    eng.state.combatant_stats["dru"]["spellcasting"]["concentrating_on"] = None
    eng.state.combatant_stats["gob"]["dex_save"] = -30
    eng.state.current_turn = TurnState(combatant_id="gob")
    eng.state.initiative_tracker.current_turn_index = next(
        i for i, c in enumerate(eng.state.initiative_tracker.combatants) if c.id == "gob")

    hp0 = eng.state.combatant_stats["gob"]["current_hp"]
    eng.end_turn()
    assert eng.state.combatant_stats["gob"]["current_hp"] == hp0
