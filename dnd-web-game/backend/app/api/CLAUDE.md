# API — Routes & Wiring

> Area doc. Parent: [backend](../../CLAUDE.md). Thin HTTP/WebSocket layer over [core](../core/CLAUDE.md) + [services](../services/CLAUDE.md). Keep logic out of routes.

## Mount map (`main.py:109-129`)

21 routers under `/api/*` (auth, combat, character, campaign, campaign-generator, spells, equipment, creation, loot, class-features, skill-check, progression, dm, shop, map_generation, social, encounters, export, multiplayer, campaign_editor). Health at both `/health` and `/api/health`. CORS allows localhost `3000/5500/8080/5173` + `FRONTEND_URL` — keep the static-server port in that list.

## 🔴 Boot blockers live here

- `routes/combat.py:2026` uses `Query(...)` but `:10` imports only `APIRouter, HTTPException, status, Depends` → **NameError at import → whole app fails** (verified). Add `Query` to the import.
- `routes/auth.py` import pulls in `services/auth_service.py` which needs `jose`/`passlib`/`bcrypt` (missing from requirements). See [backend](../../CLAUDE.md).

## 🔴 State durability (the recurring trap)

Routes resolve live state **only** from in-memory dicts and 404 on a miss — they never rehydrate from the DB even though the DB writes happen:
- `routes/combat.py:451,518,646,1681` read `active_combats` only; `core/combat_storage.py:118` (`load_combat_from_db`) + `CombatEngine.from_dict` are **never called**. Also `create_combat_state` ignores the passed `combat_id` → DB makes a new UUID → later updates miss the row. And `to_dict()` omits grid/recharge/legendary/reaction state, so even a reload would be lossy.
- `routes/campaign.py:333-348` read `active_sessions` only → saved sessions 404 after restart. Plus save/load is broken by an id-vs-filename mismatch: session stores `campaign_id='tutorial-campaign'` but `load_campaign` resolves by filename stem `tutorial` → 404 on load.
- `routes/character_creation.py:562-568` stores finalized characters in `imported_characters` memory, **never via `CharacterRepository`** → lost on restart, and stored mislabeled as `combatant` without `to_combatant_data`.

**Rule: on cache miss, load from DB → reconstruct the engine → repopulate the cache → then respond.** Make `combat_storage` round-trip via `to_dict`/`from_dict` and persist under the API's `combat_id`.

## Other verified route bugs

- 🔴 Shops 500 on every call: `models/shop.py:90,124,148` import `app.data.items` (CONSUMABLES/WEAPONS) — **module doesn't exist**.
- 🔴 `routes/loot.py:665` calls `char_repo.get(...)` — repository only has `get_by_id` → AttributeError.
- 🟠 `routes/loot.py:374` references undefined `gold_gained` → NameError *after* DB writes (gold persisted but client gets 500).
- 🟠 Gold economy is split: shop buy/sell mutate in-memory `combatant_stats['gold']`; loot writes `character.gold` in DB — never reconciled, combat gold lost on combat end.
- 🟠 `errors.py:114-167` AuthError double-`http_status` → invalid/expired tokens raise TypeError → 500 instead of 401 (also breaks 6 auth tests).
- Auth is **not enforced** on gameplay routes (`get_current_user` unused) → `Character.user_id` always None, no per-user isolation.

## Multiplayer route (`routes/multiplayer.py` + `core/multiplayer_choices.py`)

Real WebSocket transport + voting modes exist, but: **no auth/identity** (any `player_id`/`session_id` accepted, codes collide), **vote timeout never enforced** (`check_timeout` has no caller → a missing voter deadlocks VOTING/CONSENSUS forever), `required_players` snapshotted at start (disconnect = permanent stall), state is single-process in-memory (breaks with >1 worker), and **voting isn't wired to gameplay** (`startGame` is a TODO stub; nothing calls `initiate_choice` or applies the winning choice). Treat as a demo scaffold. Details: gap-fill multiplayer survey.
