# Core — Rules Engine (combat · character · spells · progression)

> Area doc. Parent: [`../../CLAUDE.md`](../../CLAUDE.md) → [backend](../../CLAUDE.md). This is the most-tested, highest-value layer. Keep it FastAPI-free and pure.

## What's here

| Domain | Files | State |
|---|---|---|
| Combat | `combat_engine.py`, `rules_engine.py`, `rules_config.py`, `initiative.py`, `movement.py`, `reactions.py`, `condition_effects.py`, `death_saves.py`, `weapon_mastery.py`, `monster_abilities.py`, `surfaces.py`, `dice.py`, `combat_storage.py` | Strong core, several crash bugs |
| Character build | `character_builder.py` | Broken seams |
| Progression | `progression.py`, `level_up.py`, `multiclass.py`, `hit_dice.py`, `feats.py`, `subclasses.py`, `subclass_registry.py` | Math solid, wiring drifts |
| Spells/resources | `spell_system.py`, `class_spellcasting.py`, `cantrip_scaling.py`, `ki_system.py`, `sorcerer_features.py`, `warlock_features.py`, `wild_shape.py` | Tables solid, effects unreliable |

## Combat — what works vs what crashes

**Solid & rules-faithful (2024):** turn/round loop + initiative (DEX tiebreak), action/bonus/reaction economy + Extra Attack, advantage/disadvantage cancellation, cover (+2/+5 via Bresenham LoS), crits (nat20, Champion range, player-only-crit rule), concentration (CON save DC max(10,dmg/2), War Caster), opportunity attacks (Disengage/Sentinel/Mobile), death saves, class features (Rage, Second Wind, Cunning Action, Martial Arts, Action Surge, Divine Smite, Stunning Strike, Sneak Attack), all 8 weapon masteries, grapple/shove, legendary actions, resistance/immunity/vulnerability.

**Crash/correctness bugs (fix before trusting monster turns):**
- 🔴 **`roll_dice` does not exist in `dice.py`** (only `roll_die`/`roll_damage`) yet it's imported/called in `surfaces.py:9` and `combat_engine.py:4380,4563,4590` → `import surfaces` fails and every monster Multiattack / generic save-AoE raises ImportError. **Add `roll_dice(notation)` to `dice.py`.**
- 🔴 `combat_engine.py:4574` reads `attack_roll.natural_roll` — `D20Result` has no such attr (`natural_20`/`base_roll`) → AttributeError on single monster attacks.
- 🟠 `monster_abilities.py:544,555` sets `result.extra_data[...]` but `AbilityResult` has no `extra_data` field → breath weapons crash vs Evasion users.
- 🟠 Monster AoE damage reads `damage_immunities/resistances/vulnerabilities` but stats cache them as `immunities/resistances/vulnerabilities` (`combat_engine.py:584-586,4628`) → monster damage ignores all resist/immune.
- 🟠 `subclass_id` is never cached in `_cache_combatant_stats` → Champion expanded crit & Assassinate never trigger (`combat_engine.py:3093-3103`).
- Surfaces are effectively dead (no `surface_manager` on `CombatState`); reaction abilities (Shield/Counterspell/Uncanny Dodge) exist as functions but aren't offered mid-resolution; positions stored as tuples aren't JSON-safe for DB round-trip.

## Character builder — the broken seams (top gameplay blockers)

1. 🔴 **Skill selection broken for 4 classes.** Builder reads `skill_choices.options` (`character_builder.py:221-234`), but `rogue/warlock/sorcerer/wizard` JSON use `skill_proficiencies{choose,from}` (verified). Those classes get `allowed_skills=[]` → every skill rejected, and validation doesn't catch it. → normalize both shapes in `rules_loader` (see [data](../data/CLAUDE.md)).
2. 🔴 **Builder output ≠ combatant shape.** `finalize_character` emits flat `ability_scores` + top-level `hit_points/armor_class` and **no** nested `abilities{str:{score,mod}}`, no top-level `*_mod`/`attack_bonus`/`damage_dice`. Both `character_service.to_combatant_data` (nested) and `combat_engine._cache_combatant_stats` (top-level mods) need that shape → created characters become 10HP/AC10/+0. **This is invariant #1 in the root doc.**
3. 🟠 HP/hit dice computed at **level 1 only** regardless of `build.level` (`:603-605,665`).
4. 🟠 **No subclass step** — `build.subclass_id` stays None; cleric/sorcerer/warlock never get their L1 subclass.
5. `_build_spellcasting` is a stub (hardcoded `{1:2}` slots, empty spell lists); background ability bonuses computed but not enforced.

## Progression — math solid, IDs drift

XP thresholds, proficiency bonus, multiclass prereqs (AND/OR), multiclass proficiency grants, and hit dice are **correct per 2024**. But: `level_up._get_subclass_options` hardcodes **wrong subclass IDs** for most classes (`berserker` vs `path_of_the_berserker`, `evocation` vs `evoker`, …) — **invariant #2: use the JSON IDs everywhere**. `_get_features_for_level` is a stub; the spell-slot update is behind a fragile `try/except ImportError`. `progression.py:262` has a typo CR key `1\2` (should be `1/2`).

## Spells — tables right, effects unreliable

Slot tables (full/half/pact), save DC (8+prof+mod), attack bonus, multiclass caster level, cantrip scaling (5/11/17), area resolution: **all correct**. But:
- 🔴 Combat damage/heal is **regex-parsed from prose** (`spell_system.py:210-219`) → Magic Missile, Cure Wounds, Healing Word, Chromatic Orb deal/heal **0**; only ~46% of 432 spells produce a real effect.
- 🔴 Upcasting guarded by a `'1d'` substring check (`:809`); `higher_levels=None` (Fireball, Lightning Bolt) never scale.
- 🟠 `cast_spell()` consumes slots on a discarded local object (`:1410`) — dead code; only the route's second caster actually spends a slot (twinned double-applies).
- 🟠 ~36 save-spells parse a save type but apply no damage/condition (`:1325`); metamagic & sorcery↔slot conversion are cosmetic (deduct points, change nothing).

**Invariant #4: give spells explicit structured combat fields** (`damage`/`type`/`heal`/`save`/`scaling`) in the JSON and consume those — stop parsing prose.

## How to work here

- Reproduce each invariant violation with a **failing unit test first** (TDD), then fix. Highest-value tests: `build→to_combatant_data` round trip (non-zero mods/HP/AC), spell→applied-effect per level, level-up slot/subclass changes.
- The unit suite already imports these modules directly (that's why it passes despite the app not booting). Keep this layer importable without FastAPI.
