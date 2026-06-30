"""Batch 51 (A3a): hazardous surfaces are live — moving onto one deals damage.

The SurfaceManager (13 BG3-style surface types: fire/grease/ice/oil/electrified water…) and
the engine's surface-processing existed, but `CombatState.surface_manager` was never created
and the regular `move_combatant` path didn't process surfaces — so surfaces were dead. Now
`start_combat` builds a SurfaceManager and entering a hazardous tile applies its damage
(through the resist/temp-HP/defeat chokepoint) and conditions.
"""
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


def test_start_combat_initializes_surface_manager():
    eng = _engine()
    assert eng.state.surface_manager is not None


def test_moving_onto_fire_surface_deals_damage():
    eng = _engine()
    eng.state.surface_manager.add_surface(1, 0, SurfaceType.FIRE)
    eng.state.combatant_stats["pc"]["dex_save"] = -11   # always fails the DC 10 save -> full 1d4

    hp0 = eng.state.combatant_stats["pc"]["current_hp"]
    result = eng.move_combatant("pc", 1, 0)
    hp1 = eng.state.combatant_stats["pc"]["current_hp"]

    assert result.success
    assert hp1 < hp0                       # took 1d4 fire damage on entry
    assert eng.state.positions["pc"] == (1, 0)


def test_moving_onto_empty_tile_deals_no_surface_damage():
    eng = _engine()
    hp0 = eng.state.combatant_stats["pc"]["current_hp"]
    eng.move_combatant("pc", 1, 0)         # no surface here
    assert eng.state.combatant_stats["pc"]["current_hp"] == hp0


def test_reloaded_combat_still_processes_surfaces():
    """A combat rehydrated from a snapshot must keep a working surface manager so newly
    created surfaces still resolve (active surfaces aren't persisted yet)."""
    import json
    eng = _engine()
    eng2 = CombatEngine.from_dict(json.loads(json.dumps(eng.to_dict())))
    assert eng2.state.surface_manager is not None
    eng2.state.phase = CombatPhase.COMBAT_ACTIVE
    eng2.state.current_turn = TurnState(combatant_id="pc")
    eng2.state.surface_manager.add_surface(1, 0, SurfaceType.FIRE)
    eng2.state.combatant_stats["pc"]["dex_save"] = -11
    hp0 = eng2.state.combatant_stats["pc"]["current_hp"]
    eng2.move_combatant("pc", 1, 0)
    assert eng2.state.combatant_stats["pc"]["current_hp"] < hp0
