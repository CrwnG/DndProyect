"""Batch 4: combat depth — enemy spellcasters + spell-applied conditions.

- Enemy casters crashed: the route did `current_hp - result.damage_dealt`, but
  damage_dealt is a per-target DICT -> `int - dict` TypeError on every enemy
  damage spell (audit rank 5).
- Save/control spells (Hold Person, Web, Faerie Fire, …) were cosmetic on the
  player route: it applied damage/healing but dropped `result.conditions_applied`
  (audit rank 6).
"""


class _Result:
    """Minimal stand-in for a SpellCastResult (data holder)."""
    def __init__(self, damage_dealt=None):
        self.damage_dealt = damage_dealt


def test_spell_total_damage_sums_per_target_dict():
    from app.api.routes.combat import _spell_total_damage

    assert _spell_total_damage(_Result({"t1": 8, "t2": 5})) == 13   # the crash case
    assert _spell_total_damage(_Result({})) == 0
    assert _spell_total_damage(_Result(7)) == 7                      # legacy int
    assert _spell_total_damage(_Result(None)) == 0


def _engine_with_target():
    from app.core.combat_engine import CombatEngine, CombatState

    player = {
        "id": "p1", "name": "Mage", "type": "player",
        "hp": 24, "max_hp": 24, "ac": 13, "speed": 30,
        "abilities": {"strength": 8, "dexterity": 14, "constitution": 12,
                      "intelligence": 16, "wisdom": 10, "charisma": 10},
        "class": "wizard", "level": 5, "conditions": [],
    }
    enemy = {
        "id": "ogre-1", "name": "Ogre", "type": "enemy",
        "hp": 30, "max_hp": 30, "ac": 11, "speed": 40,
        "abilities": {"strength": 19, "dexterity": 8, "constitution": 16,
                      "intelligence": 5, "wisdom": 7, "charisma": 7},
        "class": "monster", "level": 1, "conditions": [],
    }
    engine = CombatEngine(combat_state=CombatState())
    engine.start_combat([player], [enemy])
    return engine


def test_apply_spell_conditions_updates_stats_and_combatant():
    from app.api.routes.spells import _apply_spell_conditions

    engine = _engine_with_target()
    _apply_spell_conditions(engine, {"ogre-1": ["restrained", "prone"]})

    cached = engine.state.combatant_stats["ogre-1"]["conditions"]
    assert "restrained" in cached and "prone" in cached
    combatant = engine.state.initiative_tracker.get_combatant("ogre-1")
    assert "restrained" in combatant.conditions

    # Idempotent: re-applying the same condition doesn't duplicate it.
    _apply_spell_conditions(engine, {"ogre-1": ["restrained"]})
    assert cached.count("restrained") == 1


def test_apply_spell_conditions_tolerates_empty_and_unknown_target():
    from app.api.routes.spells import _apply_spell_conditions

    engine = _engine_with_target()
    _apply_spell_conditions(engine, None)                     # no-op
    _apply_spell_conditions(engine, {})                       # no-op
    _apply_spell_conditions(engine, {"ghost": ["stunned"]})   # unknown target -> no crash
