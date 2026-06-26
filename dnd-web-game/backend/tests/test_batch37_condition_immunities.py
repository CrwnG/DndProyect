"""Batch 37: condition immunities are respected when applying conditions.

Monsters carry `condition_immunities` in their data (a golem immune to poisoned/frightened/
prone; undead immune to frightened/poisoned), and Heroism grants Immunity to Frightened —
but `condition_immunities` was read NOWHERE, so an immune creature still got the condition.
Now `condition_immunities` is seeded into the stats cache, and a single `_apply_condition`
chokepoint refuses a condition the target is immune to (innate OR via a concentration-gated
buff like Heroism). Only real D&D conditions are immunity-checked; action-states aren't.
"""
from app.core.combat_engine import CombatEngine, CombatState


def _eng():
    player = {"id": "pc", "name": "PC", "type": "player", "hp": 30, "max_hp": 30, "ac": 14,
              "speed": 30, "conditions": [], "class": "wizard", "level": 5,
              "abilities": {"strength": 8, "dexterity": 14, "constitution": 12,
                            "intelligence": 18, "wisdom": 10, "charisma": 10}}
    golem = {"id": "golem", "name": "Golem", "type": "enemy", "hp": 60, "max_hp": 60, "ac": 17,
             "speed": 30, "conditions": [], "class": "monster", "level": 5,
             "condition_immunities": ["Frightened", "poisoned", "prone"],
             "abilities": {"strength": 20, "dexterity": 9, "constitution": 18,
                           "intelligence": 3, "wisdom": 11, "charisma": 1}}
    ogre = {"id": "ogre", "name": "Ogre", "type": "enemy", "hp": 40, "max_hp": 40, "ac": 12,
            "speed": 30, "conditions": [], "class": "monster", "level": 2,
            "abilities": {"strength": 16, "dexterity": 8, "constitution": 16,
                          "intelligence": 6, "wisdom": 7, "charisma": 7}}
    eng = CombatEngine(combat_state=CombatState())
    eng.start_combat([player], [golem, ogre])
    return eng


def test_condition_immunities_seeded_into_cache():
    eng = _eng()
    assert eng.state.combatant_stats["golem"]["condition_immunities"] == ["Frightened", "poisoned", "prone"]
    assert eng.state.combatant_stats["ogre"]["condition_immunities"] == []


def test_is_condition_immune_innate_case_insensitive():
    eng = _eng()
    gstats = eng.state.combatant_stats["golem"]
    assert eng._is_condition_immune(gstats, "frightened") is True      # data had "Frightened"
    assert eng._is_condition_immune(gstats, "POISONED") is True
    assert eng._is_condition_immune(gstats, "stunned") is False
    assert eng._is_condition_immune(eng.state.combatant_stats["ogre"], "frightened") is False


def test_apply_condition_refuses_immune_applies_others():
    eng = _eng()
    golem = eng.state.initiative_tracker.get_combatant("golem")
    gstats = eng.state.combatant_stats["golem"]
    assert eng._apply_condition(golem, gstats, "frightened") is False
    assert "frightened" not in golem.conditions and "frightened" not in gstats["conditions"]
    assert eng._apply_condition(golem, gstats, "restrained") is True    # not immune
    assert "restrained" in golem.conditions and "restrained" in gstats["conditions"]
    eng._apply_condition(golem, gstats, "restrained")                  # dedup, no double
    assert golem.conditions.count("restrained") == 1


def test_apply_spell_conditions_respects_immunity():
    eng = _eng()
    eng.apply_spell_conditions({"golem": ["frightened"], "ogre": ["frightened"]})
    assert "frightened" not in eng.state.combatant_stats["golem"]["conditions"]
    assert "frightened" in eng.state.combatant_stats["ogre"]["conditions"]


# ----------------------------- buff-granted (Heroism) ----------------------

def test_heroism_buff_grants_frightened_immunity_gated_on_concentration():
    eng = _eng()
    eng.apply_spell_buffs("pc", {"immunity": ["frightened"]}, ["ogre"], spell_id="heroism")
    eng.state.combatant_stats["pc"]["spellcasting"] = {"concentrating_on": "heroism"}
    ostats = eng.state.combatant_stats["ogre"]
    assert eng._is_condition_immune(ostats, "frightened") is True
    eng.apply_spell_conditions({"ogre": ["frightened"]})
    assert "frightened" not in ostats["conditions"]
    # Caster drops concentration -> immunity lifts.
    eng.state.combatant_stats["pc"]["spellcasting"]["concentrating_on"] = None
    assert eng._is_condition_immune(ostats, "frightened") is False


def test_apply_condition_dedup_is_case_insensitive():
    eng = _eng()
    ogre = eng.state.initiative_tracker.get_combatant("ogre")
    ostats = eng.state.combatant_stats["ogre"]
    assert eng._apply_condition(ogre, ostats, "Restrained") is True
    assert eng._apply_condition(ogre, ostats, "restrained") is True   # accepted (already present)
    assert sum(1 for c in ogre.conditions if str(c).lower() == "restrained") == 1


def test_grapple_immune_target_is_not_grappled():
    eng = _eng()  # golem is immune to... not grappled; give it grappled immunity
    eng.state.combatant_stats["golem"]["condition_immunities"] = ["grappled"]
    golem = eng.state.initiative_tracker.get_combatant("golem")
    gstats = eng.state.combatant_stats["golem"]
    assert eng._apply_condition(golem, gstats, "grappled") is False
    assert "grappled" not in golem.conditions
    assert gstats.get("grappled_by") is None


def test_heroism_strips_existing_frightened_on_grant():
    eng = _eng()
    ogre = eng.state.initiative_tracker.get_combatant("ogre")
    ogre.conditions.append("frightened")
    eng.state.combatant_stats["ogre"]["conditions"] = ["frightened"]
    eng.apply_spell_buffs("pc", {"immunity": ["frightened"]}, ["ogre"], spell_id="heroism")
    assert "frightened" not in eng.state.combatant_stats["ogre"]["conditions"]
    assert "frightened" not in ogre.conditions
