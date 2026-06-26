"""Batch 40 (Durability P2): to_dict/from_dict round-trips the full engine state.

to_dict()/from_dict() captured phase/initiative/positions/combatant_stats/current_turn/
event_log but DROPPED the engine's grid (terrain/elevation/occupancy used for cover) and
the per-combat trackers — legendary_actions_remaining, monster_ability_recharge (recharge
abilities), frightful_presence_immune, reactions_used_this_round. So a rehydrated combat
lost line-of-sight/cover, let monsters re-use breath weapons, reset legendary actions, and
forgot who had reacted. They now round-trip.
"""
import json
from app.core.combat_engine import CombatEngine, CombatState
from app.core.movement import TerrainType


def _engine():
    player = {"id": "pc", "name": "PC", "type": "player", "hp": 30, "max_hp": 30, "ac": 14,
              "speed": 30, "class": "fighter", "level": 3,
              "abilities": {"strength": 16, "dexterity": 12, "constitution": 14,
                            "intelligence": 10, "wisdom": 10, "charisma": 10}}
    dragon = {"id": "drg", "name": "Dragon", "type": "enemy", "hp": 80, "max_hp": 80, "ac": 18,
              "speed": 40, "class": "monster", "level": 10,
              "abilities": {"strength": 20, "dexterity": 10, "constitution": 18,
                            "intelligence": 12, "wisdom": 12, "charisma": 14}}
    eng = CombatEngine(combat_state=CombatState())
    eng.start_combat([player], [dragon])
    return eng


def test_round_trip_preserves_trackers():
    eng = _engine()
    eng.state.legendary_actions_remaining["drg"] = 2
    eng.state.monster_ability_recharge["drg"] = {"breath_weapon": False}
    eng.state.frightful_presence_immune["drg"] = ["pc"]
    eng.state.reactions_used_this_round["pc"] = True

    eng2 = CombatEngine.from_dict(json.loads(json.dumps(eng.to_dict())))

    assert eng2.state.legendary_actions_remaining.get("drg") == 2
    assert eng2.state.monster_ability_recharge.get("drg") == {"breath_weapon": False}
    assert eng2.state.frightful_presence_immune.get("drg") == ["pc"]
    assert eng2.state.reactions_used_this_round.get("pc") is True


def test_round_trip_preserves_grid_terrain_and_occupancy():
    eng = _engine()
    assert eng.state.grid is not None
    eng.state.grid.set_terrain(2, 2, TerrainType.DIFFICULT)
    eng.state.grid.set_occupant(3, 3, "pc")

    eng2 = CombatEngine.from_dict(json.loads(json.dumps(eng.to_dict())))

    assert eng2.state.grid is not None
    assert eng2.state.grid.get_cell(2, 2).terrain == TerrainType.DIFFICULT
    assert eng2.state.grid.get_cell(3, 3).occupied_by == "pc"
    assert eng2.state.grid.width == eng.state.grid.width
