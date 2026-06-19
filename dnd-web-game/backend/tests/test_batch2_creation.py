"""Batch 2: create-character correctness — every class must be able to pick its
class skills, and finalize must enforce that selection for every class.

Two bugs (audit ranks 19/20):
- Bard's `skill_choices.options == "any"` was treated as the literal string "any",
  so `skill not in "any"` (a substring test) rejected every real skill.
- validate_build only checked `skill_choices.count`, which is absent for the four
  `skill_proficiencies`-schema classes (rogue/sorcerer/warlock/wizard), so they
  finalized with zero class skills.
"""
from app.core.character_builder import CharacterBuilder


def _build(cls):
    builder = CharacterBuilder()
    build = builder.create_new_build()
    builder.set_class(build, cls)
    return builder, build


def test_bard_any_options_accepts_real_skills():
    builder, build = _build("bard")
    res = builder.set_skill_choices(build, ["acrobatics", "persuasion", "stealth"])
    assert res.valid, res.errors
    assert build.skill_choices == ["acrobatics", "persuasion", "stealth"]


def test_bard_still_rejects_a_non_skill():
    builder, build = _build("bard")
    res = builder.set_skill_choices(build, ["acrobatics", "persuasion", "flying"])
    assert not res.valid


def test_bard_enforces_its_count_of_three():
    builder, build = _build("bard")
    res = builder.set_skill_choices(build, ["acrobatics", "persuasion"])  # only 2
    assert not res.valid


def test_skill_proficiencies_classes_can_pick_skills():
    """rogue/sorcerer/warlock/wizard use the {from, choose} schema."""
    cases = {"rogue": 4, "sorcerer": 2, "warlock": 2, "wizard": 2}
    for cls, count in cases.items():
        builder, build = _build(cls)
        opts, required = builder._get_skill_options(builder.rules.get_class(cls))
        assert required == count
        chosen = list(opts)[:count]
        res = builder.set_skill_choices(build, chosen)
        assert res.valid, f"{cls}: {res.errors}"


def test_validate_build_requires_skills_for_every_class_with_skills():
    builder = CharacterBuilder()
    for cls in ("rogue", "sorcerer", "warlock", "wizard", "bard", "fighter"):
        build = builder.create_new_build()
        builder.set_class(build, cls)
        res = builder.validate_build(build)
        assert any("skill" in e.lower() for e in res.errors), \
            f"{cls} should require class skill selection before finalizing"


def test_setting_skills_satisfies_the_requirement_for_every_class():
    """The skill gate must be satisfiable for EVERY class (incl. Bard's 'any'):
    once valid skills are chosen, validate_build no longer reports a skill error."""
    builder = CharacterBuilder()
    for cls in ("rogue", "sorcerer", "warlock", "wizard", "bard", "fighter", "ranger"):
        build = builder.create_new_build()
        builder.set_class(build, cls)
        opts, count = builder._get_skill_options(builder.rules.get_class(cls))
        res = builder.set_skill_choices(build, list(opts)[:count])
        assert res.valid, f"{cls}: could not set skills: {res.errors}"
        errs = builder.validate_build(build).errors
        assert not any("skill" in e.lower() for e in errs), f"{cls}: {errs}"
