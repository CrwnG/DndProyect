"""Batch 35: every damage source marks a creature defeated at 0 HP.

The main weapon attack set target.is_active=False + emitted combatant_defeated when it
dropped a target to 0, but MANY other sources (monster abilities via
_apply_damage_to_target, opportunity attacks, legendary actions, graze/cleave, the Armor
of Agathys retaliation) reduced HP to 0 WITHOUT marking defeat — so a dead creature kept
taking turns and combat never ended (initiative skips on is_active; is_combat_over counts
is_active). A single idempotent, PLAYER-AWARE `_mark_defeated` helper now runs through
every damage path: enemies/NPCs become inactive (+ event); PLAYERS are left active for the
death-save flow (handled at their turn start).
"""
from app.core.combat_engine import CombatEngine, CombatState


def _eng(enemy_hp=10):
    player = {"id": "pc", "name": "PC", "type": "player", "hp": 30, "max_hp": 30, "ac": 14,
              "speed": 30, "conditions": [],
              "abilities": {"strength": 14, "dexterity": 12, "constitution": 14,
                            "intelligence": 10, "wisdom": 10, "charisma": 10},
              "class": "fighter", "level": 3}
    enemy = {"id": "ogre", "name": "Ogre", "type": "enemy", "hp": enemy_hp, "max_hp": enemy_hp,
             "ac": 12, "speed": 30, "conditions": [],
             "abilities": {"strength": 16, "dexterity": 8, "constitution": 16,
                           "intelligence": 6, "wisdom": 7, "charisma": 7},
             "class": "monster", "level": 2}
    eng = CombatEngine(combat_state=CombatState())
    eng.start_combat([player], [enemy])
    return eng


def _defeat_events(eng):
    return [e for e in (getattr(eng.state, "event_log", []) or [])
            if getattr(e, "event_type", None) == "combatant_defeated"]


def test_mark_defeated_marks_enemy_idempotently():
    eng = _eng()
    ogre = eng.state.initiative_tracker.get_combatant("ogre")
    assert ogre.is_active is True
    eng._mark_defeated(ogre)
    assert ogre.is_active is False
    n = len(_defeat_events(eng))
    assert n == 1
    eng._mark_defeated(ogre)                          # idempotent — no second event
    assert ogre.is_active is False
    assert len(_defeat_events(eng)) == n


def test_mark_defeated_leaves_player_active_for_death_saves():
    eng = _eng()
    pc = eng.state.initiative_tracker.get_combatant("pc")
    eng._mark_defeated(pc)
    assert pc.is_active is True                       # players are NOT removed — death saves
    assert len(_defeat_events(eng)) == 0


def test_mark_defeated_handles_none_target():
    eng = _eng()
    eng._mark_defeated(None)                          # must not crash (legendary actions pass None)


def test_monster_ability_kill_marks_enemy_and_ends_combat():
    """Damage routed through _apply_damage_to_target (breath/mind-blast/multiattack) that
    drops the last enemy to 0 marks it defeated AND ends combat."""
    eng = _eng(enemy_hp=10)
    eng._apply_damage_to_target("ogre", 50, "fire")
    assert eng.state.combatant_stats["ogre"]["current_hp"] == 0
    ogre = eng.state.initiative_tracker.get_combatant("ogre")
    assert ogre.is_active is False
    assert len(_defeat_events(eng)) == 1
    assert eng.state.initiative_tracker.is_combat_over() is True


def test_player_downed_by_ability_stays_active_for_death_saves():
    eng = _eng()
    eng._apply_damage_to_target("pc", 50, "fire")
    pc = eng.state.initiative_tracker.get_combatant("pc")
    assert eng.state.combatant_stats["pc"]["current_hp"] == 0
    assert pc.is_active is True                       # unconscious + death saves, not removed
    assert eng.state.initiative_tracker.is_combat_over() is False


def test_nonlethal_ability_does_not_mark_defeated():
    eng = _eng(enemy_hp=40)
    eng._apply_damage_to_target("ogre", 10, "fire")
    ogre = eng.state.initiative_tracker.get_combatant("ogre")
    assert ogre.is_active is True
    assert eng.state.initiative_tracker.is_combat_over() is False
