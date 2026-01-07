"""
D&D Combat Engine - Custom Error Types
Structured exceptions for game-specific errors with recovery hints.
"""
from typing import Dict, Any, Optional
from enum import Enum


class ErrorCode(str, Enum):
    """Standard error codes for the game engine."""
    # General errors
    UNKNOWN = "UNKNOWN"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"

    # Authentication errors
    AUTH_INVALID_CREDENTIALS = "AUTH_INVALID_CREDENTIALS"
    AUTH_TOKEN_EXPIRED = "AUTH_TOKEN_EXPIRED"
    AUTH_TOKEN_INVALID = "AUTH_TOKEN_INVALID"
    AUTH_UNAUTHORIZED = "AUTH_UNAUTHORIZED"
    AUTH_FORBIDDEN = "AUTH_FORBIDDEN"

    # Combat errors
    COMBAT_NOT_ACTIVE = "COMBAT_NOT_ACTIVE"
    COMBAT_INVALID_ACTION = "COMBAT_INVALID_ACTION"
    COMBAT_NOT_YOUR_TURN = "COMBAT_NOT_YOUR_TURN"
    COMBAT_TARGET_INVALID = "COMBAT_TARGET_INVALID"
    COMBAT_OUT_OF_RANGE = "COMBAT_OUT_OF_RANGE"
    COMBAT_RESOURCE_EXHAUSTED = "COMBAT_RESOURCE_EXHAUSTED"

    # Campaign errors
    CAMPAIGN_NOT_FOUND = "CAMPAIGN_NOT_FOUND"
    CAMPAIGN_INVALID_STATE = "CAMPAIGN_INVALID_STATE"
    CAMPAIGN_GENERATION_FAILED = "CAMPAIGN_GENERATION_FAILED"
    CAMPAIGN_PARSE_FAILED = "CAMPAIGN_PARSE_FAILED"

    # Character errors
    CHARACTER_NOT_FOUND = "CHARACTER_NOT_FOUND"
    CHARACTER_INVALID = "CHARACTER_INVALID"
    CHARACTER_IMPORT_FAILED = "CHARACTER_IMPORT_FAILED"

    # Session errors
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    SESSION_FULL = "SESSION_FULL"

    # Multiplayer errors
    MULTIPLAYER_CONNECTION_FAILED = "MULTIPLAYER_CONNECTION_FAILED"
    MULTIPLAYER_SYNC_FAILED = "MULTIPLAYER_SYNC_FAILED"
    MULTIPLAYER_VOTE_INVALID = "MULTIPLAYER_VOTE_INVALID"

    # AI errors
    AI_SERVICE_UNAVAILABLE = "AI_SERVICE_UNAVAILABLE"
    AI_RATE_LIMITED = "AI_RATE_LIMITED"
    AI_GENERATION_FAILED = "AI_GENERATION_FAILED"

    # Database errors
    DATABASE_ERROR = "DATABASE_ERROR"
    DATABASE_CONNECTION_FAILED = "DATABASE_CONNECTION_FAILED"


