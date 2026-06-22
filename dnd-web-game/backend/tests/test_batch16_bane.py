"""Batch 16: Bane — the debuff mirror of Bless.

Bless's machinery (the active_buffs store, concentration gating, attack/save dice)
only ever ADDED dice. Bane subtracts 1d4 from a failed-save target's attack rolls
and saving throws for the duration. Three gaps had to close:

1. The buff helpers must honor ``attack_penalty_dice`` / ``save_penalty_dice``.
2. Monster attacks (a separate path from player attacks) must consult attack
   buffs/penalties at all — otherwise Bane on an enemy never touches its attacks.
3. The spell must apply the debuff only to targets that FAIL the save.
"""
from app.core.combat_engine import CombatEngine, CombatState
from app.core.spell_system import (
    SpellRegistry, SpellEffectResolver, cast_spell,
)


def _engine():
    player = {
        "id": "hero", "name": "Hero", "type": "player",
        "hp": 24, "max_hp": 24, "ac": 15, "speed": 30,
        "str_mod": 3, "attack_bonus": 5, "damage_dice": "1d8", "damage_type": "slashing",
        "abilities": {"strength": 16, "dexterity": 12, "constitution": 14,
                      "intelligence": 10, "wisdom": 10, "charisma": 10},
        "class": "fighter", "level": 3, "conditions": [],
    }
    enemy = {
        "id": "goblin", "name": "Goblin", "type": "enemy",
        "hp": 12, "max_hp": 12, "ac": 13, "speed": 30,
        "abilities": {"strength": 8, "dexterity": 14, "constitution": 10,
                      "intelligence": 10, "wisdom": 8, "charisma": 8},
        "class": "monster", "level": 1, "conditions": [],
    }
    eng = CombatEngine(combat_state=CombatState())
    eng.start_combat([player], [enemy])
    return eng


# ---- 1/2. Penalty dice in the buff helpers --------------------------------

def test_attack_buff_bonus_subtracts_attack_penalty():
    eng = _engine()
    stats = eng.state.combatant_stats["goblin"]
    stats["active_buffs"] = [{"attack_penalty_dice": "1d4"}]
    for _ in range(25):
        assert -4 <= eng._attack_buff_bonus(stats) <= -1          # Bane -1d4

    # A Bless and a Bane on the same creature net out within range.
    stats["active_buffs"] = [{"attack_bonus_dice": "1d4"}, {"attack_penalty_dice": "1d4"}]
    for _ in range(25):
        assert -3 <= eng._attack_buff_bonus(stats) <= 3


def test_save_buff_bonus_subtracts_save_penalty():
    eng = _engine()
    stats = eng.state.combatant_stats["goblin"]
    stats["active_buffs"] = [{"save_penalty_dice": "1d4"}]
    for _ in range(25):
        assert -4 <= eng._save_buff_bonus(stats) <= -1


# ---- 2. Monster attacks honor the penalty (deterministic via fixed dice) --

def test_monster_attack_honors_attack_penalty(monkeypatch):
    import app.core.dice as dice
    from app.core.dice import D20Result
    from app.core.monster_abilities import MonsterAbility, AbilityType

    # Fixed, non-crit/non-fumble d20 whose total honors the modifier, and fixed dice.
    monkeypatch.setattr(dice, "roll_d20",
                        lambda modifier=0, advantage=False, disadvantage=False, **k:
                        D20Result(rolls=[10], modifier=modifier, total=10 + modifier))
    monkeypatch.setattr(dice, "roll_dice", lambda notation: 3)

    eng = _engine()
    attacker = eng.state.initiative_tracker.get_combatant("goblin")
    stats = eng.state.combatant_stats["goblin"]
    stats["active_buffs"] = [{"attack_penalty_dice": "1d4"}]   # Bane on the attacker
    attack = MonsterAbility(id="scimitar", name="Scimitar", original_description="",
                            ability_type=AbilityType.MELEE_ATTACK,
                            attack_bonus=8, damage_dice="1d6", damage_type="slashing")
    result = eng._execute_single_monster_attack(attacker, stats, attack, "hero")
    # base 10 + (attack_bonus 8 - penalty 3) = 15. Without the wiring it would be 18.
    assert result["attack_roll"] == 15


# ---- 3. Producer + failed-save application --------------------------------

def test_determine_debuff_effects_for_bane():
    sp = SpellRegistry.get_instance().get_spell("bane")
    assert sp is not None
    eff = SpellEffectResolver._determine_debuff_effects(sp)
    assert eff == {"attack_penalty_dice": "1d4", "save_penalty_dice": "1d4"}


def test_bane_debuffs_only_failed_save_targets():
    SpellRegistry.reset()
    caster = {
        "id": "wiz", "name": "Caster", "class": "wizard", "level": 5,
        "stats": {"charisma": 16},
        "spellcasting": {
            "ability": "charisma", "spell_save_dc": 15, "spell_attack_bonus": 6,
            "spell_slots_max": {1: 4}, "spell_slots_used": {},
            "cantrips_known": [], "spells_known": ["bane"], "prepared_spells": ["bane"],
        },
    }
    failer = {"id": "f", "name": "Failer", "current_hp": 20, "max_hp": 20,
              "ac": 12, "cha_save": -100}            # always fails the CHA save
    saver = {"id": "s", "name": "Saver", "current_hp": 20, "max_hp": 20,
             "ac": 12, "cha_save": 100}              # always saves
    result = cast_spell(caster, "bane", 1, [failer, saver])
    assert result.success, result.description
    assert result.debuffs_applied is not None
    assert "f" in result.debuffs_applied               # failed -> debuffed
    assert "s" not in result.debuffs_applied           # saved -> spared
    assert result.debuffs_applied["f"]["attack_penalty_dice"] == "1d4"
    SpellRegistry.reset()


# ---- 4. End-to-end: an enemy under Bane is weakened, then recovers ---------

def test_bane_on_enemy_weakens_attacks_and_saves_then_lifts():
    eng = _engine()
    # Player 'hero' casts Bane on 'goblin' (route mechanism = apply_spell_buffs).
    eng.apply_spell_buffs("hero",
                          {"attack_penalty_dice": "1d4", "save_penalty_dice": "1d4"},
                          ["goblin"], spell_id="bane")
    eng.state.combatant_stats["hero"]["spellcasting"] = {"concentrating_on": "bane"}
    g = eng.state.combatant_stats["goblin"]
    for _ in range(20):
        assert -4 <= eng._attack_buff_bonus(g) <= -1
        assert -4 <= eng._save_buff_bonus(g) <= -1

    # The caster loses concentration -> Bane lifts.
    eng.state.combatant_stats["hero"]["spellcasting"]["concentrating_on"] = None
    assert eng._attack_buff_bonus(g) == 0
    assert eng._save_buff_bonus(g) == 0
