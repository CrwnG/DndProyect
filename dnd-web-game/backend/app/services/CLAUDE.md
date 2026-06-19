# Services — AI DM, Campaign Generation, Auth

> Area doc. Parent: [backend](../../CLAUDE.md). Orchestration + side effects on top of [core](../core/CLAUDE.md).

## AI Dungeon Master (`ai_dm.py` + `ai_dm_fallbacks.py` + `ai_dm_cache.py` + `ai_dm_rate_limiter.py` + `ai_dm_personalities.py`)

- **Provider = Anthropic only** (`anthropic` SDK, Claude model). There is **no OpenAI path** — the `OPENAI_API_KEY` in `docker-compose.test.yml` is read nowhere. If you add a provider, build a real abstraction; don't half-wire it.
- **Graceful degradation is a hard requirement.** `AIDMService.__init__` only builds the client if `ANTHROPIC_API_KEY` is set; otherwise `self._client = None` and every generator (`generate_scene/npc/combat/skill_check/encounter`) falls through to a pre-written template in `ai_dm_fallbacks.py`. **The game must stay fully playable with no key.** Verified: solo tutorial + multiplayer are completable offline; only *flavor* narration needs a key.
- Cache (TTL + LRU + scenario hashing) and rate limiter are integrated but in-memory only (lost on restart). Token cost is estimated as `len(prompt)//4` — fine as a cap, not billing.

⚠️ **Route/service fallback mismatch:** the *service* always falls back, but the `dm.py` *route* handlers short-circuit with `{generated:false}` when `is_ai_enabled` is False (`dm.py:187-192,…`) — so the rich fallbacks never reach clients that fetch narration via `/dm/generate/*`. Not a play blocker (story text comes from campaign JSON), but fix the route to call the service so fallbacks are served.

**Narration↔mechanics rule:** AI narration must describe what the engine actually computed. Never let the DM claim a hit/effect the [combat engine](../core/CLAUDE.md) didn't apply.

## Campaign generation / parsing / editing

| File | Role | State |
|---|---|---|
| `campaign_generator.py` | concept → `Campaign` via Claude | needs key; ⚠️ never sets `starting_encounter` → generated campaign won't start |
| `campaign_parser.py` | text/PDF → `Campaign` | works on regex-friendly input; strict stat-block regex → real PDFs often yield combats with **0 enemies** |
| `entity_extractor.py`, `npc_generator.py` | regex entities, NPCs | OK (NPC has AI + deterministic fallback) |
| `campaign_editor.py` + `api/routes/campaign_editor.py` | edit/validate campaigns | ✅ **rebuilt 2026-06-19 — DB-backed, schema-correct** |
| `pdf_parser.py`, `json_parser.py` | D&D Beyond **character-sheet** parsers | not part of the campaign-import path despite the name |

✅ **Editor rebuilt (R1).** `campaign_editor.py` now operates on the real `models/campaign.py` `Campaign` (encounters dict + chapter encounter-id lists + plain `npcs` dict) — `CampaignEditorService` is stateless (mutates a passed-in `Campaign`). Persistence is a new `CampaignDB` table (full `Campaign.to_dict()` JSON) via `CampaignRepository` (`get_campaign_repo` dependency); routes do **load-or-seed** (seed from the shipped JSON campaign on first edit) → edit → persist, so edits are durable across restarts. Covered by `tests/test_campaign_editor.py`. The old stateful undo/history/discard endpoints were dropped. (The frontend editor's third flat schema is still unreconciled — wire it to these endpoints when the editor UI is connected.)

## Auth (`auth_service.py`)

JWT (python-jose, HS256, access+refresh, token-version invalidation) + bcrypt via passlib. Logic is sound and unit-tested, **but**: deps missing from `requirements.txt` (boot blocker #2), `errors.py` AuthError double-`http_status` bug (blocker #3), bcrypt unpinned (blocker #4), JWT secret defaults to a public dev string, and auth is **not enforced** on gameplay routes. See [backend](../../CLAUDE.md) and [api](../api/CLAUDE.md).
