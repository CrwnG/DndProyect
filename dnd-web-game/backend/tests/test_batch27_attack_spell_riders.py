"""Batch 27: attack-roll spells apply their on-hit rider (condition / debuff).

The attack-spell branch in cast_spell only dealt damage on a hit — it dropped any
declared condition or debuff. So Contagion (a melee spell attack that should poison
on a hit) and Ray of Enfeeblement (a ranged spell attack that halves the target's
STR-weapon damage) did NOTHING. This is the Batch-20 fix, but for the ATTACK branch.
"""
import app.core.spell_system as spell_system
from app.core.dice import D20Result
from app.core.combat_engine import CombatEngine, CombatState, ActionType, TurnState
from app.core.spell_system import SpellRegistry, SpellEffectResolver, cast_spell


def _caster(*spells):
    return {"id": "c", "name": "C", "class": "wizard", "level": 11,
            "stats": {"intelligence": 18},
            "spellcasting": {"ability": "intelligence", "spell_save_dc": 16,
                             "spell_attack_bonus": 9, "spell_slots_max": {i: 3 for i in range(1, 7)},
                             "spell_slots_used": {}, "cantrips_known": list(spells),
                             "spells_known": list(spells), "prepared_spells": list(spells)}}


def _target():
    return {"id": "e", "name": "Ogre", "current_hp": 60, "max_hp": 60, "ac": 13, "hp": 60}


def test_determine_debuff_effects_ray_of_enfeeblement():
    sp = SpellRegistry.get_instance().get_spell("ray_of_enfeeblement")
    assert SpellEffectResolver._determine_debuff_effects(sp) == {"halve_strength_damage": True}


def test_elemental_bane_does_not_get_banes_debuff():
    """`"bane" in spell.id` wrongly matched elemental_bane (a different spell)."""
    reg = SpellRegistry.get_instance()
    eb = reg.get_spell("elemental_bane")
    if eb is not None:
        assert SpellEffectResolver._determine_debuff_effects(eb) == {}
    # Real Bane still gets its debuff.
    assert SpellEffectResolver._determine_debuff_effects(reg.get_spell("bane")) == {
        "attack_penalty_dice": "1d4", "save_penalty_dice": "1d4"}


def test_enfeebled_monster_melee_attack_is_halved(monkeypatch):
    """Ray of Enfeeblement's main use: an enfeebled MONSTER's melee (STR) attack —
    incl. each Multiattack swing via _execute_single_monster_attack — deals half."""
    import app.core.dice as dice
    from app.core.monster_abilities import MonsterAbility, AbilityType
    monkeypatch.setattr(dice, "roll_d20",
                        lambda modifier=0, advantage=False, disadvantage=False, **k:
                        D20Result(rolls=[15], modifier=modifier, total=15 + modifier))
    monkeypatch.setattr(dice, "roll_dice", lambda notation: 8)   # each damage roll = 8

    eng = CombatEngine(combat_state=CombatState())
    player = {"id": "pc", "name": "PC", "type": "player", "hp": 60, "max_hp": 60, "ac": 5,
              "speed": 30, "abilities": {"strength": 10, "dexterity": 10, "constitution": 10,
                                         "intelligence": 10, "wisdom": 10, "charisma": 10},
              "class": "fighter", "level": 3, "conditions": []}
    ogre = {"id": "ogre", "name": "Ogre", "type": "enemy", "hp": 50, "max_hp": 50, "ac": 12,
            "speed": 30, "abilities": {"strength": 18, "dexterity": 8, "constitution": 16,
                                       "intelligence": 6, "wisdom": 7, "charisma": 7},
            "class": "monster", "level": 2, "conditions": []}
    eng.start_combat([player], [ogre])
    # Adjacent so the attack is melee.
    eng.state.positions["ogre"] = (0, 0)
    eng.state.positions["pc"] = (1, 0)
    attacker = eng.state.initiative_tracker.get_combatant("ogre")
    stats = eng.state.combatant_stats["ogre"]
    attack = MonsterAbility(id="greatclub", name="Greatclub", original_description="",
                            ability_type=AbilityType.MELEE_ATTACK,
                            attack_bonus=6, damage_dice="2d8", damage_type="bludgeoning")

    hp0 = eng.state.combatant_stats["pc"]["current_hp"]
    eng._execute_single_monster_attack(attacker, stats, attack, "pc")
    full = hp0 - eng.state.combatant_stats["pc"]["current_hp"]    # 2d8 -> 8, no flat mod

    eng.state.combatant_stats["pc"]["current_hp"] = hp0
    stats["active_buffs"] = [{"halve_strength_damage": True}]     # Ray of Enfeeblement
    eng._execute_single_monster_attack(attacker, stats, attack, "pc")
    halved = hp0 - eng.state.combatant_stats["pc"]["current_hp"]
    assert halved == full // 2 and halved < full

    # A RANGED attack (DEX) from the same enfeebled monster is NOT halved — gated on
    # the attack's nature, not distance.
    ranged = MonsterAbility(id="rock", name="Rock", original_description="",
                            ability_type=AbilityType.RANGED_ATTACK,
                            attack_bonus=6, damage_dice="2d8", damage_type="bludgeoning")
    eng.state.combatant_stats["pc"]["current_hp"] = hp0
    eng._execute_single_monster_attack(attacker, stats, ranged, "pc")
    ranged_dmg = hp0 - eng.state.combatant_stats["pc"]["current_hp"]
    assert ranged_dmg == full        # full, not halved


