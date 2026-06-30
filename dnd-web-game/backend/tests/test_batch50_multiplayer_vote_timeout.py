"""Batch 50 (D1): a multiplayer vote can't deadlock on a missing voter.

`check_timeout` was implemented but had NO caller, so a VOTING/CONSENSUS session where a
required player never voted sat IN_PROGRESS forever. `check_resolution` (called after every
vote) and the status-poll route now enforce the timeout, resolving the vote from the votes
cast once the window elapses.
"""
from datetime import datetime, timedelta

from app.core.multiplayer_choices import (
    MultiplayerChoiceHandler, DecisionMode, VoteStatus,
)


async def _started_session(timeout=60):
    h = MultiplayerChoiceHandler()
    session = await h.initiate_choice(
        game_session_id="g1", choice_id="c1", choice_text="Left or right?",
        options=[{"id": "left"}, {"id": "right"}],
        player_ids=["A", "B"], mode=DecisionMode.VOTING, timeout_seconds=timeout,
    )
    return h, session


async def test_missing_voter_does_not_deadlock_resolution():
    h, session = await _started_session()
    await h.record_vote(session.id, "A", "left")     # B never votes -> quorum not met

    # Still in progress before the window elapses.
    assert session.status == VoteStatus.IN_PROGRESS

    # Window elapses; the next resolution check must time it out, not hang forever.
    session.created_at = datetime.utcnow() - timedelta(seconds=120)
    result = await h.check_resolution(session.id)

    assert result.status == VoteStatus.TIMED_OUT
    assert result.resolved is True
    assert result.winning_choice == "left"           # resolves from the votes cast
    assert "B" in result.missing_voters


async def test_timeout_not_triggered_before_window():
    h, session = await _started_session(timeout=600)
    await h.record_vote(session.id, "A", "left")
    result = await h.check_resolution(session.id)     # fresh session, within window
    assert result.status == VoteStatus.IN_PROGRESS
    assert result.resolved is False
