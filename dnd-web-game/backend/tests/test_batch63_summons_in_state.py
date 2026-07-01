"""Batch 63 (G1): summons are visible in the state payload and playable as bonus actions.

A2a/A2b made Spiritual Weapon and Flaming Sphere mechanically real, but the client had
no way to SEE them (not in get_combat_state) and Flaming Sphere had no BonusActionType,
so its ram was unreachable through the action route. Now the payload carries
summons: [{id, owner_id, x, y}] (concentration-gated) and both summons dispatch through
take_bonus_action.
"""
from app.core.combat_engine import (
    CombatEngine, CombatState, CombatPhase, TurnState, BonusActionType,
)


def _mk(cid, ctype, **over):
    base = {"id": cid, "name": cid, "type": ctype, "hp": 30, "max_hp": 30, "ac": 12,
            "speed": 30, "abilities": {"strength": 12, "dexterity": 12, "constitution": 14,
                                       "intelligence": 10, "wisdom": 16, "charisma": 10},
            "class": "cleric", "level": 5, "conditions": []}
    base.update(over)
    return base


def _engine():
    eng = CombatEngine(combat_state=CombatState())
    eng.start_combat([_mk("cle", "player")], [_mk("gob", "enemy", ac=1)],
                     positions={"cle": (0, 0), "gob": (1, 0)})
    eng.state.phase = CombatPhase.COMBAT_ACTIVE
    eng.state.current_turn = TurnState(combatant_id="cle")
    eng.state.combatant_stats["cle"]["spellcasting"] = {
        "ability": "wisdom", "spell_save_dc": 14, "spell_attack_bonus": 30,
        "spell_slots": {"2": 3}, "prepared_spells": [], "concentrating_on": None,
    }
    return eng


def _summon(eng, summon_id, effects, pos):
    eng.state.combatant_stats["cle"]["spellcasting"]["concentrating_on"] = summon_id
    eng.apply_spell_summon("cle", {"summon_id": summon_id, **effects}, pos, spell_id=summon_id)


def test_state_payload_lists_active_summons():
    eng = _engine()
    _summon(eng, "spiritual_weapon",
            {"damage": "1d8", "damage_type": "force", "move_speed": 20, "reach": 5}, (2, 2))

    summons = eng.get_combat_state()["summons"]
    assert summons == [{"id": "spiritual_weapon", "owner_id": "cle", "x": 2, "y": 2}]


def test_summon_vanishes_from_payload_when_concentration_drops():
    eng = _engine()
    _summon(eng, "spiritual_weapon",
            {"damage": "1d8", "damage_type": "force", "move_speed": 20, "reach": 5}, (2, 2))
    eng.state.combatant_stats["cle"]["spellcasting"]["concentrating_on"] = None
    assert eng.get_combat_state()["summons"] == []


def test_flaming_sphere_dispatches_as_a_bonus_action():
    eng = _engine()
    _summon(eng, "flaming_sphere",
            {"damage": "2d6", "damage_type": "fire", "move_speed": 30, "save": "dex",
             "aura": 5}, (3, 0))
    eng.state.combatant_stats["gob"]["dex_save"] = -30

    hp0 = eng.state.combatant_stats["gob"]["current_hp"]
    result = eng.take_bonus_action(BonusActionType.FLAMING_SPHERE, target_id="gob",
                                   move_to=(2, 0))
    assert result.success
    assert eng.state.combatant_stats["gob"]["current_hp"] < hp0
    assert eng.state.current_turn.bonus_action_taken
