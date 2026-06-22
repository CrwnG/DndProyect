"""Batch 8: gold persistence across combat (campaign play).

Shop buy/sell during combat mutate the in-combat combatant_stats['gold'], but a
member's gold was never initialized from / written back to the PartyMember, so
every mid-combat purchase/sale was reverted when combat ended (audit economy
item). For campaign play the PartyMember is the source of truth (and the session
persists), so flow member.gold into the combatant and back out on combat end.
"""
from app.core.campaign_engine import CampaignEngine
from app.models.game_session import PartyMember
from app.models.campaign import (
    Campaign, Encounter, EncounterType, CombatSetup, EnemySpawn,
    GridEnvironment, StoryContent,
)


def _combat_campaign():
    return Campaign(
        id="t", name="T", description="T", author="T", starting_encounter="c1",
        encounters={
            "c1": Encounter(
                id="c1", name="Battle", type=EncounterType.COMBAT,
                story=StoryContent(intro_text="Fight!"),
                combat=CombatSetup(enemies=[EnemySpawn(template="goblin", count=1)],
                                   environment=GridEnvironment()),
            ),
        },
    )


def _member(gold):
    return PartyMember(
        id="hero", name="Hero", character_class="fighter",
        class_levels={"fighter": 1}, _level=1,
        strength=15, dexterity=12, constitution=14, max_hp=20, current_hp=20,
        gold=gold,
    )


def test_member_gold_flows_into_combat():
    engine = CampaignEngine.create_new(_combat_campaign(), [_member(100)])
    engine.session.current_encounter_id = "c1"
    engine._start_combat()
    assert engine.combat_engine.state.combatant_stats["hero"]["gold"] == 100


def test_shop_gold_change_persists_to_member_on_combat_end():
    member = _member(100)
    engine = CampaignEngine.create_new(_combat_campaign(), [member])
    engine.session.current_encounter_id = "c1"
    engine._start_combat()

    # Simulate selling loot at a shop mid-combat (gold goes up).
    engine.combat_engine.state.combatant_stats["hero"]["gold"] = 175

    engine._end_combat(victory=True)
    assert member.gold == 175       # persisted, not reverted to 100


def test_gold_persists_on_defeat_too():
    member = _member(50)
    engine = CampaignEngine.create_new(_combat_campaign(), [member])
    engine.session.current_encounter_id = "c1"
    engine._start_combat()
    engine.combat_engine.state.combatant_stats["hero"]["gold"] = 80

    engine._end_combat(victory=False)
    assert member.gold == 80        # you keep your gold whether you win or lose
