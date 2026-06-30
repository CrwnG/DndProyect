"""Batch 46: every advanced-AI role survives None spellcasting/equipment stats.

`_cache_combatant_stats` seeds `spellcasting` and `equipment` as an explicit `None` when a
combatant doesn't provide them. Several now-live AI paths did `stats.get("spellcasting", {})`
/ `stats.get("equipment", {})` (which returns None for a present-but-None key) and then
dereferenced it — so e.g. a spellcaster enemy crashed in `SpellcasterAI.__init__`, taking the
whole advanced AI down to the simple-AI fallback. All such derefs now use `or {}`.
"""
import pytest
from app.core.combat_engine import CombatEngine, CombatState, TurnState
from app.core.ai.tactical_ai import get_ai_for_role
from app.core.ai.coordination import coordinate_enemies


def _mk(cid, t, **o):
    base = {"id": cid, "name": cid, "type": t, "hp": 30, "max_hp": 30, "ac": 13, "speed": 30,
            "str_mod": 3, "dex_mod": 2, "attack_bonus": 5, "damage_dice": "1d8",
            "damage_type": "slashing",
            "abilities": {"strength": 16, "dexterity": 14, "constitution": 14,
                          "intelligence": 12, "wisdom": 12, "charisma": 10},
            "class": "monster", "level": 3, "conditions": []}
    base.update(o)
    return base


def _engine():
    eng = CombatEngine(combat_state=CombatState())
    eng.start_combat(
        [_mk("pc1", "player"), _mk("pc2", "player", hp=6, max_hp=30)],
        [_mk("e1", "enemy"), _mk("e2", "enemy")],
        positions={"pc1": (0, 0), "pc2": (1, 1), "e1": (5, 5), "e2": (6, 6)},
    )
    return eng


ROLES = ["melee_brute", "ranged_striker", "spellcaster", "support",
         "controller", "skirmisher", "minion", "boss"]


@pytest.mark.parametrize("role", ROLES)
def test_role_constructs_and_decides_with_none_stats(role):
    eng = _engine()
    assert eng.state.combatant_stats["e1"].get("spellcasting") is None  # seeded as None
    assert eng.state.combatant_stats["e1"].get("equipment") is None
    ai = get_ai_for_role(role, eng, "e1")     # SpellcasterAI.__init__ used to raise here
    decision = ai.decide_action()
    assert decision is not None and decision.action_type


def test_coordinate_enemies_runs_with_none_stats():
    eng = _engine()
    plan = coordinate_enemies(eng, ["e1", "e2"], ["pc1", "pc2"])
    assert plan is not None
