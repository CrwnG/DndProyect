"""Batch 44 (Durability P6): /encounter/generate degrades to a deterministic encounter offline.

`generate_encounter` raised 503 when no ANTHROPIC_API_KEY was set, so an offline game could
not produce an ad-hoc encounter — even though the engine, CombatSetup and EnemySpawn are all
key-free. This violates the project's "graceful degradation is a hard requirement" rule. The
new `build_offline_encounter` returns a deterministic, level-scaled combat encounter (or a
simple story beat for non-combat types) so offline play stays unblocked.
"""
from app.services.campaign_generator import build_offline_encounter
from app.models.campaign import Campaign, EncounterType


def _campaign():
    return Campaign(id="c-off", name="Offline Quest")


def test_offline_combat_encounter_has_scaled_enemies():
    enc = build_offline_encounter(_campaign(), "combat", {"party_level": 3, "difficulty": "medium"})
    assert enc.type == EncounterType.COMBAT
    assert enc.combat is not None
    assert enc.combat.enemies, "offline combat must spawn at least one enemy (no soft-lock)"
    total = sum(e.count for e in enc.combat.enemies)
    assert total >= 1
    # Round-trips to JSON for the route response.
    assert enc.to_dict()["combat"]["enemies"]


def test_offline_encounter_scales_difficulty_and_level():
    easy = build_offline_encounter(_campaign(), "combat", {"party_level": 5, "difficulty": "easy"})
    deadly = build_offline_encounter(_campaign(), "combat", {"party_level": 5, "difficulty": "deadly"})
    easy_total = sum(e.count for e in easy.combat.enemies)
    deadly_total = sum(e.count for e in deadly.combat.enemies)
    assert deadly_total > easy_total, "a deadly encounter should field more foes than an easy one"

    low = build_offline_encounter(_campaign(), "combat", {"party_level": 1})
    high = build_offline_encounter(_campaign(), "combat", {"party_level": 12})
    low_tpl = low.combat.enemies[0].template
    high_tpl = high.combat.enemies[0].template
    assert low_tpl != high_tpl, "higher-level parties should face a tougher foe template"


def test_offline_non_combat_encounter_has_story_no_combat():
    enc = build_offline_encounter(_campaign(), "social", {"party_level": 2})
    assert enc.type == EncounterType.SOCIAL
    assert enc.combat is None
    assert enc.story is not None


def test_offline_unknown_type_defaults_to_combat():
    enc = build_offline_encounter(_campaign(), "not-a-real-type", {"party_level": 1})
    assert enc.type == EncounterType.COMBAT
    assert enc.combat is not None and enc.combat.enemies
