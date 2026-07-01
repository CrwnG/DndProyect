"""Batch 59 (D3): a resolved multiplayer vote drives the campaign forward.

The voting scaffold (initiate/vote/resolve, D1 timeout) existed, but nothing applied a
winning choice to gameplay — votes resolved into the void. Now choice options may carry
a campaign action payload ({"action": ..., "data": ...}); when the vote resolves, the
multiplayer route advances the bound campaign session with the winning option (once),
persists it, and broadcasts "choice_applied".
"""
import asyncio

import pytest

from app.core.multiplayer_choices import (
    MultiplayerChoiceHandler, DecisionMode,
)
from app.api.routes import multiplayer as mp_route


class _FakeEngine:
    def __init__(self):
        self.advanced = []

    def advance(self, action, data=None):
        self.advanced.append((action, data))
        return {"scene": "next"}, {}


@pytest.fixture()
def resolved_choice():
    """A resolved ChoiceSession whose winning option carries a campaign action."""
    handler = MultiplayerChoiceHandler()
    session = asyncio.run(handler.initiate_choice(
        game_session_id="camp-1",
        choice_id="scene-choice",
        choice_text="Which way?",
        options=[
            {"id": "left", "text": "Left", "action": "make_choice", "data": {"choice_id": "left"}},
            {"id": "right", "text": "Right", "action": "make_choice", "data": {"choice_id": "right"}},
        ],
        player_ids=["p1", "p2"],
        mode=DecisionMode.VOTING,
    ))
    session.result = "left"
    return session


def _apply(choice_session, monkeypatch, engine):
    """Run _apply_winning_choice with the campaign loader/persist stubbed out."""
    from app.api.routes import campaign as campaign_route
    persisted = []

    async def fake_load(session_id, repo):
        return engine

    async def fake_persist(repo, session_id, eng):
        persisted.append(session_id)

    monkeypatch.setattr(campaign_route, "_get_or_load_session_engine", fake_load)
    monkeypatch.setattr(campaign_route, "_persist_session_state", fake_persist)
    result = asyncio.run(
        mp_route._apply_winning_choice(choice_session, session_repo=None))
    return result, persisted


def test_winning_option_advances_and_persists_the_campaign(resolved_choice, monkeypatch):
    engine = _FakeEngine()
    result, persisted = _apply(resolved_choice, monkeypatch, engine)
    assert len(engine.advanced) == 1
    action, data = engine.advanced[0]
    assert getattr(action, "value", action) == "make_choice"
    assert data == {"choice_id": "left"}
    assert persisted == ["camp-1"]
    assert resolved_choice.applied is True


def test_apply_is_idempotent(resolved_choice, monkeypatch):
    engine = _FakeEngine()
    _apply(resolved_choice, monkeypatch, engine)
    _apply(resolved_choice, monkeypatch, engine)
    assert len(engine.advanced) == 1


def test_option_without_action_is_a_noop(resolved_choice, monkeypatch):
    resolved_choice.options = [{"id": "left", "text": "Left"}]
    engine = _FakeEngine()
    _apply(resolved_choice, monkeypatch, engine)
    assert engine.advanced == []
    assert not resolved_choice.applied


def test_unresolved_choice_is_a_noop(resolved_choice, monkeypatch):
    resolved_choice.result = None
    engine = _FakeEngine()
    _apply(resolved_choice, monkeypatch, engine)
    assert engine.advanced == []


def test_vote_route_is_registered():
    """QA (Codex, critical): a mid-file helper must not swallow the @router.post
    decorator — POST /choice/vote has to dispatch to cast_vote."""
    route = next((r for r in mp_route.router.routes
                  if getattr(r, "path", "") == "/choice/vote"), None)
    assert route is not None
    assert route.endpoint.__name__ == "cast_vote"


def test_failed_advance_releases_the_applied_claim(resolved_choice, monkeypatch):
    """QA (Codex): if the campaign advance blows up, the claim is released so a later
    resolution path can retry — otherwise the winning action is lost forever."""
    class _BoomEngine:
        def advance(self, action, data=None):
            raise RuntimeError("boom")

    from app.api.routes import campaign as campaign_route

    async def fake_load(session_id, repo):
        return _BoomEngine()

    monkeypatch.setattr(campaign_route, "_get_or_load_session_engine", fake_load)
    with pytest.raises(RuntimeError):
        asyncio.run(mp_route._apply_winning_choice(resolved_choice, session_repo=None))
    assert resolved_choice.applied is False

    # …and a retry with a healthy engine succeeds.
    engine = _FakeEngine()
    _apply(resolved_choice, monkeypatch, engine)
    assert len(engine.advanced) == 1 and resolved_choice.applied is True


def test_handler_find_session_covers_history():
    handler = MultiplayerChoiceHandler()
    session = asyncio.run(handler.initiate_choice(
        game_session_id="camp-2", choice_id="c", choice_text="?",
        options=[{"id": "a"}], player_ids=["p1"], mode=DecisionMode.VOTING,
    ))
    assert handler.find_session(session.id) is session
    handler._add_to_history(session)
    del handler._active_sessions[session.id]
    assert handler.find_session(session.id) is session
