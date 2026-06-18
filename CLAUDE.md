# DnD_Proyect — Root Orchestrator

> **This is the entry-point doc.** It covers the whole repo and links to area-specific `CLAUDE.md` files. Read this first, then the file nearest the code you're touching.

## 1. What we're building

A **Baldur's Gate 3–inspired, single-player (with multiplayer) tactical D&D game in the browser**, running the **D&D 5e 2024 ruleset**, with an **AI Dungeon Master** that narrates encounters and can generate campaigns/NPCs.

- **Backend** — Python / FastAPI, SQLite (sqlmodel + aiosqlite), Anthropic SDK for the AI DM. Implements rules-accurate character creation, progression, spellcasting, and 8×8 grid tactical combat. → `dnd-web-game/backend/`
- **Frontend** — vanilla JS (native ES modules, no build step), canvas combat grid, modal-driven UI. → `dnd-web-game/frontend/`
- **Tests** — pytest (backend), Jest (frontend), Playwright (e2e).

The product goal is a **mechanically faithful** solo D&D experience with an LLM acting as DM — so *rules correctness* and *the create-character → fight → progress loop* are the things that matter most.

## 2. Current status — ⚠️ BOOTS, NOT YET PLAYABLE

**Phase 0 done (2026-06-18):** the app now **boots**, the live server answers `GET /api/health`, and **1108/1108 backend tests pass**. The audit (Claude multi-agent + Codex GPT-5.5) found the scaffolding broad and data comprehensive; the boot blockers are fixed, but the end-to-end *gameplay* loop is still broken. Remaining order of work (see [ROADMAP.md](ROADMAP.md)):

1. ✅ **Boots.** Fixed: missing `Query` import (`combat.py`), auth deps added to `requirements.txt` (`python-jose`/`passlib`/`bcrypt<4.1`), and `AuthError` `http_status` collision (`errors.py`).
2. **Created characters are broken in combat.** The builder emits flat `hit_points`/`ability_scores`; `character_service.to_combatant_data()` expects `hp`/`ac` + nested `abilities.str.mod`. Result: 10 HP, AC 10, all modifiers 0. → see `backend/app/core/CLAUDE.md`.
3. **Most spells do nothing.** Combat damage/healing is regex-parsed from prose, so Magic Missile / Cure Wounds / Healing Word / Chromatic Orb deal 0, and Fireball/Lightning Bolt never upcast. → structured spell combat-fields (see `backend/app/data/CLAUDE.md`).
4. **No durability.** Combat, campaign sessions, and created characters live only in memory, not the DB — lost on restart (and a combat-id/DB-UUID mismatch means persistence misses rows).

## 3. Run it (bootstrap)

```bash
cd dnd-web-game/backend
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash; use .venv\Scripts\activate in PowerShell
pip install -r requirements.txt
# requirements.txt now includes the auth stack (python-jose, passlib, bcrypt<4.1).
cp .env.example .env        # then set ANTHROPIC_API_KEY to enable the AI DM (optional; falls back to templates if unset)
python -m uvicorn app.main:app --reload --port 8000
```

Frontend (separate terminal, static server):
```bash
cd dnd-web-game/frontend
python -m http.server 5500   # any of the CORS-allowed ports: 3000 / 5173 / 5500 / 8080
# open http://localhost:5500
```

- Health check: `GET http://localhost:8000/api/health` → `api_key_configured` reflects whether the AI DM is enabled.
- **No API key is fine** — the AI DM degrades gracefully to templated narration. The game must remain playable offline.

## 4. Canonical conventions (single sources of truth)

| Thing | Canonical value | Notes |
|---|---|---|
| **Backend port** | **8000** | `config.py` default + frontend `config.js` already agree. Only `backend/test_new_features.py:7` is stale at 8001 — fix the test, don't move the port. |
| **AI provider** | **Anthropic** (`ANTHROPIC_API_KEY`) | `docker-compose.test.yml` mentions `OPENAI_API_KEY` — that is NOT wired. Ignore/replace it. |
| **Ruleset** | **D&D 5e 2024** | Data under `backend/app/data/rules/2024/`. |
| **Content license** | **SRD 5.2.1 / CC-BY-4.0** | See §6. |

