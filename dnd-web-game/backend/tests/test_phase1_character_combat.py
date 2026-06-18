"""Phase 1 — character creation -> combat-ready combatant (see ROADMAP.md Phase 1).

Task A: every class must expose selectable skills (the 4 classes using the
        `skill_proficiencies` JSON schema were previously unselectable).
Task C: a finalized builder character must adapt into a valid CombatantData
        (non-zero ability mods, correct HP/AC) instead of 10/10/+0.
"""
import pytest

from app.core.character_builder import CharacterBuilder, CharacterBuild

CLASSES = [
    "barbarian", "bard", "cleric", "druid", "fighter", "monk",
    "paladin", "ranger", "rogue", "sorcerer", "warlock", "wizard",
]


@pytest.mark.parametrize("class_id", CLASSES)
def test_every_class_exposes_skill_options(class_id):
    """All 12 classes must surface skill options + a non-zero count (Task A)."""
    builder = CharacterBuilder()
    build = CharacterBuild()
    result = builder.set_class(build, class_id)

    assert result.valid, result.errors
    assert len(result.data["skill_options"]) > 0, f"{class_id} exposed no skill options"
    assert result.data["skill_count"] > 0, f"{class_id} has skill_count 0"


def _sample_builder_char():
    """A representative CharacterBuilder.finalize_character output (a level-1 wizard)."""
    return {
        "name": "Test Wizard",
        "class": "wizard",
        "level": 1,
        "proficiency_bonus": 2,
        "ability_scores": {
            "strength": 8, "dexterity": 14, "constitution": 13,
            "intelligence": 16, "wisdom": 12, "charisma": 10,
        },
        "ability_modifiers": {
            "strength": -1, "dexterity": 2, "constitution": 1,
            "intelligence": 3, "wisdom": 1, "charisma": 0,
        },
        "hit_points": 7, "max_hit_points": 7, "armor_class": 12, "speed": 30,
        "skill_proficiencies": ["arcana", "history"],
        "saving_throw_proficiencies": ["intelligence", "wisdom"],
        "features": [{"name": "Arcane Recovery", "source": "class", "description": "..."}],
        "gold": 10,
        "spellcasting": {
            "ability": "intelligence", "spell_save_dc": 13, "spell_attack_bonus": 5,
            "spell_slots_max": {1: 2}, "spell_slots_used": {},
            "cantrips_known": ["fire_bolt"], "prepared_spells": ["magic_missile"],
        },
    }


def test_adapter_produces_valid_combatant():
    """builder_to_combatant_data must yield real mods/HP/AC, not the 10/10/+0 fallback (Task C)."""
    from app.services.character_service import builder_to_combatant_data

    combatant = builder_to_combatant_data(_sample_builder_char())

    # Ability modifiers must survive (regression: all were 0 before the fix).
    assert combatant["int_mod"] == 3
    assert combatant["dex_mod"] == 2
    assert combatant["str_mod"] == -1
    # HP/AC must come from the build, not default to 10.
    assert combatant["max_hp"] == 7
    assert combatant["hp"] == 7
    assert combatant["ac"] == 12
    # Nested ability scores for the combat engine.
    assert combatant["abilities"]["int_score"] == 16
    # Spellcasting keys remapped to the combat shape.
    assert combatant["spellcasting"]["spell_slots"] == {1: 2}
    assert combatant["spellcasting"]["cantrips"] == ["fire_bolt"]


def test_hp_scales_with_level():
    """Max HP must scale beyond level 1 (Task D — builder previously fixed HP at L1).

    Rule: full hit die + CON at level 1, then average-rounded-up (die//2 + 1) + CON per level after.
    """
    # d10 fighter, +2 CON
    assert CharacterBuilder._hp_for_level(10, 2, 1) == 12          # 10 + 2
    assert CharacterBuilder._hp_for_level(10, 2, 5) == 44          # 12 + 4*(6+2)
    # d6 wizard, +1 CON, level 3
    assert CharacterBuilder._hp_for_level(6, 1, 3) == 17           # 7 + 2*(4+1)


def test_hp_gain_clamped_to_one_with_negative_con():
    """Each level grants at least 1 HP even with a very negative CON (5e min-1 rule)."""
    # d6, CON 1 (mod -5): L1 = max(1, 6-5) = 1; each later level = max(1, 4-5) = 1
    assert CharacterBuilder._hp_for_level(6, -5, 1) == 1
    assert CharacterBuilder._hp_for_level(6, -5, 3) == 3           # 1 + 2*1, never negative


@pytest.mark.parametrize("class_id", CLASSES)
def test_levelup_subclass_options_match_json(class_id):
    """level_up must offer subclass IDs that exist in the class JSON (Task F / invariant #2).

    Previously _get_subclass_options hardcoded options for only 6 classes with IDs
    that did not match the JSON (e.g. 'berserker' vs 'path_of_the_berserker').
    """
    from app.core.level_up import _get_subclass_options
    from app.services.rules_loader import get_rules_loader

    options = _get_subclass_options(class_id)
    assert len(options) > 0, f"{class_id} exposed no subclass options"

    class_data = get_rules_loader().get_class(class_id)
    json_ids = {s["id"] for s in class_data.get("subclasses", [])}
    option_ids = {o["id"] for o in options}
    assert option_ids <= json_ids, f"{class_id}: {option_ids - json_ids} not in JSON {json_ids}"
