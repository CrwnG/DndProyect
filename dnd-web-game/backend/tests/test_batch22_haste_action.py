"""Batch 22 (Goal b): Haste grants an extra action each turn.

Haste's buff_effects already carry ``extra_action`` (stored on active_buffs by the
#23 buff pipeline), but nothing consumed it — the spell's headline effect did
nothing. ``use_haste_action`` grants one additional action per turn (like Action
Surge), gated on an active, concentration-held Haste buff.
"""
from app.core.combat_engine import CombatEngine, CombatState, TurnState


def _hasted_engine():
    player = {
        "id": "pal", "name": "Paladin", "type": "player",
        "hp": 30, "max_hp": 30, "ac": 16, "speed": 30,
        "str_mod": 3, "attack_bonus": 7, "damage_dice": "1d8", "damage_type": "slashing",
        "abilities": {"strength": 16, "dexterity": 14, "constitution": 14,
                      "intelligence": 10, "wisdom": 10, "charisma": 14},
        "class": "fighter", "level": 5, "conditions": [],
    }
    enemy = {
        "id": "ogre", "name": "Ogre", "type": "enemy",
        "hp": 30, "max_hp": 30, "ac": 13, "speed": 30,
        "abilities": {"strength": 16, "dexterity": 8, "constitution": 16,
                      "intelligence": 6, "wisdom": 7, "charisma": 7},
        "class": "monster", "level": 3, "conditions": [],
    }
    eng = CombatEngine(combat_state=CombatState())
    eng.start_combat([player], [enemy])
    tracker = eng.state.initiative_tracker
    tracker.current_turn_index = next(i for i, c in enumerate(tracker.combatants) if c.id == "pal")
    eng.state.current_turn = TurnState(combatant_id="pal")
    # Self-Hasted: concentration held, extra_action buff active.
    stats = eng.state.combatant_stats["pal"]
    stats["spellcasting"] = {"concentrating_on": "haste"}
    stats["active_buffs"] = [{"source": "pal", "spell_id": "haste",
                              "ac_bonus": 2, "extra_action": True, "speed_multiplier": 2}]
    return eng


def test_haste_grants_an_extra_action_after_the_normal_one():
    eng = _hasted_engine()
    eng.state.current_turn.action_taken = True            # spent the normal action
    assert not eng.state.current_turn.can_take_action()
    r = eng.use_haste_action()
    assert r.success, r.description
    assert eng.state.current_turn.can_take_action()       # action available again
    assert eng.state.current_turn.haste_action_used


def test_haste_attack_action_is_one_weapon_attack_only():
    """Even with Extra Attack, Haste's Attack action grants ONLY one attack."""
    eng = _hasted_engine()
    turn = eng.state.current_turn
    # Fighter made their full Extra Attack (2) this turn.
    turn.max_attacks = 2
    turn.attacks_made = 2
    turn.action_taken = True

    assert eng.use_haste_action().success
    # Exactly one more attack is allowed, not a fresh pair.
    assert turn.max_attacks - turn.attacks_made == 1
    assert turn.can_attack()
    turn.use_attack()                                     # take the single haste attack
    assert not turn.can_attack()                          # no second one
    assert turn.action_taken                              # action consumed again


def test_haste_action_requires_an_active_haste():
    eng = _hasted_engine()
    eng.state.combatant_stats["pal"]["active_buffs"] = []
    assert not eng.use_haste_action().success


def test_haste_action_is_once_per_turn():
    eng = _hasted_engine()
    eng.state.current_turn.action_taken = True
    assert eng.use_haste_action().success
    eng.state.current_turn.action_taken = True
    assert not eng.use_haste_action().success             # already used this turn


def test_haste_action_ends_when_concentration_drops():
    eng = _hasted_engine()
    eng.state.combatant_stats["pal"]["spellcasting"]["concentrating_on"] = None
    assert not eng.use_haste_action().success             # buff inactive -> no extra action


def test_haste_extra_action_cannot_be_used_to_cast_a_spell():
    from app.core.combat_engine import ActionType
    eng = _hasted_engine()
    eng.state.current_turn.action_taken = True
    assert eng.use_haste_action().success
    # Haste forbids spellcasting with the extra action.
    r = eng.take_action(ActionType.CAST_SPELL, target_id="ogre", spell_id="fireball")
    assert not r.success
    assert "Haste" in r.description


def test_haste_extra_action_allows_an_attack():
    from app.core.combat_engine import ActionType
    eng = _hasted_engine()
    eng.state.current_turn.action_taken = True
    eng.use_haste_action()
    r = eng.take_action(ActionType.ATTACK, target_id="ogre")
    assert r.success
    assert eng.state.current_turn.action_taken             # the haste action was spent


def test_failed_haste_attack_does_not_unlock_spellcasting():
    """A allowed-but-failed Haste action (bad target) must NOT free the slot for a
    spell — the restriction is derived from action_taken, which only flips on a spend."""
    from app.core.combat_engine import ActionType
    eng = _hasted_engine()
    eng.state.current_turn.action_taken = True
    eng.use_haste_action()
    bad = eng.take_action(ActionType.ATTACK, target_id="does-not-exist")
    assert not bad.success
    assert not eng.state.current_turn.action_taken         # nothing was spent
    # Still restricted -> can't sneak a spell in.
    assert not eng.take_action(ActionType.CAST_SPELL, target_id="ogre", spell_id="fireball").success


def test_new_turn_refreshes_the_haste_action():
    eng = _hasted_engine()
    eng.state.current_turn.haste_action_used = True
    eng.state.current_turn.reset()
    assert eng.state.current_turn.haste_action_used is False
