"""Batch 53 (A3c): standing in a surface hurts at turn start; surfaces decay over rounds.

A3a/A3b made surfaces damage on ENTRY and let spells create them, but a creature that just
STANDS in fire took no further damage, and surfaces never expired. `_start_current_turn` now
deals "standing in it" damage at the start of each turn and decays surface durations once per
round (via SurfaceManager.advance_round).
"""
from app.core.combat_engine import CombatEngine, CombatState, CombatPhase
from app.core.surfaces import SurfaceType


def _mk(cid, t):
    return {"id": cid, "name": cid, "type": t, "hp": 30, "max_hp": 30, "ac": 12, "speed": 30,
            "abilities": {"strength": 12, "dexterity": 12, "constitution": 14,
                          "intelligence": 10, "wisdom": 10, "charisma": 10},
            "class": "fighter", "level": 3, "conditions": []}


def _engine():
    eng = CombatEngine(combat_state=CombatState())
    eng.start_combat([_mk("pc", "player")], [_mk("gob", "enemy")],
                     positions={"pc": (0, 0), "gob": (1, 0)})
    eng.state.phase = CombatPhase.COMBAT_ACTIVE
    eng._start_current_turn()
    return eng


def test_apply_surface_turn_start_damages_a_standing_combatant():
    eng = _engine()
    eng.state.surface_manager.add_surface(0, 0, SurfaceType.FIRE)
    eng.state.combatant_stats["pc"]["dex_save"] = -11        # always fails -> full 1d4
    hp0 = eng.state.combatant_stats["pc"]["current_hp"]
    total, _ = eng._apply_surface_turn_start("pc", 0, 0)
    assert total > 0
    assert eng.state.combatant_stats["pc"]["current_hp"] < hp0


def test_turn_start_applies_standing_surface_damage_via_end_turn():
    eng = _engine()
    tr = eng.state.initiative_tracker
    order = [c.id for c in tr.combatants]
    cur = tr.get_current_combatant().id
    nxt = order[(order.index(cur) + 1) % len(order)]
    nx, ny = eng.state.positions[nxt]
    eng.state.surface_manager.add_surface(nx, ny, SurfaceType.FIRE)
    eng.state.combatant_stats[nxt]["dex_save"] = -11

    hp0 = eng.state.combatant_stats[nxt]["current_hp"]
    eng.end_turn()                                           # -> nxt's turn starts on the fire
    assert eng.state.combatant_stats[nxt]["current_hp"] < hp0


def test_surface_duration_decays_after_a_full_round():
    eng = _engine()
    eng.state.surface_manager.add_surface(4, 4, SurfaceType.FIRE, duration_rounds=1)
    assert eng.state.surface_manager.has_surface(4, 4, SurfaceType.FIRE)

    start_round = eng.state.initiative_tracker.current_round
    guard = 0
    while eng.state.initiative_tracker.current_round == start_round and guard < 20:
        eng.end_turn()
        guard += 1
    # The new round triggered advance_round, decaying the 1-round surface away.
    assert not eng.state.surface_manager.has_surface(4, 4, SurfaceType.FIRE)
