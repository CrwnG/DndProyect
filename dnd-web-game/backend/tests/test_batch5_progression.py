"""Batch 5: progression depth.

- Choice-based feats (Resilient, Athlete, Observant, Tavern Brawler, Weapon
  Master) granted nothing: apply_level_up / apply_multiclass_level_up called
  apply_feat_effects WITHOUT the player's ability_choice (audit rank 11).
- Multiclass level-up granted no spell slots: apply_multiclass_level_up never
  called get_multiclass_spell_slots (audit rank 10).
"""
from app.models.game_session import PartyMember
from app.core.level_up import apply_level_up, apply_multiclass_level_up


def test_choice_feat_applies_chosen_ability_and_save_proficiency():
    member = PartyMember(
        id="f1", name="Fighter", character_class="fighter",
        class_levels={"fighter": 3}, _level=3,
        constitution=14, max_hp=28, current_hp=28,
        hit_die_size=10, hit_dice_total=3, hit_dice_remaining=3,
        xp=2700,   # enough for level 4 (fighter gains an ASI/feat at 4)
    )
    result = apply_level_up(
        member, new_level=4, feat_choice="resilient", ability_choice="constitution",
    )
    assert result.success, result.errors
    assert member.constitution == 15                               # 14 + 1 (chosen)
    assert "constitution" in (getattr(member, "saving_throw_proficiencies", []) or [])


def test_multiclass_level_up_grants_spell_slots():
    member = PartyMember(
        id="mc", name="Multi", character_class="wizard",
        class_levels={"wizard": 2}, _level=2,
        strength=15, dexterity=15, constitution=15,
        intelligence=15, wisdom=15, charisma=15,   # meets both multiclass prereqs
        max_hp=14, current_hp=14,
        hit_die_size=6, hit_dice_total=2, hit_dice_remaining=2,
        spell_slots={}, spell_slots_max={},
        xp=900,    # enough for total level 3
    )
    result = apply_multiclass_level_up(member, class_choice="bard", hp_choice="average")

    assert result.success, result.errors
    # wizard 2 + bard 1 = combined caster level 3 -> full-caster slots {1:4, 2:2}
    assert member.spell_slots_max.get(1, 0) == 4
    assert member.spell_slots_max.get(2, 0) == 2
    assert member.spell_slots.get(2, 0) == 2       # newly gained 2nd-level slots available


def test_multiclass_slots_dont_refill_expended_lower_slots():
    """Newly gained slots are granted, but slots already expended stay expended."""
    member = PartyMember(
        id="mc2", name="Multi", character_class="wizard",
        class_levels={"wizard": 2}, _level=2,
        strength=15, dexterity=15, constitution=15,
        intelligence=15, wisdom=15, charisma=15,
        max_hp=14, current_hp=14,
        hit_die_size=6, hit_dice_total=2, hit_dice_remaining=2,
        spell_slots={1: 0}, spell_slots_max={1: 3},   # level-1 slots all spent
        xp=900,
    )
    apply_multiclass_level_up(member, class_choice="bard", hp_choice="average")

    assert member.spell_slots_max.get(1, 0) == 4      # max raised
    assert member.spell_slots.get(1, 0) == 1          # only the +1 gained, not refilled


def test_multiclass_slots_never_downgrade_existing_max():
    """QA: the multiclass slot update must only RAISE the max, never lower it
    (which would corrupt the character / leave remaining > max)."""
    member = PartyMember(
        id="mc3", name="Multi", character_class="wizard",
        class_levels={"wizard": 2}, _level=2,
        strength=15, dexterity=15, constitution=15,
        intelligence=15, wisdom=15, charisma=15,
        max_hp=14, current_hp=14,
        hit_die_size=6, hit_dice_total=2, hit_dice_remaining=2,
        spell_slots={1: 5}, spell_slots_max={1: 5},   # already higher than the table row
        xp=900,
    )
    apply_multiclass_level_up(member, class_choice="bard", hp_choice="average")

    assert member.spell_slots_max.get(1, 0) == 5      # NOT downgraded to the table's 4
    assert member.spell_slots.get(1, 0) <= member.spell_slots_max.get(1, 0)
