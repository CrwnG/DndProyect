"""Batch 6: subclass wiring.

- Level-up wrote subclass to divergent fields: apply_level_up set member.subclass
  (legacy) only; apply_multiclass_level_up set member.subclasses[class] only. Both
  must go through set_subclass so the two stay consistent (audit rank 17).
- The campaign engine never passed a member's subclass into the combatant, so
  subclass combat features (Champion crit, Assassinate) never triggered in play
  — even when the member HAD a subclass.
"""
from app.models.game_session import PartyMember
from app.core.level_up import apply_level_up, apply_multiclass_level_up


def test_single_class_level_up_sets_both_subclass_fields():
    member = PartyMember(
        id="f1", name="Fighter", character_class="fighter",
        class_levels={"fighter": 2}, _level=2,
        constitution=14, max_hp=20, current_hp=20,
        hit_die_size=10, hit_dice_total=2, hit_dice_remaining=2,
        xp=900,   # level 3 (fighter chooses its subclass at 3)
    )
    apply_level_up(member, new_level=3, subclass_choice="champion")

    assert member.subclass == "champion"                 # legacy field (read by combat)
    assert member.get_subclass("fighter") == "champion"  # per-class dict


def test_multiclass_level_up_records_subclass_in_dict():
    member = PartyMember(
        id="mc", name="Multi", character_class="wizard",
        class_levels={"wizard": 2}, _level=2,
        strength=15, dexterity=15, constitution=15,
        intelligence=15, wisdom=15, charisma=15,
        max_hp=14, current_hp=14,
        hit_die_size=6, hit_dice_total=2, hit_dice_remaining=2,
        xp=900,
    )
    # Cleric grants its subclass at class-level 1, so a subclass_choice is required.
    apply_multiclass_level_up(member, class_choice="cleric", subclass_choice="life_domain")

    assert member.get_subclass("cleric") == "life_domain"


def test_campaign_combat_passes_member_subclass_to_combatant():
    from app.core.campaign_engine import CampaignEngine
    from app.models.campaign import (
        Campaign, Encounter, EncounterType, CombatSetup, EnemySpawn,
        GridEnvironment, StoryContent,
    )

    campaign = Campaign(
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
    member = PartyMember(
        id="hero", name="Hero", character_class="fighter",
        class_levels={"fighter": 3}, _level=3,
        strength=16, dexterity=12, constitution=14, max_hp=28, current_hp=28,
        subclass="champion",
    )
    member.set_subclass("fighter", "champion")

    engine = CampaignEngine.create_new(campaign, [member])
    engine.session.current_encounter_id = "c1"
    engine._start_combat()

    cached = engine.combat_engine.state.combatant_stats["hero"]
    assert cached.get("subclass_id") == "champion"
