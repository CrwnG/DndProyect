"""Batch 29: Faerie Fire actually does something — attackers get advantage.

Faerie Fire (a DEX-save area control spell) outlines creatures that fail the save;
RAW, "attack rolls against an affected creature have advantage" for the duration
(concentration). The engine applied NO mechanical effect: the spell has no damage and
no standard condition, so `_determine_debuff_effects` returned {} and it fell through
the save dispatch doing nothing. It is now a concentration-gated debuff carrying an
`attacks_against_advantage` flag, applied to failed-save targets, and BOTH attack
paths (player `_handle_attack` and monster `_execute_single_monster_attack`) grant
advantage when their target is outlined.
"""
import app.core.rules_engine as rules_engine
import app.core.dice as dice
from app.core.dice import D20Result
from app.core.combat_engine import CombatEngine, CombatState, ActionType, TurnState
from app.core.spell_system import SpellRegistry, SpellEffectResolver, cast_spell


def _capturing_d20(captured):
    def fake(modifier=0, advantage=False, disadvantage=False, **k):
        captured["advantage"] = advantage
        captured["disadvantage"] = disadvantage
        return D20Result(rolls=[10], modifier=modifier, total=10 + modifier)
    return fake


def _wizard(*spells):
    return {"id": "wiz", "name": "Wiz", "class": "wizard", "level": 9,
            "stats": {"intelligence": 18},
            "spellcasting": {"ability": "intelligence", "spell_save_dc": 16,
                             "spell_attack_bonus": 8, "spell_slots_max": {i: 3 for i in range(1, 6)},
                             "spell_slots_used": {}, "cantrips_known": list(spells),
                             "spells_known": list(spells), "prepared_spells": list(spells)}}


# ----------------------------- data-level ----------------------------------

def test_faerie_fire_is_an_advantage_debuff():
    sp = SpellRegistry.get_instance().get_spell("faerie_fire")
    assert SpellEffectResolver._determine_debuff_effects(sp) == {"attacks_against_advantage": True}


def test_casting_faerie_fire_outlines_failed_targets():
    SpellRegistry.reset()
    caster = _wizard("faerie_fire")
    failer = {"id": "f", "name": "Failer", "current_hp": 30, "max_hp": 30, "ac": 13,
              "dex_save": -100}                                   # auto-fail the DEX save
    saver = {"id": "s", "name": "Saver", "current_hp": 30, "max_hp": 30, "ac": 13,
             "dex_save": 100}                                     # auto-succeed
    r = cast_spell(caster, "faerie_fire", 1, [failer, saver])
    assert r.success, r.description
    assert r.debuffs_applied.get("f") == {"attacks_against_advantage": True}
    assert "s" not in (r.debuffs_applied or {})                  # the saver is unaffected
    SpellRegistry.reset()


# ----------------------------- player path ---------------------------------

def _player_engine(monkeypatch, captured, *, outlined, concentrating=True):
    monkeypatch.setattr(rules_engine, "roll_d20", _capturing_d20(captured))
    player = {"id": "brute", "name": "Brute", "type": "player", "hp": 30, "max_hp": 30,
              "ac": 14, "speed": 30, "str_mod": 3, "dex_mod": 0, "attack_bonus": 8,
              "damage_dice": "2d6", "damage_type": "slashing",
              "abilities": {"strength": 16, "dexterity": 10, "constitution": 14,
                            "intelligence": 10, "wisdom": 10, "charisma": 10},
              "class": "fighter", "level": 3, "conditions": []}
    enemy = {"id": "ogre", "name": "Ogre", "type": "enemy", "hp": 60, "max_hp": 60,
             "ac": 5, "speed": 30,
             "abilities": {"strength": 18, "dexterity": 8, "constitution": 16,
                           "intelligence": 6, "wisdom": 7, "charisma": 7},
             "class": "monster", "level": 2, "conditions": []}
    eng = CombatEngine(combat_state=CombatState())
    eng.start_combat([player], [enemy])
    if outlined:
        eng.apply_spell_buffs("brute", {"attacks_against_advantage": True},
                              ["ogre"], spell_id="faerie_fire")
        eng.state.combatant_stats["brute"]["spellcasting"] = {
            "concentrating_on": "faerie_fire" if concentrating else None}
    tracker = eng.state.initiative_tracker
    tracker.current_turn_index = next(i for i, c in enumerate(tracker.combatants) if c.id == "brute")
    eng.state.current_turn = TurnState(combatant_id="brute")
    return eng


