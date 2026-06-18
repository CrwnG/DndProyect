# Backend — FastAPI app

> Area doc. Parent: [`../../CLAUDE.md`](../../CLAUDE.md). Siblings: [core](app/core/CLAUDE.md) · [services](app/services/CLAUDE.md) · [api](app/api/CLAUDE.md) · [data](app/data/CLAUDE.md) · [tests](tests/CLAUDE.md).

Python 3.11+/FastAPI, async SQLite (sqlmodel + aiosqlite), Anthropic SDK for the AI DM. Entry: `app/main.py` (`uvicorn app.main:app --port 8000`).

## Layering (respect this direction)

```
api/routes/*  →  core/*  +  services/*  →  models/* + database/*  →  data/*.json
   (HTTP)        (rules engine)   (AI, gen)     (persistence)        (content)
```
- **`core/`** = pure rules engine (combat, character build, spells, progression). No FastAPI imports. This layer is the crown jewel — well-tested (1095/1103 unit tests pass). See [core](app/core/CLAUDE.md).
- **`services/`** = orchestration + side effects (AI DM, campaign generation/parsing, auth). See [services](app/services/CLAUDE.md).
- **`api/routes/`** = thin HTTP/WebSocket layer. See [api](app/api/CLAUDE.md).
- **`database/`** = SQLModel models + repository pattern. **`data/`** = static JSON ruleset. See [data](app/data/CLAUDE.md).

## ✅ Boot blockers — FIXED 2026-06-18 (kept for history)

All four are resolved; the app boots and `tests/test_boot.py` guards against regression. Quick check: `python -c "import app.main"` then `GET /api/health`.

| # | Blocker (fixed) | Location |
|---|---|---|
| 1 | `Query(...)` used but never imported → NameError at import | `api/routes/combat.py:10,2026` |
| 2 | `requirements.txt` missing `python-jose`, `passlib`, `bcrypt` → ModuleNotFoundError | `requirements.txt`, `services/auth_service.py:9-10` |
| 3 | `AuthError` subclasses passed `http_status` twice → TypeError → 500 instead of 401 | `core/errors.py:114-120` |
| 4 | `bcrypt` unpinned; passlib 1.7.4 breaks with bcrypt≥4.1 → pinned `bcrypt<4.1` | `requirements.txt` |

## Persistence invariant (read before touching routes)

Combat, campaign sessions, and created characters are kept in **module-level in-memory dicts** (`active_combats`, `active_sessions`, `imported_characters`) and are **not reloaded from the DB on a cache miss** — a restart loses live state, and `combat_storage.create_combat_state` even ignores the passed `combat_id` so DB rows desync. **Any endpoint that reads live state must fall back to a DB load + rehydrate.** Details in [api](app/api/CLAUDE.md).

## Conventions

- Port **8000** everywhere (see root doc). AI provider **Anthropic** only (`ANTHROPIC_API_KEY`); ignore `OPENAI_API_KEY` in `docker-compose.test.yml`.
- JWT secrets are read directly in `auth_service.py` via `os.getenv` (not via `config.py`) and **default to a hardcoded dev secret** — set `JWT_SECRET_KEY`/`JWT_REFRESH_SECRET_KEY` for any real deploy.
- Auth exists but is **not enforced** on gameplay routes (`Character.user_id` is always None). Decide ownership before shipping multiplayer/persistence.
- Run tests: `python -m pytest` (see [tests](tests/CLAUDE.md)).
