# Game Data — 2024 ruleset JSON + SRD compliance

> Area doc. Parent: [backend](../../CLAUDE.md). Static content consumed by [core](../core/CLAUDE.md) (`rules_loader.py`, `spell_system.py`, `loot_system.py`).

## Inventory (verified, well-formed JSON — content is broad)

| Category | Count | Path |
|---|---|---|
| Classes | 12 × 20 levels × 4 subclasses (48) | `rules/2024/classes/` |
| Species | 10 | `rules/2024/species/` |
| Backgrounds | 16 | `rules/2024/backgrounds/` |
| Spells | 432 (cantrips→L9) | `rules/2024/spells/` |
| Monsters | 397 (14 type files) | `rules/2024/monsters/` |
| Magic items | 332 | `rules/2024/magic_items/` |
| Feats | origin 12 + general 44 + epic boons 12 | `rules/2024/feats/` |
| Equipment | weapons 43, armor 13, gear/tools/packs ~140 | `rules/2024/equipment/` |

The data is *not* corrupt. The problems are **field-name contracts between data and loaders** — fix these in the loader/consumer, not by mangling content:

## 🔴 Schema landmines (verified)

1. **Spell level key mismatch.** `spell_system.py:82` reads `data.get('level', 0)`, but `level_3.json`–`level_9.json` key per-spell level as **`spell_level`** (cantrips/L1/L2 differ again). Result: higher-level spells indexed as level 0 → slot gating, prepared limits, and scaling all break. Normalize on load.
2. **Class skills key split.** 8 classes use `skill_choices{options,count}`; **rogue/warlock/sorcerer/wizard use `skill_proficiencies{choose,from}`** (verified). `character_builder` reads only `skill_choices` → those 4 can't pick skills. Emit a unified `{count, options}` in `rules_loader`.
3. **Monster key split.** 9 files use `{... "monsters":[]}`, 5 use `{... "creatures":[]}` (celestials/constructs/fey/oozes/plants = 85 monsters). `monster_exporter.py:51` reads only `monsters` → 85 silently dropped.
4. **Epic boons key.** `rules_loader.py:123` requires `boons`, file uses `feats` → `get_epic_boons()` returns 0.
5. **Equipment type key.** Loader stamps `item_type` but `get_equipment_by_type` filters on `type` → always returns `[]`; loader also only ingests `weapon/armor/items/gear` keys, missing `adventuring_gear/tools/equipment_packs/ammunition` (~150 items unreachable).
6. **Encoding.** `loot_system.py:162` opens item files without `encoding='utf-8'`; `artifacts.json` has non-ASCII → can raise `UnicodeDecodeError` on Windows (cp1252). Always pass `encoding='utf-8'`.

`rules_loader` only loads species/classes/backgrounds/feats/equipment — spells/monsters/magic-items use separate ad-hoc loaders, so there's **no single source of truth and no schema validation**. Adding a small `validate_data()` that asserts required keys per category would catch all of the above.

## SRD 5.2.1 / CC-BY-4.0 compliance (see root doc §6)

This game's content boundary is **SRD 5.2.1** (CC-BY-4.0). The SRD includes only a *subset* — roughly one subclass per class, a limited spell/monster list, and excludes Product Identity names (beholder, mind flayer, etc.). **The current data exceeds the SRD** (48 subclasses, 432 spells, many monsters), so before any public/commercial release: restrict to SRD entries or rewrite descriptive text in our own words, drop excluded names, and ship the CC-BY attribution line. Mechanics themselves aren't copyrightable. See memory `dnd-srd-licensing`.

## Adding content

Match the existing per-category schema **and** confirm the loader reads the keys you used (run a load + assert count). When you add a field the engine should act on (e.g. spell `damage`/`scaling`), update the [core](../core/CLAUDE.md) consumer too — flavor text alone does nothing.