def test_player_attack_vs_outlined_enemy_has_advantage(monkeypatch):
    cap = {}
    eng = _player_engine(monkeypatch, cap, outlined=True)
    eng.take_action(ActionType.ATTACK, target_id="ogre", weapon_name="greatsword")
    assert cap["advantage"] is True


def test_player_attack_vs_normal_enemy_has_no_advantage(monkeypatch):
    cap = {}
    eng = _player_engine(monkeypatch, cap, outlined=False)
    eng.take_action(ActionType.ATTACK, target_id="ogre", weapon_name="greatsword")
    assert cap["advantage"] is False


def test_faerie_fire_advantage_lifts_when_caster_drops_concentration(monkeypatch):
    cap = {}
    eng = _player_engine(monkeypatch, cap, outlined=True, concentrating=False)
    eng.take_action(ActionType.ATTACK, target_id="ogre", weapon_name="greatsword")
    assert cap["advantage"] is False                             # gated on concentration


def test_invisible_target_without_faerie_fire_imposes_disadvantage(monkeypatch):
    """Control: attacking an Invisible creature normally has disadvantage."""
    cap = {}
    eng = _player_engine(monkeypatch, cap, outlined=False)
    eng.state.combatant_stats["ogre"]["conditions"] = ["invisible"]
    eng.take_action(ActionType.ATTACK, target_id="ogre", weapon_name="greatsword")
    assert cap["disadvantage"] is True


def test_faerie_fire_reveals_invisible_target(monkeypatch):
    """An outlined creature can't benefit from Invisible: the attacker no longer suffers
    disadvantage, and Faerie Fire's advantage applies — net advantage (a primary use:
    revealing invisible enemies)."""
    cap = {}
    eng = _player_engine(monkeypatch, cap, outlined=True)
    eng.state.combatant_stats["ogre"]["conditions"] = ["invisible"]
    eng.take_action(ActionType.ATTACK, target_id="ogre", weapon_name="greatsword")
    assert cap["advantage"] is True
    assert cap["disadvantage"] is False                          # invisible benefit suppressed


# ----------------------------- monster path --------------------------------

def test_monster_attack_vs_outlined_player_has_advantage(monkeypatch):
    from app.core.monster_abilities import MonsterAbility, AbilityType
    cap = {}
    monkeypatch.setattr(dice, "roll_d20", _capturing_d20(cap))
    monkeypatch.setattr(dice, "roll_dice", lambda notation: 5)
    monkeypatch.setattr(dice, "dice_only", lambda notation: notation)

    player = {"id": "pc", "name": "PC", "type": "player", "hp": 40, "max_hp": 40, "ac": 14,
              "speed": 30, "abilities": {"strength": 12, "dexterity": 12, "constitution": 12,
                                         "intelligence": 10, "wisdom": 10, "charisma": 10},
              "class": "fighter", "level": 3, "conditions": []}
    ogre = {"id": "ogre", "name": "Ogre", "type": "enemy", "hp": 50, "max_hp": 50, "ac": 12,
            "speed": 30, "abilities": {"strength": 18, "dexterity": 8, "constitution": 16,
                                       "intelligence": 6, "wisdom": 7, "charisma": 7},
            "class": "monster", "level": 2, "conditions": []}
    caster = {"id": "sprite", "name": "Sprite", "type": "enemy", "hp": 14, "max_hp": 14,
              "ac": 15, "speed": 30, "abilities": {"strength": 8, "dexterity": 18,
                                                   "constitution": 10, "intelligence": 14,
                                                   "wisdom": 13, "charisma": 11},
              "class": "monster", "level": 1, "conditions": []}
    eng = CombatEngine(combat_state=CombatState())
    eng.start_combat([player], [ogre, caster])
    eng.apply_spell_buffs("sprite", {"attacks_against_advantage": True},
                          ["pc"], spell_id="faerie_fire")
    eng.state.combatant_stats["sprite"]["spellcasting"] = {"concentrating_on": "faerie_fire"}
    eng.state.positions["ogre"] = (0, 0)
    eng.state.positions["pc"] = (1, 0)

    attacker = eng.state.initiative_tracker.get_combatant("ogre")
    stats = eng.state.combatant_stats["ogre"]
    attack = MonsterAbility(id="club", name="Club", original_description="",
                            ability_type=AbilityType.MELEE_ATTACK,
                            attack_bonus=6, damage_dice="2d8", damage_type="bludgeoning")
    eng._execute_single_monster_attack(attacker, stats, attack, "pc")
    assert cap["advantage"] is True
