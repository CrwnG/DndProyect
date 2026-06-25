"""Batch 33: secondary attack damage respects resistance/immunity/vulnerability.

The main weapon attack and off-hand attack pass resistance flags to the damage chokepoint,
but Martial Arts, Flurry of Blows, and the Graze/Cleave weapon-mastery extra damage called
`_apply_damage_with_temp` with NO flags — so a creature resistant/immune to the damage type
took FULL damage from those. A shared `_resist_flags(target_stats, damage_type)` now feeds
every site (and DRYs `_apply_damage_to_target`).
"""
import app.core.rules_engine as rules_engine
import app.core.dice as dice
from app.core.dice import D20Result
from app.core.combat_engine import CombatEngine, CombatState, TurnState, BonusActionType


# ----------------------------- helper unit ---------------------------------

def test_resist_flags_reads_cache_case_insensitively():
    eng = CombatEngine(combat_state=CombatState())
    stats = {"resistances": ["Bludgeoning"], "vulnerabilities": ["fire"],
             "immunities": ["Poison"]}
    assert eng._resist_flags(stats, "bludgeoning") == (True, False, False)
    assert eng._resist_flags(stats, "FIRE") == (False, True, False)
    assert eng._resist_flags(stats, "poison") == (False, False, True)
    assert eng._resist_flags(stats, "slashing") == (False, False, False)


def test_resist_flags_accepts_legacy_damage_keys_and_none():
    eng = CombatEngine(combat_state=CombatState())
    stats = {"damage_resistances": ["cold"]}
    assert eng._resist_flags(stats, "cold") == (True, False, False)
    assert eng._resist_flags({}, "fire") == (False, False, False)
    assert eng._resist_flags(stats, None) == (False, False, False)


# ----------------------------- martial arts integration --------------------

def _monk_vs(monkeypatch, *, resistances=None, immunities=None):
    monkeypatch.setattr(rules_engine, "roll_d20",
                        lambda modifier=0, advantage=False, disadvantage=False, **k:
                        D20Result(rolls=[18], modifier=modifier, total=18 + modifier))
    monkeypatch.setattr(dice, "roll_die", lambda sides: 4)       # martial-arts die -> 4

    monk = {"id": "monk", "name": "Monk", "type": "player", "hp": 30, "max_hp": 30,
            "ac": 14, "speed": 30, "str_mod": 0, "dex_mod": 0,
            "abilities": {"strength": 10, "dexterity": 10, "constitution": 12,
                          "intelligence": 10, "wisdom": 14, "charisma": 10},
            "class": "monk", "level": 3, "conditions": []}
    enemy = {"id": "dummy", "name": "Dummy", "type": "enemy", "hp": 50, "max_hp": 50,
             "ac": 5, "speed": 30, "conditions": [],
             "abilities": {"strength": 14, "dexterity": 10, "constitution": 14,
                           "intelligence": 6, "wisdom": 8, "charisma": 8},
             "class": "monster", "level": 2,
             "resistances": resistances or [], "immunities": immunities or []}
    eng = CombatEngine(combat_state=CombatState())
    eng.start_combat([monk], [enemy])
    eng.state.positions["dummy"] = (0, 0)
    eng.state.positions["monk"] = (1, 0)
    tracker = eng.state.initiative_tracker
    tracker.current_turn_index = next(i for i, c in enumerate(tracker.combatants) if c.id == "monk")
    eng.state.current_turn = TurnState(combatant_id="monk")
    return eng


def test_martial_arts_full_damage_vs_normal_target(monkeypatch):
    eng = _monk_vs(monkeypatch)
    hp0 = eng.state.combatant_stats["dummy"]["current_hp"]
    eng.take_bonus_action(BonusActionType.MARTIAL_ARTS, target_id="dummy")
    assert hp0 - eng.state.combatant_stats["dummy"]["current_hp"] == 4   # die 4 + mod 0


def test_martial_arts_halved_vs_bludgeoning_resistant(monkeypatch):
    eng = _monk_vs(monkeypatch, resistances=["bludgeoning"])
    hp0 = eng.state.combatant_stats["dummy"]["current_hp"]
    eng.take_bonus_action(BonusActionType.MARTIAL_ARTS, target_id="dummy")
    assert hp0 - eng.state.combatant_stats["dummy"]["current_hp"] == 2   # 4 // 2


def test_martial_arts_zero_vs_bludgeoning_immune(monkeypatch):
    eng = _monk_vs(monkeypatch, immunities=["bludgeoning"])
    hp0 = eng.state.combatant_stats["dummy"]["current_hp"]
    eng.take_bonus_action(BonusActionType.MARTIAL_ARTS, target_id="dummy")
    assert hp0 - eng.state.combatant_stats["dummy"]["current_hp"] == 0


# ----------------------------- Divine Smite (radiant) integration ----------

def _paladin_vs(monkeypatch, *, resistances=None):
    monkeypatch.setattr(dice, "roll_die", lambda sides: 4)      # 2d8 -> 8 radiant
    pal = {"id": "pal", "name": "Pal", "type": "player", "hp": 40, "max_hp": 40,
           "ac": 16, "speed": 30, "class": "paladin", "level": 2, "conditions": [],
           "abilities": {"strength": 16, "dexterity": 10, "constitution": 14,
                         "intelligence": 10, "wisdom": 10, "charisma": 14}}
    enemy = {"id": "dummy", "name": "Dummy", "type": "enemy", "hp": 50, "max_hp": 50,
             "ac": 12, "speed": 30, "conditions": [],
             "abilities": {"strength": 14, "dexterity": 10, "constitution": 14,
                           "intelligence": 6, "wisdom": 8, "charisma": 8},
             "class": "monster", "level": 2, "resistances": resistances or []}
    eng = CombatEngine(combat_state=CombatState())
    eng.start_combat([pal], [enemy])
    eng.state.combatant_stats["pal"]["spell_slots"] = {1: 1}
    tracker = eng.state.initiative_tracker
    tracker.current_turn_index = next(i for i, c in enumerate(tracker.combatants) if c.id == "pal")
    eng.state.current_turn = TurnState(combatant_id="pal")
    return eng


def test_divine_smite_full_vs_normal_target(monkeypatch):
    eng = _paladin_vs(monkeypatch)
    hp0 = eng.state.combatant_stats["dummy"]["current_hp"]
    eng.use_divine_smite(1, "dummy")
    assert hp0 - eng.state.combatant_stats["dummy"]["current_hp"] == 8    # 2d8 -> 8


def test_divine_smite_halved_vs_radiant_resistant(monkeypatch):
    eng = _paladin_vs(monkeypatch, resistances=["radiant"])
    hp0 = eng.state.combatant_stats["dummy"]["current_hp"]
    eng.use_divine_smite(1, "dummy")
    assert hp0 - eng.state.combatant_stats["dummy"]["current_hp"] == 4    # 8 // 2
