"""
Database models for D&D web game.

Uses SQLModel (SQLAlchemy + Pydantic) for type-safe database access.
"""
from datetime import datetime
from typing import Dict, List, Optional, Any
from uuid import uuid4

from sqlmodel import SQLModel, Field, Column, JSON, Relationship
from sqlalchemy import Text
from pydantic import BaseModel


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def generate_uuid() -> str:
    """Generate a UUID string."""
    return str(uuid4())


def utc_now() -> datetime:
    """Get current UTC datetime."""
    return datetime.utcnow()


# =============================================================================
# USER MODEL (Authentication)
# =============================================================================

class User(SQLModel, table=True):
    """
    User account for authentication.

    Supports multiplayer sessions and character ownership.
    """
    __tablename__ = "users"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    username: str = Field(unique=True, index=True, min_length=3, max_length=32)
    email: str = Field(unique=True, index=True)
    password_hash: str

    # Profile
    display_name: Optional[str] = Field(default=None, max_length=64)
    avatar_url: Optional[str] = None

    # Account status
    is_active: bool = Field(default=True)
    is_verified: bool = Field(default=False)

    # Timestamps
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    last_login: Optional[datetime] = None

    # Token management (for logout/refresh)
    token_version: int = Field(default=0)


class UserCreate(SQLModel):
    """Model for user registration."""
    username: str = Field(min_length=3, max_length=32)
    email: str
    password: str = Field(min_length=8)
    display_name: Optional[str] = None


class UserLogin(SQLModel):
    """Model for user login."""
    username: str
    password: str


class UserUpdate(SQLModel):
    """Model for updating user profile."""
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None


