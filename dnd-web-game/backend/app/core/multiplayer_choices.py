"""
Multiplayer Choice Handler.

Handles shared decision-making for multiplayer campaigns with various voting modes.

Features:
- Multiple decision modes (leader, voting, rotating, consensus)
- Real-time vote tracking
- Tie resolution
- Timeout handling
- Vote history
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import uuid

logger = logging.getLogger(__name__)


class DecisionMode(str, Enum):
    """How multiplayer decisions are made."""
    LEADER_DECIDES = "leader_decides"       # Party leader makes all story choices
    VOTING = "voting"                        # Players vote on major decisions
    ROTATING = "rotating"                    # Players take turns being "face"
    CONSENSUS = "consensus"                  # All must agree (timeout to leader)


class VoteStatus(str, Enum):
    """Status of a vote session."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


@dataclass
class Vote:
    """A single player's vote."""
    player_id: str
    choice_id: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    changed: bool = False  # True if player changed their vote


@dataclass
class ChoiceSession:
    """A voting session for a choice point."""
    id: str
    session_id: str  # Game session ID
    choice_id: str
    choice_text: str
    options: List[Dict[str, Any]]  # Available choices
    mode: DecisionMode
    status: VoteStatus = VoteStatus.PENDING
    votes: Dict[str, Vote] = field(default_factory=dict)  # player_id -> Vote
    required_players: Set[str] = field(default_factory=set)
    leader_id: Optional[str] = None
    current_face_id: Optional[str] = None  # For rotating mode
    timeout_seconds: int = 60
    created_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    result: Optional[str] = None  # Winning choice_id


@dataclass
class VoteResult:
    """Result of a vote."""
    choice_session_id: str
    status: VoteStatus
    current_votes: Dict[str, int]  # choice_id -> vote count
    total_votes: int
    required_votes: int
    missing_voters: List[str]
    resolved: bool
    winning_choice: Optional[str] = None
    tie: bool = False


