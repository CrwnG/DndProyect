"""
Multiplayer WebSocket and REST Routes.

Handles real-time multiplayer functionality:
- WebSocket connections for real-time updates
- Choice voting endpoints
- Session synchronization
- Player presence tracking
"""

import asyncio
import json
import logging
from typing import Dict, Set, Optional, Any, List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, status
from pydantic import BaseModel, Field
from datetime import datetime

from app.core.multiplayer_choices import (
    MultiplayerChoiceHandler,
    DecisionMode,
    get_multiplayer_choice_handler,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# CONNECTION MANAGER
# =============================================================================

class ConnectionManager:
    """Manages WebSocket connections for multiplayer sessions."""

    def __init__(self):
        # session_id -> set of (player_id, websocket) tuples
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}
        # player_id -> session_id mapping
        self.player_sessions: Dict[str, str] = {}
        # session_id -> set of player_ids
        self.session_players: Dict[str, Set[str]] = {}

    async def connect(
        self,
        websocket: WebSocket,
        session_id: str,
        player_id: str,
    ):
        """Accept a new WebSocket connection."""
        await websocket.accept()

        if session_id not in self.active_connections:
            self.active_connections[session_id] = {}
            self.session_players[session_id] = set()

        # Close existing connection for this player if any
        if player_id in self.active_connections[session_id]:
            try:
                await self.active_connections[session_id][player_id].close()
            except Exception:
                pass

        self.active_connections[session_id][player_id] = websocket
        self.player_sessions[player_id] = session_id
        self.session_players[session_id].add(player_id)

        logger.info(f"Player {player_id} connected to session {session_id}")

        # Notify others that a player joined
        await self.broadcast_to_session(session_id, {
            "type": "player_joined",
            "player_id": player_id,
            "players": list(self.session_players[session_id]),
            "timestamp": datetime.utcnow().isoformat(),
        }, exclude=player_id)

    async def disconnect(self, websocket: WebSocket, session_id: str, player_id: str):
        """Handle WebSocket disconnection."""
        if session_id in self.active_connections:
            if player_id in self.active_connections[session_id]:
                del self.active_connections[session_id][player_id]

            if session_id in self.session_players:
                self.session_players[session_id].discard(player_id)

            # Clean up empty sessions
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]
                if session_id in self.session_players:
                    del self.session_players[session_id]

        if player_id in self.player_sessions:
            del self.player_sessions[player_id]

        logger.info(f"Player {player_id} disconnected from session {session_id}")

        # Notify others that a player left
        await self.broadcast_to_session(session_id, {
            "type": "player_left",
            "player_id": player_id,
            "players": list(self.session_players.get(session_id, [])),
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def send_to_player(
        self,
        session_id: str,
        player_id: str,
        message: Dict[str, Any],
    ):
        """Send a message to a specific player."""
        if session_id in self.active_connections:
            if player_id in self.active_connections[session_id]:
                try:
                    await self.active_connections[session_id][player_id].send_json(message)
                except Exception as e:
                    logger.error(f"Failed to send to {player_id}: {e}")

    async def broadcast_to_session(
        self,
        session_id: str,
        message: Dict[str, Any],
        exclude: Optional[str] = None,
    ):
        """Broadcast a message to all players in a session."""
        if session_id not in self.active_connections:
            return

        for player_id, websocket in self.active_connections[session_id].items():
            if player_id == exclude:
                continue
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Failed to broadcast to {player_id}: {e}")

    def get_session_players(self, session_id: str) -> List[str]:
        """Get list of players in a session."""
        return list(self.session_players.get(session_id, []))

    def is_player_connected(self, session_id: str, player_id: str) -> bool:
        """Check if a player is connected to a session."""
        return (
            session_id in self.active_connections and
            player_id in self.active_connections[session_id]
        )


# Global connection manager
manager = ConnectionManager()


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class InitiateChoiceRequest(BaseModel):
    """Request to initiate a choice voting session."""
    session_id: str = Field(..., description="Game session ID")
    choice_id: str = Field(..., description="Choice identifier")
    choice_text: str = Field(..., description="Choice description")
    options: List[Dict[str, Any]] = Field(..., description="Available options")
    mode: str = Field("voting", description="Decision mode")
    leader_id: Optional[str] = Field(None, description="Party leader ID")
    timeout_seconds: int = Field(60, description="Vote timeout in seconds")


class VoteRequest(BaseModel):
    """Request to cast a vote."""
    choice_session_id: str = Field(..., description="Choice session ID")
    player_id: str = Field(..., description="Voting player ID")
    choice_id: str = Field(..., description="Chosen option ID")


class ResolveTieRequest(BaseModel):
    """Request to manually resolve a tie."""
    choice_session_id: str = Field(..., description="Choice session ID")
    method: str = Field("leader", description="Resolution method: leader, random, forced")
    forced_choice: Optional[str] = Field(None, description="Forced choice ID if method=forced")


# =============================================================================
# WEBSOCKET ENDPOINT
# =============================================================================

@router.websocket("/ws/{session_id}/{player_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    player_id: str,
):
    """
    WebSocket endpoint for multiplayer real-time communication.

    Handles:
    - Player connections/disconnections
    - Choice voting updates
    - Campaign state sync
    - Chat messages (optional)
    """
    await manager.connect(websocket, session_id, player_id)

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            message_type = data.get("type")

            if message_type == "ping":
                # Heartbeat
                await manager.send_to_player(session_id, player_id, {
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat(),
                })

            elif message_type == "vote":
                # Handle vote
                await handle_vote_message(session_id, player_id, data)

            elif message_type == "chat":
                # Broadcast chat message
                await manager.broadcast_to_session(session_id, {
                    "type": "chat",
                    "player_id": player_id,
                    "message": data.get("message", ""),
                    "timestamp": datetime.utcnow().isoformat(),
                })

            elif message_type == "ready":
                # Player ready status
                await manager.broadcast_to_session(session_id, {
                    "type": "player_ready",
                    "player_id": player_id,
                    "ready": data.get("ready", True),
                    "timestamp": datetime.utcnow().isoformat(),
                })

            elif message_type == "sync_request":
                # Request state sync
                await handle_sync_request(session_id, player_id)

    except WebSocketDisconnect:
        await manager.disconnect(websocket, session_id, player_id)
    except Exception as e:
        logger.error(f"WebSocket error for {player_id}: {e}")
        await manager.disconnect(websocket, session_id, player_id)


async def handle_vote_message(session_id: str, player_id: str, data: Dict[str, Any]):
    """Handle a vote message from WebSocket."""
    choice_handler = get_multiplayer_choice_handler()
    choice_session_id = data.get("choice_session_id")
    choice_id = data.get("choice_id")

    if not choice_session_id or not choice_id:
        await manager.send_to_player(session_id, player_id, {
            "type": "error",
            "message": "Missing choice_session_id or choice_id",
        })
        return

    try:
        result = await choice_handler.record_vote(choice_session_id, player_id, choice_id)

        # Broadcast vote update to all players
        await manager.broadcast_to_session(session_id, {
            "type": "vote_update",
            "choice_session_id": choice_session_id,
            "voter": player_id,
            "result": choice_handler.serialize_result(result),
            "timestamp": datetime.utcnow().isoformat(),
        })

        # If resolved, send resolution
        if result.resolved:
            await manager.broadcast_to_session(session_id, {
                "type": "choice_resolved",
                "choice_session_id": choice_session_id,
                "winning_choice": result.winning_choice,
                "tie": result.tie,
                "timestamp": datetime.utcnow().isoformat(),
            })

    except ValueError as e:
        await manager.send_to_player(session_id, player_id, {
            "type": "error",
            "message": str(e),
        })


async def handle_sync_request(session_id: str, player_id: str):
    """Handle state sync request."""
    choice_handler = get_multiplayer_choice_handler()

    # Get active choice session if any
    active_session = choice_handler.get_active_for_game(session_id)

    await manager.send_to_player(session_id, player_id, {
        "type": "sync_response",
        "players": manager.get_session_players(session_id),
        "active_choice": choice_handler.serialize_session(active_session) if active_session else None,
        "timestamp": datetime.utcnow().isoformat(),
    })


# =============================================================================
# REST ENDPOINTS
# =============================================================================

@router.post("/choice/initiate")
async def initiate_choice(request: InitiateChoiceRequest):
    """
    Initiate a new choice voting session.

    This starts a voting session for all connected players.
    """
    choice_handler = get_multiplayer_choice_handler()
    players = manager.get_session_players(request.session_id)

    if not players:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No players connected to session",
        )

    try:
        mode = DecisionMode(request.mode)
    except ValueError:
        mode = DecisionMode.VOTING

    session = await choice_handler.initiate_choice(
        game_session_id=request.session_id,
        choice_id=request.choice_id,
        choice_text=request.choice_text,
        options=request.options,
        player_ids=players,
        mode=mode,
        leader_id=request.leader_id,
        timeout_seconds=request.timeout_seconds,
    )

    # Broadcast to all players
    await manager.broadcast_to_session(request.session_id, {
        "type": "choice_started",
        "session": choice_handler.serialize_session(session),
        "timestamp": datetime.utcnow().isoformat(),
    })

    return {
        "success": True,
        "choice_session_id": session.id,
        "session": choice_handler.serialize_session(session),
    }


@router.post("/choice/vote")
async def cast_vote(request: VoteRequest):
    """
    Cast a vote in an active choice session.

    Votes are broadcast to all players in real-time.
    """
    choice_handler = get_multiplayer_choice_handler()

    try:
        result = await choice_handler.record_vote(
            request.choice_session_id,
            request.player_id,
            request.choice_id,
        )

        # Get the session to find game session ID
        session = choice_handler.get_active_session(request.choice_session_id)
        if session:
            # Broadcast vote update
            await manager.broadcast_to_session(session.session_id, {
                "type": "vote_update",
                "choice_session_id": request.choice_session_id,
                "voter": request.player_id,
                "result": choice_handler.serialize_result(result),
                "timestamp": datetime.utcnow().isoformat(),
            })

            if result.resolved:
                await manager.broadcast_to_session(session.session_id, {
                    "type": "choice_resolved",
                    "choice_session_id": request.choice_session_id,
                    "winning_choice": result.winning_choice,
                    "tie": result.tie,
                    "timestamp": datetime.utcnow().isoformat(),
                })

        return {
            "success": True,
            "result": choice_handler.serialize_result(result),
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/choice/resolve-tie")
async def resolve_tie(request: ResolveTieRequest):
    """
    Manually resolve a tied vote.
    """
    choice_handler = get_multiplayer_choice_handler()

    try:
        result = await choice_handler.resolve_tie(
            request.choice_session_id,
            request.method,
            request.forced_choice,
        )

        return {
            "success": True,
            "result": choice_handler.serialize_result(result),
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/choice/{choice_session_id}")
async def get_choice_status(choice_session_id: str):
    """Get current status of a choice session."""
    choice_handler = get_multiplayer_choice_handler()

    session = choice_handler.get_active_session(choice_session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Choice session not found",
        )

    return {
        "success": True,
        "session": choice_handler.serialize_session(session),
    }


@router.post("/choice/{choice_session_id}/cancel")
async def cancel_choice(choice_session_id: str):
    """Cancel an active choice session."""
    choice_handler = get_multiplayer_choice_handler()

    success = await choice_handler.cancel_choice(choice_session_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Choice session not found",
        )

    return {"success": True}


@router.get("/session/{session_id}/players")
async def get_session_players(session_id: str):
    """Get list of connected players in a session."""
    players = manager.get_session_players(session_id)
    return {
        "session_id": session_id,
        "players": players,
        "count": len(players),
    }


@router.get("/session/{session_id}/status")
async def get_session_status(session_id: str):
    """Get full status of a multiplayer session."""
    choice_handler = get_multiplayer_choice_handler()

    players = manager.get_session_players(session_id)
    active_choice = choice_handler.get_active_for_game(session_id)

    return {
        "session_id": session_id,
        "players": players,
        "player_count": len(players),
        "active_choice": choice_handler.serialize_session(active_choice) if active_choice else None,
    }


# =============================================================================
# BROADCAST HELPERS
# =============================================================================

async def broadcast_consequence(session_id: str, consequence_data: Dict[str, Any]):
    """Broadcast a consequence trigger to all players."""
    await manager.broadcast_to_session(session_id, {
        "type": "consequence_triggered",
        "data": consequence_data,
        "timestamp": datetime.utcnow().isoformat(),
    })


async def broadcast_state_update(session_id: str, state_data: Dict[str, Any]):
    """Broadcast a campaign state update to all players."""
    await manager.broadcast_to_session(session_id, {
        "type": "state_update",
        "data": state_data,
        "timestamp": datetime.utcnow().isoformat(),
    })


async def broadcast_combat_update(session_id: str, combat_data: Dict[str, Any]):
    """Broadcast a combat state update to all players."""
    await manager.broadcast_to_session(session_id, {
        "type": "combat_update",
        "data": combat_data,
        "timestamp": datetime.utcnow().isoformat(),
    })
