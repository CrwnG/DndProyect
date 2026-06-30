# Frontend — Vanilla-JS client

> Area doc. Parent: [`../CLAUDE.md`](../CLAUDE.md). No build step — native ES modules served statically.

## Architecture

- **Entry:** `index.html` loads one ES module, `js/main.js`, which statically imports ~40 modules and runs a `Game` class on `DOMContentLoaded`.
- **State:** singleton `StateManager` (`js/engine/state-manager.js`) — combat/turn/grid/ui; `getState()` deep-clones via JSON round-trip; subscribe/notify re-renders grid + action bar.
- **Events:** singleton `EventBus` (`js/engine/event-bus.js`) — pub/sub with a ~120-entry `EVENTS` catalog gluing combat/campaign/UI/animation.
- **API:** singleton `APIClient` (`js/api/api-client.js`) — `fetch` wrapper, `APIError`, ~120 typed endpoint methods. Base URL `CONFIG.API_BASE_URL` = `http://localhost:8000/api` (**matches backend — port is correct, don't change it**).
- **Combat UI:** `js/combat/combat-grid.js` (canvas: terrain/elevation/cover/threat/tokens/animations), `movement-handler.js`, `targeting-system.js`, `js/ui/action-bar.js` (4356 lines — the action economy + feature buttons).

The combat and campaign loops are **genuinely wired** (not stubbed): action bar → `api.performAction/castSpell` → dice animation → `state.update` → grid re-render → combat-over check; campaign phase machine handles story/choice/combat/rest/victory. An **offline demo** path (`loadDemoCombat`) runs a Fighter-5 vs 3 goblins fully client-side.

## Verified bugs

- 🟠 **Auth is doubly broken.** `js/services/auth.js:295` does `fetch(`${API_BASE_URL}${url}`)` where `API_BASE_URL` already ends `/api` and `url` is `/api/auth/...` → `…/api/api/auth/login` → 404. AND the access token is **never attached** as a Bearer header in `api-client.js`, so even if login worked, gameplay calls are unauthenticated.
- ✅ **FIXED — created character reaches combat.** The Quick Combat handler (`main.js:446`) reads `this.importedCharacter`, builds a `playerOverride` from its `combatant`, and passes it to `loadDemoCombat(playerOverride)` (`:687`), which uses the override (`:693`) instead of the hardcoded `demoPlayers`. The new-player → fight path completes.
- ✅ **FIXED — `collectLoot` party gold.** `api-client.js:1260` signature is `collectLoot(combatId, characterId, itemIds, takeCoins, partyCharacterIds=[])` — the 5th arg is accepted; `main.js` passes `playerIds` for gold division.
- ✅ **FIXED — dead `#btn-start-combat` wiring removed** (`main.js`, 2026-06-26). (`combat-grid.js:357` orphan `combatant_stats.*` state branch — still present, minor.)
- 🟡 Character creation: equipment step is a placeholder (`creation-wizard.js:1022`); Standard Array is non-interactive (hard-assigns a fixed spread, `:881`); errors use `alert()`.

## Notes

- `CONFIG.WS_BASE_URL` is defined but **never used** — multiplayer EVENTS aren't wired into `main.js` (the multiplayer UI lives in `js/ui/multiplayer-*.js` but isn't connected to the play loop; see [api](../backend/app/api/CLAUDE.md)).
- Frontend depends on the backend API contract — when you change a route's params/response in [api](../backend/app/api/CLAUDE.md), update the matching `api-client.js` method.
- There is **no real test coverage** of these modules yet — see [tests](../backend/tests/CLAUDE.md).
