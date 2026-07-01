"""Batch 54 (A3d): active surfaces survive a combat save/reload round-trip.

SurfaceManager has had to_dict/from_dict since A3a, but the engine's to_dict never
serialized it and from_dict rebuilt an empty manager — so any Grease/Wall of Fire/Web
on the battlefield silently vanished when a combat was rehydrated (golden rule #3:
state must survive a restart). Now the engine round-trips the manager's surfaces.
"""
import json

from app.core.combat_engine import CombatEngine, CombatState, CombatPhase, TurnState
from app.core.surfaces import SurfaceType


def _mk(cid, ctype, **over):
    base = {"id": cid, "name": cid, "type": ctype, "hp": 30, "max_hp": 30, "ac": 12,
            "speed": 30, "abilities": {"strength": 12, "dexterity": 12, "constitution": 14,
                                       "intelligence": 10, "wisdom": 10, "charisma": 10},
            "class": "fighter", "level": 3, "conditions": []}
    base.update(over)
    return base


def _engine():
    eng = CombatEngine(combat_state=CombatState())
    eng.start_combat([_mk("pc", "player")], [_mk("gob", "enemy")],
                     positions={"pc": (0, 0), "gob": (5, 5)})
    eng.state.phase = CombatPhase.COMBAT_ACTIVE
    eng.state.current_turn = TurnState(combatant_id="pc")
    return eng


def _roundtrip(eng):
    return CombatEngine.from_dict(json.loads(json.dumps(eng.to_dict())))


def test_active_surfaces_survive_serialization_roundtrip():
    eng = _engine()
    eng.state.surface_manager.add_surface(1, 0, SurfaceType.FIRE)
    eng.state.surface_manager.add_surface(3, 3, SurfaceType.GREASE)

    eng2 = _roundtrip(eng)

    assert eng2.state.surface_manager.get_surfaces_at(1, 0), "fire surface lost on reload"
    assert eng2.state.surface_manager.get_surfaces_at(3, 3), "grease surface lost on reload"
    types = {s.surface_type for s in eng2.state.surface_manager.get_surfaces_at(1, 0)}
    assert SurfaceType.FIRE in types


def test_reloaded_surface_still_damages_on_entry():
    eng = _engine()
    eng.state.surface_manager.add_surface(1, 0, SurfaceType.FIRE)

    eng2 = _roundtrip(eng)
    eng2.state.phase = CombatPhase.COMBAT_ACTIVE
    eng2.state.current_turn = TurnState(combatant_id="pc")
    eng2.state.combatant_stats["pc"]["dex_save"] = -11   # always fails the save -> full damage

    hp0 = eng2.state.combatant_stats["pc"]["current_hp"]
    result = eng2.move_combatant("pc", 1, 0)
    assert result.success
    assert eng2.state.combatant_stats["pc"]["current_hp"] < hp0


def test_surface_duration_survives_roundtrip():
    eng = _engine()
    eng.state.surface_manager.add_surface(1, 0, SurfaceType.FIRE, duration_rounds=3)

    eng2 = _roundtrip(eng)

    surfaces = eng2.state.surface_manager.get_surfaces_at(1, 0)
    assert surfaces and surfaces[0].duration_rounds == 3


def test_combat_without_surfaces_roundtrips_cleanly():
    eng = _engine()
    eng2 = _roundtrip(eng)
    assert eng2.state.surface_manager is not None
    assert not eng2.state.surface_manager.get_surfaces_at(1, 0)
