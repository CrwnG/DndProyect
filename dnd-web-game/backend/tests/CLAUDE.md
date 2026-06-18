# Tests & Run-Readiness

> Area doc. Parent: [backend](../CLAUDE.md). Covers pytest (here), Jest (`../../frontend/tests/`), and Playwright (`../../e2e/`).

## Current reality

| Suite | Status |
|---|---|
| **Backend pytest** (`tests/`, `pytest.ini`) | **1095 / 1103 pass.** Strong, real coverage of the [core](../app/core/CLAUDE.md) rules engine (~30 test modules import the real `app.core.*`). |
| **Frontend Jest** (`../../frontend/tests/`) | **~0% real coverage** + not runnable. |
| **Playwright e2e** (`../../e2e/`) | **Cannot pass** as configured. |

**Why a passing pytest suite didn't catch the boot blockers:** the unit tests import `app.core.*` directly, **not** `app.main` or the route layer — so the `combat.py` `Query` NameError, the missing auth deps, and the `errors.py` AuthError bug never get exercised. The rules engine is trustworthy; the *assembled app* is unverified.

## Verified failures / gaps

- 🟠 Backend 8 failures: 6 from the `errors.py` AuthError `http_status` TypeError (`test_auth.py` token-expiry/invalid/forbidden), 1 stale assertion `len(ActionType)==13` (now 14) in `test_tactical_ai.py:37`, 1 `token_version` MagicMock not JSON-serializable.
- 🔴 Jest tests (`combat-grid/event-bus/state-manager.test.js`) **redefine the class inline as a mock** and test the mock — they never import `frontend/js/`. There's **no `package.json` or babel config anywhere**, so `npm test` can't even run.
- 🔴 Playwright: `webServer` starts only the backend, but `app/main.py` **never serves `frontend/index.html`** — every spec does `page.goto('/')` + waits for `.game-container`, which is never served → all specs time out. Docker healthcheck also curls `/health` but the app serves `/api/health`.
- `test_new_features.py` (backend root) is a manual `requests` script (not pytest, not collected) and hits the stale `:8001`.

## Required regression tests (write these as we fix bugs — TDD)

1. **Boot smoke:** `import app.main` succeeds; `TestClient` GET `/api/health` → 200. (Catches the import blockers.)
2. **Create → retrieve → combat round trip:** build a character of each of the 12 classes → `to_combatant_data` → assert non-zero ability mods, correct HP/AC, real attack bonus/damage. (Invariant #1.)
3. **Per-class skill selection** succeeds for all 12 (catches `skill_choices`/`skill_proficiencies`). 
4. **Spell resolution per effect type & level:** Magic Missile/Cure Wounds/Fireball-upcast apply real damage/heal at the correct slot level. (Catches the prose-regex + spell-level-key bugs.)
5. **Level-up:** slots + valid subclass IDs change correctly per class. (Invariant #2.)
6. **Durability:** create combat → drop the in-memory cache → endpoint rehydrates from DB. (Invariant #3.)

## CI target

Add a job that: installs `requirements.txt` (+ the missing auth deps), runs `python -c "import app.main"`, runs `pytest`, then (once the backend serves or mounts the frontend) runs Playwright. Add a `frontend/package.json` + babel config and point Jest at the real modules before trusting any JS coverage number.
