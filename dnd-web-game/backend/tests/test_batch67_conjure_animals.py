"""Batch 67 (A2b): Conjure Animals rides the summon scaffolding (2024 SRD semantics).

The 2024 SRD pack is not a stat-block creature: it's a movable entity — when it comes
within 10 ft of a creature (or a creature ends its turn there), that creature makes a
Dex save or takes 3d10 slashing (+1d10 per slot level above 3). The save NEGATES
(unlike Flaming Sphere's half), and a creature makes the save only ONCE PER TURN.
Commanding the pack is modeled as the caster's bonus action (documented approximation
of the move-triggered saves).
"""
from app.core.combat_engine import (
    CombatEngine, CombatState, CombatPhase, TurnState, BonusActionType,
)
from app.core.spell_system import SpellRegistry, SpellEffectResolver


def _mk(cid, ctype, **over):
    base = {"id": cid, "name": cid, "type": ctype, "hp": 60, "max_hp": 60, "ac": 12,
            "speed": 30, "abilities": {"strength": 12, "dexterity": 12, "constitution": 14,
                                       "intelligence": 10, "wisdom": 16, "charisma": 10},
            "class": "druid", "level": 5, "conditions": []}
    base.update(over)
    return base


def _engine():
    eng = CombatEngine(combat_state=CombatState())
    eng.start_combat([_mk("dru", "player")], [_mk("gob", "enemy")],
                     positions={"dru": (0, 0), "gob": (1, 0)})
    eng.state.phase = CombatPhase.COMBAT_ACTIVE
    eng.state.current_turn = TurnState(combatant_id="dru")
    eng.state.combatant_stats["dru"]["spellcasting"] = {
        "ability": "wisdom", "spell_save_dc": 14, "spell_attack_bonus": 6,
        "spell_slots": {"3": 3}, "prepared_spells": ["conjure_animals"],
        "concentrating_on": "conjure_animals",
    }
    return eng


def _pack(eng, pos=(2, 0)):
    eng.apply_spell_summon(
        "dru",
        {"summon_id": "conjure_animals", "damage": "3d10", "damage_type": "slashing",
         "move_speed": 30, "save": "dex", "aura": 10, "save_negates": True,
         "once_per_turn": True},
        pos, spell_id="conjure_animals",
    )


def test_determine_summon_recognizes_conjure_animals_with_upcast():
    reg = SpellRegistry.get_instance()
    spell = reg.get_spell("conjure_animals")
    s3 = SpellEffectResolver._determine_summon_created(spell, 3)
    assert s3 and s3["summon_id"] == "conjure_animals"
    assert s3["damage"] == "3d10" and s3["save"] == "dex"
    assert s3["save_negates"] is True and s3["once_per_turn"] is True
    assert s3["aura"] == 10
    assert not s3.get("on_cast_attack")
    s5 = SpellEffectResolver._determine_summon_created(spell, 5)
    assert s5["damage"] == "5d10"          # +1d10 per slot level above 3


def test_successful_save_negates_all_damage():
    eng = _engine()
    _pack(eng)
    eng.state.combatant_stats["gob"]["dex_save"] = 30    # always saves

    hp0 = eng.state.combatant_stats["gob"]["current_hp"]
    result = eng.summon_attack("dru", "conjure_animals", "gob")
    assert result.success
    assert eng.state.combatant_stats["gob"]["current_hp"] == hp0   # negated, not halved


def test_failed_save_takes_full_damage():
    eng = _engine()
    _pack(eng)
    eng.state.combatant_stats["gob"]["dex_save"] = -30   # always fails

    hp0 = eng.state.combatant_stats["gob"]["current_hp"]
    eng.summon_attack("dru", "conjure_animals", "gob")
    assert hp0 - eng.state.combatant_stats["gob"]["current_hp"] >= 3   # 3d10


def test_a_creature_saves_only_once_per_round():
    eng = _engine()
    _pack(eng)
    eng.state.combatant_stats["gob"]["dex_save"] = -30

    hp0 = eng.state.combatant_stats["gob"]["current_hp"]
    eng.summon_attack("dru", "conjure_animals", "gob")
    hp1 = eng.state.combatant_stats["gob"]["current_hp"]
    assert hp1 < hp0
    # Same round: the pack can't grind the same creature again.
    eng.summon_attack("dru", "conjure_animals", "gob")
    assert eng.state.combatant_stats["gob"]["current_hp"] == hp1
    # ...and the end-of-turn aura doesn't double-dip either.
    eng.state.current_turn = TurnState(combatant_id="gob")
    eng.state.initiative_tracker.current_turn_index = next(
        i for i, c in enumerate(eng.state.initiative_tracker.combatants) if c.id == "gob")
    eng.end_turn()
    assert eng.state.combatant_stats["gob"]["current_hp"] == hp1


def test_pack_commanded_as_bonus_action():
    eng = _engine()
    _pack(eng, pos=(4, 0))
    eng.state.combatant_stats["gob"]["dex_save"] = -30

    hp0 = eng.state.combatant_stats["gob"]["current_hp"]
    result = eng.take_bonus_action(BonusActionType.CONJURED_PACK, target_id="gob",
                                   move_to=(2, 0))
    assert result.success
    assert eng.state.combatant_stats["gob"]["current_hp"] < hp0
    assert eng.state.current_turn.bonus_action_taken
