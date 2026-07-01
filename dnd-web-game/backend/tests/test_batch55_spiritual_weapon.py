"""Batch 55 (A2a): Spiritual Weapon becomes a real battlefield entity.

Casting spiritual_weapon previously succeeded but did nothing (ActionType.SPIRITUAL_WEAPON
was an unused enum member). Now the cast emits a summon (stored on the caster, position
tracked), makes the on-cast attack, and on later turns the caster can spend a bonus action
to move the weapon up to 20 ft and attack again — 1d8+mod Force, melee spell attack,
concentration-gated, upcast +1d8 per two slot levels above 2 (per the spell JSON).
"""
import json

from app.core.combat_engine import (
    CombatEngine, CombatState, CombatPhase, TurnState, BonusActionType,
)
from app.core.spell_system import SpellRegistry, SpellEffectResolver, cast_spell


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
    stats = eng.state.combatant_stats["cle"]
    stats["spellcasting"] = {
        "ability": "wisdom", "spell_save_dc": 14, "spell_attack_bonus": 30,
        "spell_slots": {"2": 3}, "prepared_spells": ["spiritual_weapon"],
        "concentrating_on": "spiritual_weapon",
    }
    return eng


def _summon(eng, pos=(1, 0)):
    eng.apply_spell_summon(
        "cle",
        {"summon_id": "spiritual_weapon", "damage": "1d8", "damage_type": "force",
         "move_speed": 20, "reach": 5},
        pos, spell_id="spiritual_weapon",
    )


def test_determine_summon_created_recognizes_spiritual_weapon():
    reg = SpellRegistry.get_instance()
    spell = reg.get_spell("spiritual_weapon")
    s2 = SpellEffectResolver._determine_summon_created(spell, 2)
    assert s2 and s2["summon_id"] == "spiritual_weapon"
    assert s2["damage"] == "1d8" and s2["damage_type"] == "force"
    s4 = SpellEffectResolver._determine_summon_created(spell, 4)
    assert s4["damage"] == "2d8"          # +1d8 per two slot levels above 2


def test_cast_spell_emits_summon_and_concentration():
    sc = {"ability": "wisdom", "spell_save_dc": 14, "spell_attack_bonus": 6,
          "spell_slots": {"2": 3}, "prepared_spells": ["spiritual_weapon"],
          "concentrating_on": None}
    caster = {"id": "cle", "name": "Cle", "level": 5, "spellcasting": sc, "wis_mod": 3}
    r = cast_spell(caster, "spiritual_weapon", 2, [{"id": "gob", "name": "Gob"}])
    assert r.success and r.concentration_started
    assert getattr(r, "summon_created", None)
    assert r.summon_created["summon_id"] == "spiritual_weapon"


def test_summon_attack_damages_target_and_respects_reach():
    eng = _engine()
    _summon(eng, pos=(1, 0))              # weapon adjacent to gob at (1,0)... same tile: reach ok

    hp0 = eng.state.combatant_stats["gob"]["current_hp"]
    result = eng.summon_attack("cle", "spiritual_weapon", "gob")
    assert result.success
    assert eng.state.combatant_stats["gob"]["current_hp"] < hp0   # AC 1 + atk +30 -> guaranteed hit

    # Out of reach without a move: weapon parked far away must fail
    eng2 = _engine()
    _summon(eng2, pos=(7, 7))
    result2 = eng2.summon_attack("cle", "spiritual_weapon", "gob")
    assert not result2.success


def test_summon_attack_moves_weapon_within_20ft():
    eng = _engine()
    _summon(eng, pos=(5, 0))              # 20 ft from gob at (1,0)
    result = eng.summon_attack("cle", "spiritual_weapon", "gob", move_to=(2, 0))
    assert result.success                 # moved 15 ft, now adjacent
    # move beyond 20 ft must fail
    eng2 = _engine()
    _summon(eng2, pos=(7, 7))
    result2 = eng2.summon_attack("cle", "spiritual_weapon", "gob", move_to=(1, 1))
    assert not result2.success


def test_summon_attack_gated_by_concentration():
    eng = _engine()
    _summon(eng, pos=(1, 0))
    eng.state.combatant_stats["cle"]["spellcasting"]["concentrating_on"] = None
    result = eng.summon_attack("cle", "spiritual_weapon", "gob")
    assert not result.success


def test_bonus_action_dispatch_and_economy():
    eng = _engine()
    _summon(eng, pos=(1, 0))
    result = eng.take_bonus_action(BonusActionType.SPIRITUAL_WEAPON, target_id="gob")
    assert result.success
    assert eng.state.current_turn.bonus_action_taken
    # second use the same turn is refused
    again = eng.take_bonus_action(BonusActionType.SPIRITUAL_WEAPON, target_id="gob")
    assert not again.success


def test_failed_attack_does_not_commit_movement():
    """QA (Codex): an out-of-reach attack must not grant free movement — the move only
    commits when the whole action validates."""
    eng = _engine()
    _summon(eng, pos=(7, 7))
    result = eng.summon_attack("cle", "spiritual_weapon", "gob", move_to=(5, 5))  # still out of reach
    assert not result.success
    assert eng.state.combatant_stats["cle"]["active_summons"]["spiritual_weapon"]["position"] == [7, 7]


def test_immune_target_takes_no_damage_and_no_concentration_check():
    """QA (Codex): report/gate on post-mitigation damage, not the raw roll."""
    eng = _engine()
    _summon(eng, pos=(1, 0))
    eng.state.combatant_stats["gob"]["immunities"] = ["force"]
    hp0 = eng.state.combatant_stats["gob"]["current_hp"]
    result = eng.summon_attack("cle", "spiritual_weapon", "gob")
    assert result.success
    assert result.damage_dealt == 0
    assert eng.state.combatant_stats["gob"]["current_hp"] == hp0


def test_target_without_position_is_rejected():
    """QA (Codex): a positionless target must not be attackable from any distance."""
    eng = _engine()
    _summon(eng, pos=(1, 0))
    del eng.state.positions["gob"]
    result = eng.summon_attack("cle", "spiritual_weapon", "gob")
    assert not result.success


def test_summon_survives_serialization_roundtrip():
    eng = _engine()
    _summon(eng, pos=(1, 0))
    eng2 = CombatEngine.from_dict(json.loads(json.dumps(eng.to_dict())))
    eng2.state.phase = CombatPhase.COMBAT_ACTIVE
    eng2.state.current_turn = TurnState(combatant_id="cle")
    hp0 = eng2.state.combatant_stats["gob"]["current_hp"]
    result = eng2.summon_attack("cle", "spiritual_weapon", "gob")
    assert result.success
    assert eng2.state.combatant_stats["gob"]["current_hp"] < hp0
