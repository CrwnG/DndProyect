"""Batch 30: Temporary Hit Points are modeled in the combat damage pipeline.

Temp HP was unmodeled — every damage site reduced current_hp directly and ignored
temp HP, so Heroism / False Life / Armor of Agathys / moon-druid wild shape granted a
buffer that did nothing. This batch makes temp HP a real buffer: a single chokepoint
`_apply_damage_with_temp` applies resistance/vulnerability/immunity, then depletes temp
HP BEFORE real HP, and EVERY damage site routes through it. `grant_temp_hp` is the
non-stacking grant API; `apply_spell_damage` is the route-side spell-damage path.

RAW temp HP: depletes before real HP; resistance applies first; does NOT stack (a new
grant replaces the old only if larger); is NOT restored by healing; max HP is unaffected.
"""
from types import SimpleNamespace

import app.core.rules_engine as rules_engine
import app.core.dice as dice
from app.core.dice import D20Result
from app.core.combat_engine import CombatEngine, CombatState, ActionType, TurnState


# ----------------------------- the chokepoint ------------------------------

def _eng():
    return CombatEngine(combat_state=CombatState())


def test_temp_hp_absorbs_all_damage():
    eng = _eng()
    stats = {"current_hp": 30, "max_hp": 30, "temp_hp": 10}
    target = SimpleNamespace(current_hp=30)
    new_hp, dealt, down = eng._apply_damage_with_temp(target, stats, 6)
    assert stats["temp_hp"] == 4
    assert new_hp == 30 and stats["current_hp"] == 30 and target.current_hp == 30
    assert dealt == 6 and down is False


def test_temp_hp_overflows_to_real_hp():
    eng = _eng()
    stats = {"current_hp": 30, "max_hp": 30, "temp_hp": 5}
    target = SimpleNamespace(current_hp=30)
    new_hp, dealt, down = eng._apply_damage_with_temp(target, stats, 8)
    assert stats["temp_hp"] == 0           # exhausted
    assert new_hp == 27                     # 8 - 5 absorbed = 3 to HP
    assert target.current_hp == 27
    assert dealt == 8


def test_resistance_applies_before_temp_hp():
    eng = _eng()
    stats = {"current_hp": 30, "max_hp": 30, "temp_hp": 5}
    # 10 damage, resistance -> 5 effective, temp 5 absorbs all -> HP untouched.
    new_hp, dealt, _ = eng._apply_damage_with_temp(None, stats, 10, resistance=True)
    assert stats["temp_hp"] == 0
    assert new_hp == 30 and stats["current_hp"] == 30
    assert dealt == 5


def test_resistance_and_vulnerability_cancel():
    """RAW (and rules_engine apply_damage): resistance + vulnerability to the same type
    cancel to normal damage — NOT applied sequentially."""
    eng = _eng()
    stats = {"current_hp": 30, "max_hp": 30, "temp_hp": 0}
    new_hp, dealt, _ = eng._apply_damage_with_temp(
        None, stats, 7, resistance=True, vulnerability=True)
    assert dealt == 7 and new_hp == 23           # normal damage, not 7//2*2 = 6


def test_immunity_leaves_temp_and_hp_untouched():
    eng = _eng()
    stats = {"current_hp": 30, "max_hp": 30, "temp_hp": 5}
    new_hp, dealt, _ = eng._apply_damage_with_temp(None, stats, 100, immunity=True)
    assert stats["temp_hp"] == 5 and new_hp == 30 and dealt == 0


def test_temp_hp_then_zero_hp_is_unconscious():
    eng = _eng()
    stats = {"current_hp": 4, "max_hp": 30, "temp_hp": 3}
    new_hp, dealt, down = eng._apply_damage_with_temp(None, stats, 10)
    assert stats["temp_hp"] == 0 and new_hp == 0 and down is True


# ----------------------------- grant (non-stacking) ------------------------

