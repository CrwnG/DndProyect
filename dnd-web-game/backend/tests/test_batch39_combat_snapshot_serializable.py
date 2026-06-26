"""Batch 39 (Durability P1): the combat snapshot (to_dict) must be JSON-serializable.

Combat events store raw roll objects in their `data` (e.g. an attack's `roll` is a
`D20Result` dataclass). `to_dict()` emitted `e.data` verbatim, so persisting the engine
snapshot to the DB's JSON column raised `TypeError: Object of type D20Result is not JSON
serializable` -> the session commit rolled back and durable save/resume was broken. The
snapshot now sanitizes event data into JSON-safe values (dataclasses -> dicts).
"""
import json
from app.core.combat_engine import CombatEngine, CombatState, ActionType, TurnState


def _engine_after_attack():
    player = {"id": "pc", "name": "Hero", "type": "player", "hp": 28, "max_hp": 28, "ac": 10,
              "str_mod": 3, "attack_bonus": 5, "damage_dice": "1d8", "damage_type": "slashing",
              "speed": 30, "class": "fighter", "level": 3,
              "abilities": {"strength": 16, "dexterity": 12, "constitution": 14,
                            "intelligence": 10, "wisdom": 10, "charisma": 10}}
    enemy = {"id": "gob", "name": "Goblin", "type": "enemy", "hp": 15, "max_hp": 15, "ac": 1,
             "speed": 30, "class": "monster", "level": 1,
             "abilities": {"strength": 8, "dexterity": 14, "constitution": 10,
                           "intelligence": 10, "wisdom": 8, "charisma": 8}}
    eng = CombatEngine(combat_state=CombatState())
    eng.start_combat([player], [enemy])
    eng.state.positions["pc"] = (0, 0)
    eng.state.positions["gob"] = (1, 0)
    tr = eng.state.initiative_tracker
    tr.current_turn_index = next(i for i, c in enumerate(tr.combatants) if c.id == "pc")
    eng.state.current_turn = TurnState(combatant_id="pc")
    eng.take_action(ActionType.ATTACK, target_id="gob", weapon_name="longsword")
    return eng


def test_to_dict_is_json_serializable_after_an_attack():
    eng = _engine_after_attack()
    blob = json.dumps(eng.to_dict())            # must NOT raise (was D20Result TypeError)
    assert isinstance(blob, str) and len(blob) > 0


def test_snapshot_round_trips_through_from_dict():
    eng = _engine_after_attack()
    snap = json.loads(json.dumps(eng.to_dict()))
    eng2 = CombatEngine.from_dict(snap)
    assert eng2.state.combatant_stats.get("pc") is not None
    assert eng2.state.combatant_stats.get("gob") is not None


def test_event_roll_objects_become_serializable_dicts():
    """A persisted attack-roll keeps its info as a JSON object (with a numeric total),
    not a dropped/stringified value."""
    eng = _engine_after_attack()
    events = eng.to_dict()["combat_state"]["event_log"]
    roll_dicts = [d for e in events for d in (e["data"].get("roll"), e["data"].get("attack_roll"))
                  if isinstance(d, dict)]
    assert roll_dicts, "expected at least one roll serialized as a dict"
    assert all(isinstance(d.get("total"), int) for d in roll_dicts)
