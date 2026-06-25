"""Batch 34: Armor of Agathys retaliates — a melee attacker takes Cold damage.

Batch 31 wired Armor of Agathys's temp-HP grant; this adds its signature mechanic: while
the bearer still has those temporary HP, any creature that HITS them with a melee attack
takes Cold damage (5, +5 per slot above 1st). The amount is stored as `cold_retaliate`
and a shared `_apply_melee_retaliation` burns the attacker on a melee hit — in both the
player and monster attack paths — gated on the bearer having had temp HP when hit.
"""
import app.core.rules_engine as rules_engine
import app.core.dice as dice
from app.core.dice import D20Result
from app.core.combat_engine import CombatEngine, CombatState, ActionType, TurnState
from app.core.spell_system import SpellRegistry, cast_spell


# ----------------------------- cast layer ----------------------------------

def _caster(*spells):
    return {"id": "wiz", "name": "Wiz", "class": "wizard", "level": 5,
            "stats": {"intelligence": 18},
            "spellcasting": {"ability": "intelligence", "spell_save_dc": 15,
                             "spell_attack_bonus": 7, "spell_slots_max": {i: 3 for i in range(1, 6)},
                             "spell_slots_used": {}, "cantrips_known": [],
                             "spells_known": list(spells), "prepared_spells": list(spells)}}


def _self():
    return {"id": "wiz", "name": "Wiz", "current_hp": 20, "max_hp": 20, "ac": 12, "hp": 20}


def test_armor_of_agathys_sets_cold_retaliate():
    SpellRegistry.reset()
    r = cast_spell(_caster("armor_of_agathys"), "armor_of_agathys", 1, [_self()])
    assert r.temp_hp_granted["wiz"] == 5
    assert r.cold_retaliate["wiz"] == 5
    r3 = cast_spell(_caster("armor_of_agathys"), "armor_of_agathys", 3, [_self()])
    assert r3.cold_retaliate["wiz"] == 15                       # 5 + 5*2
    SpellRegistry.reset()


def test_false_life_has_no_cold_retaliate():
    SpellRegistry.reset()
    r = cast_spell(_caster("false_life"), "false_life", 1, [_self()])
    assert not r.cold_retaliate
    SpellRegistry.reset()


# ----------------------------- engine grant + gating -----------------------

def test_grant_cold_retaliate_stores_amount():
    eng = CombatEngine(combat_state=CombatState())
    eng.state.combatant_stats["x"] = {"current_hp": 10, "max_hp": 10, "temp_hp": 5}
    eng.grant_cold_retaliate("x", 5)
    assert eng.state.combatant_stats["x"]["cold_retaliate"] == 5


# ----------------------------- player attacks an AoA bearer ----------------

def _player_vs_bearer(monkeypatch, *, weapon="greatsword", bearer_temp=10,
                      attacker_resist_cold=False):
    monkeypatch.setattr(rules_engine, "roll_d20",
                        lambda modifier=0, advantage=False, disadvantage=False, **k:
                        D20Result(rolls=[18], modifier=modifier, total=18 + modifier))
    monkeypatch.setattr(dice, "roll_die", lambda sides: 1)      # tiny weapon damage

    player = {"id": "pc", "name": "PC", "type": "player", "hp": 30, "max_hp": 30,
              "ac": 14, "speed": 30, "str_mod": 3, "dex_mod": 0, "attack_bonus": 8,
              "damage_dice": "1d6", "damage_type": "slashing",
              "abilities": {"strength": 16, "dexterity": 10, "constitution": 14,
                            "intelligence": 10, "wisdom": 10, "charisma": 10},
              "class": "fighter", "level": 3, "conditions": [],
              "resistances": (["cold"] if attacker_resist_cold else [])}
    bearer = {"id": "mage", "name": "Mage", "type": "enemy", "hp": 40, "max_hp": 40,
              "temp_hp": bearer_temp, "ac": 1, "speed": 30, "conditions": [],
              "abilities": {"strength": 8, "dexterity": 12, "constitution": 12,
                            "intelligence": 16, "wisdom": 10, "charisma": 10},
              "class": "monster", "level": 3}
    eng = CombatEngine(combat_state=CombatState())
    eng.start_combat([player], [bearer])
    eng.grant_cold_retaliate("mage", 5)
    tracker = eng.state.initiative_tracker
    tracker.current_turn_index = next(i for i, c in enumerate(tracker.combatants) if c.id == "pc")
    eng.state.current_turn = TurnState(combatant_id="pc")
    return eng