class MultiplayerChoiceHandler:
    """
    Handles shared decision-making for multiplayer campaigns.

    Supports multiple voting modes to accommodate different play styles.
    """

    _instance: Optional["MultiplayerChoiceHandler"] = None

    def __init__(self):
        # Active choice sessions: session_id -> ChoiceSession
        self._active_sessions: Dict[str, ChoiceSession] = {}
        # History of resolved sessions
        self._history: Dict[str, List[ChoiceSession]] = {}  # game_session_id -> list
        # Rotation tracking for rotating mode
        self._rotation_index: Dict[str, int] = {}  # game_session_id -> index

    @classmethod
    def get_instance(cls) -> "MultiplayerChoiceHandler":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # =========================================================================
    # CHOICE SESSION MANAGEMENT
    # =========================================================================

    async def initiate_choice(
        self,
        game_session_id: str,
        choice_id: str,
        choice_text: str,
        options: List[Dict[str, Any]],
        player_ids: List[str],
        mode: DecisionMode = DecisionMode.VOTING,
        leader_id: Optional[str] = None,
        timeout_seconds: int = 60,
    ) -> ChoiceSession:
        """
        Initiate a new choice voting session.

        Args:
            game_session_id: The game session ID
            choice_id: ID of the choice being voted on
            choice_text: Description of the choice
            options: Available choice options
            player_ids: List of player IDs who can vote
            mode: Decision mode
            leader_id: Party leader ID (for leader/consensus modes)
            timeout_seconds: Timeout for the vote

        Returns:
            New ChoiceSession
        """
        session_id = str(uuid.uuid4())

        # Determine current "face" for rotating mode
        current_face = None
        if mode == DecisionMode.ROTATING:
            idx = self._rotation_index.get(game_session_id, 0)
            if player_ids:
                current_face = player_ids[idx % len(player_ids)]
                self._rotation_index[game_session_id] = idx + 1

        choice_session = ChoiceSession(
            id=session_id,
            session_id=game_session_id,
            choice_id=choice_id,
            choice_text=choice_text,
            options=options,
            mode=mode,
            status=VoteStatus.IN_PROGRESS,
            required_players=set(player_ids),
            leader_id=leader_id,
            current_face_id=current_face,
            timeout_seconds=timeout_seconds,
        )

        self._active_sessions[session_id] = choice_session

        logger.info(
            f"Initiated choice session {session_id} for game {game_session_id} "
            f"mode={mode.value} players={len(player_ids)}"
        )

        return choice_session

    async def record_vote(
        self,
        choice_session_id: str,
        player_id: str,
        choice_id: str,
    ) -> VoteResult:
        """
        Record a player's vote.

        Args:
            choice_session_id: The choice session ID
            player_id: The voting player's ID
            choice_id: The choice they're voting for

        Returns:
            Current VoteResult
        """
        session = self._active_sessions.get(choice_session_id)
        if not session:
            raise ValueError(f"Choice session {choice_session_id} not found")

        if session.status != VoteStatus.IN_PROGRESS:
            raise ValueError(f"Choice session is {session.status.value}, cannot vote")

        if player_id not in session.required_players:
            raise ValueError(f"Player {player_id} is not part of this vote")

        # Validate choice option exists
        valid_choices = [opt["id"] for opt in session.options]
        if choice_id not in valid_choices:
            raise ValueError(f"Invalid choice {choice_id}")

        # Record or update vote
        existing = session.votes.get(player_id)
        session.votes[player_id] = Vote(
            player_id=player_id,
            choice_id=choice_id,
            changed=existing is not None and existing.choice_id != choice_id,
        )

        logger.info(
            f"Vote recorded: session={choice_session_id} player={player_id} choice={choice_id}"
        )

        # Check if vote is resolved
        return await self.check_resolution(choice_session_id)

    async def check_resolution(self, choice_session_id: str) -> VoteResult:
        """
        Check if a choice session is resolved.

        Args:
            choice_session_id: The choice session ID

        Returns:
            VoteResult with current status
        """
        session = self._active_sessions.get(choice_session_id)
        if not session:
            raise ValueError(f"Choice session {choice_session_id} not found")

        # Count votes
        vote_counts: Dict[str, int] = {}
        for vote in session.votes.values():
            vote_counts[vote.choice_id] = vote_counts.get(vote.choice_id, 0) + 1

        total_votes = len(session.votes)
        required_votes = len(session.required_players)
        missing_voters = [
            pid for pid in session.required_players
            if pid not in session.votes
        ]

        result = VoteResult(
            choice_session_id=choice_session_id,
            status=session.status,
            current_votes=vote_counts,
            total_votes=total_votes,
            required_votes=required_votes,
            missing_voters=missing_voters,
            resolved=False,
        )

        # Check resolution based on mode
        if session.mode == DecisionMode.LEADER_DECIDES:
            # Leader's vote immediately resolves
            if session.leader_id in session.votes:
                result.resolved = True
                result.winning_choice = session.votes[session.leader_id].choice_id

        elif session.mode == DecisionMode.ROTATING:
            # Current face's vote resolves
            if session.current_face_id and session.current_face_id in session.votes:
                result.resolved = True
                result.winning_choice = session.votes[session.current_face_id].choice_id

        elif session.mode == DecisionMode.VOTING:
            # Majority wins when all have voted
            if total_votes >= required_votes:
                result.resolved = True
                winner = self._get_majority_choice(vote_counts, session.leader_id)
                result.winning_choice = winner["choice"]
                result.tie = winner["tie"]

        elif session.mode == DecisionMode.CONSENSUS:
            # All must agree
            if total_votes >= required_votes:
                unique_choices = set(vote_counts.keys())
                if len(unique_choices) == 1:
                    result.resolved = True
                    result.winning_choice = list(unique_choices)[0]
                else:
                    # No consensus - check if timed out
                    elapsed = (datetime.utcnow() - session.created_at).total_seconds()
                    if elapsed >= session.timeout_seconds:
                        # Timeout - leader decides
                        result.resolved = True
                        if session.leader_id in session.votes:
                            result.winning_choice = session.votes[session.leader_id].choice_id
                        else:
                            # Fall back to majority
                            winner = self._get_majority_choice(vote_counts, None)
                            result.winning_choice = winner["choice"]
                            result.tie = winner["tie"]

        # Update session if resolved
        if result.resolved:
            session.status = VoteStatus.RESOLVED
            session.resolved_at = datetime.utcnow()
            session.result = result.winning_choice
            result.status = VoteStatus.RESOLVED

            # Move to history
            self._add_to_history(session)
            del self._active_sessions[choice_session_id]

            logger.info(
                f"Choice session {choice_session_id} resolved: {result.winning_choice}"
            )

        return result

    def _get_majority_choice(
        self,
        vote_counts: Dict[str, int],
        tiebreaker_player_id: Optional[str],
    ) -> Dict[str, Any]:
        """Get the majority choice, handling ties."""
        if not vote_counts:
            return {"choice": None, "tie": True}

        max_votes = max(vote_counts.values())
        winners = [c for c, v in vote_counts.items() if v == max_votes]

        if len(winners) == 1:
            return {"choice": winners[0], "tie": False}

        # Tie - use tiebreaker if available
        # For now, just pick the first one alphabetically for consistency
        return {"choice": sorted(winners)[0], "tie": True}

    async def resolve_tie(
        self,
        choice_session_id: str,
        method: str = "leader",
        forced_choice: Optional[str] = None,
    ) -> VoteResult:
        """
        Manually resolve a tie.

        Args:
            choice_session_id: The choice session ID
            method: "leader" (leader decides) or "random" or "forced"
            forced_choice: The choice to force (if method is "forced")

        Returns:
            Final VoteResult
        """
        session = self._active_sessions.get(choice_session_id)
        if not session:
            raise ValueError(f"Choice session {choice_session_id} not found")

        if method == "forced" and forced_choice:
            winning_choice = forced_choice
        elif method == "leader" and session.leader_id:
            if session.leader_id in session.votes:
                winning_choice = session.votes[session.leader_id].choice_id
            else:
                # Leader hasn't voted - pick first option
                winning_choice = session.options[0]["id"] if session.options else None
        else:
            # Random - pick first option
            import random
            winning_choice = random.choice([opt["id"] for opt in session.options])

        # Resolve the session
        session.status = VoteStatus.RESOLVED
        session.resolved_at = datetime.utcnow()
        session.result = winning_choice

        # Count votes for the result
        vote_counts = {}
        for vote in session.votes.values():
            vote_counts[vote.choice_id] = vote_counts.get(vote.choice_id, 0) + 1

        result = VoteResult(
            choice_session_id=choice_session_id,
            status=VoteStatus.RESOLVED,
            current_votes=vote_counts,
            total_votes=len(session.votes),
            required_votes=len(session.required_players),
            missing_voters=[],
            resolved=True,
            winning_choice=winning_choice,
            tie=True,
        )

        # Move to history
        self._add_to_history(session)
        del self._active_sessions[choice_session_id]

        logger.info(f"Tie resolved for session {choice_session_id}: {winning_choice}")

        return result

    # =========================================================================
    # TIMEOUT HANDLING
    # =========================================================================

    async def check_timeout(self, choice_session_id: str) -> Optional[VoteResult]:
        """
        Check if a session has timed out and handle it.

        Args:
            choice_session_id: The choice session ID

        Returns:
            VoteResult if timed out, None otherwise
        """
        session = self._active_sessions.get(choice_session_id)
        if not session:
            return None

        if session.status != VoteStatus.IN_PROGRESS:
            return None

        elapsed = (datetime.utcnow() - session.created_at).total_seconds()
        if elapsed < session.timeout_seconds:
            return None

        logger.info(f"Choice session {choice_session_id} timed out")

        # Handle timeout based on mode
        session.status = VoteStatus.TIMED_OUT

        vote_counts = {}
        for vote in session.votes.values():
            vote_counts[vote.choice_id] = vote_counts.get(vote.choice_id, 0) + 1

        # Determine winner
        winning_choice = None
        if session.leader_id and session.leader_id in session.votes:
            winning_choice = session.votes[session.leader_id].choice_id
        elif vote_counts:
            # Most votes wins
            winning_choice = max(vote_counts, key=vote_counts.get)
        elif session.options:
            # Default to first option
            winning_choice = session.options[0]["id"]

        session.result = winning_choice
        session.resolved_at = datetime.utcnow()

        result = VoteResult(
            choice_session_id=choice_session_id,
            status=VoteStatus.TIMED_OUT,
            current_votes=vote_counts,
            total_votes=len(session.votes),
            required_votes=len(session.required_players),
            missing_voters=[
                pid for pid in session.required_players
                if pid not in session.votes
            ],
            resolved=True,
            winning_choice=winning_choice,
        )

        # Move to history
        self._add_to_history(session)
        del self._active_sessions[choice_session_id]

        return result

    async def cancel_choice(self, choice_session_id: str) -> bool:
        """Cancel an active choice session."""
        session = self._active_sessions.get(choice_session_id)
        if not session:
            return False

        session.status = VoteStatus.CANCELLED
        self._add_to_history(session)
        del self._active_sessions[choice_session_id]

        logger.info(f"Choice session {choice_session_id} cancelled")
        return True

    # =========================================================================
    # HISTORY & QUERIES
    # =========================================================================

    def _add_to_history(self, session: ChoiceSession):
        """Add session to history."""
        if session.session_id not in self._history:
            self._history[session.session_id] = []
        self._history[session.session_id].append(session)

        # Keep only last 100 per game session
        if len(self._history[session.session_id]) > 100:
            self._history[session.session_id].pop(0)

    def get_active_session(self, choice_session_id: str) -> Optional[ChoiceSession]:
        """Get an active choice session."""
        return self._active_sessions.get(choice_session_id)

    def get_session_history(
        self,
        game_session_id: str,
        limit: int = 20,
    ) -> List[ChoiceSession]:
        """Get history of resolved sessions for a game."""
        history = self._history.get(game_session_id, [])
        return history[-limit:] if history else []

    def get_active_for_game(self, game_session_id: str) -> Optional[ChoiceSession]:
        """Get the active choice session for a game."""
        for session in self._active_sessions.values():
            if session.session_id == game_session_id:
                return session
        return None

    def serialize_session(self, session: ChoiceSession) -> Dict[str, Any]:
        """Serialize a choice session for API response."""
        return {
            "id": session.id,
            "session_id": session.session_id,
            "choice_id": session.choice_id,
            "choice_text": session.choice_text,
            "options": session.options,
            "mode": session.mode.value,
            "status": session.status.value,
            "votes": {
                pid: {
                    "choice_id": vote.choice_id,
                    "timestamp": vote.timestamp.isoformat(),
                }
                for pid, vote in session.votes.items()
            },
            "required_players": list(session.required_players),
            "leader_id": session.leader_id,
            "current_face_id": session.current_face_id,
            "timeout_seconds": session.timeout_seconds,
            "created_at": session.created_at.isoformat(),
            "resolved_at": session.resolved_at.isoformat() if session.resolved_at else None,
            "result": session.result,
        }

    def serialize_result(self, result: VoteResult) -> Dict[str, Any]:
        """Serialize a vote result for API response."""
        return {
            "choice_session_id": result.choice_session_id,
            "status": result.status.value,
            "current_votes": result.current_votes,
            "total_votes": result.total_votes,
            "required_votes": result.required_votes,
            "missing_voters": result.missing_voters,
            "resolved": result.resolved,
            "winning_choice": result.winning_choice,
            "tie": result.tie,
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_multiplayer_choice_handler() -> MultiplayerChoiceHandler:
    """Get the multiplayer choice handler instance."""
    return MultiplayerChoiceHandler.get_instance()