## 5. Cross-cutting invariants (the golden rules)

These bugs keep recurring because data shapes drift between producers and consumers. **When you change any of these, update the consumer AND add a round-trip test:**

1. **Character data contract.** Anything that becomes a combatant must satisfy `character_service.to_combatant_data()`: `hp`/`max_hp`/`ac` and nested `abilities` = `{ "str": {"score", "mod"}, ... }`. The builder's flat output must be adapted *before* persist/cache.
2. **One subclass-ID namespace.** Use the IDs from the class JSON (e.g. `path_of_the_berserker`, `evoker`, `life_domain`) **everywhere** — `subclasses.py`, `subclass_registry.py`, and `level_up.py` currently disagree.
3. **State is DB-backed, not memory-backed.** Combat / campaign / character endpoints must reload from the DB on a cache miss. Never assume the in-memory dict survives a restart.
4. **Spells use structured combat fields, not prose.** Add explicit `damage`/`type`/`heal`/`save`/`scaling` fields to spell JSON; don't rely on regex over description text.
5. **Mechanics over flavor text.** Species traits, conditions, and buffs must be *applied mechanically*, not just stored as descriptive strings.

## 6. Content & licensing — SRD 5.2.1 (CC-BY-4.0)

Our content boundary is the **System Reference Document 5.2.1** (2024 rules), licensed **CC-BY-4.0** (free commercial use with attribution; irrevocable). BG3 itself uses full 2014 5e under a *direct WotC commercial license* — not a path we can copy.

- **Mechanics/rules are not copyrightable** → engine logic is fine.
- **Risk:** the repo currently ships far more content than the SRD includes (~48 subclasses, 432 spells, 16 backgrounds, many monsters) → likely sourced from the full 2024 PHB/Monster Manual. Remediation = restrict to SRD entries or rewrite descriptive text in our own words, and **drop Product Identity names** (beholder, mind flayer, etc.) that the SRD excludes.
- Ship the attribution line: *"This work includes material from the System Reference Document 5.2.1 by Wizards of the Coast LLC, available under CC-BY-4.0."*
- This is guidance, not legal advice — get a lawyer before commercial release. See memory `dnd-srd-licensing`.

## 7. Modular docs index

| Area | Doc | Covers |
|---|---|---|
| **Root** | `CLAUDE.md` (this file) | Vision, run, conventions, invariants, licensing |
| Backend | `dnd-web-game/backend/CLAUDE.md` | FastAPI app layering, request flow, durability |
| Rules engine | `dnd-web-game/backend/app/core/CLAUDE.md` | Combat, character builder, progression, spells, class resources |
| Services / AI DM | `dnd-web-game/backend/app/services/CLAUDE.md` | AI DM + fallbacks, campaign generation/parsing |
| API / wiring | `dnd-web-game/backend/app/api/CLAUDE.md` | Routes, mount order, CORS, state persistence |
| Game data | `dnd-web-game/backend/app/data/CLAUDE.md` | 2024 JSON schemas + SRD compliance |
| Frontend | `dnd-web-game/frontend/CLAUDE.md` | ES-module architecture, API client, combat grid |
| Tests | `dnd-web-game/backend/tests/CLAUDE.md` | pytest/Jest/Playwright + required regression tests |

## 8. How to work in this repo

- **Fix bugs with TDD** — for each invariant violation above, write the failing round-trip test first (create→retrieve→combat; spell→applied effect; level-up→slots), then fix.
- **Verify before claiming done** — run `python -m pytest` (backend) and the relevant suite; don't assert success without the output.
- **QA with a second opinion** — the user wants **Codex GPT-5.5** run as an independent QA/debug pass on substantial changes; reconcile its findings with the Claude audit.
- Keep these docs current: if you change a contract in §5, update the affected area doc in the same change.
