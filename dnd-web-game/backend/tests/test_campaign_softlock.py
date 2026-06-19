"""Batch 1: campaign combat soft-lock fixes.

A COMBAT encounter must never end up with combat=None / 0 enemies — that strands
the session forever (_start_combat returns "No combat setup" with no transition).
Two triggers: (1) a prose combat with no inline stat block -> parser leaves
combat=None; (2) any enemy other than goblin/orc/skeleton (the only 3 templates)
-> silently dropped at spawn time. These tests cover the fix end to end.
"""
from app.models.campaign import (
    Campaign, Encounter, EncounterType, CombatSetup, EnemySpawn, GridEnvironment,
    StoryContent,
)


def _engine_stub():
    """A CampaignEngine instance sufficient to exercise enemy-spawn helpers
    (they only touch self._enemy_cache)."""
    from app.core.campaign_engine import CampaignEngine
    eng = CampaignEngine.__new__(CampaignEngine)
    eng._enemy_cache = {}
    return eng


def _combat_campaign(combat):
    return Campaign(
        id="t", name="T", description="T", author="T",
        starting_encounter="c1",
        encounters={
            "c1": Encounter(id="c1", name="Battle", type=EncounterType.COMBAT,
                            story=StoryContent(intro_text="Fight!"), combat=combat),
        },
    )


# --------------------------------------------------------------------------- #
# Engine: unknown enemy templates fall back to a shipped one instead of dropping
# --------------------------------------------------------------------------- #

def test_resolve_fallback_template_picks_by_hint():
    eng = _engine_stub()
    assert eng._resolve_fallback_template(EnemySpawn(template="zombie")) == "skeleton"
    assert eng._resolve_fallback_template(EnemySpawn(template="ogre")) == "orc"
    assert eng._resolve_fallback_template(EnemySpawn(template="bandit")) == "goblin"


def test_create_enemy_dicts_never_drops_unknown_template():
    eng = _engine_stub()
    setup = CombatSetup(enemies=[EnemySpawn(template="bandit", count=6)],
                        environment=GridEnvironment())
    dicts = eng._create_enemy_dicts(setup)

    assert len(dicts) == 6                         # not dropped to []
    for d in dicts:
        assert d["name"]                           # keeps a display name
        assert d["actions"]                        # real attacks (shipped template)
        assert d["max_hp"] > 1                      # real stats, not a 1-HP stub


def test_enemy_spawn_count_is_clamped_to_at_least_one():
    """QA-F1: a 0/negative/malformed count must not yield 0 enemies (which would
    pass the 'non-empty list' checks yet still soft-lock)."""
    assert EnemySpawn(template="bandit", count=0).count == 1
    assert EnemySpawn(template="bandit", count=-3).count == 1
    assert EnemySpawn(template="bandit", count="oops").count == 1
    assert EnemySpawn(template="bandit", count=4).count == 4


def test_create_enemy_dicts_handles_zero_count_spawn():
    """QA-F1: a zero-count spawn still produces at least one combatant."""
    eng = _engine_stub()
    setup = CombatSetup(enemies=[EnemySpawn(template="bandit", count=0)],
                        environment=GridEnvironment())
    assert len(eng._create_enemy_dicts(setup)) >= 1


def test_create_enemy_dicts_keeps_narrative_name():
    eng = _engine_stub()
    setup = CombatSetup(enemies=[EnemySpawn(template="cultist", count=1)],
                        environment=GridEnvironment())
    [d] = eng._create_enemy_dicts(setup)
    assert "cultist" in d["name"].lower()          # the requested identity is preserved


# --------------------------------------------------------------------------- #
# Parser: a COMBAT section with no parseable enemies gets a non-None combat
# --------------------------------------------------------------------------- #

def test_parser_combat_without_enemies_gets_default_spawn():
    from app.services.campaign_parser import CampaignParserService
    p = CampaignParserService()
    enc = p._create_encounter(
        {"type": "combat", "name": "Ambush", "description": "Bandits leap out!", "enemies": []},
        0, 1,
    )
    assert enc.type == EncounterType.COMBAT
    assert enc.combat is not None
    assert len(enc.combat.enemies) >= 1


def test_parser_recovers_enemy_counts_from_prose():
    from app.services.campaign_parser import CampaignParserService
    p = CampaignParserService()
    enc = p._create_encounter(
        {"type": "combat", "name": "Ambush",
         "description": "Combat: 6 bandits ambush the party on the road.", "enemies": []},
        0, 1,
    )
    assert enc.combat is not None
    total = sum(s.count for s in enc.combat.enemies)
    assert total >= 6


# --------------------------------------------------------------------------- #
# validate(): the soft-lock is reported
# --------------------------------------------------------------------------- #

def test_validate_flags_combat_without_enemies():
    none_combat = _combat_campaign(None)
    assert any("enem" in e.lower() for e in none_combat.validate())

    empty_combat = _combat_campaign(CombatSetup(enemies=[], environment=GridEnvironment()))
    assert any("enem" in e.lower() for e in empty_combat.validate())

    ok = _combat_campaign(CombatSetup(enemies=[EnemySpawn(template="goblin")],
                                      environment=GridEnvironment()))
    assert not any("enem" in e.lower() for e in ok.validate())


# --------------------------------------------------------------------------- #
# Generator: empty COMBAT encounters are sanitized before the campaign is used
# --------------------------------------------------------------------------- #

def test_generator_sanitizes_empty_combat_encounters():
    from app.services.campaign_generator import sanitize_combat_encounters
    campaign = _combat_campaign(None)
    sanitize_combat_encounters(campaign)
    enc = campaign.encounters["c1"]
    assert enc.combat is not None and len(enc.combat.enemies) >= 1


# --------------------------------------------------------------------------- #
# End-to-end: a COMBAT encounter that reached gameplay with no combat must not
# strand the session (defense-in-depth in _start_combat).
# --------------------------------------------------------------------------- #

def test_start_combat_does_not_strand_on_missing_combat():
    from app.core.campaign_engine import CampaignEngine
    from app.models.game_session import PartyMember

    campaign = _combat_campaign(None)
    engine = CampaignEngine.create_new(
        campaign, [PartyMember(id="p1", name="Hero", character_class="Fighter")]
    )
    engine.session.current_encounter_id = "c1"

    result = engine._start_combat()
    assert result.get("error") != "No combat setup for this encounter"
