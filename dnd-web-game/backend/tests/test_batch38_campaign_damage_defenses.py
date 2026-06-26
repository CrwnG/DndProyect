"""Batch 38: campaign-spawned monsters keep their damage immunities/resistances/vulnerabilities.

`campaign_engine._create_enemy_dicts` built the enemy dict WITHOUT the stat block's
`damage_immunities`/`damage_resistances`/`damage_vulnerabilities`, so a fire elemental
spawned in a campaign took full fire damage and a skeleton took full club damage — the
damage-resistance engine (which works) was a no-op in campaign play. The enemy dict now
maps those `damage_*` fields to the `immunities`/`resistances`/`vulnerabilities` keys the
combat cache + `_resist_flags` read.
"""
from app.core.campaign_engine import CampaignEngine
from app.models.campaign import CombatSetup, EnemySpawn, GridEnvironment
from app.core.combat_engine import CombatEngine, CombatState


def _stub():
    eng = CampaignEngine.__new__(CampaignEngine)
    eng._enemy_cache = {}
    return eng


_TEMPLATE = {
    "name": "Fire Elemental", "hit_points_average": 60, "armor_class": 13,
    "speed": 50, "actions": [],
    "abilities": {"strength": 10, "dexterity": 17, "constitution": 16,
                  "intelligence": 6, "wisdom": 10, "charisma": 7},
    "damage_immunities": ["fire", "poison"],
    "damage_resistances": ["bludgeoning"],
    "damage_vulnerabilities": ["cold"],
    "condition_immunities": ["paralyzed", "poisoned"],
}


def _setup():
    return CombatSetup(enemies=[EnemySpawn(template="fire_elemental", count=1)],
                       environment=GridEnvironment())


def test_create_enemy_dicts_carries_damage_defenses(monkeypatch):
    eng = _stub()
    monkeypatch.setattr(eng, "_load_enemy_template_or_fallback", lambda spawn: _TEMPLATE)
    [d] = eng._create_enemy_dicts(_setup())
    assert d["immunities"] == ["fire", "poison"]
    assert d["resistances"] == ["bludgeoning"]
    assert d["vulnerabilities"] == ["cold"]
    assert d["condition_immunities"] == ["paralyzed", "poisoned"]


def test_campaign_fire_immune_monster_resolves_immunity_in_combat(monkeypatch):
    eng = _stub()
    monkeypatch.setattr(eng, "_load_enemy_template_or_fallback", lambda spawn: _TEMPLATE)
    [d] = eng._create_enemy_dicts(_setup())

    player = {"id": "pc", "name": "PC", "type": "player", "hp": 30, "max_hp": 30, "ac": 14,
              "speed": 30, "conditions": [], "class": "wizard", "level": 5,
              "abilities": {"strength": 8, "dexterity": 14, "constitution": 12,
                            "intelligence": 18, "wisdom": 10, "charisma": 10}}
    ce = CombatEngine(combat_state=CombatState())
    ce.start_combat([player], [d])
    eid = d["id"]
    hp0 = ce.state.combatant_stats[eid]["current_hp"]

    ce._apply_damage_to_target(eid, 20, "fire")                       # immune -> 0
    assert ce.state.combatant_stats[eid]["current_hp"] == hp0

    ce._apply_damage_to_target(eid, 10, "cold")                       # vulnerable -> x2 = 20
    assert ce.state.combatant_stats[eid]["current_hp"] == hp0 - 20

    hp1 = ce.state.combatant_stats[eid]["current_hp"]
    ce._apply_damage_to_target(eid, 8, "bludgeoning")                 # resistant -> //2 = 4
    assert ce.state.combatant_stats[eid]["current_hp"] == hp1 - 4