def test_grant_temp_hp_takes_the_higher():
    eng = _eng()
    eng.state.combatant_stats["x"] = {"current_hp": 10, "max_hp": 10, "temp_hp": 0}
    eng.grant_temp_hp("x", 5)
    assert eng.state.combatant_stats["x"]["temp_hp"] == 5
    eng.grant_temp_hp("x", 3)                                   # smaller -> ignored
    assert eng.state.combatant_stats["x"]["temp_hp"] == 5
    eng.grant_temp_hp("x", 8)                                   # larger -> replaces
    assert eng.state.combatant_stats["x"]["temp_hp"] == 8


# ----------------------------- seeding -------------------------------------

def test_temp_hp_seeded_from_combatant_data():
    eng = _eng()
    player = {"id": "hero", "name": "Hero", "type": "player", "hp": 24, "max_hp": 24,
              "temp_hp": 7, "ac": 15, "speed": 30,
              "abilities": {"strength": 14, "dexterity": 12, "constitution": 14,
                            "intelligence": 10, "wisdom": 10, "charisma": 10},
              "class": "fighter", "level": 3, "conditions": []}
    enemy = {"id": "ogre", "name": "Ogre", "type": "enemy", "hp": 30, "max_hp": 30,
             "ac": 13, "speed": 30,
             "abilities": {"strength": 16, "dexterity": 8, "constitution": 16,
                           "intelligence": 6, "wisdom": 7, "charisma": 7},
             "class": "monster", "level": 2, "conditions": []}
    eng.start_combat([player], [enemy])
    assert eng.state.combatant_stats["hero"]["temp_hp"] == 7
    assert eng.state.combatant_stats["ogre"]["temp_hp"] == 0    # default when absent


# ----------------------------- route spell damage --------------------------

def test_apply_spell_damage_depletes_temp_first():
    eng = _eng()
    player = {"id": "pc", "name": "PC", "type": "player", "hp": 30, "max_hp": 30,
              "temp_hp": 8, "ac": 12, "speed": 30,
              "abilities": {"strength": 10, "dexterity": 10, "constitution": 10,
                            "intelligence": 10, "wisdom": 10, "charisma": 10},
              "class": "fighter", "level": 1, "conditions": []}
    enemy = {"id": "ogre", "name": "Ogre", "type": "enemy", "hp": 30, "max_hp": 30,
             "ac": 12, "speed": 30,
             "abilities": {"strength": 16, "dexterity": 8, "constitution": 16,
                           "intelligence": 6, "wisdom": 7, "charisma": 7},
             "class": "monster", "level": 1, "conditions": []}
    eng.start_combat([player], [enemy])
    eng.apply_spell_damage("pc", 5)
    assert eng.state.combatant_stats["pc"]["temp_hp"] == 3
    assert eng.state.combatant_stats["pc"]["current_hp"] == 30
    eng.apply_spell_damage("pc", 10)                           # 3 temp + 7 to HP
    assert eng.state.combatant_stats["pc"]["temp_hp"] == 0
    assert eng.state.combatant_stats["pc"]["current_hp"] == 23


# ----------------------------- integration: real attack path ---------------

