"""Batch 52 (A3b): surface-creating spells actually place a surface on the battlefield.

A3a made surfaces live on movement, but nothing CREATED them in play. Grease, Wall of Fire,
Web, Wall of Ice, and Cloudkill now mark `surfaces_created` on the cast result, and the engine
places the surface at the targeted tiles (the combat cast route calls `apply_spell_surfaces`),
so a creature later moving onto e.g. grease is affected.
"""
from app.core.spell_system import SpellRegistry, SpellEffectResolver, cast_spell
from app.core.combat_engine import CombatEngine, CombatState, CombatPhase, TurnState
from app.core.surfaces import SurfaceType


def test_determine_surface_created_maps_known_spells():
    reg = SpellRegistry.get_instance()
    assert SpellEffectResolver._determine_surface_created(reg.get_spell("grease")) == "grease"
    assert SpellEffectResolver._determine_surface_created(reg.get_spell("wall_of_fire")) == "fire"
    assert SpellEffectResolver._determine_surface_created(reg.get_spell("web")) == "web"
    assert SpellEffectResolver._determine_surface_created(reg.get_spell("wall_of_ice")) == "ice"
    assert SpellEffectResolver._determine_surface_created(reg.get_spell("fireball")) is None


def test_cast_grease_sets_surfaces_created():
    sc = {"ability": "intelligence", "spell_save_dc": 15, "spell_attack_bonus": 7,
          "spell_slots": {"1": 4}, "prepared_spells": ["grease"]}
    caster = {"id": "w", "name": "W", "level": 5, "spellcasting": sc, "int_mod": 4}
    r = cast_spell(caster, "grease", 1, [{"id": "t", "name": "t", "position": (2, 2)}])
    assert r.surfaces_created == ["grease"]


def _engine():
    mk = lambda cid, t: {"id": cid, "name": cid, "type": t, "hp": 30, "max_hp": 30, "ac": 12,
                         "speed": 30, "abilities": {"strength": 12, "dexterity": 12, "constitution": 14,
                                                    "intelligence": 10, "wisdom": 10, "charisma": 10},
                         "class": "fighter", "level": 3, "conditions": []}
    eng = CombatEngine(combat_state=CombatState())
    eng.start_combat([mk("pc", "player")], [mk("gob", "enemy")],
                     positions={"pc": (0, 0), "gob": (5, 5)})
    eng.state.phase = CombatPhase.COMBAT_ACTIVE
    eng.state.current_turn = TurnState(combatant_id="pc")
    return eng


def test_apply_spell_surfaces_places_surface_on_grid():
    eng = _engine()
    n = eng.apply_spell_surfaces(["grease"], [(1, 0)], caster_id="w", spell_id="grease")
    assert n == 4   # batch 57: grease covers its real 10-ft square (2x2 tiles)
    assert eng.state.surface_manager.has_surface(1, 0, SurfaceType.GREASE)


def test_created_fire_surface_damages_a_mover():
    eng = _engine()
    eng.apply_spell_surfaces(["fire"], [(1, 0)], caster_id="w", spell_id="wall_of_fire")
    eng.state.combatant_stats["pc"]["dex_save"] = -11   # always fails -> full 1d4
    hp0 = eng.state.combatant_stats["pc"]["current_hp"]
    eng.move_combatant("pc", 1, 0)
    assert eng.state.combatant_stats["pc"]["current_hp"] < hp0
