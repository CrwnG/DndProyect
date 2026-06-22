"""Batch 14: AC buffs (Shield of Faith / Haste) are honored by the reaction
resolver.

Batch 12 centralized AC buffs through CombatEngine._effective_ac in the main
attack-resolution paths, but the /combat/reaction route still read raw
``stats.get("ac")`` for opportunity attacks, the Shield spell, and Riposte — so a
defender's +2 AC silently vanished the moment a reaction was involved. These tests
drive the route function directly (DB persistence stubbed) and assert the buffed
AC is what reaches each resolver.
"""
import pytest

from app.core.reactions import ReactionsManager, ReactionResult, ReactionType
import app.api.routes.combat as combat_routes
from app.api.routes.combat import use_reaction, ReactionRequest


def _combatant(cid, name, ctype, ac):
    return {
        "id": cid, "name": name, "type": ctype,
        "hp": 20, "max_hp": 20, "ac": ac, "speed": 30,
        "attack_bonus": 5, "damage_dice": "1d8", "damage_type": "slashing",
        "str_mod": 3, "superiority_dice": 4,
        "abilities": {"strength": 16, "dexterity": 14, "constitution": 14,
                      "intelligence": 12, "wisdom": 10, "charisma": 10},
        "class": "fighter", "level": 5, "conditions": [],
    }


def _setup(reactor_ac=13, reactor_buffs=None, reactor_slots=None,
           target_ac=13, target_buffs=None):
    from app.core.combat_engine import CombatEngine, CombatState
    reactor = _combatant("mage", "Mage", "player", reactor_ac)
    target = _combatant("orc", "Orc", "enemy", target_ac)
    eng = CombatEngine(combat_state=CombatState())
    eng.start_combat([reactor], [target])
    if reactor_buffs is not None:
        eng.state.combatant_stats["mage"]["active_buffs"] = reactor_buffs
    if reactor_slots is not None:
        eng.state.combatant_stats["mage"]["spell_slots"] = reactor_slots
    if target_buffs is not None:
        eng.state.combatant_stats["orc"]["active_buffs"] = target_buffs

    cid = "combat-1"
    combat_routes.active_combats[cid] = eng
    mgr = ReactionsManager()
    mgr.register_combatant("mage")
    mgr.register_combatant("orc")
    combat_routes.reactions_managers[cid] = mgr
    return eng, cid


@pytest.fixture(autouse=True)
def _no_persist(monkeypatch):
    async def _noop(*args, **kwargs):
        return None
    monkeypatch.setattr(combat_routes, "persist_combat_state", _noop)


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    combat_routes.active_combats.pop("combat-1", None)
    combat_routes.reactions_managers.pop("combat-1", None)


async def test_shield_reaction_uses_reactor_ac_buff():
    """The Shield reaction (+5 AC) stacks on top of an active AC buff. A reactor
    with base AC 13 + Shield of Faith (+2) is at 15; Shield brings it to 20, so an
    attack roll of 19 should MISS. Without the buff it would be AC 18 and hit."""
    eng, cid = _setup(reactor_ac=13, reactor_buffs=[{"ac_bonus": 2}],
                      reactor_slots={1: 1})
    req = ReactionRequest(
        combat_id=cid, reaction_type="shield", trigger_source_id="orc",
        extra_data={"reactor_id": "mage", "attack_roll": 19,
                    "incoming_damage": 8, "pre_hit_hp": 20},
    )
    resp = await use_reaction(req, combat_repo=None)
    assert "misses" in resp.description
    assert "still hits" not in resp.description


async def test_opportunity_attack_uses_target_ac_buff(monkeypatch):
    """An opportunity attack must resolve against the fleeing target's BUFFED AC."""
    captured = {}

    def _spy(**kwargs):
        captured.update(kwargs)
        return ReactionResult(success=True,
                              reaction_type=ReactionType.OPPORTUNITY_ATTACK.value,
                              description="spy", damage_dealt=0)

    monkeypatch.setattr(combat_routes, "resolve_opportunity_attack", _spy)
    eng, cid = _setup(target_ac=10, target_buffs=[{"ac_bonus": 5}])
    req = ReactionRequest(
        combat_id=cid, reaction_type="opportunity_attack",
        trigger_source_id="orc", extra_data={"reactor_id": "mage"},
    )
    await use_reaction(req, combat_repo=None)
    assert captured["target_ac"] == 15        # base 10 + buff 5


async def test_riposte_uses_target_ac_buff(monkeypatch):
    """Battlemaster Riposte must resolve against the target's BUFFED AC."""
    captured = {}

    def _spy(**kwargs):
        captured.update(kwargs)
        return ReactionResult(success=True,
                              reaction_type=ReactionType.RIPOSTE.value,
                              description="spy", damage_dealt=0)

    monkeypatch.setattr(combat_routes, "resolve_riposte", _spy)
    eng, cid = _setup(target_ac=12, target_buffs=[{"ac_bonus": 2}])
    req = ReactionRequest(
        combat_id=cid, reaction_type="riposte",
        trigger_source_id="orc", extra_data={"reactor_id": "mage"},
    )
    await use_reaction(req, combat_repo=None)
    assert captured["target_ac"] == 14        # base 12 + buff 2