def test_weapon_attack_depletes_temp_hp_first(monkeypatch):
    monkeypatch.setattr(rules_engine, "roll_d20",
                        lambda modifier=0, advantage=False, disadvantage=False, **k:
                        D20Result(rolls=[18], modifier=modifier, total=18 + modifier))
    monkeypatch.setattr(dice, "roll_die", lambda sides: 4)      # each weapon die = 4

    player = {"id": "brute", "name": "Brute", "type": "player", "hp": 30, "max_hp": 30,
              "ac": 14, "speed": 30, "str_mod": 3, "dex_mod": 0, "attack_bonus": 8,
              "damage_dice": "2d6", "damage_type": "slashing",
              "abilities": {"strength": 16, "dexterity": 10, "constitution": 14,
                            "intelligence": 10, "wisdom": 10, "charisma": 10},
              "class": "fighter", "level": 3, "conditions": []}
    enemy = {"id": "dummy", "name": "Dummy", "type": "enemy", "hp": 40, "max_hp": 40,
             "temp_hp": 12, "ac": 1, "speed": 30,
             "abilities": {"strength": 10, "dexterity": 10, "constitution": 10,
                           "intelligence": 8, "wisdom": 8, "charisma": 8},
             "class": "monster", "level": 1, "conditions": []}
    eng = _eng()
    eng.start_combat([player], [enemy])
    tracker = eng.state.initiative_tracker
    tracker.current_turn_index = next(i for i, c in enumerate(tracker.combatants) if c.id == "brute")
    eng.state.current_turn = TurnState(combatant_id="brute")

    # 2d6 -> 8 + STR 3 = 11 damage, fully absorbed by 12 temp HP -> HP untouched.
    eng.take_action(ActionType.ATTACK, target_id="dummy", weapon_name="greatsword")
    assert eng.state.combatant_stats["dummy"]["temp_hp"] == 1
    assert eng.state.combatant_stats["dummy"]["current_hp"] == 40


# ----------------------------- integration: monster ability ----------------

def test_monster_ability_damage_depletes_temp_hp():
    eng = _eng()
    player = {"id": "pc", "name": "PC", "type": "player", "hp": 30, "max_hp": 30,
              "temp_hp": 6, "ac": 14, "speed": 30,
              "abilities": {"strength": 12, "dexterity": 12, "constitution": 12,
                            "intelligence": 10, "wisdom": 10, "charisma": 10},
              "class": "fighter", "level": 3, "conditions": []}
    enemy = {"id": "ogre", "name": "Ogre", "type": "enemy", "hp": 30, "max_hp": 30,
             "ac": 12, "speed": 30,
             "abilities": {"strength": 16, "dexterity": 8, "constitution": 16,
                           "intelligence": 6, "wisdom": 7, "charisma": 7},
             "class": "monster", "level": 2, "conditions": []}
    eng.start_combat([player], [enemy])
    eng._apply_damage_to_target("pc", 4, "fire")
    assert eng.state.combatant_stats["pc"]["temp_hp"] == 2     # 6 - 4
    assert eng.state.combatant_stats["pc"]["current_hp"] == 30


def test_get_combat_state_exposes_temp_hp():
    """Clients (and the frontend HP bar) need temp_hp in the combat state payload."""
    eng = _eng()
    player = {"id": "hero", "name": "Hero", "type": "player", "hp": 24, "max_hp": 24,
              "temp_hp": 9, "ac": 15, "speed": 30,
              "abilities": {"strength": 14, "dexterity": 12, "constitution": 14,
                            "intelligence": 10, "wisdom": 10, "charisma": 10},
              "class": "fighter", "level": 3, "conditions": []}
    enemy = {"id": "ogre", "name": "Ogre", "type": "enemy", "hp": 30, "max_hp": 30,
             "ac": 13, "speed": 30,
             "abilities": {"strength": 16, "dexterity": 8, "constitution": 16,
                           "intelligence": 6, "wisdom": 7, "charisma": 7},
             "class": "monster", "level": 2, "conditions": []}
    eng.start_combat([player], [enemy])
    state = eng.get_combat_state()
    hero = next(c for c in state["combatants"] if c["id"] == "hero")
    assert hero["temp_hp"] == 9


def test_fall_damage_depletes_temp_hp():
    """Fall damage (a combat hazard) absorbs into temp HP first, like every source."""
    from app.core.falling import apply_falling_damage
    combatant = SimpleNamespace(hp=30, conditions=[])
    stats = {"current_hp": 30, "max_hp": 30, "temp_hp": 100}    # plenty to absorb a fall
    result = apply_falling_damage(combatant, stats, 20)         # 20 ft -> 2d6
    assert result["damage"] > 0
    assert stats["temp_hp"] == 100 - result["damage"]          # temp absorbed the fall
    assert combatant.hp == 30                                   # real HP untouched
