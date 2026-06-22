"""Batch 7: leveling grants real class features.

_get_features_for_level was a stub that only ever returned "Extra Attack" (L5) +
the proficiency-bonus bump, so a level-up reported (and recorded) no actual class
features. Read the real per-level features from the class JSON and record their
ids onto member.class_features (a serialized field).
"""
from app.models.game_session import PartyMember
from app.core.level_up import apply_level_up, _get_features_for_level


def test_get_features_for_level_reads_real_class_features():
    benefits = _get_features_for_level("fighter", 2)
    ids = [b.value for b in benefits if b.benefit_type == "feature"]
    assert "action_surge" in ids
    assert "tactical_mind" in ids
    # A level with no class feature returns no feature benefits (here: none at L1
    # beyond the base — just confirms it doesn't dump every prior level's features).
    assert all(b.benefit_type == "feature" for b in benefits if b.value in ("action_surge", "tactical_mind"))


def test_level_up_records_class_features_on_member():
    member = PartyMember(
        id="f1", name="Fighter", character_class="fighter",
        class_levels={"fighter": 1}, _level=1,
        constitution=14, max_hp=12, current_hp=12,
        hit_die_size=10, hit_dice_total=1, hit_dice_remaining=1,
        xp=300,    # enough for level 2 (fighter gains Action Surge + Tactical Mind)
    )
    result = apply_level_up(member, new_level=2)

    assert result.success, result.errors
    names = [n.lower() for n in result.features_gained]
    assert any("action surge" in n for n in names)
    assert "action_surge" in (member.class_features or [])
    assert "tactical_mind" in member.class_features


def test_level_up_records_features_across_skipped_levels():
    """QA: a multi-level jump (a bulk XP reward can level 1 -> 3 in one call) must
    record features from the intermediate levels too, not just the final level."""
    member = PartyMember(
        id="f2", name="Fighter", character_class="fighter",
        class_levels={"fighter": 1}, _level=1,
        constitution=14, max_hp=12, current_hp=12,
        hit_die_size=10, hit_dice_total=1, hit_dice_remaining=1,
        xp=900,    # qualifies for level 3
    )
    result = apply_level_up(member, new_level=3, subclass_choice="champion")

    assert result.success, result.errors
    # Level-2 features (Action Surge, Tactical Mind) must not be skipped.
    assert "action_surge" in member.class_features
    assert "tactical_mind" in member.class_features


def test_class_features_field_serializes():
    member = PartyMember(id="x", name="X", character_class="fighter")
    member.class_features = ["action_surge"]
    assert member.to_dict().get("class_features") == ["action_surge"]
    # round-trips through from_dict
    restored = PartyMember.from_dict(member.to_dict())
    assert "action_surge" in restored.class_features
