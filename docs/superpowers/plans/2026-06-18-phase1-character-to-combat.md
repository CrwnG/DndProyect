# Phase 1 — Character → Combat Loop Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans (inline) or subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**GOAL:** A character created through the builder becomes a **valid, combat-ready combatant for all 12 classes** — correct ability modifiers, HP, AC, and (for casters) correctly-leveled spells — and the created character can actually enter a fight.

**Architecture:** Fix the data-contract seams the audit found. Keep `core/` pure and TDD-driven. Reuse the existing `to_combatant_data` by adding a builder→import-shape **adapter** rather than rewriting either side. Normalize the two class-skill JSON schemas in the builder. Fix the spell-level loader to read per-spell level. Frontend: pass the created character into `startCombat`.

**Tech Stack:** Python 3.13 / FastAPI / pytest (backend); vanilla JS (frontend).

**Success criteria (measurable):**
- `pytest` stays green (currently 1108) + new Phase 1 tests pass.
- All 12 classes can select skills and finalize.
- A finalized character → combatant has non-zero ability mods and correct HP/AC.
- A known L3 spell (Fireball) loads at level 3, a cantrip at level 0.

---

## File structure

- `app/core/character_builder.py` — add `_get_skill_options()` normalizer; use it in `set_class`/`set_skill_choices`/`validate_build`; compute HP across level in `finalize_character`.
- `app/services/character_service.py` — add `builder_to_combatant_data(builder_char)` adapter.
- `app/core/spell_system.py` — fix `_load_spell_file` to read per-spell level with `spell_level`/file fallback.
- `app/api/routes/character_creation.py` — finalize route stores combatant via the adapter.
- `frontend/js/main.js` — pass `this.importedCharacter` into combat start.
- `tests/test_phase1_character_combat.py` — new tests (skills, adapter round-trip, HP-by-level).
- `tests/test_spell_levels.py` — new spell-level regression test.

---

## Task A: Normalize class-skill schema (unblock 4 classes)

8 classes use `skill_choices{options,count}`; rogue/warlock/sorcerer/wizard use `skill_proficiencies{from,choose}`. The builder only reads the former.

**Files:** Modify `app/core/character_builder.py` (`set_class` ~196-209, `set_skill_choices` ~220-223, `validate_build` skill check). Test: `tests/test_phase1_character_combat.py`.

- [ ] **A1 Write failing test**
```python
import pytest
from app.core.character_builder import CharacterBuilder, CharacterBuild

CLASSES = ["barbarian","bard","cleric","druid","fighter","monk","paladin","ranger","rogue","sorcerer","warlock","wizard"]

@pytest.mark.parametrize("class_id", CLASSES)
def test_every_class_exposes_skill_options(class_id):
    b = CharacterBuilder()
    build = CharacterBuild()
    result = b.set_class(build, class_id)
    assert result.valid
    assert len(result.data["skill_options"]) > 0, f"{class_id} has no skill options"
    assert result.data["skill_count"] > 0
```
- [ ] **A2 Run → expect FAIL** for rogue/sorcerer/warlock/wizard (`skill_options == []`).
- [ ] **A3 Implement** — add normalizer and use it:
```python
@staticmethod
def _get_skill_options(class_data: dict):
    """Return (options, count) from either JSON skill schema."""
    sc = class_data.get("skill_choices")
    if isinstance(sc, dict) and sc.get("options"):
        return sc.get("options", []), sc.get("count", 2)
    sp = class_data.get("skill_proficiencies")
    if isinstance(sp, dict):
        return sp.get("from", []), sp.get("choose", 2)
    return [], 2
```
Use it in `set_class` (`skill_options`/`skill_count`) and `set_skill_choices` (`allowed_skills`/`required_count`).
- [ ] **A4 Run → PASS** all 12.

## Task B: Fix spell-level loader

`_load_spell_file` reads file-level `data.get("level")`; L3–L9 files key it `spell_level` (per-spell `level` also present) → those spells default to 0.

**Files:** Modify `app/core/spell_system.py:82-87`. Test: `tests/test_spell_levels.py`.

- [ ] **B1 Failing test**
```python
from app.core.spell_system import SpellRegistry

def test_spell_levels_loaded_correctly():
    reg = SpellRegistry(); reg.load()
    fireball = reg.get_spell("fireball")
    assert fireball is not None and fireball.level == 3
    acid = reg.get_spell("acid_splash")
    assert acid is not None and acid.level == 0
```
- [ ] **B2 Run → FAIL** (fireball.level == 0).
- [ ] **B3 Implement** — prefer per-spell level, fall back to file `spell_level`/`level`:
```python
file_level = data.get("level", data.get("spell_level", 0))
for spell_data in spells_data:
    lvl = spell_data.get("level", file_level)
    spell = self._parse_spell(spell_data, lvl)
    self._index_spell(spell)
```
- [ ] **B4 Run → PASS.** (Adjust `get_spell`/registry method names to the real API if different.)

## Task C: Builder → combatant adapter + finalize route

**Files:** Add `builder_to_combatant_data` to `app/services/character_service.py`; use it in `app/api/routes/character_creation.py:561-568`. Test: `tests/test_phase1_character_combat.py`.

