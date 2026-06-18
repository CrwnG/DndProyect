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
- 🟠 **Created character never reaches combat.** `main.js:341` stores the wizard result in `this.importedCharacter`, but `loadDemoCombat` (`:684`) always sends hardcoded `demoPlayers`; `importedCharacter` is **never read** → the new-player → fight path can't complete. (Backend side of this seam is invariant #1 — see [core](../backend/app/core/CLAUDE.md).)
- 🟠 `main.js:229` passes a 5th `playerIds` arg to `collectLoot`, but the signature only takes 4 → party gold split silently dropped.
- 🟡 `main.js:348` updates `#btn-start-combat` which doesn't exist in `index.html` (dead wiring); `combat-grid.js:357` writes an orphan `combatant_stats.*` state branch nothing reads.
- 🟡 Character creation: equipment step is a placeholder (`creation-wizard.js:1022`); Standard Array is non-interactive (hard-assigns a fixed spread, `:881`); errors use `alert()`.

## Notes

- `CONFIG.WS_BASE_URL` is defined but **never used** — multiplayer EVENTS aren't wired into `main.js` (the multiplayer UI lives in `js/ui/multiplayer-*.js` but isn't connected to the play loop; see [api](../backend/app/api/CLAUDE.md)).
- Frontend depends on the backend API contract — when you change a route's params/response in [api](../backend/app/api/CLAUDE.md), update the matching `api-client.js` method.
- There is **no real test coverage** of these modules yet — see [tests](../backend/tests/CLAUDE.md).
