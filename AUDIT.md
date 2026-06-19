# DnD_Proyect — Progress & Playability Audit

**Date:** 2026-06-18 · **Method:** two Claude multi-agent passes (16 subsystem/flow agents, structured) + an independent Codex GPT-5.5 (xhigh, read-only) QA pass. Top boot blockers re-verified by hand. See per-area [CLAUDE.md](CLAUDE.md) docs for fix-level detail.

## Vision

A **Baldur's Gate 3–inspired tactical D&D 5e (2024) browser game with an AI Dungeon Master**: FastAPI backend with a rules-accurate engine (character creation, progression, spellcasting, 8×8 grid combat), an Anthropic-powered AI DM with template fallbacks, authored + AI-generated campaigns, a campaign editor, multiplayer with party voting, and loot/shops. Frontend is vanilla-JS. Content target: **SRD 5.2.1 / CC-BY-4.0**.

> **Update 2026-06-18 (post-audit):** Phase 0 executed — the app now **boots**, the live server serves `/api/health`, and **1108/1108 backend tests pass** (was 1095/1103). Fixed: `combat.py` `Query` import, missing auth deps, `errors.py` `AuthError` `http_status`, + 3 stale tests. The verdict below was the pre-fix baseline; the boot blockers are cleared, the **gameplay** blockers (#2–#5) remain. See [ROADMAP.md](ROADMAP.md) Phase 1.

## Verdict: ⚠️ NOT YET PLAYABLE (but the foundation is strong)

The **logic** of the core loop is complete and correct — a static trace of the tutorial (cutscene → choice/skill-check → goblin combat → victory → next encounter → boss → win) resolves end-to-end, works offline with no API key, and the rules engine passes 1095/1103 unit tests. But the **assembled application cannot run** (import/dependency blockers), and the **create-character → fight** seam is broken at multiple points. Estimated overall completeness: **~50%** — lots of breadth, blocked by a handful of high-leverage seams.

## Subsystem scorecard

| Subsystem | Done | Status |
|---|---|---|
| Combat engine & rules | 62% | Solid core (turn loop, action economy, adv/cover/crits/concentration/OAs/death saves/masteries); monster Multiattack/AoE crash; no DB rehydrate |
| Character creation & progression | ~50% | Progression math solid; skill selection broken for 4 classes; no subclass step; output shape ≠ combatant |
| Spells & spellcasting | 52% | Slot/DC/scaling tables correct; ~54% of spells deal 0 effect (prose regex); upcast broken; metamagic cosmetic |
| Campaign engine & AI DM | 62% | State machine + graceful no-key fallback solid; cutscene rewards dropped; save/load broken; consequence/pacing modules unwired |
| Campaign generator/parser/editor | 60% | Import path plausibly works; **editor rebuilt 2026-06-19 — DB-backed + schema-correct (R1)** |
| Multiplayer | 38% | Real WS + voting UI, but no auth, deadlocking timeouts, not wired to gameplay — demo scaffold |
| Loot/equipment/shops | 55% | Loot + equip affect combat (verified); **shops 500 (missing module)**; split gold economy |
| Map/dungeon generation | 45% | Single-room OK but orphaned; multi-room spawns 0 enemies (verified) |
| Frontend | 72% | Combat/campaign loops genuinely wired + offline demo; auth double-`/api`; created char never reaches combat |
| Game data (2024 JSON) | 68% | Content broad & well-formed; loader field-name mismatches mis-index spells & block skills |
| Backend infra/auth/persistence | 55% | DB layer coherent; **app won't import**; auth deps missing; auth not enforced |
| Tests | 52% | Backend engine well-tested (1095/1103); frontend ~0% real; e2e can't pass |

## Critical blockers (must fix to be playable)

1. 🔴 **App won't boot:** `combat.py:2026` uses unimported `Query`; `requirements.txt` missing `jose`/`passlib`/`bcrypt`; `errors.py` AuthError double-`http_status` TypeError; bcrypt unpinned.
2. 🔴 **Created characters are unusable:** builder output shape ≠ `to_combatant_data` (→ 10HP/AC10/+0), and the frontend never passes the created character into combat anyway.
3. 🔴 **Spellcasting mis-indexed:** L3–L9 spells read as cantrips (`level` vs `spell_level` key); most spells deal 0 effect (prose regex); upcasting broken.
4. 🔴 **Class skills broken:** rogue/warlock/sorcerer/wizard can't pick skills (`skill_choices` vs `skill_proficiencies`).
5. 🔴 **No durability:** combat/campaign/character live only in memory; lost on restart; save/load broken.

## What's genuinely strong 💪

- Rules-faithful 2024 combat engine and progression math, **backed by 1095 passing unit tests**.
- Correct spell slot / DC / multiclass-caster tables and cantrip/area resolution.
- Comprehensive, well-formed content (12 classes×20 levels×4 subclasses, 10 species, 16 backgrounds, 432 spells, 397 monsters, 332 magic items).
- Clean AI-DM degradation: fully playable offline; AI is purely additive flavor.
- Coherent frontend architecture (single ES-module entry, state manager + event bus + typed API client) with a working offline combat demo.

## Cross-cutting invariants (enforced in [CLAUDE.md](CLAUDE.md))

1. Character data must satisfy `to_combatant_data`. 2. One subclass-ID namespace (the JSON IDs). 3. State round-trips through the DB. 4. Spells use structured combat fields, not prose. 5. Apply mechanics, not flavor text.

## Licensing

Content currently exceeds the SRD subset (likely sourced from the full 2024 PHB/MM) → a real IP risk. Plan: align to **SRD 5.2.1 (CC-BY-4.0)**, drop Product Identity names, add attribution. Not legal advice. See memory `dnd-srd-licensing`.

→ **Fix order:** [ROADMAP.md](ROADMAP.md).