- [ ] **C1 Failing test** (adapter on a representative finalize-output dict):
```python
from app.services.character_service import builder_to_combatant_data

def _sample_builder_char():
    return {
        "name": "Test Wizard", "class": "wizard", "level": 1, "proficiency_bonus": 2,
        "ability_scores": {"strength":8,"dexterity":14,"constitution":13,
                           "intelligence":16,"wisdom":12,"charisma":10},
        "ability_modifiers": {"strength":-1,"dexterity":2,"constitution":1,
                              "intelligence":3,"wisdom":1,"charisma":0},
        "hit_points": 7, "max_hit_points": 7, "armor_class": 12, "speed": 30,
        "skill_proficiencies": ["arcana","history"], "saving_throw_proficiencies": ["intelligence","wisdom"],
        "features": [{"name":"Arcane Recovery","source":"class","description":"..."}],
        "gold": 10, "spellcasting": {"ability":"intelligence","spell_save_dc":13,
            "spell_attack_bonus":5,"spell_slots_max":{1:2},"cantrips_known":["fire_bolt"],
            "prepared_spells":["magic_missile"]},
    }

def test_adapter_produces_valid_combatant():
    c = builder_to_combatant_data(_sample_builder_char())
    assert c["int_mod"] == 3            # non-zero mod (was 0 before fix)
    assert c["max_hp"] == 7 and c["ac"] == 12
    assert c["abilities"]["int_score"] == 16
    assert c["spellcasting"]["spell_slots"] == {1: 2}
    assert c["spellcasting"]["cantrips"] == ["fire_bolt"]
```
- [ ] **C2 Run → FAIL** (`builder_to_combatant_data` undefined).
- [ ] **C3 Implement** in `character_service.py`:
```python
_ABILITY_FULL_TO_ABBR = {"strength":"str","dexterity":"dex","constitution":"con",
                         "intelligence":"int","wisdom":"wis","charisma":"cha"}

def builder_to_combatant_data(char: Dict[str, Any]) -> Dict[str, Any]:
    """Adapt a CharacterBuilder.finalize_character output into to_combatant_data input."""
    scores = char.get("ability_scores", {})
    mods = char.get("ability_modifiers", {})
    abilities = {}
    for full, abbr in _ABILITY_FULL_TO_ABBR.items():
        abilities[abbr] = {"score": scores.get(full, scores.get(abbr, 10)),
                           "mod": mods.get(full, mods.get(abbr, 0))}
    sc = char.get("spellcasting")
    spellcasting = None
    if sc:
        spellcasting = {
            "ability": sc.get("ability", "intelligence"),
            "spell_save_dc": sc.get("spell_save_dc", 10),
            "spell_attack_bonus": sc.get("spell_attack_bonus", 0),
            "spell_slots": sc.get("spell_slots_max", sc.get("spell_slots", {})),
            "cantrips": sc.get("cantrips_known", sc.get("cantrips", [])),
            "prepared_spells": sc.get("prepared_spells", []),
        }
    import_shape = {
        "name": char.get("name", "Unknown Character"),
        "abilities": abilities,
        "hp": char.get("hit_points", char.get("hp", 10)),
        "max_hp": char.get("max_hit_points", char.get("max_hp", char.get("hit_points", 10))),
        "ac": char.get("armor_class", char.get("ac", 10)),
        "speed": char.get("speed", 30),
        "class": char.get("class", "fighter"),
        "level": char.get("level", 1),
        "proficiency_bonus": char.get("proficiency_bonus", 2),
        "features": char.get("features", []),
        "skills": {s: {"proficient": True} for s in char.get("skill_proficiencies", [])},
        "saving_throws": {s: {"proficient": True} for s in char.get("saving_throw_proficiencies", [])},
        "gold": char.get("gold", 0),
        "weapons": char.get("weapons", []),
        "spellcasting": spellcasting,
    }
    return to_combatant_data(import_shape)
```
- [ ] **C4 Run → PASS.**
- [ ] **C5 Wire finalize route** (`character_creation.py:561-568`):
```python
from app.services.character_service import builder_to_combatant_data
imported_characters[result["id"]] = {
    "raw": result,
    "combatant": builder_to_combatant_data(result),
    "source": "character_builder",
    "build_id": build_id,
}
```
- [ ] **C6 Run full suite → green.**

## Task D: HP across level

`finalize_character` computes level-1 HP only. Compute average-per-level for levels 2+.

**Files:** `app/core/character_builder.py:602-665`.

- [ ] **D1 Failing test** — a level-5 fighter (d10) should have HP > level-1 (10+CON):
```python
# build a level-5 fighter via CharacterBuild, finalize, assert hit_points > 10 + con_mod
```
- [ ] **D2 Implement** — HP = `hit_die_max + con` (L1) + `(level-1) * (avg_per_level + con)` where `avg = hit_die_max//2 + 1`; set `hit_dice_remaining = level`.
- [ ] **D3 Run → PASS.**

## Task E (frontend, manual-verify): pass created character into combat
`main.js` stores `this.importedCharacter` but `loadDemoCombat` ignores it. Add a path that, when `importedCharacter` exists, sends it (its `combatant`) to `api.startCombat` instead of the hardcoded demo party. No JS test harness yet (see tests doc) → verify by running the app.

## Task F (follow-up): subclass-selection step
Add a `CreationStep.SUBCLASS` gated by each class's subclass level; populate L1 subclass for cleric/sorcerer/warlock; source IDs from class JSON (invariant #2). Larger — separate task.

---

## Self-review
- Spec coverage: A=skills, B=spells, C=data contract, D=HP, E=frontend wiring, F=subclass. All Phase 1 roadmap items covered.
- Types consistent: adapter output feeds existing `to_combatant_data`; spell test uses registry API (verify method names at execution).
- No placeholders in A–D (full code). E/F are explicitly scoped as manual-verify / follow-up.