class GameError(Exception):
    """
    Base exception for all game-related errors.

    Provides structured error information with:
    - Error code for programmatic handling
    - Human-readable message
    - Additional context details
    - Recovery hints for the frontend
    """

    def __init__(
        self,
        code: ErrorCode = ErrorCode.UNKNOWN,
        message: str = "An unexpected error occurred",
        details: Optional[Dict[str, Any]] = None,
        recoverable: bool = True,
        recovery_hint: Optional[str] = None,
        http_status: int = 500
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.recoverable = recoverable
        self.recovery_hint = recovery_hint
        self.http_status = http_status

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for JSON response."""
        return {
            "error": {
                "code": self.code.value,
                "message": self.message,
                "details": self.details,
                "recoverable": self.recoverable,
                "recovery_hint": self.recovery_hint
            }
        }

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(code={self.code.value}, message={self.message!r})"


# =============================================================================
# Authentication Errors
# =============================================================================

class AuthError(GameError):
    """Authentication and authorization errors."""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.AUTH_UNAUTHORIZED,
        message: str = "Authentication required",
        **kwargs
    ):
        super().__init__(code=code, message=message, http_status=401, **kwargs)


class InvalidCredentialsError(AuthError):
    """Raised when login credentials are invalid."""

    def __init__(self, message: str = "Invalid username or password"):
        super().__init__(
            code=ErrorCode.AUTH_INVALID_CREDENTIALS,
            message=message,
            recovery_hint="Check your username and password and try again"
        )


class TokenExpiredError(AuthError):
    """Raised when JWT token has expired."""

    def __init__(self):
        super().__init__(
            code=ErrorCode.AUTH_TOKEN_EXPIRED,
            message="Your session has expired",
            recovery_hint="Please log in again to continue",
            http_status=401
        )


class TokenInvalidError(AuthError):
    """Raised when JWT token is malformed or invalid."""

    def __init__(self):
        super().__init__(
            code=ErrorCode.AUTH_TOKEN_INVALID,
            message="Invalid authentication token",
            recovery_hint="Please log in again",
            http_status=401
        )


class ForbiddenError(AuthError):
    """Raised when user lacks permission for an action."""

    def __init__(self, message: str = "You don't have permission for this action"):
        super().__init__(
            code=ErrorCode.AUTH_FORBIDDEN,
            message=message,
            http_status=403,
            recovery_hint="Contact the session host if you need access"
        )


# =============================================================================
# Combat Errors
# =============================================================================

class CombatError(GameError):
    """Combat-related errors."""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.COMBAT_INVALID_ACTION,
        message: str = "Invalid combat action",
        **kwargs
    ):
        super().__init__(code=code, message=message, http_status=400, **kwargs)


class NotYourTurnError(CombatError):
    """Raised when attempting action outside your turn."""

    def __init__(self, current_combatant: Optional[str] = None):
        details = {}
        if current_combatant:
            details["current_turn"] = current_combatant
        super().__init__(
            code=ErrorCode.COMBAT_NOT_YOUR_TURN,
            message="It's not your turn",
            details=details,
            recovery_hint="Wait for your turn in the initiative order"
        )


class TargetInvalidError(CombatError):
    """Raised when targeting an invalid combatant."""

    def __init__(self, reason: str = "Target is not valid"):
        super().__init__(
            code=ErrorCode.COMBAT_TARGET_INVALID,
            message=reason,
            recovery_hint="Select a valid target within range"
        )


class OutOfRangeError(CombatError):
    """Raised when target is out of range."""

    def __init__(self, distance: Optional[int] = None, max_range: Optional[int] = None):
        details = {}
        if distance is not None:
            details["distance"] = distance
        if max_range is not None:
            details["max_range"] = max_range
        super().__init__(
            code=ErrorCode.COMBAT_OUT_OF_RANGE,
            message="Target is out of range",
            details=details,
            recovery_hint="Move closer or use a ranged attack"
        )


class ResourceExhaustedError(CombatError):
    """Raised when combat resource (spell slot, ki, etc.) is exhausted."""

    def __init__(self, resource_name: str, available: int = 0, required: int = 1):
        super().__init__(
            code=ErrorCode.COMBAT_RESOURCE_EXHAUSTED,
            message=f"Not enough {resource_name}",
            details={
                "resource": resource_name,
                "available": available,
                "required": required
            },
            recovery_hint=f"Rest to recover {resource_name} or use a different ability"
        )


class CombatNotActiveError(CombatError):
    """Raised when combat action is attempted outside combat."""

    def __init__(self):
        super().__init__(
            code=ErrorCode.COMBAT_NOT_ACTIVE,
            message="No active combat",
            recovery_hint="Start an encounter to enter combat"
        )


# =============================================================================
# Campaign Errors
# =============================================================================

class CampaignError(GameError):
    """Campaign-related errors."""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.CAMPAIGN_INVALID_STATE,
        message: str = "Campaign error",
        **kwargs
    ):
        super().__init__(code=code, message=message, http_status=400, **kwargs)


class CampaignNotFoundError(CampaignError):
    """Raised when campaign is not found."""

    def __init__(self, campaign_id: Optional[str] = None):
        details = {}
        if campaign_id:
            details["campaign_id"] = campaign_id
        super().__init__(
            code=ErrorCode.CAMPAIGN_NOT_FOUND,
            message="Campaign not found",
            details=details,
            http_status=404,
            recovery_hint="Start a new campaign or load a saved game"
        )


class CampaignGenerationError(CampaignError):
    """Raised when AI campaign generation fails."""

    def __init__(self, reason: str = "Failed to generate campaign"):
        super().__init__(
            code=ErrorCode.CAMPAIGN_GENERATION_FAILED,
            message=reason,
            recovery_hint="Try a different prompt or check your API connection"
        )


class CampaignParseError(CampaignError):
    """Raised when PDF/document parsing fails."""

    def __init__(self, reason: str = "Failed to parse campaign document"):
        super().__init__(
            code=ErrorCode.CAMPAIGN_PARSE_FAILED,
            message=reason,
            recovery_hint="Ensure the document is a valid PDF or text file"
        )


# =============================================================================
# Character Errors
# =============================================================================

class CharacterError(GameError):
    """Character-related errors."""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.CHARACTER_INVALID,
        message: str = "Character error",
        **kwargs
    ):
        super().__init__(code=code, message=message, http_status=400, **kwargs)


class CharacterNotFoundError(CharacterError):
    """Raised when character is not found."""

    def __init__(self, character_id: Optional[str] = None):
        details = {}
        if character_id:
            details["character_id"] = character_id
        super().__init__(
            code=ErrorCode.CHARACTER_NOT_FOUND,
            message="Character not found",
            details=details,
            http_status=404,
            recovery_hint="Create or import a character"
        )


class CharacterImportError(CharacterError):
    """Raised when character import fails."""

    def __init__(self, reason: str = "Failed to import character"):
        super().__init__(
            code=ErrorCode.CHARACTER_IMPORT_FAILED,
            message=reason,
            recovery_hint="Check the PDF format or try manual character creation"
        )


# =============================================================================
# Session Errors
# =============================================================================

class SessionError(GameError):
    """Game session errors."""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.SESSION_NOT_FOUND,
        message: str = "Session error",
        **kwargs
    ):
        super().__init__(code=code, message=message, http_status=400, **kwargs)


class SessionNotFoundError(SessionError):
    """Raised when session is not found."""

    def __init__(self, session_id: Optional[str] = None):
        details = {}
        if session_id:
            details["session_id"] = session_id
        super().__init__(
            code=ErrorCode.SESSION_NOT_FOUND,
            message="Game session not found",
            details=details,
            http_status=404,
            recovery_hint="Start a new session or load a saved game"
        )


class SessionExpiredError(SessionError):
    """Raised when session has expired."""

    def __init__(self):
        super().__init__(
            code=ErrorCode.SESSION_EXPIRED,
            message="Session has expired",
            recovery_hint="Start a new session"
        )


class SessionFullError(SessionError):
    """Raised when session has reached player limit."""

    def __init__(self, max_players: int = 6):
        super().__init__(
            code=ErrorCode.SESSION_FULL,
            message="Session is full",
            details={"max_players": max_players},
            recovery_hint="Wait for a player to leave or join a different session"
        )


# =============================================================================
# Multiplayer Errors
# =============================================================================

class MultiplayerError(GameError):
    """Multiplayer-specific errors."""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.MULTIPLAYER_CONNECTION_FAILED,
        message: str = "Multiplayer error",
        **kwargs
    ):
        super().__init__(code=code, message=message, http_status=400, **kwargs)


class ConnectionFailedError(MultiplayerError):
    """Raised when WebSocket connection fails."""

    def __init__(self, reason: str = "Failed to connect to server"):
        super().__init__(
            code=ErrorCode.MULTIPLAYER_CONNECTION_FAILED,
            message=reason,
            recovery_hint="Check your internet connection and try again"
        )


class SyncFailedError(MultiplayerError):
    """Raised when state synchronization fails."""

    def __init__(self):
        super().__init__(
            code=ErrorCode.MULTIPLAYER_SYNC_FAILED,
            message="Failed to sync game state",
            recovery_hint="Reconnecting will attempt to resync"
        )


# =============================================================================
# AI Service Errors
# =============================================================================

class AIError(GameError):
    """AI service errors (Claude API)."""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.AI_SERVICE_UNAVAILABLE,
        message: str = "AI service error",
        **kwargs
    ):
        super().__init__(code=code, message=message, http_status=503, **kwargs)


class AIServiceUnavailableError(AIError):
    """Raised when AI service is unavailable."""

    def __init__(self):
        super().__init__(
            code=ErrorCode.AI_SERVICE_UNAVAILABLE,
            message="AI service is temporarily unavailable",
            recovery_hint="Try again in a few moments"
        )


class AIRateLimitedError(AIError):
    """Raised when AI API rate limit is hit."""

    def __init__(self, retry_after: Optional[int] = None):
        details = {}
        if retry_after:
            details["retry_after_seconds"] = retry_after
        super().__init__(
            code=ErrorCode.AI_RATE_LIMITED,
            message="AI request rate limit exceeded",
            details=details,
            http_status=429,
            recovery_hint=f"Wait {retry_after or 60} seconds before trying again"
        )


class AIGenerationError(AIError):
    """Raised when AI generation fails."""

    def __init__(self, reason: str = "AI generation failed"):
        super().__init__(
            code=ErrorCode.AI_GENERATION_FAILED,
            message=reason,
            recovery_hint="Try rephrasing your request"
        )


# =============================================================================
# Database Errors
# =============================================================================

class DatabaseError(GameError):
    """Database-related errors."""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.DATABASE_ERROR,
        message: str = "Database error",
        **kwargs
    ):
        super().__init__(
            code=code,
            message=message,
            http_status=500,
            recoverable=False,
            **kwargs
        )


class DatabaseConnectionError(DatabaseError):
    """Raised when database connection fails."""

    def __init__(self):
        super().__init__(
            code=ErrorCode.DATABASE_CONNECTION_FAILED,
            message="Unable to connect to database",
            recovery_hint="Please try again later"
        )


# =============================================================================
# Validation Error
# =============================================================================

class ValidationError(GameError):
    """Input validation errors."""

    def __init__(self, field: str, message: str, value: Any = None):
        details = {"field": field}
        if value is not None:
            details["value"] = str(value)
        super().__init__(
            code=ErrorCode.VALIDATION_ERROR,
            message=message,
            details=details,
            http_status=400,
            recovery_hint=f"Check the value for '{field}'"
        )


class NotFoundError(GameError):
    """Generic not found error."""

    def __init__(self, resource: str, identifier: Optional[str] = None):
        details = {"resource": resource}
        if identifier:
            details["identifier"] = identifier
        super().__init__(
            code=ErrorCode.NOT_FOUND,
            message=f"{resource} not found",
            details=details,
            http_status=404
        )
