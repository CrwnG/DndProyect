# DnD_Proyect — Roadmap

Ordered by dependency: each phase unblocks the next. Status today (2026-06-18): **strong rules engine, but the assembled game does not boot and the create-character→fight loop is broken.** See [AUDIT.md](AUDIT.md) for evidence and [CLAUDE.md](CLAUDE.md) for invariants.

Severity legend: 🔴 blocks play · 🟠 breaks a system · 🟡 polish.

---

## Phase 0 — Make it boot ✅ DONE (2026-06-18)
**Goal:** `python -c "import app.main"` succeeds and `GET /api/health` returns 200. **Achieved — app boots, server serves, 1108/1108 tests pass.**
- ✅ Added `Query` to the fastapi import in `api/routes/combat.py:10`.
- ✅ Added `python-jose[cryptography]`, `passlib[bcrypt]`, `bcrypt<4.1` to `backend/requirements.txt`.
- ✅ Fixed `core/errors.py` — `AuthError` now takes `http_status` as a param (default 401; `ForbiddenError`=403).
- ✅ Fixed stale `test_new_features.py:7` (`:8001`→`:8000`); fixed 2 stale tests (ActionType count 13→14; missing `username` in an auth fixture).
- ✅ **Exit test:** `tests/test_boot.py` (app import + health route mounted + auth errors instantiate) — green.

## Phase 1 — Make the core loop playable 🎯 (in progress — A/B/C done 2026-06-18)
**Goal:** create a character of any class → enter the tutorial → fight → win → progress.
- ✅ **Character data contract (invariant #1):** added `builder_to_combatant_data` adapter (`character_service.py`) and wired the finalize route to use it, so created characters carry real mods/HP/AC instead of 10/10/+0. *(Persisting via `CharacterRepository` instead of the in-memory dict is deferred to Phase 3 durability.)*
- ✅ **Spell-level key mismatch fixed** — `spell_system._load_spell_file` now reads per-spell `level` with a `spell_level`/file fallback (L3–L9 no longer load as cantrips).
- ✅ **Skill schema normalized** — `CharacterBuilder._get_skill_options` reads both `skill_choices` and `skill_proficiencies`; all 12 classes can pick skills.
- 🔴 **TODO: Wire the created character into combat on the frontend** (`main.js` `importedCharacter` → `startCombat`). No JS test harness yet → manual/Playwright verify.
- 🟠 **TODO: Compute HP/hit dice across `build.level`** (not just level 1); add a subclass-selection step (invariant #2).
- ✅ **Exit test (backend):** `tests/test_phase1_character_combat.py` + `tests/test_spell_levels.py` green; full suite **1136 passed**.
- ✅ **Codex GPT-5.5 review (2026-06-18):** reconciled — applied the valid HP-clamp fix (min 1 HP/level on negative CON); rejected a false-positive (demo has one player); deferred two low-impact notes (empty-at-creation spell fields; missing-level data-lint). **Residual: Task E frontend rendering needs a browser smoke-test** (backend combat acceptance is sound by construction).

## Phase 2 — Harden combat & spells ⚔️ (in progress — crash bugs fixed 2026-06-18)
**Goal:** monster turns and spells produce correct, crash-free mechanics.
- ✅ Added `roll_dice()` to `core/dice.py` (general roller). Fixes the unimportable `surfaces`/`falling`/`throwing` modules and the monster Multiattack / save-AoE crash. Tested.
- ✅ Fixed `attack_roll.natural_roll` → `natural_20`/`natural_1` (`combat_engine.py`); added `extra_data` field to `AbilityResult` (breath weapons vs Evasion). A combat-engine integration test now covers the monster single-attack path.
- ✅ Fixed monster damage resist/immunity key mismatch (`_apply_damage_to_target` now reads the cached `resistances/immunities/vulnerabilities`); `subclass_id` is now cached in `_cache_combatant_stats` and carried through `to_combatant_data`/the builder adapter (Champion crit / Assassinate can fire). Tested.
- 🟠 Give spells structured combat fields (`damage/type/heal/save/scaling`) and consume them instead of prose regex; fix upcasting; make `cast_spell` consume the persisted slot. **(next big item)**
- 🟠 Unify the three subclass-ID namespaces on the JSON IDs (invariant #2).
- ✅ **Exit test:** per-effect-type spell tests; a multiattack boss fight runs without exceptions.

## Phase 3 — Durability & persistence 💾
**Goal:** combats, sessions, and characters survive a restart.
- 🔴 On cache miss, rehydrate combat/campaign/character from the DB (invariant #3); make `combat_storage` round-trip via `to_dict`/`from_dict` and persist under the API `combat_id`.
- 🟠 Fix campaign save/load id-vs-filename mismatch; make `to_dict` serialize grid/recharge/legendary/reaction state.
- ✅ **Exit test:** durability round-trip test.

## Phase 4 — Content, campaigns & economy 🗺️
**Goal:** authored campaigns play cleanly; one campaign editor schema; shops work; SRD-clean content.
- 🟠 Reconcile the THREE campaign schemas (model / backend editor / frontend editor) to one; fix the broken `campaign_editor` service + routes.
- 🟠 Fix cutscene rewards being dropped and combat XP always 0 (CR not propagated; `get_xp_for_cr` key mismatch); fix the `1\2` CR typo.
- 🟠 Create `app/data/items.py` (or repoint shop models) so shops stop 500ing; reconcile the split gold economy; fix `loot.py` `get`/`gold_gained` bugs.
- 🟠 **SRD 5.2.1 compliance pass** (root §6): restrict/rewrite content to the SRD subset, drop Product Identity names, add the CC-BY attribution. *(Can run in parallel; required before public release.)*
- 🟡 Wire map/dungeon generation into the play flow (or mark it out of scope); fix multi-room enemy-spawn indexing + RNG reseed bugs first.

## Phase 5 — Multiplayer 👥
**Goal:** a real shared session, not a demo scaffold.
- 🔴 Add identity/auth to WS connections; server-side session registry (creation/capacity/membership).
- 🔴 Enforce vote timeout server-side; handle disconnects in quorum; wire `initiate_choice`/`winning_choice` into the campaign so votes affect play; replace the `startGame` TODO stub.
- 🟠 Attach the JWT bearer token in `api-client.js`; enforce `get_current_user` ownership on gameplay routes.
- 🟠 Move shared state out of single-process memory if multi-worker is a goal.

## Phase 6 — Test, CI & deploy 🚀
**Goal:** regression-proof and shippable.
- 🟠 Add `frontend/package.json` + babel; point Jest at real modules; serve/mount the frontend so Playwright e2e can pass; fix the docker healthcheck path.
- 🟠 CI: install → import smoke → pytest → e2e. Add the Phase 0–3 regression tests to the gate.
- 🟡 Add a Dockerfile (referenced by compose but missing), Alembic migrations, and a one-command dev startup.
