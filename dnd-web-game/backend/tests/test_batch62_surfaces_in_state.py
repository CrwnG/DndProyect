"""Batch 62 (V2): active surfaces are exposed in the combat state payload.

The A3 epic made surfaces real (placement, damage, decay, persistence) but the
frontend could never SHOW them: get_combat_state() didn't include them, so a burning
battlefield looked identical to an empty one. Now the payload carries a flat
[{x, y, type}] list the grid renderer can draw.
"""
from app.core.combat_engine import CombatEngine, CombatState, CombatPhase, TurnState


def _mk(cid, ctype):
    return {"id": cid, "name": cid, "type": ctype, "hp": 30, "max_hp": 30, "ac": 12,
            "speed": 30, "abilities": {"strength": 12, "dexterity": 12, "constitution": 14,
                                       "intelligence": 10, "wisdom": 10, "charisma": 10},
            "class": "wizard", "level": 5, "conditions": []}


def _engine():
    eng = CombatEngine(combat_state=CombatState())
    eng.start_combat([_mk("wiz", "player")], [_mk("gob", "enemy")],
                     positions={"wiz": (0, 0), "gob": (5, 5)})
    eng.state.phase = CombatPhase.COMBAT_ACTIVE
    eng.state.current_turn = TurnState(combatant_id="wiz")
    return eng


def test_state_payload_lists_active_surface_tiles():
    eng = _engine()
    eng.apply_spell_surfaces(["grease"], [(3, 3)], caster_id="wiz", spell_id="grease")

    surfaces = eng.get_combat_state()["surfaces"]
    tiles = {(s["x"], s["y"]) for s in surfaces}
    assert tiles == {(3, 3), (4, 3), (3, 4), (4, 4)}   # the 2x2 grease square
    assert all(s["type"] == "grease" for s in surfaces)


def test_state_payload_empty_when_no_surfaces():
    eng = _engine()
    assert eng.get_combat_state()["surfaces"] == []


def test_reloaded_combat_still_reports_surfaces():
    import json
    eng = _engine()
    eng.apply_spell_surfaces(["fire"], [(2, 2)], caster_id="wiz", spell_id="create_bonfire")
    eng2 = CombatEngine.from_dict(json.loads(json.dumps(eng.to_dict())))
    types = {s["type"] for s in eng2.get_combat_state()["surfaces"]}
    assert types == {"fire"}