def test_conjure_fey_no_longer_frightens():
    sp = SpellRegistry.get_instance().get_spell("conjure_fey")
    assert "frightened" not in (sp.conditions_applied or [])


def test_has_active_buff_flag():
    eng = CombatEngine(combat_state=CombatState())
    stats = {"active_buffs": [{"halve_strength_damage": True}]}
    assert eng._has_active_buff_flag(stats, "halve_strength_damage") is True
    assert eng._has_active_buff_flag(stats, "nope") is False
    assert eng._has_active_buff_flag({}, "halve_strength_damage") is False


def test_contagion_poisons_on_a_hit(monkeypatch):
    SpellRegistry.reset()
    monkeypatch.setattr(spell_system, "roll_d20",
                        lambda *a, **k: D20Result(rolls=[15], modifier=0, total=15))  # forced hit
    r = cast_spell(_caster("contagion"), "contagion", 5, [_target()])
    assert r.success, r.description
    assert (r.conditions_applied or {}).get("e") == ["poisoned"]
    SpellRegistry.reset()


def test_ray_of_enfeeblement_debuffs_on_a_hit_only(monkeypatch):
    SpellRegistry.reset()
    # Hit -> debuff applied.
    monkeypatch.setattr(spell_system, "roll_d20",
                        lambda *a, **k: D20Result(rolls=[15], modifier=0, total=15))
    r = cast_spell(_caster("ray_of_enfeeblement"), "ray_of_enfeeblement", 2, [_target()])
    assert r.success
    assert (r.debuffs_applied or {}).get("e") == {"halve_strength_damage": True}

    # Miss -> nothing applied.
    monkeypatch.setattr(spell_system, "roll_d20",
                        lambda *a, **k: D20Result(rolls=[1], modifier=0, total=1, natural_1=True))
    r2 = cast_spell(_caster("ray_of_enfeeblement"), "ray_of_enfeeblement", 2, [_target()])
    assert not (r2.debuffs_applied or {})
    SpellRegistry.reset()


def _combat(attacker_str_mod):
    player = {"id": "brute", "name": "Brute", "type": "player", "hp": 30, "max_hp": 30,
              "ac": 14, "speed": 30, "str_mod": attacker_str_mod, "dex_mod": 0,
              "attack_bonus": 8, "damage_dice": "2d6", "damage_type": "slashing",
              "abilities": {"strength": 18, "dexterity": 10, "constitution": 14,
                            "intelligence": 10, "wisdom": 10, "charisma": 10},
              "class": "fighter", "level": 3, "conditions": []}
    enemy = {"id": "dummy", "name": "Dummy", "type": "enemy", "hp": 200, "max_hp": 200,
             "ac": 5, "speed": 30,
             "abilities": {"strength": 10, "dexterity": 10, "constitution": 10,
                           "intelligence": 8, "wisdom": 8, "charisma": 8},
             "class": "monster", "level": 1, "conditions": []}
    eng = CombatEngine(combat_state=CombatState())
    eng.start_combat([player], [enemy])
    tracker = eng.state.initiative_tracker
    tracker.current_turn_index = next(i for i, c in enumerate(tracker.combatants) if c.id == "brute")
    eng.state.current_turn = TurnState(combatant_id="brute")
    return eng


def test_enfeebled_creature_deals_half_str_weapon_damage(monkeypatch):
    import app.core.rules_engine as rules_engine
    import app.core.dice as dice
    monkeypatch.setattr(rules_engine, "roll_d20",
                        lambda modifier=0, advantage=False, disadvantage=False, **k:
                        D20Result(rolls=[12], modifier=modifier, total=12 + modifier))
    monkeypatch.setattr(dice, "roll_die", lambda sides: 1)   # every damage die = 1

    # Baseline: greatsword (2d6, STR) -> 2 dice + STR mod 4 = 6.
    base = _combat(4)
    r = base.take_action(ActionType.ATTACK, target_id="dummy", weapon_name="greatsword")
    assert r.damage_dealt == 6

    # Enfeebled attacker -> half of a STR weapon attack = 3.
    enf = _combat(4)
    enf.state.combatant_stats["brute"]["active_buffs"] = [{"halve_strength_damage": True}]
    r2 = enf.take_action(ActionType.ATTACK, target_id="dummy", weapon_name="greatsword")
    assert r2.damage_dealt == 3


def test_enfeebled_finesse_attacker_with_tied_mods_uses_dex_and_is_not_halved(monkeypatch):
    """A finesse weapon with STR == DEX is used with DEX (dodging enfeeblement), so the
    damage is NOT halved (the tie must not classify as a Strength attack)."""
    import app.core.rules_engine as rules_engine
    import app.core.dice as dice
    monkeypatch.setattr(rules_engine, "roll_d20",
                        lambda modifier=0, advantage=False, disadvantage=False, **k:
                        D20Result(rolls=[12], modifier=modifier, total=12 + modifier))
    monkeypatch.setattr(dice, "roll_die", lambda sides: 1)

    eng = _combat(3)                                            # str_mod 3
    eng.state.combatant_stats["brute"]["dex_mod"] = 3          # tie
    eng.state.combatant_stats["brute"]["active_buffs"] = [{"halve_strength_damage": True}]
    r = eng.take_action(ActionType.ATTACK, target_id="dummy", weapon_name="rapier")
    # rapier 1d8 (finesse) -> die 1 + mod 3 = 4, NOT halved (uses DEX on the tie).
    assert r.damage_dealt == 4