def test_melee_attacker_takes_cold_from_bearer(monkeypatch):
    eng = _player_vs_bearer(monkeypatch)
    hp0 = eng.state.combatant_stats["pc"]["current_hp"]
    eng.take_action(ActionType.ATTACK, target_id="mage", weapon_name="greatsword")
    assert hp0 - eng.state.combatant_stats["pc"]["current_hp"] == 5   # 5 cold to attacker


def test_no_retaliate_when_bearer_has_no_temp_hp(monkeypatch):
    eng = _player_vs_bearer(monkeypatch, bearer_temp=0)
    hp0 = eng.state.combatant_stats["pc"]["current_hp"]
    eng.take_action(ActionType.ATTACK, target_id="mage", weapon_name="greatsword")
    assert eng.state.combatant_stats["pc"]["current_hp"] == hp0      # no retaliation


def test_ranged_attacker_is_not_burned(monkeypatch):
    eng = _player_vs_bearer(monkeypatch, weapon="shortbow")
    hp0 = eng.state.combatant_stats["pc"]["current_hp"]
    eng.take_action(ActionType.ATTACK, target_id="mage", weapon_name="shortbow")
    assert eng.state.combatant_stats["pc"]["current_hp"] == hp0      # ranged -> no retaliation


def test_cold_resistant_attacker_takes_half(monkeypatch):
    eng = _player_vs_bearer(monkeypatch, attacker_resist_cold=True)
    hp0 = eng.state.combatant_stats["pc"]["current_hp"]
    eng.take_action(ActionType.ATTACK, target_id="mage", weapon_name="greatsword")
    assert hp0 - eng.state.combatant_stats["pc"]["current_hp"] == 2  # 5 // 2 (cold resistance)


# ----------------------------- monster attacks an AoA-bearing player -------

def test_monster_melee_attacker_takes_cold(monkeypatch):
    from app.core.monster_abilities import MonsterAbility, AbilityType
    monkeypatch.setattr(dice, "roll_d20",
                        lambda modifier=0, advantage=False, disadvantage=False, **k:
                        D20Result(rolls=[18], modifier=modifier, total=18 + modifier))
    monkeypatch.setattr(dice, "roll_dice", lambda notation: 3)
    monkeypatch.setattr(dice, "dice_only", lambda notation: notation)

    player = {"id": "pc", "name": "PC", "type": "player", "hp": 40, "max_hp": 40,
              "temp_hp": 10, "ac": 1, "speed": 30, "conditions": [],
              "abilities": {"strength": 12, "dexterity": 12, "constitution": 14,
                            "intelligence": 10, "wisdom": 10, "charisma": 16},
              "class": "warlock", "level": 5}
    ogre = {"id": "ogre", "name": "Ogre", "type": "enemy", "hp": 50, "max_hp": 50, "ac": 12,
            "speed": 30, "conditions": [],
            "abilities": {"strength": 18, "dexterity": 8, "constitution": 16,
                          "intelligence": 6, "wisdom": 7, "charisma": 7},
            "class": "monster", "level": 2}
    eng = CombatEngine(combat_state=CombatState())
    eng.start_combat([player], [ogre])
    eng.grant_cold_retaliate("pc", 5)
    eng.state.positions["ogre"] = (0, 0)
    eng.state.positions["pc"] = (1, 0)

    attacker = eng.state.initiative_tracker.get_combatant("ogre")
    stats = eng.state.combatant_stats["ogre"]
    attack = MonsterAbility(id="club", name="Club", original_description="",
                            ability_type=AbilityType.MELEE_ATTACK,
                            attack_bonus=6, damage_dice="2d8", damage_type="bludgeoning")
    hp0 = eng.state.combatant_stats["ogre"]["current_hp"]
    eng._execute_single_monster_attack(attacker, stats, attack, "pc")
    assert hp0 - eng.state.combatant_stats["ogre"]["current_hp"] == 5   # ogre burned for 5 cold