class TokenPair(BaseModel):
    """JWT token pair response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 3600  # seconds


class TokenRefresh(BaseModel):
    """Token refresh request."""
    refresh_token: str


# =============================================================================
# CHARACTER MODEL
# =============================================================================

class Character(SQLModel, table=True):
    """
    Persistent character storage.

    Stores complete character data including stats, equipment, and progression.
    """
    __tablename__ = "characters"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    user_id: Optional[str] = Field(default=None, index=True)  # For future auth

    # Basic info
    name: str = Field(index=True)
    species: str = Field(default="human")
    character_class: str = Field(default="fighter")
    subclass: Optional[str] = None
    level: int = Field(default=1, ge=1, le=20)
    background: Optional[str] = None

    # Ability scores (stored as JSON for flexibility)
    abilities: Dict[str, int] = Field(
        default_factory=lambda: {
            "strength": 10,
            "dexterity": 10,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
        },
        sa_column=Column(JSON),
    )

    # Hit points
    max_hp: int = Field(default=10)
    current_hp: int = Field(default=10)
    temp_hp: int = Field(default=0)

    # Progression
    experience: int = Field(default=0)
    proficiency_bonus: int = Field(default=2)

    # Proficiencies (stored as JSON lists)
    skill_proficiencies: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    saving_throw_proficiencies: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    tool_proficiencies: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    weapon_proficiencies: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    armor_proficiencies: List[str] = Field(default_factory=list, sa_column=Column(JSON))

    # Equipment (stored as JSON object)
    equipment: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    inventory: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    gold: int = Field(default=0)

    # Spellcasting (stored as JSON)
    spellcasting: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    # Class features and resources
    class_features: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    class_resources: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    # Conditions and status
    conditions: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    death_saves: Dict[str, int] = Field(
        default_factory=lambda: {"successes": 0, "failures": 0},
        sa_column=Column(JSON),
    )

    # Metadata
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    is_active: bool = Field(default=True)

    # Relationships
    # game_sessions: List["GameSessionCharacter"] = Relationship(back_populates="character")


class CharacterCreate(SQLModel):
    """Model for creating a new character."""
    name: str
    species: str = "human"
    character_class: str = "fighter"
    subclass: Optional[str] = None
    level: int = 1
    background: Optional[str] = None
    abilities: Optional[Dict[str, int]] = None


class CharacterUpdate(SQLModel):
    """Model for updating a character."""
    name: Optional[str] = None
    level: Optional[int] = None
    max_hp: Optional[int] = None
    current_hp: Optional[int] = None
    temp_hp: Optional[int] = None
    experience: Optional[int] = None
    equipment: Optional[Dict[str, Any]] = None
    inventory: Optional[List[Dict[str, Any]]] = None
    gold: Optional[int] = None
    conditions: Optional[List[str]] = None
    spellcasting: Optional[Dict[str, Any]] = None
    class_resources: Optional[Dict[str, Any]] = None
    class_features: Optional[List[str]] = None
    skill_proficiencies: Optional[List[str]] = None


# =============================================================================
# GAME SESSION MODEL
# =============================================================================

class GameSession(SQLModel, table=True):
    """
    A game session (campaign instance).

    Tracks party, state, and progress through a campaign.
    """
    __tablename__ = "game_sessions"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    name: str = Field(default="New Adventure")

    # Campaign reference
    campaign_id: Optional[str] = Field(default=None, index=True)
    current_scene_id: Optional[str] = None

    # Party (stored as JSON array of character data)
    party: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    party_character_ids: List[str] = Field(default_factory=list, sa_column=Column(JSON))

    # Session state
    state: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    flags: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    # Current combat (if any)
    active_combat_id: Optional[str] = None

    # Metadata
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    last_played_at: Optional[datetime] = None
    is_active: bool = Field(default=True)


class GameSessionCreate(SQLModel):
    """Model for creating a new game session."""
    name: str = "New Adventure"
    campaign_id: Optional[str] = None
    party_character_ids: List[str] = Field(default_factory=list)


# =============================================================================
# COMBAT LOG MODEL
# =============================================================================

class CombatLog(SQLModel, table=True):
    """
    Combat event log entry.

    Stores individual combat events for replay and analysis.
    """
    __tablename__ = "combat_logs"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    combat_state_id: str = Field(index=True)
    session_id: Optional[str] = Field(default=None, index=True)

    # Event info
    round_number: int = Field(default=1)
    turn_number: int = Field(default=1)
    event_type: str  # attack, damage, heal, move, spell, condition, etc.
    actor_id: Optional[str] = None
    actor_name: Optional[str] = None
    target_id: Optional[str] = None
    target_name: Optional[str] = None

    # Event data (flexible JSON)
    data: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    description: str = Field(default="", sa_column=Column(Text))

    # Metadata
    timestamp: datetime = Field(default_factory=utc_now)


# =============================================================================
# COMBAT STATE MODEL
# =============================================================================

class CombatState(SQLModel, table=True):
    """
    Persistent combat state.

    Allows combat to be saved and resumed.
    """
    __tablename__ = "combat_states"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    session_id: Optional[str] = Field(default=None, index=True)

    # Combat phase
    phase: str = Field(default="setup")  # setup, rolling_initiative, combat_active, ended
    round_number: int = Field(default=0)
    current_turn_index: int = Field(default=0)

    # Combatants (stored as JSON)
    combatants: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    initiative_order: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))

    # Positions on combat grid
    positions: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    # Combatant stats (HP, conditions, etc.)
    combatant_stats: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    # Current turn state
    current_turn: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    # Active effects (buffs, debuffs, concentration)
    active_effects: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))

    # Combat result
    result: Optional[str] = None  # victory, defeat, fled, none
    xp_awarded: int = Field(default=0)

    # Metadata
    started_at: datetime = Field(default_factory=utc_now)
    ended_at: Optional[datetime] = None
    is_active: bool = Field(default=True)


class CombatStateCreate(SQLModel):
    """Model for creating a new combat state."""
    session_id: Optional[str] = None
    combatants: List[Dict[str, Any]] = Field(default_factory=list)


# =============================================================================
# CAMPAIGN PROGRESS MODEL
# =============================================================================

class CampaignProgress(SQLModel, table=True):
    """
    Tracks progress through a campaign.

    Stores completed scenes, acquired items, and story flags.
    """
    __tablename__ = "campaign_progress"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    session_id: str = Field(index=True)
    campaign_id: str = Field(index=True)

    # Progress tracking
    completed_scenes: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    current_scene_id: Optional[str] = None

    # Story flags
    flags: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    # Acquired items and rewards
    items_acquired: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    total_xp_earned: int = Field(default=0)
    total_gold_earned: int = Field(default=0)

    # Metadata
    started_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    completed_at: Optional[datetime] = None


# =============================================================================
# SAVE GAME MODEL
# =============================================================================

class SaveGameDB(SQLModel, table=True):
    """
    Persisted save game snapshot.

    Stores complete session state for loading later.
    Survives server restarts (unlike in-memory saves).
    """
    __tablename__ = "save_games"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    session_id: str = Field(index=True)
    slot_number: int = Field(default=0)
    name: str = Field(default="Save")

    # Full session state snapshot
    session_data: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    # Optional combat state if saved during combat
    combat_data: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    # Preview info for save menu
    campaign_name: str = Field(default="")
    encounter_name: str = Field(default="")
    party_summary: str = Field(default="")  # e.g., "Lv3 Fighter, Lv2 Wizard"
    playtime_minutes: int = Field(default=0)

    # Metadata
    created_at: datetime = Field(default_factory=utc_now)


class SaveGameCreate(BaseModel):
    """Data for creating a new save game."""
    session_id: str
    slot_number: int = 0
    name: str = "Save"
    session_data: Dict[str, Any]
    combat_data: Optional[Dict[str, Any]] = None
    campaign_name: str = ""
    encounter_name: str = ""
    party_summary: str = ""
    playtime_minutes: int = 0
